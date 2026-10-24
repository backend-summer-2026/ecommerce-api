from decimal import Decimal
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.orders.admin import (
    CouponAdmin,
    CouponUsageAdmin,
    OrderAddressInline,
    OrderAdmin,
    OrderItemInline,
    OrderStatusHistoryInline,
    order_status_badge,
    payment_method_badge,
    payment_status_badge,
    shipping_method_badge,
)
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.products.models import Brand, Category, Inventory, Product, ProductVariant

User = get_user_model()


class DummyAdminSite(AdminSite):
    pass


class OrderAdminTestCase(TestCase):
    def setUp(self):
        self.site = DummyAdminSite()
        self.factory = RequestFactory()

        # Users
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='User',
        )
        self.customer = User.objects.create_user(
            email='customer@example.com',
            password='CustomerPassword123!',
            first_name='Anvar',
            last_name='Qodirov',
            phone_number='+998901234567',
        )

        # Products & Variants
        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.category = Category.objects.create(name='Smartphones', slug='smartphones')
        self.product = Product.objects.create(
            name='iPhone 15 Pro',
            slug='iphone-15-pro',
            brand=self.brand,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title='128GB Black Titanium',
            sku='IPH15P-128-BLK',
            price=Decimal('12000000.00'),
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=20,
            reserved_quantity=2,
        )

        # Coupon
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='SUPERPROMO10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('100000.00'),
            max_discount_amount=Decimal('500000.00'),
            usage_limit=100,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            is_active=True,
        )

        # Order with Customer
        self.order = Order.objects.create(
            user=self.customer,
            coupon=self.coupon,
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            payment_method=Order.PaymentMethod.PAYME,
            shipping_method=Order.ShippingMethod.STANDARD,
            subtotal=Decimal('12000000.00'),
            shipping_fee=Decimal('30000.00'),
            discount_amount=Decimal('500000.00'),
            total_price=Decimal('11530000.00'),
            currency='UZS',
            tracking_number='TRK-987654321',
        )

        # Order Address
        self.address = OrderAddress.objects.create(
            order=self.order,
            recipient_name='Anvar Qodirov',
            phone_number='+998901234567',
            region='Toshkent',
            district='Yunusobod',
            street_address='Amir Temur ko\'chasi, 12-uy',
            latitude=Decimal('41.311081'),
            longitude=Decimal('69.240562'),
        )

        # Order Item
        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name='iPhone 15 Pro',
            variant_sku='IPH15P-128-BLK',
            unit_price=Decimal('12000000.00'),
            quantity=1,
            total_price=Decimal('12000000.00'),
        )

        # Order Status History
        self.status_history = OrderStatusHistory.objects.create(
            order=self.order,
            old_status=None,
            new_status=Order.OrderStatus.PENDING,
            comment='Buyurtma yaratildi',
            created_by=None,
            is_customer_visible=True,
        )

        # Guest Order
        self.guest_order = Order.objects.create(
            user=None,
            status=Order.OrderStatus.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.UZUM,
            shipping_method=Order.ShippingMethod.EXPRESS,
            subtotal=Decimal('500000.00'),
            shipping_fee=Decimal('50000.00'),
            total_price=Decimal('550000.00'),
            currency='UZS',
        )
        self.guest_address = OrderAddress.objects.create(
            order=self.guest_order,
            recipient_name='Vali Aliyev',
            phone_number='+998911112233',
            region='Samarqand',
            district='Markaz',
            street_address='Registon ko\'chasi, 1-uy',
        )

        # Coupon Usage
        self.coupon_usage = CouponUsage.objects.create(
            coupon=self.coupon,
            user=self.customer,
            order=self.order,
            discount_amount=Decimal('500000.00'),
        )

        # Admin instances
        self.order_admin = OrderAdmin(Order, self.site)
        self.coupon_admin = CouponAdmin(Coupon, self.site)
        self.coupon_usage_admin = CouponUsageAdmin(CouponUsage, self.site)
        self.order_item_inline = OrderItemInline(Order, self.site)
        self.order_address_inline = OrderAddressInline(Order, self.site)
        self.history_inline = OrderStatusHistoryInline(Order, self.site)

    def _get_request_with_messages(self, user=None):
        request = self.factory.get('/admin/orders/order/')
        request.user = user or self.admin_user
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_badge_helpers(self):
        # Order Status Badge
        badge_html = order_status_badge(Order.OrderStatus.PENDING)
        self.assertIn('badge-warning', badge_html)
        self.assertIn('fa-clock', badge_html)

        badge_confirmed = order_status_badge(Order.OrderStatus.CONFIRMED)
        self.assertIn('badge-primary', badge_confirmed)

        badge_delivered = order_status_badge(Order.OrderStatus.DELIVERED)
        self.assertIn('badge-success', badge_delivered)

        badge_cancelled = order_status_badge(Order.OrderStatus.CANCELLED)
        self.assertIn('badge-danger', badge_cancelled)

        # Payment Status Badge
        pay_paid = payment_status_badge(Order.PaymentStatus.PAID)
        self.assertIn('badge-success', pay_paid)

        pay_failed = payment_status_badge(Order.PaymentStatus.FAILED)
        self.assertIn('badge-danger', pay_failed)

        # Payment Method Badge
        method_payme = payment_method_badge(Order.PaymentMethod.PAYME)
        self.assertIn('badge-info', method_payme)

        method_uzum = payment_method_badge(Order.PaymentMethod.UZUM)
        self.assertIn('Uzum Bank', method_uzum)

        # Shipping Method Badge
        ship_standard = shipping_method_badge(Order.ShippingMethod.STANDARD)
        self.assertIn('fa-truck', ship_standard)

        ship_express = shipping_method_badge(Order.ShippingMethod.EXPRESS)
        self.assertIn('fa-bolt', ship_express)

    def test_order_admin_displays(self):
        # order_number_display
        num_html = self.order_admin.order_number_display(self.order)
        self.assertIn(self.order.order_number, num_html)
        self.assertIn('fa-shopping-bag', num_html)

        # customer_display (registered user)
        cust_html = self.order_admin.customer_display(self.order)
        self.assertIn('Anvar Qodirov', cust_html)
        self.assertIn('fa-user-circle', cust_html)

        # customer_display (guest order)
        guest_html = self.order_admin.customer_display(self.guest_order)
        self.assertIn('Mehmon (Vali Aliyev)', guest_html)
        self.assertIn('fa-user-secret', guest_html)

        # Links
        cust_link = self.order_admin.customer_link(self.order)
        self.assertIn(self.customer.email, cust_link)

        coupon_link = self.order_admin.coupon_link(self.order)
        self.assertIn('SUPERPROMO10', coupon_link)

        # Badges on admin
        status_html = self.order_admin.status_badge(self.order)
        self.assertIn('badge-warning', status_html)

        payment_html = self.order_admin.payment_status_badge(self.order)
        self.assertIn('badge-warning', payment_html)

        method_html = self.order_admin.payment_method_badge(self.order)
        self.assertIn('Payme', method_html)

        ship_html = self.order_admin.shipping_method_badge(self.order)
        self.assertIn('Standart', ship_html)

        # Financials & Totals
        items_html = self.order_admin.total_items_display(self.order)
        self.assertIn('1 ta', items_html)

        subtotal_html = self.order_admin.subtotal_display(self.order)
        self.assertIn('12,000,000.00 UZS', subtotal_html)

        total_html = self.order_admin.total_price_display(self.order)
        self.assertIn('11,530,000.00', total_html)

    def test_order_admin_actions(self):
        request = self._get_request_with_messages()

        # 1. mark_as_confirmed
        qs = Order.objects.filter(id=self.order.id)
        self.order_admin.mark_as_confirmed(request, qs)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)

        # 2. mark_as_processing
        self.order_admin.mark_as_processing(request, qs)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PROCESSING)

        # 3. mark_as_shipped
        self.order_admin.mark_as_shipped(request, qs)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.SHIPPED)

        # 4. mark_as_delivered
        self.order_admin.mark_as_delivered(request, qs)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.DELIVERED)

        # 5. mark_as_paid
        self.order_admin.mark_as_paid(request, qs)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(self.order.paid_at)

        # 6. cancel_orders on a cancellable order
        new_order = Order.objects.create(
            user=self.customer,
            status=Order.OrderStatus.PENDING,
            total_price=Decimal('100000.00'),
        )
        self.order_admin.cancel_orders(request, Order.objects.filter(id=new_order.id))
        new_order.refresh_from_db()
        self.assertEqual(new_order.status, Order.OrderStatus.CANCELLED)

    def test_inlines_displays(self):
        # OrderItemInline
        variant_link = self.order_item_inline.variant_link(self.order_item)
        self.assertIn('IPH15P-128-BLK', variant_link)

        unit_price = self.order_item_inline.unit_price_display(self.order_item)
        self.assertIn('12,000,000.00 UZS', unit_price)

        total_price = self.order_item_inline.total_price_display(self.order_item)
        self.assertIn('12,000,000.00 UZS', total_price)

        # OrderAddressInline
        phone_html = self.order_address_inline.phone_link(self.address)
        self.assertIn('tel:+998901234567', phone_html)

        map_html = self.order_address_inline.map_link(self.address)
        self.assertIn('Google Maps', map_html)
        self.assertIn('Yandex Maps', map_html)

        # OrderStatusHistoryInline
        old_status = self.history_inline.old_status_badge(self.status_history)
        self.assertIn('Boshlang\'ich', old_status)

        new_status = self.history_inline.new_status_badge(self.status_history)
        self.assertIn('badge-warning', new_status)

        arrow = self.history_inline.arrow_icon(self.status_history)
        self.assertIn('fa-arrow-right', arrow)

        created_by_sys = self.history_inline.created_by_display(self.status_history)
        self.assertIn('Tizim (Avtomatik)', created_by_sys)

        self.assertFalse(self.history_inline.has_add_permission(None))

    def test_coupon_admin(self):
        request = self._get_request_with_messages()

        # code_display
        code_html = self.coupon_admin.code_display(self.coupon)
        self.assertIn('SUPERPROMO10', code_html)

        # discount_display
        disc_html = self.coupon_admin.discount_display(self.coupon)
        self.assertIn('10.00%', disc_html)

        # min_order_amount_display
        min_html = self.coupon_admin.min_order_amount_display(self.coupon)
        self.assertIn('100,000.00 UZS', min_html)

        # usage_display & usage_progress
        usage_html = self.coupon_admin.usage_display(self.coupon)
        self.assertIn('0 / 100', usage_html)

        progress_html = self.coupon_admin.usage_progress(self.coupon)
        self.assertIn('progress-bar', progress_html)

        # validity_display & is_active_badge
        valid_html = self.coupon_admin.validity_display(self.coupon)
        self.assertIn('Aktiv', valid_html)

        active_html = self.coupon_admin.is_active_badge(self.coupon)
        self.assertIn('Faol', active_html)

        # Actions: deactivate and activate
        qs = Coupon.objects.filter(id=self.coupon.id)
        self.coupon_admin.deactivate_coupons(request, qs)
        self.coupon.refresh_from_db()
        self.assertFalse(self.coupon.is_active)

        self.coupon_admin.activate_coupons(request, qs)
        self.coupon.refresh_from_db()
        self.assertTrue(self.coupon.is_active)

    def test_coupon_usage_admin(self):
        # coupon_link
        c_link = self.coupon_usage_admin.coupon_link(self.coupon_usage)
        self.assertIn('SUPERPROMO10', c_link)

        # user_link
        u_link = self.coupon_usage_admin.user_link(self.coupon_usage)
        self.assertIn(self.customer.email, u_link)

        # order_link
        o_link = self.coupon_usage_admin.order_link(self.coupon_usage)
        self.assertIn(self.order.order_number, o_link)

        # discount_amount_display
        d_display = self.coupon_usage_admin.discount_amount_display(self.coupon_usage)
        self.assertIn('+500,000.00 UZS', d_display)

        # has_add_permission is False
        self.assertFalse(self.coupon_usage_admin.has_add_permission(None))
