from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.carts.models import Cart, CartItem
from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)
from apps.payments.models import Payment, PaymentTransaction, Refund, SavedCard
from apps.products.models import Brand, Category, Inventory, Product, ProductVariant
from apps.reviews.models import (
    ProductRatingSummary,
    Review,
    ReviewImage,
    ReviewReply,
    ReviewStatus,
    ReviewVote,
    VoteType,
)
from apps.users.models import OTPCode

User = get_user_model()


class FixtureLoadingTestCase(TestCase):
    """
    Test suite to verify that consolidated test fixtures (ecommerce_data.json)
    load cleanly into the test database and maintain 100% relational consistency.
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

    def test_orders_fixture_data(self):
        self.assertEqual(Coupon.objects.count(), 3)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(OrderAddress.objects.count(), 4)
        self.assertEqual(OrderItem.objects.count(), 4)
        self.assertEqual(OrderStatusHistory.objects.count(), 10)
        self.assertEqual(CouponUsage.objects.count(), 1)

        # Delivered order check
        order_1 = Order.objects.get(order_number='ORD-20261024-0001')
        self.assertEqual(order_1.status, Order.OrderStatus.DELIVERED)
        self.assertEqual(order_1.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order_1.user.email, 'john.doe@example.com')
        self.assertEqual(order_1.total_price, Decimal('2249.00'))
        self.assertEqual(order_1.shipping_address.region, 'Toshkent shahri')
        self.assertEqual(order_1.items.count(), 1)
        self.assertEqual(order_1.items.first().variant_sku, 'MBP16-M3-16-512-SG')

        # Coupon usage check
        coupon = Coupon.objects.get(code='SUMMER50')
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(CouponUsage.objects.filter(coupon=coupon).count(), 1)

    def test_payments_fixture_data(self):
        self.assertEqual(SavedCard.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 4)
        self.assertEqual(PaymentTransaction.objects.count(), 3)
        self.assertEqual(Refund.objects.count(), 1)

        # Successful payment check
        payment_1 = Payment.objects.get(payment_number='PAY-20261024-0001')
        self.assertEqual(payment_1.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(payment_1.provider, Payment.PaymentProvider.PAYME)
        self.assertEqual(payment_1.amount, Decimal('2249.00'))

        # Refunded payment check
        refund = Refund.objects.get(refund_number='REF-20261024-0001')
        self.assertEqual(refund.status, Refund.RefundStatus.COMPLETED)
        self.assertEqual(refund.amount, Decimal('2499.00'))
        self.assertEqual(refund.payment.status, Payment.PaymentStatus.REFUNDED)

    def test_notifications_fixture_data(self):
        self.assertEqual(NotificationTemplate.objects.count(), 3)
        self.assertEqual(NotificationPreference.objects.count(), 3)
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(EmailNotification.objects.count(), 3)

        # Template check
        template = NotificationTemplate.objects.get(code='ORDER_CONFIRMED')
        self.assertTrue(template.is_active)

        # User in-app notification check
        notif = Notification.objects.get(id=1)
        self.assertEqual(notif.user.email, 'john.doe@example.com')
        self.assertTrue(notif.is_read)

        # Sent email notification check
        email_notif = EmailNotification.objects.get(id=1)
        self.assertEqual(email_notif.status, EmailNotification.EmailStatus.SENT)
        self.assertEqual(email_notif.recipient_email, 'john.doe@example.com')

    def test_reviews_fixture_data(self):
        self.assertEqual(Review.objects.count(), 4)
        self.assertEqual(ReviewImage.objects.count(), 2)
        self.assertEqual(ReviewReply.objects.count(), 1)
        self.assertEqual(ReviewVote.objects.count(), 2)
        self.assertEqual(ProductRatingSummary.objects.count(), 3)

        # Approved verified purchase review check
        review_1 = Review.objects.get(id=1)
        self.assertEqual(review_1.status, ReviewStatus.APPROVED)
        self.assertTrue(review_1.is_verified_purchase)
        self.assertEqual(review_1.rating, 5)
        self.assertEqual(review_1.images.count(), 1)
        self.assertTrue(hasattr(review_1, 'reply'))
        self.assertEqual(review_1.votes.filter(vote_type=VoteType.HELPFUL).count(), 1)

        # Rating summary check
        summary = ProductRatingSummary.objects.get(product_id=1)
        self.assertEqual(summary.average_rating, Decimal('5.00'))
        self.assertEqual(summary.total_reviews, 1)


class ModularFixtureLoadingTestCase(TestCase):
    """
    Test suite to verify that all modular app-level fixtures can be loaded together seamlessly.
    """

    fixtures = [
        'users_data.json',
        'products_data.json',
        'carts_data.json',
        'orders_data.json',
        'payments_data.json',
        'notifications_data.json',
        'reviews_data.json',
    ]

    def test_all_modular_fixtures_loaded(self):
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(Cart.objects.count(), 4)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(Payment.objects.count(), 4)
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(Review.objects.count(), 4)
