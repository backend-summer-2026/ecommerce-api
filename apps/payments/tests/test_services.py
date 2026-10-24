from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction, Refund, SavedCard
from apps.payments.services import (
    ClickGateway,
    PaymeGateway,
    PaymentService,
    RefundService,
    SavedCardService,
    UzumGateway,
)

User = get_user_model()


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='StrongPassword123!',
            first_name='Shopper',
            last_name='User',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('200000.00'),
            shipping_fee=Decimal('25000.00'),
            total_price=Decimal('225000.00'),
            payment_method=Order.PaymentMethod.PAYME,
        )

    def test_initialize_payment_payme(self):
        payment = PaymentService.initialize_payment(
            order=self.order,
            provider=Payment.PaymentProvider.PAYME,
            user=self.user,
            return_url='https://example.com/checkout/success',
        )
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.amount, Decimal('225000.00'))
        self.assertIsNotNone(payment.checkout_url)
        self.assertIn('https://checkout.paycom.uz', payment.checkout_url)

        tx = PaymentTransaction.objects.filter(payment=payment).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.transaction_type, PaymentTransaction.TransactionType.CREATE)
        self.assertEqual(tx.status, PaymentTransaction.TransactionStatus.SUCCESS)

    def test_initialize_payment_click(self):
        payment = PaymentService.initialize_payment(
            order=self.order,
            provider=Payment.PaymentProvider.CLICK,
            user=self.user,
            return_url='https://example.com/order-success',
        )
        self.assertEqual(payment.provider, Payment.PaymentProvider.CLICK)
        self.assertIn('https://my.click.uz/services/pay', payment.checkout_url)
        self.assertEqual(self.order.payment_method, Order.PaymentMethod.CLICK)

    def test_initialize_payment_uzum(self):
        payment = PaymentService.initialize_payment(
            order=self.order,
            provider=Payment.PaymentProvider.UZUM,
            user=self.user,
        )
        self.assertEqual(payment.provider, Payment.PaymentProvider.UZUM)
        self.assertIn('https://www.uzumbank.uz/open-service', payment.checkout_url)

    def test_initialize_payment_already_paid_raises_validation_error(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save()

        with self.assertRaises(ValidationError):
            PaymentService.initialize_payment(
                order=self.order,
                provider=Payment.PaymentProvider.PAYME,
                user=self.user,
            )

    def test_initialize_payment_cancelled_order_raises_validation_error(self):
        self.order.status = Order.OrderStatus.CANCELLED
        self.order.save()

        with self.assertRaises(ValidationError):
            PaymentService.initialize_payment(
                order=self.order,
                provider=Payment.PaymentProvider.PAYME,
                user=self.user,
            )

    def test_process_success_syncs_order_and_sends_notification(self):
        payment = PaymentService.initialize_payment(
            order=self.order,
            provider=Payment.PaymentProvider.PAYME,
            user=self.user,
        )

        PaymentService.process_success(
            payment=payment,
            provider_transaction_id='ext_tx_123456',
            user=self.user,
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(payment.provider_transaction_id, 'ext_tx_123456')
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

        notif = Notification.objects.filter(user=self.user, notification_type=Notification.NotificationType.PAYMENT).first()
        self.assertIsNotNone(notif)
        self.assertIn(self.order.order_number, notif.message)

    def test_process_failure_and_notifications(self):
        payment = PaymentService.initialize_payment(
            order=self.order,
            provider=Payment.PaymentProvider.CLICK,
            user=self.user,
        )

        PaymentService.process_failure(
            payment=payment,
            reason="Card limit exceeded",
            error_code="-200",
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, Payment.PaymentStatus.FAILED)
        self.assertEqual(payment.failure_reason, "Card limit exceeded")
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        notif = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.NotificationType.PAYMENT,
            priority=Notification.NotificationPriority.HIGH,
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("Card limit exceeded", notif.message)


class RefundServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='StrongPassword123!',
        )
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('300000.00'),
            shipping_fee=Decimal('0.00'),
            total_price=Decimal('300000.00'),
            payment_status=Order.PaymentStatus.PAID,
            status=Order.OrderStatus.CONFIRMED,
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            currency='UZS',
            provider=Payment.PaymentProvider.PAYME,
            status=Payment.PaymentStatus.SUCCESS,
        )

    def test_process_partial_and_full_refund(self):
        refund1 = RefundService.process_refund(
            payment=self.payment,
            amount=Decimal('100000.00'),
            reason="Damaged item returned",
            admin_user=self.admin_user,
        )

        self.assertEqual(refund1.status, Refund.RefundStatus.COMPLETED)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.refunded_amount, Decimal('100000.00'))
        self.assertEqual(self.payment.status, Payment.PaymentStatus.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PARTIALLY_REFUNDED)

        refund2 = RefundService.process_refund(
            payment=self.payment,
            amount=Decimal('200000.00'),
            reason="Full return",
            admin_user=self.admin_user,
        )

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.refunded_amount, Decimal('300000.00'))
        self.assertEqual(self.payment.status, Payment.PaymentStatus.REFUNDED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.REFUNDED)

    def test_process_refund_exceeding_balance_raises_error(self):
        with self.assertRaises(ValidationError):
            RefundService.process_refund(
                payment=self.payment,
                amount=Decimal('350000.00'),
                admin_user=self.admin_user,
            )


class SavedCardServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='cardholder@example.com',
            password='StrongPassword123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('150000.00'),
            shipping_fee=Decimal('25000.00'),
            total_price=Decimal('175000.00'),
            payment_method=Order.PaymentMethod.PAYME,
        )

    def test_add_and_verify_saved_card(self):
        card, otp_code = SavedCardService.add_card(
            user=self.user,
            card_number='8600 1234 5678 9012',
            expire_month='12',
            expire_year='28',
            card_holder='CARD HOLDER',
            provider=Payment.PaymentProvider.PAYME,
        )

        self.assertEqual(card.card_type, SavedCard.CardType.UZCARD)
        self.assertEqual(card.card_mask, '8600 12** **** 9012')
        self.assertFalse(card.is_verified)

        verified_card = SavedCardService.verify_card(
            user=self.user,
            card_id=card.id,
            otp_code=otp_code,
        )
        self.assertTrue(verified_card.is_verified)
        self.assertTrue(verified_card.is_default)

    def test_charge_saved_card_one_click(self):
        card, otp = SavedCardService.add_card(
            user=self.user,
            card_number='9860 0000 1111 2222',
            expire_month='05',
            expire_year='27',
        )
        SavedCardService.verify_card(user=self.user, card_id=card.id, otp_code=otp)

        payment = SavedCardService.charge_saved_card(
            user=self.user,
            card_id=card.id,
            order=self.order,
        )

        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)
