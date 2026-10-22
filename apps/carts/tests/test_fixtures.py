from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.carts.models import Cart, CartItem
from apps.products.models import Brand, Category, Inventory, Product, ProductVariant
from apps.users.models import OTPCode

User = get_user_model()


class FixtureLoadingTestCase(TestCase):
    """
    Test suite to verify that test fixtures load cleanly into the test database
    and contain valid, consistent relational data.
    """

    fixtures = ['ecommerce_data.json']

    def test_users_fixture_data(self):
        self.assertEqual(User.objects.count(), 4)

        # Admin user checks
        admin = User.objects.get(email='admin@ecommerce.uz')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, 'admin')
        self.assertTrue(admin.check_password('testpass123'))

        # Customer user checks
        customer = User.objects.get(email='john.doe@example.com')
        self.assertTrue(customer.is_active)
        self.assertFalse(customer.is_staff)
        self.assertEqual(customer.role, 'customer')
        self.assertTrue(customer.check_password('testpass123'))

        # Inactive user check
        inactive_user = User.objects.get(email='inactive.user@example.com')
        self.assertFalse(inactive_user.is_active)

        # OTP codes check
        self.assertEqual(OTPCode.objects.count(), 3)
        valid_otp = OTPCode.objects.get(user=customer)
        self.assertTrue(valid_otp.is_valid())

    def test_products_fixture_data(self):
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Brand.objects.count(), 4)
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(ProductVariant.objects.count(), 5)
        self.assertEqual(Inventory.objects.count(), 5)

        # Category hierarchy check
        laptops = Category.objects.get(slug='laptops')
        self.assertEqual(laptops.get_full_path(), 'Electronics > Computers > Laptops')

        # Variant pricing and discount check
        mbp = ProductVariant.objects.get(sku='MBP16-M3-16-512-SG')
        self.assertEqual(mbp.price, Decimal('2499.00'))
        self.assertEqual(mbp.discount_price, Decimal('2299.00'))
        self.assertEqual(mbp.final_price, Decimal('2299.00'))
        self.assertTrue(mbp.is_on_sale)

        # Inventory check
        self.assertEqual(mbp.inventory.quantity, 50)
        self.assertEqual(mbp.inventory.reserved_quantity, 2)
        self.assertEqual(mbp.inventory.available_quantity, 48)
        self.assertTrue(mbp.inventory.is_in_stock)

        # Out-of-stock variant check
        samsung_variant = ProductVariant.objects.get(sku='GALS24-256-BLK')
        self.assertEqual(samsung_variant.inventory.available_quantity, 0)
        self.assertFalse(samsung_variant.inventory.is_in_stock)

    def test_carts_fixture_data(self):
        self.assertEqual(Cart.objects.count(), 4)
        self.assertEqual(CartItem.objects.count(), 5)

        # Authenticated user open cart
        user_cart = Cart.objects.get(id='c1000000-0000-0000-0000-000000000001')
        self.assertEqual(user_cart.status, Cart.CartStatus.OPEN)
        self.assertEqual(user_cart.user.email, 'john.doe@example.com')
        self.assertEqual(user_cart.total_items, 3)
        self.assertEqual(user_cart.unique_items_count, 2)
        self.assertEqual(user_cart.subtotal, Decimal('2819.00'))
        self.assertEqual(user_cart.total_price, Decimal('2559.00'))
        self.assertEqual(user_cart.total_discount, Decimal('260.00'))
        self.assertFalse(user_cart.is_empty)

        # Guest open cart
        guest_cart = Cart.objects.get(id='c2000000-0000-0000-0000-000000000002')
        self.assertIsNone(guest_cart.user)
        self.assertEqual(guest_cart.session_key, 'guest_session_alpha_123')
        self.assertEqual(guest_cart.status, Cart.CartStatus.OPEN)
        self.assertEqual(guest_cart.total_items, 1)

        # Merged cart
        merged_cart = Cart.objects.get(id='c3000000-0000-0000-0000-000000000003')
        self.assertEqual(merged_cart.status, Cart.CartStatus.MERGED)


class ModularFixtureLoadingTestCase(TestCase):
    """
    Test suite to verify that modular app-level fixtures can also be loaded together.
    """

    fixtures = ['users_data.json', 'products_data.json', 'carts_data.json']

    def test_modular_fixtures_loaded(self):
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(Cart.objects.count(), 4)
