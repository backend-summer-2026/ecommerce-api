import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.notifications.models import Notification
from apps.notifications.services import EmailService, NotificationService
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction
from apps.payments.services.gateways import ClickGateway, PaymeGateway, UzumGateway

logger = logging.getLogger(__name__)


def safe_json_data(val: Any) -> Any:
    """Recursively converts Decimals and non-serializable objects for JSONField."""
    if isinstance(val, dict):
        return {str(k): safe_json_data(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [safe_json_data(x) for x in val]
    elif isinstance(val, Decimal):
        return str(val)
    return val


class PaymentService:
    """
    Core orchestrator for payment initialization, lifecycle execution,
    and automatic synchronization with Orders and Notifications.
    """

    @classmethod
    @transaction.atomic
    def initialize_payment(
        cls,
        order: Order,
        provider: str,
        user=None,
        return_url: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Payment:
        """
        Initializes a payment session for an order, computes checkout URLs,
        and records the initial audit transaction.
        """
        if order.status == Order.OrderStatus.CANCELLED:
            raise ValidationError("Cannot initiate payment for a cancelled order.")

        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValidationError("Order is already paid.")

        if provider not in Payment.PaymentProvider.values:
            raise ValidationError(f"Invalid payment provider: {provider}")

        # Update order's payment_method if customer decided to switch online provider
        if order.payment_method != provider:
            order.payment_method = provider
            order.save(update_fields=['payment_method', 'updated_at'])

        # Check for existing pending payment with the same provider
        payment = Payment.objects.filter(
            order=order,
            provider=provider,
            status=Payment.PaymentStatus.PENDING,
        ).first()

        amount = order.total_price

        if not payment:
            payment = Payment.objects.create(
                order=order,
                user=user or order.user,
                amount=amount,
                currency='UZS',
                provider=provider,
                status=Payment.PaymentStatus.PENDING,
            )

        # Generate checkout redirect URL based on gateway provider
        checkout_url = None
        if provider == Payment.PaymentProvider.PAYME:
            checkout_url = PaymeGateway.generate_checkout_url(order, amount, return_url)
        elif provider == Payment.PaymentProvider.CLICK:
            checkout_url = ClickGateway.generate_checkout_url(order, amount, return_url)
        elif provider == Payment.PaymentProvider.UZUM:
            checkout_url = UzumGateway.generate_checkout_url(order, amount, return_url)

        if checkout_url:
            payment.checkout_url = checkout_url
            payment.save(update_fields=['checkout_url', 'updated_at'])

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.CREATE,
            amount=payment.amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=f"INIT_{payment.payment_number}",
            request_payload={
                'order_number': order.order_number,
                'provider': provider,
                'amount': str(amount),
                'return_url': return_url,
            },
            response_payload={'checkout_url': checkout_url},
            ip_address=ip_address,
        )

        return payment

    @classmethod
    @transaction.atomic
    def process_success(
        cls,
        payment: Payment,
        provider_transaction_id: Optional[str] = None,
        raw_request: Optional[Dict[str, Any]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Payment:
        """
        Finalizes payment as SUCCESS, advances Order to CONFIRMED and PAID,
        logs transaction audit record, and triggers In-App & Email notifications.
        """
        payment.mark_as_success(
            provider_transaction_id=provider_transaction_id,
            user=user or payment.user,
        )

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.PERFORM,
            amount=payment.amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=provider_transaction_id or f"PERF_{payment.payment_number}",
            provider_transaction_id=provider_transaction_id or payment.provider_transaction_id,
            request_payload=safe_json_data(raw_request or {}),
            response_payload=safe_json_data(raw_response or {}),
            ip_address=ip_address,
        )

        cls._send_success_notifications(payment)

        return payment

    @classmethod
    @transaction.atomic
    def process_failure(
        cls,
        payment: Payment,
        reason: str = '',
        error_code: Optional[str] = None,
        raw_request: Optional[Dict[str, Any]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Payment:
        """
        Marks payment as FAILED, logs error transaction, and sends alert notification.
        """
        payment.mark_as_failed(reason=reason)

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.PERFORM,
            amount=payment.amount,
            status=PaymentTransaction.TransactionStatus.FAILED,
            idempotency_key=f"FAIL_{payment.payment_number}_{error_code or 'UNKNOWN'}",
            provider_transaction_id=payment.provider_transaction_id,
            request_payload=safe_json_data(raw_request or {}),
            response_payload=safe_json_data(raw_response or {}),
            error_code=error_code or 'PAYMENT_FAILED',
            error_message=reason,
            ip_address=ip_address,
        )

        cls._send_failure_notifications(payment)

        return payment

    @classmethod
    @transaction.atomic
    def process_cancellation(
        cls,
        payment: Payment,
        reason: str = '',
        raw_request: Optional[Dict[str, Any]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Payment:
        """
        Cancels pending payment attempt and logs cancellation audit.
        """
        payment.mark_as_cancelled(reason=reason)

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.CANCEL,
            amount=payment.amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=f"CANCEL_{payment.payment_number}",
            provider_transaction_id=payment.provider_transaction_id,
            request_payload=safe_json_data(raw_request or {}),
            response_payload=safe_json_data(raw_response or {}),
            error_message=reason,
            ip_address=ip_address,
        )

        return payment

    @classmethod
    def _send_success_notifications(cls, payment: Payment):
        """Dispatches in-app notification and email receipt for successful payment."""
        order = payment.order
        recipient = payment.user or (order.user if order else None)
        if not recipient:
            return

        # 1. In-App Notification
        try:
            NotificationService.send_in_app(
                user=recipient,
                title="To'lov muvaffaqiyatli qabul qilindi!",
                message=(
                    f"Buyurtma {order.order_number} uchun {payment.amount:,.2f} {payment.currency} "
                    f"miqdoridagi to'lov {payment.get_provider_display()} orqali qabul qilindi."
                ),
                notification_type=Notification.NotificationType.PAYMENT,
                priority=Notification.NotificationPriority.NORMAL,
                action_url=f"/orders/{order.order_number}/",
                data={
                    'order_number': order.order_number,
                    'payment_number': payment.payment_number,
                    'provider': payment.provider,
                    'amount': str(payment.amount),
                    'currency': payment.currency,
                },
            )
        except Exception as exc:
            logger.warning("Failed to send in-app payment success notification: %s", exc)

        # 2. Email Receipt
        if recipient.email:
            try:
                full_name = getattr(recipient, 'full_name', '') or str(recipient)
                subject = f"To'lov kvitansiyasi - Buyurtma {order.order_number}"
                body_text = (
                    f"Hurmatli {full_name},\n\n"
                    f"Sizning buyurtmangiz ({order.order_number}) uchun to'lov muvaffaqiyatli qabul qilindi.\n"
                    f"To'lov raqami: {payment.payment_number}\n"
                    f"To'lov usuli: {payment.get_provider_display()}\n"
                    f"Summa: {payment.amount:,.2f} {payment.currency}\n\n"
                    f"Xaridingiz uchun tashakkur!"
                )
                EmailService.send_or_queue_email(
                    recipient_email=recipient.email,
                    subject=subject,
                    body_text=body_text,
                    user=recipient,
                    context_data={
                        'order_number': order.order_number,
                        'payment_number': payment.payment_number,
                        'amount': str(payment.amount),
                        'provider': payment.provider,
                    },
                    send_immediately=True,
                )
            except Exception as exc:
                logger.warning("Failed to dispatch payment receipt email: %s", exc)

    @classmethod
    def _send_failure_notifications(cls, payment: Payment):
        """Dispatches in-app notification when payment fails."""
        order = payment.order
        recipient = payment.user or (order.user if order else None)
        if not recipient:
            return

        try:
            NotificationService.send_in_app(
                user=recipient,
                title="To'lov amalga oshmadi",
                message=(
                    f"Buyurtma {order.order_number} uchun to'lov amalga oshmadi. "
                    f"Sabab: {payment.failure_reason or 'Texnik xatolik'}. Iltimos, qayta urinib ko'ring."
                ),
                notification_type=Notification.NotificationType.PAYMENT,
                priority=Notification.NotificationPriority.HIGH,
                action_url=f"/orders/{order.order_number}/",
                data={
                    'order_number': order.order_number,
                    'payment_number': payment.payment_number,
                    'failure_reason': payment.failure_reason,
                },
            )
        except Exception as exc:
            logger.warning("Failed to send payment failure notification: %s", exc)
