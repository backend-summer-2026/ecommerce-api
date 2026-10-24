import base64
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction

logger = logging.getLogger(__name__)


class PaymeError:
    """Payme JSON-RPC 2.0 Standard Error Codes."""
    METHOD_NOT_FOUND = -32601
    INVALID_AMOUNT = -31001
    ORDER_NOT_FOUND = -31050
    ORDER_ALREADY_PAID = -31051
    ORDER_CANCELLED = -31052
    TRANSACTION_NOT_FOUND = -31003
    UNABLE_TO_PERFORM_OPERATION = -31008
    AUTH_ERROR = -32504


class PaymeGateway:
    """
    Payme JSON-RPC 2.0 Merchant Protocol handler:
    Handles transaction check, creation, authorization, perform, and cancellation.
    Amounts in Payme protocol are denominated in TIYIN (1 UZS = 100 Tiyin).
    """

    STATE_CREATED = 1
    STATE_COMPLETED = 2
    STATE_CANCELLED = -1
    STATE_CANCELLED_AFTER_COMPLETE = -2

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        return getattr(settings, 'PAYME_SETTINGS', {
            'MERCHANT_ID': 'test_merchant_id',
            'SECRET_KEY': 'test_secret_key',
            'CHECKOUT_URL': 'https://checkout.paycom.uz',
        })

    @classmethod
    def validate_auth(cls, auth_header: Optional[str]) -> bool:
        """
        Validates HTTP Basic Auth: 'Basic base64(Paycom:SECRET_KEY)'.
        """
        if not auth_header or not auth_header.startswith('Basic '):
            return False

        try:
            token = auth_header.split(' ', 1)[1].strip()
            decoded = base64.b64decode(token).decode('utf-8')
            username, password = decoded.split(':', 1)
            secret_key = cls.get_settings().get('SECRET_KEY')
            return username == 'Paycom' and password == secret_key
        except Exception as exc:
            logger.warning("Payme auth decode failed: %s", exc)
            return False

    @classmethod
    def generate_checkout_url(cls, order: Order, amount: Decimal, return_url: Optional[str] = None) -> str:
        """
        Generates standard Payme checkout URL with base64 encoded parameters.
        m=MERCHANT_ID;ac.order_number=ORD-XYZ;a=AMOUNT_IN_TIYIN
        """
        merchant_id = cls.get_settings().get('MERCHANT_ID', '')
        base_url = cls.get_settings().get('CHECKOUT_URL', 'https://checkout.paycom.uz')
        tiyin_amount = int(amount * Decimal('100.00'))

        payload = f"m={merchant_id};ac.order_number={order.order_number};a={tiyin_amount}"
        if return_url:
            payload += f";c={return_url}"

        encoded = base64.b64encode(payload.encode('utf-8')).decode('utf-8')
        return f"{base_url.rstrip('/')}/{encoded}"

    @classmethod
    def process_rpc(cls, data: Dict[str, Any], ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Main JSON-RPC 2.0 dispatcher for Payme callbacks.
        """
        method = data.get('method')
        params = data.get('params', {})
        rpc_id = data.get('id')

        methods_map = {
            'CheckPerformTransaction': cls._check_perform_transaction,
            'CreateTransaction': cls._create_transaction,
            'PerformTransaction': cls._perform_transaction,
            'CancelTransaction': cls._cancel_transaction,
            'CheckTransaction': cls._check_transaction,
        }

        handler = methods_map.get(method)
        if not handler:
            return {
                'id': rpc_id,
                'error': {
                    'code': PaymeError.METHOD_NOT_FOUND,
                    'message': {'ru': 'Method not found', 'uz': 'Metod topilmadi', 'en': 'Method not found'},
                },
            }

        try:
            result = handler(params, rpc_id=rpc_id, ip_address=ip_address)
            return {'id': rpc_id, 'result': result}
        except PaymeException as exc:
            return {
                'id': rpc_id,
                'error': {
                    'code': exc.code,
                    'message': exc.message,
                    'data': exc.data,
                },
            }
        except Exception as exc:
            logger.exception("Unexpected error in Payme gateway: %s", exc)
            return {
                'id': rpc_id,
                'error': {
                    'code': PaymeError.UNABLE_TO_PERFORM_OPERATION,
                    'message': {'ru': str(exc), 'uz': str(exc), 'en': str(exc)},
                },
            }

    @classmethod
    def _check_perform_transaction(cls, params: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        account = params.get('account', {})
        order_number = account.get('order_number')
        amount_tiyin = params.get('amount')

        if not order_number:
            raise PaymeException(PaymeError.ORDER_NOT_FOUND, "Order identifier not specified", "order_number")

        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            raise PaymeException(PaymeError.ORDER_NOT_FOUND, "Order not found", "order_number")

        if order.status == Order.OrderStatus.CANCELLED:
            raise PaymeException(PaymeError.ORDER_CANCELLED, "Order was cancelled", "order_number")

        if order.payment_status == Order.PaymentStatus.PAID:
            raise PaymeException(PaymeError.ORDER_ALREADY_PAID, "Order is already paid", "order_number")

        expected_tiyin = int(order.total_price * Decimal('100.00'))
        if int(amount_tiyin) != expected_tiyin:
            raise PaymeException(PaymeError.INVALID_AMOUNT, "Amount mismatch", "amount")

        return {'allow': True}

    @classmethod
    def _create_transaction(cls, params: Dict[str, Any], rpc_id=None, ip_address=None) -> Dict[str, Any]:
        cls._check_perform_transaction(params)

        provider_trans_id = str(params.get('id'))
        account = params.get('account', {})
        order_number = account.get('order_number')
        time_ms = int(params.get('time', 0))
        amount_tiyin = params.get('amount')
        amount = Decimal(str(amount_tiyin)) / Decimal('100.00')

        order = Order.objects.get(order_number=order_number)

        # Look for existing payment for this provider transaction ID
        existing_payment = Payment.objects.filter(
            provider=Payment.PaymentProvider.PAYME,
            provider_transaction_id=provider_trans_id,
        ).first()

        if existing_payment:
            if existing_payment.status == Payment.PaymentStatus.SUCCESS:
                state = cls.STATE_COMPLETED
            elif existing_payment.status == Payment.PaymentStatus.CANCELLED:
                state = cls.STATE_CANCELLED
            else:
                state = cls.STATE_CREATED

            create_time = int(existing_payment.created_at.timestamp() * 1000)
            return {
                'create_time': create_time,
                'transaction': str(existing_payment.payment_number),
                'state': state,
            }

        # Check if order already has an active pending payment
        payment = Payment.objects.filter(
            order=order,
            provider=Payment.PaymentProvider.PAYME,
            status=Payment.PaymentStatus.PENDING,
        ).first()

        if not payment:
            payment = Payment.objects.create(
                order=order,
                user=order.user,
                amount=amount,
                currency='UZS',
                provider=Payment.PaymentProvider.PAYME,
                status=Payment.PaymentStatus.PENDING,
                provider_transaction_id=provider_trans_id,
                provider_state=str(cls.STATE_CREATED),
                metadata={'payme_time': time_ms, 'payme_id': provider_trans_id},
            )
        else:
            payment.provider_transaction_id = provider_trans_id
            payment.provider_state = str(cls.STATE_CREATED)
            payment.metadata['payme_time'] = time_ms
            payment.metadata['payme_id'] = provider_trans_id
            payment.save(update_fields=['provider_transaction_id', 'provider_state', 'metadata', 'updated_at'])

        PaymentTransaction.objects.create(
            payment=payment,
            transaction_type=PaymentTransaction.TransactionType.CREATE,
            amount=amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key=provider_trans_id,
            provider_transaction_id=provider_trans_id,
            request_payload=params,
            response_payload={'state': cls.STATE_CREATED},
            ip_address=ip_address,
        )

        create_time = int(payment.created_at.timestamp() * 1000)
        return {
            'create_time': create_time,
            'transaction': str(payment.payment_number),
            'state': cls.STATE_CREATED,
        }

    @classmethod
    def _perform_transaction(cls, params: Dict[str, Any], rpc_id=None, ip_address=None) -> Dict[str, Any]:
        provider_trans_id = str(params.get('id'))

        payment = Payment.objects.filter(
            provider=Payment.PaymentProvider.PAYME,
            provider_transaction_id=provider_trans_id,
        ).first()

        if not payment:
            raise PaymeException(PaymeError.TRANSACTION_NOT_FOUND, "Transaction not found", "id")

        now_ms = int(timezone.now().timestamp() * 1000)

        if payment.status == Payment.PaymentStatus.SUCCESS:
            perform_time = int(payment.paid_at.timestamp() * 1000) if payment.paid_at else now_ms
            return {
                'transaction': str(payment.payment_number),
                'perform_time': perform_time,
                'state': cls.STATE_COMPLETED,
            }

        if payment.status == Payment.PaymentStatus.CANCELLED:
            raise PaymeException(PaymeError.UNABLE_TO_PERFORM_OPERATION, "Transaction is cancelled", "id")

        from apps.payments.services.payment_service import PaymentService
        PaymentService.process_success(
            payment=payment,
            provider_transaction_id=provider_trans_id,
            raw_request=params,
            raw_response={'state': cls.STATE_COMPLETED},
            ip_address=ip_address,
        )

        perform_time = int(payment.paid_at.timestamp() * 1000) if payment.paid_at else now_ms
        return {
            'transaction': str(payment.payment_number),
            'perform_time': perform_time,
            'state': cls.STATE_COMPLETED,
        }

    @classmethod
    def _cancel_transaction(cls, params: Dict[str, Any], rpc_id=None, ip_address=None) -> Dict[str, Any]:
        provider_trans_id = str(params.get('id'))
        reason = params.get('reason')

        payment = Payment.objects.filter(
            provider=Payment.PaymentProvider.PAYME,
            provider_transaction_id=provider_trans_id,
        ).first()

        if not payment:
            raise PaymeException(PaymeError.TRANSACTION_NOT_FOUND, "Transaction not found", "id")

        now_ms = int(timezone.now().timestamp() * 1000)

        if payment.status == Payment.PaymentStatus.CANCELLED:
            cancel_time = int(payment.cancelled_at.timestamp() * 1000) if payment.cancelled_at else now_ms
            return {
                'transaction': str(payment.payment_number),
                'cancel_time': cancel_time,
                'state': cls.STATE_CANCELLED,
            }

        from apps.payments.services.payment_service import PaymentService
        PaymentService.process_cancellation(
            payment=payment,
            reason=f"Payme cancellation reason: {reason}",
            raw_request=params,
            ip_address=ip_address,
        )

        cancel_time = int(payment.cancelled_at.timestamp() * 1000) if payment.cancelled_at else now_ms
        return {
            'transaction': str(payment.payment_number),
            'cancel_time': cancel_time,
            'state': cls.STATE_CANCELLED,
        }

    @classmethod
    def _check_transaction(cls, params: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        provider_trans_id = str(params.get('id'))

        payment = Payment.objects.filter(
            provider=Payment.PaymentProvider.PAYME,
            provider_transaction_id=provider_trans_id,
        ).first()

        if not payment:
            raise PaymeException(PaymeError.TRANSACTION_NOT_FOUND, "Transaction not found", "id")

        create_time = int(payment.created_at.timestamp() * 1000)
        perform_time = int(payment.paid_at.timestamp() * 1000) if payment.paid_at else 0
        cancel_time = int(payment.cancelled_at.timestamp() * 1000) if payment.cancelled_at else 0

        if payment.status == Payment.PaymentStatus.SUCCESS:
            state = cls.STATE_COMPLETED
        elif payment.status == Payment.PaymentStatus.CANCELLED:
            state = cls.STATE_CANCELLED
        else:
            state = cls.STATE_CREATED

        return {
            'create_time': create_time,
            'perform_time': perform_time,
            'cancel_time': cancel_time,
            'transaction': str(payment.payment_number),
            'state': state,
            'reason': payment.metadata.get('payme_reason'),
        }


class PaymeException(Exception):
    def __init__(self, code: int, message: str, data: Optional[str] = None):
        self.code = code
        self.message = {'ru': message, 'uz': message, 'en': message}
        self.data = data
        super().__init__(message)
