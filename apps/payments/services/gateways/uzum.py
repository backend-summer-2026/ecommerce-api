import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction

logger = logging.getLogger(__name__)


class UzumGateway:
    """
    Uzum Bank / Uzum Pay Gateway Integration.
    Handles checkout link generation and webhook notifications.
    """

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        return getattr(settings, 'UZUM_SETTINGS', {
            'MERCHANT_ID': 'test_uzum_merchant_id',
            'SECRET_KEY': 'test_uzum_secret_key',
            'CHECKOUT_URL': 'https://www.uzumbank.uz/open-service',
        })

    @classmethod
    def validate_signature(cls, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Validates HMAC-SHA256 signature using UZUM secret key.
        """
        if not signature_header:
            return False

        secret = cls.get_settings().get('SECRET_KEY', '')
        computed = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed.lower(), signature_header.lower())

    @classmethod
    def generate_checkout_url(cls, order: Order, amount: Decimal, return_url: Optional[str] = None) -> str:
        """
        Generates Uzum Bank checkout redirect link.
        """
        cfg = cls.get_settings()
        merchant_id = cfg.get('MERCHANT_ID', '')
        base_url = cfg.get('CHECKOUT_URL', 'https://www.uzumbank.uz/open-service')

        url = f"{base_url}?merchant_id={merchant_id}&order_id={order.order_number}&amount={amount:.2f}"
        if return_url:
            url += f"&return_url={return_url}"
        return url

    @classmethod
    def process_webhook(cls, data: Dict[str, Any], ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes server-to-server webhook callback from Uzum.
        """
        order_number = data.get('order_id')
        provider_trans_id = str(data.get('payment_id', ''))
        status_str = str(data.get('status', '')).upper()
        amount_raw = data.get('amount')

        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return {'status': 'ERROR', 'message': f"Order '{order_number}' not found"}

        payment = Payment.objects.filter(
            order=order,
            provider=Payment.PaymentProvider.UZUM,
        ).first()

        if not payment:
            amount = Decimal(str(amount_raw)) if amount_raw else order.total_price
            payment = Payment.objects.create(
                order=order,
                user=order.user,
                amount=amount,
                currency='UZS',
                provider=Payment.PaymentProvider.UZUM,
                status=Payment.PaymentStatus.PENDING,
                provider_transaction_id=provider_trans_id,
            )

        from apps.payments.services.payment_service import PaymentService

        if status_str in ['SUCCESS', 'COMPLETED', 'PAID']:
            if payment.status == Payment.PaymentStatus.SUCCESS:
                return {'status': 'OK', 'message': 'Already processed'}

            PaymentService.process_success(
                payment=payment,
                provider_transaction_id=provider_trans_id,
                raw_request=data,
                raw_response={'status': 'OK'},
                ip_address=ip_address,
            )
            return {'status': 'OK', 'message': 'Payment marked as success'}

        elif status_str in ['FAILED', 'ERROR']:
            reason = data.get('failure_reason', 'Uzum payment failed')
            PaymentService.process_failure(
                payment=payment,
                reason=reason,
                raw_request=data,
                raw_response={'status': 'FAILED'},
                ip_address=ip_address,
            )
            return {'status': 'OK', 'message': 'Payment marked as failed'}

        elif status_str in ['CANCELLED', 'REVERSED']:
            PaymentService.process_cancellation(
                payment=payment,
                reason=data.get('failure_reason', 'Uzum payment cancelled'),
                raw_request=data,
                ip_address=ip_address,
            )
            return {'status': 'OK', 'message': 'Payment marked as cancelled'}

        return {'status': 'IGNORED', 'message': f"Unhandled status {status_str}"}
