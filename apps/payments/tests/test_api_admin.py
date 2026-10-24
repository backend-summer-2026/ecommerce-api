from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction, Refund

User = get_user_model()


class AdminPaymentApiTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='Staff',
        )
        self.regular_user = User.objects.create_user(
            email='customer@example.com',
            password='CustomerPassword123!',
            first_name='Customer',
            last_name='User',
        )

        self.order = Order.objects.create(
            user=self.regular_user,
            subtotal=Decimal('500000.00'),
            shipping_fee=Decimal('0.00'),
            total_price=Decimal('500000.00'),
            payment_status=Order.PaymentStatus.PAID,
            status=Order.OrderStatus.CONFIRMED,
        )

        self.payment = Payment.objects.create(
            order=self.order,
            user=self.regular_user,
            amount=self.order.total_price,
            currency='UZS',
            provider=Payment.PaymentProvider.PAYME,
            status=Payment.PaymentStatus.SUCCESS,
        )

        self.tx = PaymentTransaction.objects.create(
            payment=self.payment,
            transaction_type=PaymentTransaction.TransactionType.PERFORM,
            amount=self.payment.amount,
            status=PaymentTransaction.TransactionStatus.SUCCESS,
            idempotency_key='ADMIN_TEST_KEY_1',
            provider_transaction_id='ADMIN_TX_1',
        )

    def test_admin_endpoints_forbidden_for_regular_users(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('payments:admin-payment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_payment_list_and_detail(self):
        self.client.force_authenticate(user=self.staff_user)

        # List
        list_url = reverse('payments:admin-payment-list')
        res_list = self.client.get(list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data['count'], 1)

        # Detail
        detail_url = reverse('payments:admin-payment-detail', kwargs={'payment_number': self.payment.payment_number})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data['payment_number'], self.payment.payment_number)
        self.assertEqual(len(res_detail.data['transactions']), 1)

    def test_admin_refund_create_and_list(self):
        self.client.force_authenticate(user=self.staff_user)

        # 1. Create refund
        refund_create_url = reverse('payments:admin-payment-refund', kwargs={'payment_number': self.payment.payment_number})
        payload = {
            'amount': '150000.00',
            'reason': 'Customer requested refund for item',
            'provider_refund_id': 'GATEWAY_REF_001',
        }
        res_ref = self.client.post(refund_create_url, payload, format='json')
        self.assertEqual(res_ref.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_ref.data['status'], Refund.RefundStatus.COMPLETED)
        refund_number = res_ref.data['refund_number']

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal('150000.00'))
        self.assertEqual(self.payment.status, Payment.PaymentStatus.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PARTIALLY_REFUNDED)

        # 2. List refunds
        refund_list_url = reverse('payments:admin-refund-list')
        res_list = self.client.get(refund_list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data['count'], 1)

        # 3. Detail refund
        refund_detail_url = reverse('payments:admin-refund-detail', kwargs={'refund_number': refund_number})
        res_det = self.client.get(refund_detail_url)
        self.assertEqual(res_det.status_code, status.HTTP_200_OK)
        self.assertEqual(res_det.data['refund_number'], refund_number)

    def test_admin_transaction_list(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('payments:admin-transaction-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['idempotency_key'], 'ADMIN_TEST_KEY_1')
