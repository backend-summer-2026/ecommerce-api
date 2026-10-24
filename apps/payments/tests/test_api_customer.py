from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.orders.models import Order
from apps.payments.models import Payment, SavedCard
from apps.payments.services import SavedCardService

User = get_user_model()


class CustomerPaymentApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='alice@example.com',
            password='StrongPassword123!',
            first_name='Alice',
            last_name='Smith',
        )
        self.other_user = User.objects.create_user(
            email='bob@example.com',
            password='StrongPassword123!',
            first_name='Bob',
            last_name='Jones',
        )
        self.client.force_authenticate(user=self.user)

        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('100000.00'),
            shipping_fee=Decimal('25000.00'),
            total_price=Decimal('125000.00'),
            payment_method=Order.PaymentMethod.PAYME,
        )

    def test_payment_initialize_success(self):
        url = reverse('payments:payment-initialize')
        payload = {
            'order_number': self.order.order_number,
            'provider': Payment.PaymentProvider.PAYME,
            'return_url': 'https://example.com/checkout/success',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment_number', response.data)
        self.assertEqual(response.data['status'], Payment.PaymentStatus.PENDING)
        self.assertIsNotNone(response.data['checkout_url'])

    def test_payment_initialize_unauthorized_order(self):
        self.client.force_authenticate(user=self.other_user)
        url = reverse('payments:payment-initialize')
        payload = {
            'order_number': self.order.order_number,
            'provider': Payment.PaymentProvider.CLICK,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_list_filters_by_owner(self):
        Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.PAYME,
        )
        other_order = Order.objects.create(
            user=self.other_user,
            subtotal=Decimal('50000.00'),
            shipping_fee=Decimal('0.00'),
            total_price=Decimal('50000.00'),
        )
        Payment.objects.create(
            order=other_order,
            user=self.other_user,
            amount=Decimal('50000.00'),
            provider=Payment.PaymentProvider.CLICK,
        )

        url = reverse('payments:payment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['order_number'], self.order.order_number)

    def test_payment_detail_and_cancel(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            amount=self.order.total_price,
            provider=Payment.PaymentProvider.PAYME,
        )

        detail_url = reverse('payments:payment-detail', kwargs={'payment_number': payment.payment_number})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_number'], payment.payment_number)

        cancel_url = reverse('payments:payment-cancel', kwargs={'payment_number': payment.payment_number})
        cancel_response = self.client.post(cancel_url, {'reason': 'Changed mind'}, format='json')
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data['payment']['status'], Payment.PaymentStatus.CANCELLED)

    def test_saved_card_lifecycle(self):
        cards_url = reverse('payments:card-list-create')
        reg_payload = {
            'card_number': '8600 5555 4444 3333',
            'expire_month': '10',
            'expire_year': '29',
            'card_holder': 'ALICE SMITH',
            'provider': Payment.PaymentProvider.PAYME,
        }
        res_reg = self.client.post(cards_url, reg_payload, format='json')
        self.assertEqual(res_reg.status_code, status.HTTP_201_CREATED)
        card_id = res_reg.data['card']['id']
        otp_code = res_reg.data['otp_code']
        self.assertFalse(res_reg.data['card']['is_verified'])

        verify_url = reverse('payments:card-verify', kwargs={'pk': card_id})
        res_ver = self.client.post(verify_url, {'otp_code': otp_code}, format='json')
        self.assertEqual(res_ver.status_code, status.HTTP_200_OK)
        self.assertTrue(res_ver.data['card']['is_verified'])
        self.assertTrue(res_ver.data['card']['is_default'])

        res_list = self.client.get(cards_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

        pay_url = reverse('payments:pay-with-card')
        res_pay = self.client.post(
            pay_url,
            {'order_number': self.order.order_number, 'card_id': card_id},
            format='json',
        )
        self.assertEqual(res_pay.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pay.data['payment']['status'], Payment.PaymentStatus.SUCCESS)

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

        del_url = reverse('payments:card-delete', kwargs={'pk': card_id})
        res_del = self.client.delete(del_url)
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SavedCard.objects.filter(id=card_id).count(), 0)
