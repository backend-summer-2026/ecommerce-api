from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from apps.carts.admin import (
    CartAdmin,
    CartAvailabilityFilter,
    CartHasItemsFilter,
    CartItemAdmin,
    CartItemInline,
    CartOwnerTypeFilter,
    get_product_thumbnail,
)
from apps.carts.models import Cart, CartItem
from apps.products.models import Brand, Category, Inventory, Product, ProductVariant

User = get_user_model()


class DummyAdminSite(AdminSite):
    pass


class CartAdminTestCase(TestCase):
    def setUp(self):
        self.site = DummyAdminSite()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='cartuser@example.com',
            password='Password123!',
            first_name='Ali',
            last_name='Valiyev',
            is_active=True,
        )
        self.brand = Brand.objects.create(name='Samsung', slug='samsung')
        self.category = Category.objects.create(name='Phones', slug='phones')
        self.product = Product.objects.create(
            name='Galaxy S24',
            slug='galaxy-s24',
            brand=self.brand,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            title='256GB Gray',
            sku='SAMS-S24-256-GRY',
            price=Decimal('10000000.00'),
            discount_price=Decimal('9000000.00'),
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=15,
            reserved_quantity=2,
        )

        self.cart_user = Cart.objects.create(
            user=self.user,
            status=Cart.CartStatus.OPEN,
        )
        self.cart_item = CartItem.objects.create(
            cart=self.cart_user,
            variant=self.variant,
            quantity=2,
            unit_price_at_addition=Decimal('9000000.00'),
        )

        self.cart_guest = Cart.objects.create(
            session_key='guest_session_key_123456789',
            status=Cart.CartStatus.ABANDONED,
        )

        self.cart_admin = CartAdmin(Cart, self.site)
        self.cart_item_admin = CartItemAdmin(CartItem, self.site)
        self.cart_item_inline = CartItemInline(Cart, self.site)

    def test_cart_admin_displays(self):
        # Test cart_id_display
        cart_id_html = self.cart_admin.cart_id_display(self.cart_user)
        self.assertIn(str(self.cart_user.id)[:8], cart_id_html)

        # Test customer_display for registered user
        customer_html = self.cart_admin.customer_display(self.cart_user)
        self.assertIn('cartuser@example.com', customer_html)
        self.assertIn('fa-user-circle', customer_html)

        # Test customer_display for guest
        guest_customer_html = self.cart_admin.customer_display(self.cart_guest)
        self.assertIn('Mehmon', guest_customer_html)
        self.assertIn('fa-user-secret', guest_customer_html)

        # Test status_badge for OPEN and ABANDONED
        status_open_html = self.cart_admin.status_badge(self.cart_user)
        self.assertIn('badge-success', status_open_html)
        self.assertIn('Ochiq', status_open_html)

        status_abandoned_html = self.cart_admin.status_badge(self.cart_guest)
        self.assertIn('badge-secondary', status_abandoned_html)
        self.assertIn('Tashlab ketilgan', status_abandoned_html)

        # Test total_items_display
        items_html = self.cart_admin.total_items_display(self.cart_user)
        self.assertIn('2 dona', items_html)

        empty_items_html = self.cart_admin.total_items_display(self.cart_guest)
        self.assertIn('Bo\'sh', empty_items_html)

        # Test unique_items_display
        unique_html = self.cart_admin.unique_items_display(self.cart_user)
        self.assertIn('1 xil tovar', unique_html)

        # Test total_price_display, subtotal_display, total_discount_display
        total_price_html = self.cart_admin.total_price_display(self.cart_user)
        self.assertIn('18,000,000.00', total_price_html)

        subtotal_html = self.cart_admin.subtotal_display(self.cart_user)
        self.assertIn('20,000,000.00', subtotal_html)

        discount_html = self.cart_admin.total_discount_display(self.cart_user)
        self.assertIn('2,000,000.00', discount_html)

        # Test availability_badge
        avail_html = self.cart_admin.availability_badge(self.cart_user)
        self.assertIn('Barchasi mavjud', avail_html)

        empty_avail_html = self.cart_admin.availability_badge(self.cart_guest)
        self.assertIn('—', empty_avail_html)

    def test_cart_admin_queryset_optimization(self):
        request = self.factory.get('/admin/carts/cart/')
        request.user = self.user
        qs = self.cart_admin.get_queryset(request)
        cart = qs.get(id=self.cart_user.id)
        self.assertEqual(cart._total_qty, 2)
        self.assertEqual(cart._items_count, 1)

    def test_cart_admin_actions(self):
        request = self.factory.post('/admin/carts/cart/')
        request.user = self.user
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # Test mark_as_abandoned
        self.cart_admin.mark_as_abandoned(request, Cart.objects.filter(id=self.cart_user.id))
        self.cart_user.refresh_from_db()
        self.assertEqual(self.cart_user.status, Cart.CartStatus.ABANDONED)

        # Test mark_as_open
        self.cart_admin.mark_as_open(request, Cart.objects.filter(id=self.cart_user.id))
        self.cart_user.refresh_from_db()
        self.assertEqual(self.cart_user.status, Cart.CartStatus.OPEN)

        # Test clear_empty_carts
        empty_cart_id = self.cart_guest.id
        self.cart_admin.clear_empty_carts(request, Cart.objects.filter(id=empty_cart_id))
        self.assertFalse(Cart.objects.filter(id=empty_cart_id).exists())

    def test_cart_filters(self):
        request = self.factory.get('/admin/carts/cart/')
        request.user = self.user

        # Test CartOwnerTypeFilter
        filter_reg = CartOwnerTypeFilter(request, {'owner_type': ['registered']}, Cart, self.cart_admin)
        qs_reg = filter_reg.queryset(request, Cart.objects.all())
        self.assertIn(self.cart_user, qs_reg)
        self.assertNotIn(self.cart_guest, qs_reg)

        filter_guest = CartOwnerTypeFilter(request, {'owner_type': ['guest']}, Cart, self.cart_admin)
        qs_guest = filter_guest.queryset(request, Cart.objects.all())
        self.assertIn(self.cart_guest, qs_guest)
        self.assertNotIn(self.cart_user, qs_guest)

        # Test CartHasItemsFilter
        filter_items = CartHasItemsFilter(request, {'has_items': ['with_items']}, Cart, self.cart_admin)
        qs_items = filter_items.queryset(request, Cart.objects.all())
        self.assertIn(self.cart_user, qs_items)
        self.assertNotIn(self.cart_guest, qs_items)

        filter_empty = CartHasItemsFilter(request, {'has_items': ['empty']}, Cart, self.cart_admin)
        qs_empty = filter_empty.queryset(request, Cart.objects.all())
        self.assertIn(self.cart_guest, qs_empty)
        self.assertNotIn(self.cart_user, qs_empty)

        # Test CartAvailabilityFilter
        filter_avail = CartAvailabilityFilter(request, {'stock_status': ['available']}, Cart, self.cart_admin)
        qs_avail = filter_avail.queryset(request, Cart.objects.all())
        self.assertIn(self.cart_user, qs_avail)

    def test_cart_item_inline_and_admin(self):
        # Test thumbnail placeholder
        thumb_html = get_product_thumbnail(self.variant)
        self.assertIn('fa-box', thumb_html)

        # Test CartItemInline display methods
        unit_price_html = self.cart_item_inline.unit_price_at_addition_display(self.cart_item)
        self.assertIn('9,000,000.00', unit_price_html)

        current_price_html = self.cart_item_inline.current_price_display(self.cart_item)
        self.assertIn('9,000,000.00', current_price_html)

        price_status_html = self.cart_item_inline.price_status_display(self.cart_item)
        self.assertIn('O\'zgarmagan', price_status_html)

        total_price_html = self.cart_item_inline.total_price_display(self.cart_item)
        self.assertIn('18,000,000.00', total_price_html)

        stock_html = self.cart_item_inline.stock_status_display(self.cart_item)
        self.assertIn('Mavjud', stock_html)
        self.assertIn('13 dona', stock_html)

        # Test CartItemAdmin display methods
        cart_link_html = self.cart_item_admin.cart_link(self.cart_item)
        self.assertIn(str(self.cart_user.id)[:8], cart_link_html)
        self.assertIn('cartuser@example.com', cart_link_html)

        variant_display_html = self.cart_item_admin.variant_display(self.cart_item)
        self.assertIn('Galaxy S24', variant_display_html)
        self.assertIn('SAMS-S24-256-GRY', variant_display_html)

        # Test price changed condition
        self.variant.discount_price = Decimal('8500000.00')
        self.variant.save()
        changed_status_html = self.cart_item_admin.price_status_display(self.cart_item)
        self.assertIn('badge-warning', changed_status_html)
        self.assertIn('-500,000.00 UZS', changed_status_html)
