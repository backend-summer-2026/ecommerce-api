import base64
import hashlib
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction
from apps.payments.services.gateways import ClickError, PaymeError

User = get_user_model()


class WebhookApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='StrongPassword123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('200000.00'),
            shipping_fee=Decimal('25000.00'),
            total_price=Decimal('225000.00'),
            payment_method=Order.PaymentMethod.PAYME,
        )

        self.payme_secret = settings.PAYME_SETTINGS.get('SECRET_KEY', 'test_secret_key')
        self.payme_auth = 'Basic ' + base64.b64encode(f"Paycom:{self.payme_secret}".encode('utf-8')).decode('utf-8')

    def test_payme_auth_failure(self):
        url = reverse('payments:webhook-payme')
        payload = {'method': 'CheckPerformTransaction', 'params': {}, 'id': 1}
        response = self.client.post(
            url,
            payload,
            format='json',
            HTTP_AUTHORIZATION='Basic invalid_credentials',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['error']['code'], PaymeError.AUTH_ERROR)

    def test_payme_check_perform_transaction_success(self):
        url = reverse('payments:webhook-payme')
        payload = {
            'method': 'CheckPerformTransaction',
            'params': {
                'amount': 22500000,
                'account': {'order_number': self.order.order_number},
            },
            'id': 123,
        }
        response = self.client.post(url, payload, format='json', HTTP_AUTHORIZATION=self.payme_auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['result']['allow'])

    def test_payme_check_perform_transaction_invalid_amount(self):
        url = reverse('payments:webhook-payme')
        payload = {
            'method': 'CheckPerformTransaction',
            'params': {
                'amount': 10000000,
                'account': {'order_number': self.order.order_number},
            },
            'id': 124,
        }
        response = self.client.post(url, payload, format='json', HTTP_AUTHORIZATION=self.payme_auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['error']['code'], PaymeError.INVALID_AMOUNT)

    def test_payme_create_and_perform_transaction_lifecycle(self):
        url = reverse('payments:webhook-payme')

        # 1. CreateTransaction
        create_payload = {
            'method': 'CreateTransaction',
            'params': {
                'id': 'payme_trans_001',
                'time': 1600000000000,
                'amount': 22500000,
                'account': {'order_number': self.order.order_number},
            },
            'id': 101,
        }
        res_create = self.client.post(url, create_payload, format='json', HTTP_AUTHORIZATION=self.payme_auth)
        self.assertEqual(res_create.status_code, status.HTTP_200_OK)
        self.assertEqual(res_create.data['result']['state'], 1)

        # 2. PerformTransaction
        perform_payload = {
            'method': 'PerformTransaction',
            'params': {'id': 'payme_trans_001'},
            'id': 102,
        }
        res_perform = self.client.post(url, perform_payload, format='json', HTTP_AUTHORIZATION=self.payme_auth)
        self.assertEqual(res_perform.status_code, status.HTTP_200_OK)
        self.assertEqual(res_perform.data['result']['state'], 2)

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

        # 3. CheckTransaction
        check_payload = {
            'method': 'CheckTransaction',
            'params': {'id': 'payme_trans_001'},
            'id': 103,
        }
        res_check = self.client.post(url, check_payload, format='json', HTTP_AUTHORIZATION=self.payme_auth)
        self.assertEqual(res_check.status_code, status.HTTP_200_OK)
        self.assertEqual(res_check.data['result']['state'], 2)

    def test_click_prepare_and_complete_lifecycle(self):
        url = reverse('payments:webhook-click')
        click_cfg = settings.CLICK_SETTINGS
        service_id = str(click_cfg.get('SERVICE_ID', 'test_service_id'))
        secret_key = str(click_cfg.get('SECRET_KEY', 'test_secret_key'))

        click_trans_id = 99881122
        amount = '225000.00'
        sign_time = '2026-10-22 12:00:00'

        # 1. Prepare action (0)
        prep_payload = {
            'click_trans_id': click_trans_id,
            'service_id': 12345,
            'click_paydoc_id': 5544,
            'merchant_trans_id': self.order.order_number,
            'amount': amount,
            'action': 0,
            'error': 0,
            'error_note': 'Success',
            'sign_time': sign_time,
            'sign_string': '',
        }
        prep_payload['service_id'] = int(service_id) if service_id.isdigit() else 12345
        sign_source = f"{click_trans_id}{prep_payload['service_id']}{secret_key}{self.order.order_number}{amount}0{sign_time}"
        prep_payload['sign_string'] = hashlib.md5(sign_source.encode('utf-8')).hexdigest()

        res_prep = self.client.post(url, prep_payload, format='json')
        self.assertEqual(res_prep.status_code, status.HTTP_200_OK)
        self.assertEqual(res_prep.data['error'], ClickError.SUCCESS)
        prepare_id = res_prep.data['merchant_prepare_id']

        # 2. Complete action (1)
        sign_source_complete = f"{click_trans_id}{prep_payload['service_id']}{secret_key}{self.order.order_number}{amount}1{sign_time}"
        sign_string_complete = hashlib.md5(sign_source_complete.encode('utf-8')).hexdigest()

        complete_payload = {
            'click_trans_id': click_trans_id,
            'service_id': prep_payload['service_id'],
            'click_paydoc_id': 5544,
            'merchant_trans_id': self.order.order_number,
            'merchant_prepare_id': prepare_id,
            'amount': amount,
            'action': 1,
            'error': 0,
            'error_note': 'Success',
            'sign_time': sign_time,
            'sign_string': sign_string_complete,
        }
        res_comp = self.client.post(url, complete_payload, format='json')
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)
        self.assertEqual(res_comp.data['error'], ClickError.SUCCESS)

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

    def test_uzum_webhook_success(self):
        url = reverse('payments:webhook-uzum')
        payload = {
            'order_id': self.order.order_number,
            'payment_id': 'UZUM_TX_9999',
            'amount': '225000.00',
            'status': 'SUCCESS',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'OK')

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
