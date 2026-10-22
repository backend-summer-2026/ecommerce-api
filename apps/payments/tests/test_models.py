from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.orders.models import Order
from apps.payments.models import (
    Payment,
    PaymentTransaction,
    Refund,
    SavedCard,
)

User = get_user_model()


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='SecurePassword123!',
            first_name='Customer',
            last_name='User',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('250000.00'),
            shipping_fee=Decimal('25000.00'),
            total_price=Decimal('275000.00'),
            payment_method=Order.PaymentMethod.PAYME,
        )

    def test_payment_creation_and_auto_number(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.PAYME,
        )
        self.assertTrue(payment.payment_number.startswith('PAY-'))
        self.assertEqual(len(payment.payment_number), 19)  # PAY-YYYYMMDD-XXXXXX -> 4 + 8 + 1 + 6 = 19
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.currency, 'UZS')
        self.assertIn(payment.payment_number, str(payment))
        self.assertIn('275,000.00 UZS', str(payment))

    def test_payment_mark_as_success_syncs_with_order(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.PAYME,
        )
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)

        payment.mark_as_success(provider_transaction_id='payme_tx_998877', user=self.user)

        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(payment.provider_transaction_id, 'payme_tx_998877')
        self.assertIsNotNone(payment.paid_at)

        # Linked order should be synchronized
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)
        self.assertIsNotNone(self.order.paid_at)

    def test_payment_mark_as_failed(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.CLICK,
        )
        payment.mark_as_failed(reason="Insufficient card balance")

        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(payment.status, Payment.PaymentStatus.FAILED)
        self.assertEqual(payment.failure_reason, "Insufficient card balance")
        self.assertIsNotNone(payment.failed_at)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    def test_payment_mark_as_cancelled(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.UZUM,
        )
        payment.mark_as_cancelled(reason="User clicked back to cart")

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.CANCELLED)
        self.assertEqual(payment.failure_reason, "User clicked back to cart")
        self.assertIsNotNone(payment.cancelled_at)

    def test_payment_can_refund_logic(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=Decimal('100000.00'),
            provider=Payment.PaymentProvider.PAYME,
        )
        # Cannot refund pending payment
        self.assertFalse(payment.can_refund())

        payment.mark_as_success()
        self.assertTrue(payment.can_refund())
        self.assertTrue(payment.can_refund(Decimal('50000.00')))
        self.assertTrue(payment.can_refund(Decimal('100000.00')))
        self.assertFalse(payment.can_refund(Decimal('150000.00')))
        self.assertFalse(payment.can_refund(Decimal('0.00')))

        # After partial refund
        payment.refunded_amount = Decimal('80000.00')
        payment.status = Payment.PaymentStatus.PARTIALLY_REFUNDED
        payment.save()

        self.assertTrue(payment.can_refund(Decimal('20000.00')))
        self.assertFalse(payment.can_refund(Decimal('20000.01')))


class PaymentTransactionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='tx_user@example.com',
            password='SecurePassword123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('150000.00'),
            total_price=Decimal('150000.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.PAYME,
        )

    def test_create_payment_transaction_log(self):
        tx = PaymentTransaction.objects.create(
            payment=self.payment,
            transaction_type=PaymentTransaction.TransactionType.CHECK,
            amount=self.payment.amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key='idem-key-12345',
            provider_transaction_id='payme-raw-tx-1',
            request_payload={'method': 'CheckPerformTransaction', 'params': {'amount': 15000000}},
            response_payload={'result': {'allow': True}},
            ip_address='195.158.3.1',
        )
        self.assertEqual(tx.payment, self.payment)
        self.assertEqual(tx.request_payload['method'], 'CheckPerformTransaction')
        self.assertEqual(tx.response_payload['result']['allow'], True)
        self.assertIn('Check / Verify', str(tx))
        self.assertIn(self.payment.payment_number, str(tx))


class RefundModelTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email='manager@example.com',
            password='SecurePassword123!',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email='refund_customer@example.com',
            password='SecurePassword123!',
        )
        self.order = Order.objects.create(
            user=self.customer,
            subtotal=Decimal('300000.00'),
            total_price=Decimal('300000.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.customer,
            amount=Decimal('300000.00'),
            provider=Payment.PaymentProvider.CLICK,
        )
        self.payment.mark_as_success(provider_transaction_id='click_tx_112233')

    def test_refund_creation_and_auto_number(self):
        refund = Refund.objects.create(
            payment=self.payment,
            amount=Decimal('100000.00'),
            reason="Customer returned 1 damaged item",
            created_by=self.staff_user,
        )
        self.assertTrue(refund.refund_number.startswith('REF-'))
        self.assertEqual(refund.order, self.order)
        self.assertEqual(refund.status, Refund.RefundStatus.PENDING)
        self.assertIn(refund.refund_number, str(refund))
        self.assertIn('100,000.00 UZS', str(refund))

    def test_refund_validation_exceeding_amount(self):
        refund = Refund(
            payment=self.payment,
            order=self.order,
            amount=Decimal('350000.00'),  # Exceeds payment total of 300,000
            reason="Too large refund",
        )
        with self.assertRaises(ValidationError):
            refund.full_clean()

    def test_partial_and_full_refund_completion(self):
        # 1. Partial refund of 100,000
        refund1 = Refund.objects.create(
            payment=self.payment,
            amount=Decimal('100000.00'),
            reason="Partial return",
            created_by=self.staff_user,
        )
        refund1.mark_as_completed(provider_refund_id='click_ref_1')

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal('100000.00'))
        self.assertEqual(self.payment.status, Payment.PaymentStatus.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PARTIALLY_REFUNDED)

        # 2. Remaining refund of 200,000
        refund2 = Refund.objects.create(
            payment=self.payment,
            amount=Decimal('200000.00'),
            reason="Full remaining refund",
            created_by=self.staff_user,
        )
        refund2.mark_as_completed(provider_refund_id='click_ref_2')

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal('300000.00'))
        self.assertEqual(self.payment.status, Payment.PaymentStatus.REFUNDED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.REFUNDED)


class SavedCardModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='cardholder@example.com',
            password='SecurePassword123!',
        )

    def test_saved_card_creation_and_str(self):
        card = SavedCard.objects.create(
            user=self.user,
            provider=Payment.PaymentProvider.PAYME,
            card_token='tok_secret_payme_987654321',
            card_mask='8600 12** **** 5678',
            card_holder='ALI VALIYEV',
            card_type=SavedCard.CardType.UZCARD,
            expire_month='12',
            expire_year='28',
            is_default=True,
            is_verified=True,
        )
        self.assertEqual(str(card), 'Uzcard 8600 12** **** 5678 (Payme)')

    def test_default_card_switching(self):
        card1 = SavedCard.objects.create(
            user=self.user,
            provider=Payment.PaymentProvider.PAYME,
            card_token='tok_card_1',
            card_mask='8600 **** **** 1111',
            card_type=SavedCard.CardType.UZCARD,
            expire_month='01',
            expire_year='27',
            is_default=True,
        )
        self.assertTrue(card1.is_default)

        # Create second card with is_default=True
        card2 = SavedCard.objects.create(
            user=self.user,
            provider=Payment.PaymentProvider.CLICK,
            card_token='tok_card_2',
            card_mask='9860 **** **** 2222',
            card_type=SavedCard.CardType.HUMO,
            expire_month='02',
            expire_year='28',
            is_default=True,
        )
        card1.refresh_from_db()
        self.assertFalse(card1.is_default)
        self.assertTrue(card2.is_default)

    def test_unique_user_provider_card_token_constraint(self):
        SavedCard.objects.create(
            user=self.user,
            provider=Payment.PaymentProvider.PAYME,
            card_token='tok_duplicate_check',
            card_mask='8600 **** **** 3333',
            expire_month='05',
            expire_year='29',
        )
        with self.assertRaises(IntegrityError):
            SavedCard.objects.create(
                user=self.user,
                provider=Payment.PaymentProvider.PAYME,
                card_token='tok_duplicate_check',
                card_mask='8600 **** **** 3333',
                expire_month='05',
                expire_year='29',
            )
