import hashlib
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction

logger = logging.getLogger(__name__)


class ClickError:
    SUCCESS = 0
    SIGN_CHECK_FAILED = -1
    INCORRECT_AMOUNT = -2
    ACTION_NOT_FOUND = -3
    ALREADY_PAID = -4
    USER_NOT_FOUND = -5
    TRANSACTION_NOT_FOUND = -6
    FAILED_TO_UPDATE_USER = -7
    ERROR_IN_REQUEST = -8
    TRANSACTION_CANCELLED = -9


class ClickGateway:
    """
    Click Shop API Protocol Handler (Prepare & Complete).
    Validates MD5 sign hash and manages payment state machine.
    """

    ACTION_PREPARE = 0
    ACTION_COMPLETE = 1

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        return getattr(settings, 'CLICK_SETTINGS', {
            'SERVICE_ID': 'test_service_id',
            'MERCHANT_ID': 'test_merchant_id',
            'SECRET_KEY': 'test_secret_key',
            'MERCHANT_USER_ID': 'test_merchant_user_id',
            'CHECKOUT_URL': 'https://my.click.uz/services/pay',
        })

    @classmethod
    def validate_sign(cls, data: Dict[str, Any]) -> bool:
        """
        Validates MD5 sign_string:
        md5(click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time)
        """
        click_trans_id = str(data.get('click_trans_id', ''))
        service_id = str(data.get('service_id', ''))
        secret_key = str(cls.get_settings().get('SECRET_KEY', ''))
        merchant_trans_id = str(data.get('merchant_trans_id', ''))
        amount = str(data.get('amount', ''))
        action = str(data.get('action', ''))
        sign_time = str(data.get('sign_time', ''))
        received_sign = str(data.get('sign_string', '')).lower()

        # Handle Complete action sign format (might include merchant_prepare_id if sent back by Click)
        sign_source = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}"
        merchant_prepare_id = data.get('merchant_prepare_id')
        if merchant_prepare_id is not None and str(action) == str(cls.ACTION_COMPLETE):
            sign_source += str(merchant_prepare_id)
        sign_source += f"{amount}{action}{sign_time}"

        expected_sign = hashlib.md5(sign_source.encode('utf-8')).hexdigest().lower()
        if expected_sign != received_sign:
            # Fallback without merchant_prepare_id in sign
            simple_source = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
            simple_sign = hashlib.md5(simple_source.encode('utf-8')).hexdigest().lower()
            return simple_sign == received_sign

        return True

    @classmethod
    def generate_checkout_url(cls, order: Order, amount: Decimal, return_url: Optional[str] = None) -> str:
        """
        Generates standard Click checkout redirect link.
        """
        cfg = cls.get_settings()
        service_id = cfg.get('SERVICE_ID', '')
        merchant_id = cfg.get('MERCHANT_ID', '')
        base_url = cfg.get('CHECKOUT_URL', 'https://my.click.uz/services/pay')

        url = f"{base_url}?service_id={service_id}&merchant_id={merchant_id}&amount={amount:.2f}&transaction_param={order.order_number}"
        if return_url:
            url += f"&return_url={return_url}"
        return url

    @classmethod
    def process_request(cls, data: Dict[str, Any], ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes Click Shop API webhook (Prepare or Complete).
        """
        click_trans_id = data.get('click_trans_id')
        merchant_trans_id = data.get('merchant_trans_id')
        amount_raw = data.get('amount')
        action = data.get('action')

        try:
            action_int = int(action)
        except (TypeError, ValueError):
            return {
                'error': ClickError.ACTION_NOT_FOUND,
                'error_note': 'Invalid action format',
            }

        # Sign validation
        if not cls.validate_sign(data):
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.SIGN_CHECK_FAILED,
                'error_note': 'Sign check failed',
            }

        # Resolve order
        try:
            order = Order.objects.get(order_number=merchant_trans_id)
        except Order.DoesNotExist:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.USER_NOT_FOUND,
                'error_note': f"Order '{merchant_trans_id}' not found",
            }

        # Validate amount
        try:
            req_amount = Decimal(str(amount_raw)).quantize(Decimal('0.01'))
            if req_amount != order.total_price:
                return {
                    'click_trans_id': click_trans_id,
                    'merchant_trans_id': merchant_trans_id,
                    'error': ClickError.INCORRECT_AMOUNT,
                    'error_note': f"Amount mismatch: expected {order.total_price}, received {req_amount}",
                }
        except Exception:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.INCORRECT_AMOUNT,
                'error_note': 'Invalid amount representation',
            }

        if action_int == cls.ACTION_PREPARE:
            return cls._handle_prepare(data, order, req_amount, ip_address)
        elif action_int == cls.ACTION_COMPLETE:
            return cls._handle_complete(data, order, req_amount, ip_address)
        else:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.ACTION_NOT_FOUND,
                'error_note': f"Action {action_int} not found",
            }

    @classmethod
    def _handle_prepare(cls, data: Dict[str, Any], order: Order, amount: Decimal, ip_address: Optional[str]) -> Dict[str, Any]:
        click_trans_id = str(data.get('click_trans_id'))
        merchant_trans_id = str(data.get('merchant_trans_id'))

        if order.status == Order.OrderStatus.CANCELLED:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.TRANSACTION_CANCELLED,
                'error_note': 'Order is cancelled',
            }

        if order.payment_status == Order.PaymentStatus.PAID:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.ALREADY_PAID,
                'error_note': 'Order is already paid',
            }

        payment = Payment.objects.filter(
            order=order,
            provider=Payment.PaymentProvider.CLICK,
            provider_transaction_id=click_trans_id,
        ).first()

        if not payment:
            payment = Payment.objects.filter(
                order=order,
                provider=Payment.PaymentProvider.CLICK,
                status=Payment.PaymentStatus.PENDING,
            ).first()

            if not payment:
                payment = Payment.objects.create(
                    order=order,
                    user=order.user,
                    amount=amount,
                    currency='UZS',
                    provider=Payment.PaymentProvider.CLICK,
                    status=Payment.PaymentStatus.PENDING,
                    provider_transaction_id=click_trans_id,
                    metadata={'click_trans_id': click_trans_id},
                )
            else:
                payment.provider_transaction_id = click_trans_id
                payment.save(update_fields=['provider_transaction_id', 'updated_at'])

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.CHECK,
            amount=amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=f"CLICK_PREPARE_{click_trans_id}",
            provider_transaction_id=click_trans_id,
            request_payload=data,
            response_payload={'error': ClickError.SUCCESS},
            ip_address=ip_address,
        )

        return {
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_prepare_id': payment.id,
            'error': ClickError.SUCCESS,
            'error_note': 'Success',
        }

    @classmethod
    def _handle_complete(cls, data: Dict[str, Any], order: Order, amount: Decimal, ip_address: Optional[str]) -> Dict[str, Any]:
        click_trans_id = str(data.get('click_trans_id'))
        merchant_trans_id = str(data.get('merchant_trans_id'))
        merchant_prepare_id = data.get('merchant_prepare_id')
        error_code = int(data.get('error', 0))

        payment = None
        if merchant_prepare_id:
            payment = Payment.objects.filter(id=merchant_prepare_id).first()
        if not payment:
            payment = Payment.objects.filter(
                provider=Payment.PaymentProvider.CLICK,
                provider_transaction_id=click_trans_id,
            ).first()

        if not payment:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': ClickError.TRANSACTION_NOT_FOUND,
                'error_note': 'Transaction not found',
            }

        if error_code < 0:
            from apps.payments.services.payment_service import PaymentService
            PaymentService.process_failure(
                payment=payment,
                reason=f"Click reported error: {data.get('error_note')}",
                error_code=str(error_code),
                raw_request=data,
                raw_response={'error': error_code},
                ip_address=ip_address,
            )
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'error': error_code,
                'error_note': data.get('error_note', 'Transaction failed'),
            }

        if payment.status == Payment.PaymentStatus.SUCCESS:
            return {
                'click_trans_id': click_trans_id,
                'merchant_trans_id': merchant_trans_id,
                'merchant_confirm_id': payment.id,
                'error': ClickError.SUCCESS,
                'error_note': 'Success',
            }

        from apps.payments.services.payment_service import PaymentService
        PaymentService.process_success(
            payment=payment,
            provider_transaction_id=click_trans_id,
            raw_request=data,
            raw_response={'error': ClickError.SUCCESS},
            ip_address=ip_address,
        )

        return {
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_confirm_id': payment.id,
            'error': ClickError.SUCCESS,
            'error_note': 'Success',
        }
