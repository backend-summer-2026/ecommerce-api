from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.carts.models import Cart
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class CouponModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='SecurePassword123!',
            first_name='Shopper',
            last_name='One',
        )
        self.now = timezone.now()
        self.coupon_percent = Coupon.objects.create(
            code='SAVE20',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('20.00'),
            min_order_amount=Decimal('100000.00'),
            max_discount_amount=Decimal('50000.00'),
            usage_limit=10,
            usage_limit_per_user=1,
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=7),
            is_active=True,
        )
        self.coupon_fixed = Coupon.objects.create(
            code='FLAT30K',
            discount_type=Coupon.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('30000.00'),
            min_order_amount=Decimal('50000.00'),
            valid_from=self.now - timedelta(days=1),
            valid_until=self.now + timedelta(days=7),
            is_active=True,
        )

    def test_coupon_str_and_code_normalization(self):
        self.assertIn('SAVE20', str(self.coupon_percent))
        self.assertIn('20.00%', str(self.coupon_percent))
        self.assertIn('FLAT30K', str(self.coupon_fixed))
        self.assertIn('30,000.00 UZS', str(self.coupon_fixed))

        # Test case insensitivity / auto-uppercase
        coupon_lower = Coupon.objects.create(
            code='lowercase10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            valid_from=self.now,
            valid_until=self.now + timedelta(days=1),
        )
        self.assertEqual(coupon_lower.code, 'LOWERCASE10')

    def test_coupon_clean_validation(self):
        # Expiry date before valid_from
        invalid_dates = Coupon(
            code='BADTIME',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            valid_from=self.now,
            valid_until=self.now - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            invalid_dates.clean()

        # Percentage discount over 100%
        invalid_percent = Coupon(
            code='OVER100',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('105.00'),
            valid_from=self.now,
            valid_until=self.now + timedelta(days=5),
        )
        with self.assertRaises(ValidationError):
            invalid_percent.clean()

    def test_coupon_is_valid_method(self):
        # Normal valid case
        is_valid, msg = self.coupon_percent.is_valid(user=self.user, subtotal=Decimal('150000.00'))
        self.assertTrue(is_valid)

        # Inactive coupon
        self.coupon_percent.is_active = False
        self.coupon_percent.save(update_fields=['is_active'])
        is_valid, msg = self.coupon_percent.is_valid(user=self.user, subtotal=Decimal('150000.00'))
        self.assertFalse(is_valid)
        self.coupon_percent.is_active = True
        self.coupon_percent.save(update_fields=['is_active'])

        # Expired coupon
        expired_coupon = Coupon.objects.create(
            code='EXPIRED',
            discount_type=Coupon.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('10000.00'),
            valid_from=self.now - timedelta(days=10),
            valid_until=self.now - timedelta(days=1),
        )
        is_valid, msg = expired_coupon.is_valid()
        self.assertFalse(is_valid)
        self.assertIn("expired", msg)

        # Future coupon
        future_coupon = Coupon.objects.create(
            code='FUTURE',
            discount_type=Coupon.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('10000.00'),
            valid_from=self.now + timedelta(days=2),
            valid_until=self.now + timedelta(days=10),
        )
        is_valid, msg = future_coupon.is_valid()
        self.assertFalse(is_valid)
        self.assertIn("not valid yet", msg)

        # Subtotal below minimum order amount
        is_valid, msg = self.coupon_percent.is_valid(user=self.user, subtotal=Decimal('50000.00'))
        self.assertFalse(is_valid)
        self.assertIn("Minimum order amount", msg)

        # Global usage limit reached
        self.coupon_percent.used_count = 10
        self.coupon_percent.save(update_fields=['used_count'])
        is_valid, msg = self.coupon_percent.is_valid(user=self.user, subtotal=Decimal('150000.00'))
        self.assertFalse(is_valid)
        self.assertIn("maximum usage limit", msg)

    def test_coupon_calculate_discount(self):
        # 20% of 200,000 = 40,000 (below max cap of 50,000)
        discount = self.coupon_percent.calculate_discount(Decimal('200000.00'))
        self.assertEqual(discount, Decimal('40000.00'))

        # 20% of 300,000 = 60,000 -> capped at 50,000
        discount_capped = self.coupon_percent.calculate_discount(Decimal('300000.00'))
        self.assertEqual(discount_capped, Decimal('50000.00'))

        # Fixed discount of 30,000 on 100,000 = 30,000
        discount_fixed = self.coupon_fixed.calculate_discount(Decimal('100000.00'))
        self.assertEqual(discount_fixed, Decimal('30000.00'))

        # Fixed discount on small subtotal (20,000) does not exceed subtotal
        discount_fixed_small = self.coupon_fixed.calculate_discount(Decimal('200000.00'))
        self.assertEqual(discount_fixed_small, Decimal('30000.00'))


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='SecurePassword123!',
            first_name='Alisher',
            last_name='Navoiy',
            phone_number='+998901234567',
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.product = Product.objects.create(
            name='iPhone 15 Pro',
            slug='iphone-15-pro',
            brand=self.brand,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='IPHONE-15-PRO-BLK',
            price=Decimal('12000000.00'),
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=0,
        )

        self.order = Order.objects.create(
            user=self.user,
            shipping_method=Order.ShippingMethod.STANDARD,
            payment_method=Order.PaymentMethod.CLICK,
            subtotal=Decimal('12000000.00'),
            shipping_fee=Decimal('30000.00'),
            discount_amount=Decimal('0.00'),
            total_price=Decimal('12030000.00'),
        )
        self.order_address = OrderAddress.objects.create(
            order=self.order,
            recipient_name='Alisher Navoiy',
            phone_number='+998901234567',
            region='Toshkent shahar',
            district='Mirobod tumani',
            street_address='Amir Temur ko\'chasi 45-uy',
            apartment_office='7-qavat, 42-ofis',
            postal_code='100000',
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_sku=self.variant.sku,
            variant_attributes_display='Rang: Qora | Xotira: 256GB',
            unit_price=Decimal('12000000.00'),
            quantity=1,
        )

    def test_order_number_auto_generation(self):
        self.assertTrue(self.order.order_number.startswith('ORD-'))
        self.assertEqual(len(self.order.order_number), 19)  # ORD-YYYYMMDD-XXXXXX is 19 chars

    def test_order_str_and_total_items(self):
        self.assertIn(self.order.order_number, str(self.order))
        self.assertEqual(self.order.total_items, 1)

    def test_recalculate_totals(self):
        # Add another item
        OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name='Accessory',
            variant_sku='ACC-01',
            unit_price=Decimal('500000.00'),
            quantity=2,
        )
        self.order.recalculate_totals()
        # Item 1: 12,000,000 + Item 2: 2 * 500,000 = 13,000,000
        self.assertEqual(self.order.subtotal, Decimal('13000000.00'))
        # 13,000,000 + 30,000 shipping = 13,030,000
        self.assertEqual(self.order.total_price, Decimal('13030000.00'))

    def test_can_cancel_property(self):
        self.assertTrue(self.order.can_cancel)

        self.order.status = Order.OrderStatus.SHIPPED
        self.order.save(update_fields=['status'])
        self.assertFalse(self.order.can_cancel)

        self.order.status = Order.OrderStatus.DELIVERED
        self.order.save(update_fields=['status'])
        self.assertFalse(self.order.can_cancel)

    def test_transition_status(self):
        self.assertEqual(self.order.status_history.count(), 0)

        self.order.transition_status(
            new_status=Order.OrderStatus.PROCESSING,
            comment="Preparing package in warehouse",
            user=self.user,
        )
        self.assertEqual(self.order.status, Order.OrderStatus.PROCESSING)
        self.assertEqual(self.order.status_history.count(), 1)
        history_entry = self.order.status_history.first()
        self.assertEqual(history_entry.old_status, Order.OrderStatus.PENDING)
        self.assertEqual(history_entry.new_status, Order.OrderStatus.PROCESSING)
        self.assertEqual(history_entry.comment, "Preparing package in warehouse")
        self.assertEqual(history_entry.created_by, self.user)

    def test_mark_as_paid(self):
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
        self.assertIsNone(self.order.paid_at)

        self.order.mark_as_paid(user=self.user)
        self.order.refresh_from_db()

        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(self.order.paid_at)
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

    def test_cancel_order_and_release_inventory(self):
        # Simulate inventory reservation
        self.inventory.reserved_quantity = 1
        self.inventory.save()

        self.order.cancel(reason="Customer changed their mind", user=self.user)
        self.order.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(self.order.status, Order.OrderStatus.CANCELLED)
        self.assertEqual(self.order.cancellation_reason, "Customer changed their mind")
        self.assertEqual(self.inventory.reserved_quantity, 0)

    def test_cancel_already_delivered_order_raises_error(self):
        self.order.status = Order.OrderStatus.DELIVERED
        self.order.save(update_fields=['status'])

        with self.assertRaises(ValidationError):
            self.order.cancel(reason="Too late to cancel")


class OrderAddressModelTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            subtotal=Decimal('50000.00'),
            total_price=Decimal('50000.00'),
        )
        self.address = OrderAddress.objects.create(
            order=self.order,
            recipient_name='Jamshid Qodirov',
            phone_number='+998931234567',
            region='Samarqand',
            district='Pastdarg\'om',
            street_address='Guliston MFY 12-uy',
            apartment_office='2-etaj',
            postal_code='140100',
        )

    def test_full_address_property(self):
        full = self.address.full_address
        self.assertIn('Samarqand', full)
        self.assertIn('Pastdarg\'om', full)
        self.assertIn('Guliston MFY 12-uy', full)
        self.assertIn('Apt/Office: 2-etaj', full)
        self.assertIn('Postal Code: 140100', full)

    def test_order_address_str(self):
        self.assertIn('Jamshid Qodirov', str(self.address))
        self.assertIn('Samarqand', str(self.address))


class OrderItemModelTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            subtotal=Decimal('100000.00'),
            total_price=Decimal('100000.00'),
        )
        self.category = Category.objects.create(name='Shoes', slug='shoes')
        self.brand = Brand.objects.create(name='Nike', slug='nike')
        self.product = Product.objects.create(name='Nike Air', slug='nike-air', brand=self.brand)
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)
        self.variant = ProductVariant.objects.create(product=self.product, sku='NIKE-AIR-42', price=Decimal('50000.00'))

    def test_order_item_save_calculates_total_price(self):
        item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_sku=self.variant.sku,
            unit_price=Decimal('50000.00'),
            quantity=3,
        )
        self.assertEqual(item.total_price, Decimal('150000.00'))
        self.assertIn('Nike Air', str(item))
        self.assertIn('NIKE-AIR-42', str(item))

    def test_order_item_persists_when_variant_is_deleted(self):
        item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name='Nike Air Snapshot',
            variant_sku='NIKE-AIR-42',
            unit_price=Decimal('50000.00'),
            quantity=1,
        )
        # Delete catalog variant
        self.variant.delete()
        item.refresh_from_db()
        # Item must still exist with variant=None and preserved snapshots
        self.assertIsNone(item.variant)
        self.assertEqual(item.product_name, 'Nike Air Snapshot')
        self.assertEqual(item.variant_sku, 'NIKE-AIR-42')
        self.assertEqual(item.total_price, Decimal('50000.00'))


class CouponUsageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='user@coupon.com', password='Password123!')
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='ONCEONLY',
            discount_type=Coupon.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('25000.00'),
            usage_limit_per_user=1,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=5),
        )
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('100000.00'),
            discount_amount=Decimal('25000.00'),
            total_price=Decimal('75000.00'),
        )

    def test_coupon_usage_record_and_uniqueness(self):
        usage = CouponUsage.objects.create(
            coupon=self.coupon,
            user=self.user,
            order=self.order,
            discount_amount=Decimal('25000.00'),
        )
        self.assertIn('ONCEONLY', str(usage))
        self.assertIn(self.user.email, str(usage))

        # Check coupon validity for user is now False
        is_valid, msg = self.coupon.is_valid(user=self.user, subtotal=Decimal('100000.00'))
        self.assertFalse(is_valid)
        self.assertIn("already redeemed this coupon the maximum allowed times", msg)

        # UniqueConstraint on coupon and order prevents duplicate usage entry on same order
        with self.assertRaises(IntegrityError):
            CouponUsage.objects.create(
                coupon=self.coupon,
                user=self.user,
                order=self.order,
                discount_amount=Decimal('25000.00'),
            )
