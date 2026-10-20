from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.carts.models import Cart, CartItem
from apps.products.models import Brand, Category, Inventory, Product, ProductVariant

User = get_user_model()


class CartModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='TestPassword123!',
            first_name='John',
            last_name='Doe',
            is_active=True,
        )
        self.user2 = User.objects.create_user(
            email='shopper2@example.com',
            password='TestPassword123!',
            first_name='Jane',
            last_name='Doe',
            is_active=True,
        )
        self.category = Category.objects.create(name='Smartphones', slug='smartphones')
        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.product = Product.objects.create(
            name='iPhone 15 Pro',
            slug='iphone-15-pro',
            brand=self.brand,
            is_active=True,
        )
        self.variant1 = ProductVariant.objects.create(
            product=self.product,
            title='128GB Black Titanium',
            sku='IPHONE-15P-128-BLK',
            price=Decimal('12000000.00'),
            discount_price=Decimal('11000000.00'),
            is_active=True,
            is_default=True,
        )
        self.inventory1 = Inventory.objects.create(
            variant=self.variant1,
            quantity=10,
            reserved_quantity=2,  # available = 8
        )

        self.variant2 = ProductVariant.objects.create(
            product=self.product,
            title='256GB Natural Titanium',
            sku='IPHONE-15P-256-NAT',
            price=Decimal('14000000.00'),
            discount_price=None,  # No discount
            is_active=True,
        )
        self.inventory2 = Inventory.objects.create(
            variant=self.variant2,
            quantity=5,
            reserved_quantity=0,  # available = 5
        )

    def test_create_user_cart(self):
        cart = Cart.objects.create(user=self.user)
        self.assertIsInstance(cart.id, uuid.UUID)
        self.assertEqual(cart.user, self.user)
        self.assertEqual(cart.status, Cart.CartStatus.OPEN)
        self.assertTrue(cart.is_empty)
        self.assertEqual(cart.total_items, 0)
        self.assertEqual(cart.total_price, Decimal('0.00'))
        self.assertIn('shopper@example.com', str(cart))

    def test_create_guest_cart(self):
        session_id = 'session_xyz_123'
        cart = Cart.objects.create(session_key=session_id)
        self.assertIsNone(cart.user)
        self.assertEqual(cart.session_key, session_id)
        self.assertEqual(cart.status, Cart.CartStatus.OPEN)
        self.assertIn('Guest', str(cart))

    def test_cart_clean_requires_user_or_session_key(self):
        cart = Cart()
        with self.assertRaises(ValidationError):
            cart.clean()

    def test_unique_active_user_cart_constraint(self):
        Cart.objects.create(user=self.user, status=Cart.CartStatus.OPEN)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Cart.objects.create(user=self.user, status=Cart.CartStatus.OPEN)

        # But a user can have a second cart if the first one is CONVERTED or MERGED
        converted_cart = Cart.objects.create(user=self.user2, status=Cart.CartStatus.CONVERTED)
        active_cart = Cart.objects.create(user=self.user2, status=Cart.CartStatus.OPEN)
        self.assertEqual(converted_cart.status, Cart.CartStatus.CONVERTED)
        self.assertEqual(active_cart.status, Cart.CartStatus.OPEN)

    def test_add_cart_item_and_calculations(self):
        cart = Cart.objects.create(user=self.user)
        item1 = CartItem.objects.create(cart=cart, variant=self.variant1, quantity=2)

        # Snapshot price should be automatically set to final_price
        self.assertEqual(item1.unit_price_at_addition, Decimal('11000000.00'))
        self.assertEqual(item1.current_unit_price, Decimal('11000000.00'))
        self.assertEqual(item1.subtotal, Decimal('24000000.00'))
        self.assertEqual(item1.total_price, Decimal('22000000.00'))
        self.assertEqual(item1.discount_amount, Decimal('2000000.00'))
        self.assertFalse(item1.is_price_changed)
        self.assertTrue(item1.is_available)

        # Add second item without discount
        item2 = CartItem.objects.create(cart=cart, variant=self.variant2, quantity=1)
        self.assertEqual(item2.unit_price_at_addition, Decimal('14000000.00'))
        self.assertEqual(item2.subtotal, Decimal('14000000.00'))
        self.assertEqual(item2.total_price, Decimal('14000000.00'))
        self.assertEqual(item2.discount_amount, Decimal('0.00'))

        # Cart totals
        self.assertEqual(cart.total_items, 3)
        self.assertEqual(cart.unique_items_count, 2)
        self.assertFalse(cart.is_empty)
        # Subtotal: 24,000,000 + 14,000,000 = 38,000,000
        self.assertEqual(cart.subtotal, Decimal('38000000.00'))
        # Total Price: 22,000,000 + 14,000,000 = 36,000,000
        self.assertEqual(cart.total_price, Decimal('36000000.00'))
        # Total Discount: 2,000,000
        self.assertEqual(cart.total_discount, Decimal('2000000.00'))
        self.assertFalse(cart.has_unavailable_items)

    def test_price_change_detection(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, variant=self.variant1, quantity=1)
        self.assertFalse(item.is_price_changed)

        # Simulate price drop
        self.variant1.discount_price = Decimal('10000000.00')
        self.variant1.save()

        self.assertTrue(item.is_price_changed)
        self.assertEqual(item.unit_price_at_addition, Decimal('11000000.00'))
        self.assertEqual(item.current_unit_price, Decimal('10000000.00'))

    def test_cart_item_unique_variant_constraint(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant1, quantity=1)
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(cart=cart, variant=self.variant1, quantity=2)

    def test_stock_validation(self):
        cart = Cart.objects.create(user=self.user)
        # available is 8, try to add 9
        item = CartItem(cart=cart, variant=self.variant1, quantity=9)
        with self.assertRaises(ValidationError):
            item.clean()

        # 0 or negative quantity
        invalid_item = CartItem(cart=cart, variant=self.variant1, quantity=0)
        with self.assertRaises(ValidationError):
            invalid_item.clean()

    def test_cart_clear(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant1, quantity=1)
        CartItem.objects.create(cart=cart, variant=self.variant2, quantity=1)
        self.assertEqual(cart.items.count(), 2)

        cart.clear()
        self.assertEqual(cart.items.count(), 0)
        self.assertTrue(cart.is_empty)

    def test_merge_guest_cart_into_user_cart(self):
        guest_cart = Cart.objects.create(session_key='session_anon_999')
        CartItem.objects.create(cart=guest_cart, variant=self.variant1, quantity=2)
        CartItem.objects.create(cart=guest_cart, variant=self.variant2, quantity=1)

        user_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=user_cart, variant=self.variant1, quantity=1)

        user_cart.merge_with(guest_cart)

        # Variant 1 quantity should now be 1 + 2 = 3
        v1_item = user_cart.items.get(variant=self.variant1)
        self.assertEqual(v1_item.quantity, 3)

        # Variant 2 was moved from guest cart into user cart
        v2_item = user_cart.items.get(variant=self.variant2)
        self.assertEqual(v2_item.quantity, 1)

        # Guest cart must be marked as MERGED
        guest_cart.refresh_from_db()
        self.assertEqual(guest_cart.status, Cart.CartStatus.MERGED)
        self.assertEqual(user_cart.total_items, 4)
