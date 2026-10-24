import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.notifications.models import Notification
from apps.notifications.services import EmailService, NotificationService
from apps.payments.models import Payment, PaymentTransaction, Refund
from apps.payments.services.payment_service import safe_json_data

logger = logging.getLogger(__name__)


class RefundService:
    """
    Business service layer managing monetary refunds:
    - Full & partial refund validation against payment balance
    - Refund record generation (REF-YYYYMMDD-XXXXXX)
    - Automatic synchronization with Payment and linked Order status
    - Customer notification dispatch via In-App and Email
    """

    @classmethod
    @transaction.atomic
    def process_refund(
        cls,
        payment: Payment,
        amount: Decimal,
        reason: str = '',
        admin_user=None,
        provider_refund_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Refund:
        """
        Executes refund atomically, updates payment & order financial statuses,
        and records audit transaction log.
        """
        if not payment.can_refund(amount):
            available = payment.amount - payment.refunded_amount
            raise ValidationError(
                f"Cannot refund {amount:,.2f} {payment.currency}. Available balance: {available:,.2f} {payment.currency}."
            )

        refund = Refund.objects.create(
            payment=payment,
            order=payment.order,
            amount=amount,
            currency=payment.currency,
            status=Refund.RefundStatus.PENDING,
            reason=reason or "Customer refund",
            created_by=admin_user,
            provider_refund_id=provider_refund_id or '',
        )

        refund.mark_as_completed(provider_refund_id=provider_refund_id)

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.REFUND,
            amount=amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=f"REF_{refund.refund_number}",
            provider_transaction_id=provider_refund_id or refund.refund_number,
            request_payload=safe_json_data({'refund_number': refund.refund_number, 'reason': reason}),
            response_payload=safe_json_data({'status': refund.status, 'processed_at': str(refund.processed_at)}),
            ip_address=ip_address,
        )

        cls._send_refund_notifications(refund)

        return refund

    @classmethod
    def _send_refund_notifications(cls, refund: Refund):
        payment = refund.payment
        order = refund.order
        recipient = payment.user or (order.user if order else None)
        if not recipient:
            return

        # 1. In-App Notification
        try:
            NotificationService.send_in_app(
                user=recipient,
                title="Mablag' qaytarildi (Refund)",
                message=(
                    f"Buyurtma {order.order_number if order else ''} bo'yicha {refund.amount:,.2f} {refund.currency} "
                    f"miqdoridagi mablag' muvaffaqiyatli qaytarildi. To'lov holati: {payment.get_status_display()}."
                ),
                notification_type=Notification.NotificationType.PAYMENT,
                priority=Notification.NotificationPriority.NORMAL,
                action_url=f"/orders/{order.order_number}/" if order else "",
                data={
                    'refund_number': refund.refund_number,
                    'payment_number': payment.payment_number,
                    'amount': str(refund.amount),
                    'currency': refund.currency,
                },
            )
        except Exception as exc:
            logger.warning("Failed to dispatch refund in-app notification: %s", exc)

        # 2. Email Receipt
        if recipient.email:
            try:
                full_name = getattr(recipient, 'full_name', '') or str(recipient)
                subject = f"Mablag' qaytarildi - Buyurtma {order.order_number if order else ''}"
                body_text = (
                    f"Hurmatli {full_name},\n\n"
                    f"Sizning buyurtmangiz uchun {refund.amount:,.2f} {refund.currency} miqdoridagi to'lov "
                    f"qaytarildi.\nQaytarish raqami: {refund.refund_number}\n"
                    f"Sabab: {refund.reason or 'Mijoz talabiga binoan'}\n\n"
                    f"Mablag' bank kartangizga 1-3 ish kunida qaytadi."
                )
                EmailService.send_or_queue_email(
                    recipient_email=recipient.email,
                    subject=subject,
                    body_text=body_text,
                    user=recipient,
                    context_data={
                        'refund_number': refund.refund_number,
                        'amount': str(refund.amount),
                        'order_number': order.order_number if order else '',
                    },
                    send_immediately=True,
                )
            except Exception as exc:
                logger.warning("Failed to dispatch refund email notification: %s", exc)
