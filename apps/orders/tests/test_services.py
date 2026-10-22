from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.carts.models import Cart, CartItem
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.orders.services import OrderService
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='order_shopper@example.com',
            password='TestPassword123!',
            first_name='Shopper',
            last_name='User',
        )
        self.staff_user = User.objects.create_user(
            email='order_admin@example.com',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='Staff',
            is_staff=True,
        )
        self.other_user = User.objects.create_user(
            email='other_shopper@example.com',
            password='OtherPassword123!',
            first_name='Other',
            last_name='User',
        )

        self.brand = Brand.objects.create(name='TechCorp', slug='techcorp')
        self.category = Category.objects.create(name='Gadgets', slug='gadgets')

        self.product = Product.objects.create(
            name='Pro Smartphone',
            slug='pro-smartphone',
            brand=self.brand,
            is_active=True,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)

        self.variant = ProductVariant.objects.create(
            product=self.product,
            title='Pro Smartphone 256GB Black',
            sku='PRO-SMART-256-BLK',
            price=Decimal('1000000.00'),
            discount_price=Decimal('900000.00'),
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=20,
            reserved_quantity=2,
            low_stock_threshold=5,
        )

        self.now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='DISCOUNT10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('500000.00'),
            max_discount_amount=Decimal('100000.00'),
            usage_limit=50,
            usage_limit_per_user=1,
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=7),
            is_active=True,
        )

        # Setup an active cart with an item
        self.cart = Cart.objects.create(user=self.user, status=Cart.CartStatus.OPEN)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price_at_addition=self.variant.final_price,
        )

        self.valid_address_data = {
            'recipient_name': 'Shopper User',
            'phone_number': '+998901234567',
            'region': 'Tashkent',
            'district': 'Yunusabad',
            'street_address': 'Amir Temur street 12',
            'apartment_office': 'Apt 45',
            'postal_code': '100000',
            'delivery_instructions': 'Ring doorbell twice',
        }

    def test_calculate_shipping_fee(self):
        # Tashkent Standard
        fee_standard_tashkent = OrderService.calculate_shipping_fee(Order.ShippingMethod.STANDARD, 'Tashkent')
        self.assertEqual(fee_standard_tashkent, Decimal('25000.00'))

        # Samarkand Standard
        fee_standard_samarkand = OrderService.calculate_shipping_fee(Order.ShippingMethod.STANDARD, 'Samarkand')
        self.assertEqual(fee_standard_samarkand, Decimal('40000.00'))

        # Tashkent Express
        fee_express_tashkent = OrderService.calculate_shipping_fee(Order.ShippingMethod.EXPRESS, 'Toshkent shahri')
        self.assertEqual(fee_express_tashkent, Decimal('45000.00'))

        # Other Express
        fee_express_other = OrderService.calculate_shipping_fee(Order.ShippingMethod.EXPRESS, 'Bukhara')
        self.assertEqual(fee_express_other, Decimal('70000.00'))

        # Pickup
        fee_pickup = OrderService.calculate_shipping_fee(Order.ShippingMethod.PICKUP, 'Tashkent')
        self.assertEqual(fee_pickup, Decimal('0.00'))

    def test_validate_coupon_success(self):
        coupon, discount, msg = OrderService.validate_coupon(
            'discount10',
            self.user,
            Decimal('1800000.00'),
        )
        self.assertIsNotNone(coupon)
        self.assertEqual(coupon.code, 'DISCOUNT10')
        # 10% of 1,800,000 is 180,000, capped at max_discount_amount=100,000
        self.assertEqual(discount, Decimal('100000.00'))
        self.assertIn("Coupon applied successfully", msg)

    def test_validate_coupon_expired_or_invalid(self):
        # Non existent
        coupon, discount, msg = OrderService.validate_coupon('INVALID_CODE', self.user, Decimal('500000.00'))
        self.assertIsNone(coupon)
        self.assertEqual(discount, Decimal('0.00'))

        # Min order amount not reached
        coupon, discount, msg = OrderService.validate_coupon('DISCOUNT10', self.user, Decimal('100000.00'))
        self.assertIsNone(coupon)
        self.assertIn("Minimum order amount", msg)

    def test_preview_checkout_success(self):
        preview = OrderService.preview_checkout(
            user=self.user,
            shipping_method=Order.ShippingMethod.STANDARD,
            coupon_code='DISCOUNT10',
            region='Tashkent',
        )

        self.assertEqual(preview['cart_id'], self.cart.id)
        self.assertEqual(preview['total_items'], 2)
        # 2 * 900,000 = 1,800,000
        self.assertEqual(preview['subtotal'], Decimal('1800000.00'))
        self.assertEqual(preview['shipping_fee'], Decimal('25000.00'))
        self.assertEqual(preview['discount_amount'], Decimal('100000.00'))
        # 1,800,000 + 25,000 - 100,000 = 1,725,000
        self.assertEqual(preview['total_price'], Decimal('1725000.00'))
        self.assertFalse(preview['has_stock_issues'])
        self.assertEqual(len(preview['items']), 1)

    def test_preview_checkout_empty_cart_raises_error(self):
        # Clear cart items
        self.cart.items.all().delete()
        with self.assertRaises(ValidationError) as ctx:
            OrderService.preview_checkout(user=self.user)
        self.assertIn("Your shopping cart is empty", str(ctx.exception))

    def test_create_order_from_cart_success(self):
        initial_reserved = self.inventory.reserved_quantity

        order = OrderService.create_order_from_cart(
            user=self.user,
            shipping_address_data=self.valid_address_data,
            shipping_method=Order.ShippingMethod.STANDARD,
            payment_method=Order.PaymentMethod.CASH_ON_DELIVERY,
            coupon_code='DISCOUNT10',
            customer_notes='Please call before delivery',
        )

        self.assertIsNotNone(order.id)
        self.assertTrue(order.order_number.startswith('ORD-'))
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(order.subtotal, Decimal('1800000.00'))
        self.assertEqual(order.shipping_fee, Decimal('25000.00'))
        self.assertEqual(order.discount_amount, Decimal('100000.00'))
        self.assertEqual(order.total_price, Decimal('1725000.00'))

        # Check address snapshot
        self.assertEqual(order.shipping_address.recipient_name, 'Shopper User')
        self.assertEqual(order.shipping_address.street_address, 'Amir Temur street 12')

        # Check items snapshot
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.variant, self.variant)
        self.assertEqual(item.product_name, 'Pro Smartphone')
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal('900000.00'))
        self.assertEqual(item.total_price, Decimal('1800000.00'))

        # Check inventory reservation
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, initial_reserved + 2)

        # Check coupon usage
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 1)
        self.assertTrue(CouponUsage.objects.filter(coupon=self.coupon, order=order, user=self.user).exists())

        # Check cart converted
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.CartStatus.CONVERTED)

        # Check status history
        self.assertTrue(order.status_history.filter(new_status=Order.OrderStatus.PENDING).exists())

    def test_create_order_insufficient_stock_raises_error(self):
        # Set inventory quantity lower than requested
        self.inventory.quantity = 2
        self.inventory.reserved_quantity = 2  # available is 0
        self.inventory.save()

        with self.assertRaises(ValidationError) as ctx:
            OrderService.create_order_from_cart(
                user=self.user,
                shipping_address_data=self.valid_address_data,
            )
        self.assertIn("Insufficient stock", str(ctx.exception))

    def test_cancel_order_releases_stock(self):
        order = OrderService.create_order_from_cart(
            user=self.user,
            shipping_address_data=self.valid_address_data,
        )
        self.inventory.refresh_from_db()
        reserved_after_order = self.inventory.reserved_quantity

        # Cancel order
        cancelled_order = OrderService.cancel_order(
            order=order,
            user=self.user,
            reason='Customer changed mind',
        )

        self.assertEqual(cancelled_order.status, Order.OrderStatus.CANCELLED)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, reserved_after_order - 2)

        # Check cancellation history
        self.assertTrue(
            cancelled_order.status_history.filter(new_status=Order.OrderStatus.CANCELLED).exists()
        )

    def test_cancel_order_unauthorized_fails(self):
        order = OrderService.create_order_from_cart(
            user=self.user,
            shipping_address_data=self.valid_address_data,
        )

        with self.assertRaises(ValidationError) as ctx:
            OrderService.cancel_order(order=order, user=self.other_user)
        self.assertIn("You do not have permission", str(ctx.exception))

    def test_admin_transition_status(self):
        order = OrderService.create_order_from_cart(
            user=self.user,
            shipping_address_data=self.valid_address_data,
        )

        updated_order = OrderService.admin_transition_status(
            order=order,
            new_status=Order.OrderStatus.SHIPPED,
            comment="Handed over to Express Courier",
            user=self.staff_user,
            tracking_number="UZEX-99887766",
            is_customer_visible=True,
        )

        self.assertEqual(updated_order.status, Order.OrderStatus.SHIPPED)
        self.assertEqual(updated_order.tracking_number, "UZEX-99887766")
        self.assertTrue(
            updated_order.status_history.filter(
                new_status=Order.OrderStatus.SHIPPED,
                created_by=self.staff_user,
            ).exists()
        )
