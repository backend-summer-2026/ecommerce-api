from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.carts.models import Cart, CartItem
from apps.orders.models import (
    Coupon,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class OrderAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper_api@example.com',
            password='TestPassword123!',
            first_name='Shopper',
            last_name='API',
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            email='other_api@example.com',
            password='OtherPassword123!',
            first_name='Other',
            last_name='Shopper',
            is_active=True,
        )
        self.staff_user = User.objects.create_user(
            email='staff_api@example.com',
            password='StaffPassword123!',
            first_name='Staff',
            last_name='Admin',
            is_staff=True,
            is_active=True,
        )

        self.brand = Brand.objects.create(name='BrandMax', slug='brandmax')
        self.category = Category.objects.create(name='Electronics', slug='electronics')

        self.product = Product.objects.create(
            name='Ultra Laptop',
            slug='ultra-laptop',
            brand=self.brand,
            is_active=True,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)

        self.variant = ProductVariant.objects.create(
            product=self.product,
            title='Ultra Laptop 16GB / 512GB',
            sku='LAPTOP-16-512',
            price=Decimal('12000000.00'),
            discount_price=Decimal('10000000.00'),
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=1,
            low_stock_threshold=2,
        )

        self.now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='SUPER500K',
            discount_type=Coupon.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('500000.00'),
            min_order_amount=Decimal('5000000.00'),
            usage_limit=100,
            usage_limit_per_user=1,
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=7),
            is_active=True,
        )

        self.valid_address_payload = {
            'recipient_name': 'Shopper API',
            'phone_number': '+998901112233',
            'region': 'Tashkent',
            'district': 'Mirabad',
            'street_address': 'Oybek street 15',
            'apartment_office': 'Suite 101',
            'postal_code': '100015',
            'delivery_instructions': 'Leave with receptionist',
        }

    def _setup_cart(self, quantity=1):
        cart = Cart.objects.create(user=self.user, status=Cart.CartStatus.OPEN)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=quantity,
            unit_price_at_addition=self.variant.final_price,
        )
        return cart

    # 1. Checkout Preview Tests
    def test_checkout_preview_unauthenticated(self):
        url = reverse('orders:checkout-preview')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_checkout_preview_success(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)

        url = reverse('orders:checkout-preview')
        payload = {
            'shipping_method': Order.ShippingMethod.STANDARD,
            'coupon_code': 'SUPER500K',
            'region': 'Tashkent',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data['total_items'], 1)
        self.assertEqual(Decimal(str(data['subtotal'])), Decimal('10000000.00'))
        self.assertEqual(Decimal(str(data['shipping_fee'])), Decimal('25000.00'))
        self.assertEqual(Decimal(str(data['discount_amount'])), Decimal('500000.00'))
        # 10,000,000 + 25,000 - 500,000 = 9,525,000
        self.assertEqual(Decimal(str(data['total_price'])), Decimal('9525000.00'))
        self.assertFalse(data['has_stock_issues'])
        self.assertEqual(len(data['items']), 1)

    def test_checkout_preview_empty_cart(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:checkout-preview')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Your shopping cart is empty", response.json()['detail'])

    # 2. Coupon Validation Tests
    def test_coupon_validate_endpoint_valid(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:coupon-validate')
        response = self.client.post(url, {'code': 'super500k', 'subtotal': '6000000.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['is_valid'])
        self.assertEqual(Decimal(str(data['discount_amount'])), Decimal('500000.00'))
        self.assertIsNotNone(data['coupon'])

    def test_coupon_validate_endpoint_invalid_code(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:coupon-validate')
        response = self.client.post(url, {'code': 'NO_SUCH_COUPON', 'subtotal': '6000000.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['is_valid'])
        self.assertEqual(Decimal(str(data['discount_amount'])), Decimal('0.00'))

    # 3. Order Create Tests
    def test_create_order_success(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)

        url = reverse('orders:order-list-create')
        payload = {
            'shipping_address': self.valid_address_payload,
            'shipping_method': Order.ShippingMethod.STANDARD,
            'payment_method': Order.PaymentMethod.CASH_ON_DELIVERY,
            'coupon_code': 'SUPER500K',
            'customer_notes': 'Please call before delivery',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertTrue(data['order_number'].startswith('ORD-'))
        self.assertEqual(data['status'], Order.OrderStatus.PENDING)
        self.assertEqual(Decimal(str(data['subtotal'])), Decimal('10000000.00'))
        self.assertEqual(Decimal(str(data['discount_amount'])), Decimal('500000.00'))
        self.assertEqual(Decimal(str(data['total_price'])), Decimal('9525000.00'))
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['shipping_address']['recipient_name'], 'Shopper API')

    def test_create_order_empty_cart_fails(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order-list-create')
        payload = {
            'shipping_address': self.valid_address_payload,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Your shopping cart is empty", response.json()['detail'])

    # 4. List User Orders Tests
    def test_list_user_orders(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)

        # Place order
        create_url = reverse('orders:order-list-create')
        self.client.post(create_url, {'shipping_address': self.valid_address_payload}, format='json')

        list_url = reverse('orders:order-list-create')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertTrue(data['results'][0]['order_number'].startswith('ORD-'))

    # 5. Get Order Details Tests
    def test_get_order_detail_owner_success(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        detail_url = reverse('orders:order-detail', kwargs={'order_number': order_number})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order_number'], order_number)
        self.assertEqual(data['status'], Order.OrderStatus.PENDING)
        self.assertTrue(data['can_cancel'])

    def test_get_order_detail_other_user_404(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        # Authenticate as different shopper
        self.client.force_authenticate(user=self.other_user)
        detail_url = reverse('orders:order-detail', kwargs={'order_number': order_number})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_order_detail_staff_success(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        # Authenticate as staff administrator
        self.client.force_authenticate(user=self.staff_user)
        detail_url = reverse('orders:order-detail', kwargs={'order_number': order_number})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['order_number'], order_number)

    # 6. Cancel Order Tests
    def test_cancel_order_success(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        cancel_url = reverse('orders:order-cancel', kwargs={'order_number': order_number})
        response = self.client.post(cancel_url, {'reason': 'Ordered by mistake'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order']['status'], Order.OrderStatus.CANCELLED)
        self.assertFalse(data['order']['can_cancel'])

    def test_cancel_already_delivered_order_fails(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        # Transition order to DELIVERED directly
        order = Order.objects.get(order_number=order_number)
        order.status = Order.OrderStatus.DELIVERED
        order.save()

        cancel_url = reverse('orders:order-cancel', kwargs={'order_number': order_number})
        response = self.client.post(cancel_url, {'reason': 'Cannot keep it'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be cancelled", response.json()['detail'])

    # 7. Order Tracking Timeline Tests
    def test_order_tracking_timeline(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        tracking_url = reverse('orders:order-tracking', kwargs={'order_number': order_number})
        response = self.client.get(tracking_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order_number'], order_number)
        self.assertEqual(data['status'], Order.OrderStatus.PENDING)
        self.assertTrue(len(data['timeline']) >= 1)

    # 8. Order Invoice Tests
    def test_order_invoice_endpoint(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        invoice_url = reverse('orders:order-invoice', kwargs={'order_number': order_number})
        response = self.client.get(invoice_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order_number'], order_number)
        self.assertEqual(data['customer_email'], 'shopper_api@example.com')
        self.assertEqual(len(data['items']), 1)

    # 9. Admin Endpoints Tests
    def test_admin_order_list_forbidden_for_shopper(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:admin-order-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_order_list_success_for_staff(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )

        self.client.force_authenticate(user=self.staff_user)
        url = reverse('orders:admin-order-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['count'] >= 1)

    def test_admin_update_status_and_tracking(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        self.client.force_authenticate(user=self.staff_user)
        status_url = reverse('orders:admin-order-status', kwargs={'order_number': order_number})
        payload = {
            'new_status': Order.OrderStatus.SHIPPED,
            'comment': 'Dispatched via Express Courier',
            'tracking_number': 'TRK-12345678',
            'is_customer_visible': True,
        }
        response = self.client.patch(status_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], Order.OrderStatus.SHIPPED)
        self.assertEqual(data['tracking_number'], 'TRK-12345678')

    def test_admin_order_notes_endpoint(self):
        self._setup_cart(quantity=1)
        self.client.force_authenticate(user=self.user)
        create_resp = self.client.post(
            reverse('orders:order-list-create'),
            {'shipping_address': self.valid_address_payload},
            format='json',
        )
        order_number = create_resp.json()['order_number']

        self.client.force_authenticate(user=self.staff_user)
        notes_url = reverse('orders:admin-order-notes', kwargs={'order_number': order_number})
        payload = {'admin_notes': 'Customer requested gift packaging via support call.'}
        response = self.client.post(notes_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('admin_notes', data)
        self.assertEqual(data['admin_notes'], 'Customer requested gift packaging via support call.')
