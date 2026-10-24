from decimal import Decimal
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.products.admin import (
    AttributeAdmin,
    AttributeValueAdmin,
    BrandAdmin,
    CategoryAdmin,
    InventoryAdmin,
    InventoryInline,
    ProductAdmin,
    ProductMediaInline,
    ProductVariantAdmin,
    StockStatusFilter,
    render_image_thumbnail,
    render_status_pill,
    render_stock_badge,
)
from apps.products.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Inventory,
    Product,
    ProductCategory,
    ProductMedia,
    ProductVariant,
)
from apps.users.models import User


class DummyAdminSite(AdminSite):
    pass


class ProductsAdminHelpersTest(TestCase):
    def test_render_image_thumbnail_empty(self):
        html = render_image_thumbnail(None, default_icon='fa-box')
        self.assertIn('<i class="fas fa-box"></i>', html)

    def test_render_stock_badge(self):
        out_of_stock = render_stock_badge(0, 5)
        self.assertIn('badge-danger', out_of_stock)
        self.assertIn('Tugagan', out_of_stock)

        low_stock = render_stock_badge(3, 5)
        self.assertIn('badge-warning', low_stock)
        self.assertIn('Oz qoldi', low_stock)

        in_stock = render_stock_badge(15, 5)
        self.assertIn('badge-success', in_stock)
        self.assertIn('Mavjud', in_stock)

    def test_render_status_pill(self):
        active = render_status_pill(True)
        self.assertIn('badge-success', active)
        self.assertIn('Faol', active)

        inactive = render_status_pill(False)
        self.assertIn('badge-secondary', inactive)
        self.assertIn('Nofaol', inactive)


class ProductsAdminTestCase(TestCase):
    def setUp(self):
        self.site = DummyAdminSite()
        self.factory = RequestFactory()
        self.request = self.factory.get('/admin/')
        # Set up session and message middleware emulation for RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(self.request, 'session', 'test_session')
        messages = FallbackStorage(self.request)
        setattr(self.request, '_messages', messages)

        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='testpassword123',
        )
        self.request.user = self.admin_user

        # Create base test data
        self.brand = Brand.objects.create(
            name='Apple',
            slug='apple',
            website='https://apple.com',
            is_active=True,
        )
        self.parent_cat = Category.objects.create(
            name='Elektronika',
            slug='elektronika',
            is_active=True,
        )
        self.child_cat = Category.objects.create(
            name='Smartfonlar',
            slug='smartfonlar',
            parent=self.parent_cat,
            is_active=True,
        )
        self.product = Product.objects.create(
            name='iPhone 15 Pro',
            slug='iphone-15-pro',
            brand=self.brand,
            short_description='Flagship phone',
            description='Detailed description',
            is_active=True,
        )
        ProductCategory.objects.create(
            product=self.product,
            category=self.child_cat,
            is_primary=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='IPH15P-128',
            title='128GB Titanium',
            price=Decimal('999.00'),
            discount_price=Decimal('899.00'),
            is_default=True,
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=20,
            reserved_quantity=2,
            low_stock_threshold=5,
        )
        self.media = ProductMedia.objects.create(
            product=self.product,
            media_type=ProductMedia.MediaType.IMAGE,
            is_main=True,
            order=0,
        )
        self.attr = Attribute.objects.create(name='Rang', slug='rang')
        self.attr_val = AttributeValue.objects.create(
            attribute=self.attr,
            value='Qora',
            slug='qora',
        )

    def test_category_admin(self):
        admin_instance = CategoryAdmin(Category, self.site)
        qs = admin_instance.get_queryset(self.request)
        self.assertTrue(qs.filter(pk=self.child_cat.pk).exists())

        img_prev = admin_instance.image_preview(self.child_cat)
        self.assertIn('<span', img_prev)

        count_badge = admin_instance.display_products_count(qs.get(pk=self.child_cat.pk))
        self.assertIn('1 ta', count_badge)

        # Test actions
        admin_instance.mark_inactive(self.request, Category.objects.filter(pk=self.child_cat.pk))
        self.child_cat.refresh_from_db()
        self.assertFalse(self.child_cat.is_active)

        admin_instance.mark_active(self.request, Category.objects.filter(pk=self.child_cat.pk))
        self.child_cat.refresh_from_db()
        self.assertTrue(self.child_cat.is_active)

    def test_brand_admin(self):
        admin_instance = BrandAdmin(Brand, self.site)
        qs = admin_instance.get_queryset(self.request)
        brand_obj = qs.get(pk=self.brand.pk)

        self.assertIn('apple.com', admin_instance.website_button(brand_obj))
        self.assertIn('1 ta', admin_instance.display_products_count(brand_obj))
        self.assertIn('<span', admin_instance.logo_preview(brand_obj))

        # Test actions
        admin_instance.mark_inactive(self.request, Brand.objects.filter(pk=self.brand.pk))
        self.brand.refresh_from_db()
        self.assertFalse(self.brand.is_active)

        admin_instance.mark_active(self.request, Brand.objects.filter(pk=self.brand.pk))
        self.brand.refresh_from_db()
        self.assertTrue(self.brand.is_active)

    def test_product_admin(self):
        admin_instance = ProductAdmin(Product, self.site)
        qs = admin_instance.get_queryset(self.request)
        prod = qs.get(pk=self.product.pk)

        # Previews and badges
        self.assertIn('<span', admin_instance.thumbnail_preview(prod))
        self.assertIn('Smartfonlar', admin_instance.categories_badges(prod))
        self.assertIn('$899.00', admin_instance.price_range_display(prod))
        self.assertIn('1 ta', admin_instance.variants_count_badge(prod))
        self.assertIn('Mavjud (18)', admin_instance.stock_summary_badge(prod))

        # Test actions
        admin_instance.mark_inactive(self.request, Product.objects.filter(pk=self.product.pk))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

        admin_instance.mark_active(self.request, Product.objects.filter(pk=self.product.pk))
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_product_variant_admin(self):
        admin_instance = ProductVariantAdmin(ProductVariant, self.site)
        qs = admin_instance.get_queryset(self.request)
        variant = qs.get(pk=self.variant.pk)

        self.assertIn('iPhone 15 Pro', admin_instance.product_link(variant))
        self.assertIn('$999.00', admin_instance.formatted_price(variant))
        self.assertIn('$899.00', admin_instance.display_final_price(variant))
        self.assertIn('-10%', admin_instance.display_final_price(variant))
        self.assertIn('Mavjud (18)', admin_instance.display_stock_status(variant))

        # Test actions
        admin_instance.mark_inactive(self.request, ProductVariant.objects.filter(pk=self.variant.pk))
        self.variant.refresh_from_db()
        self.assertFalse(self.variant.is_active)

        admin_instance.mark_active(self.request, ProductVariant.objects.filter(pk=self.variant.pk))
        self.variant.refresh_from_db()
        self.assertTrue(self.variant.is_active)

    def test_inventory_admin(self):
        admin_instance = InventoryAdmin(Inventory, self.site)
        qs = admin_instance.get_queryset(self.request)
        inv = qs.get(pk=self.inventory.pk)

        self.assertIn('iPhone 15 Pro', admin_instance.product_name(inv))
        self.assertIn('18 dona', admin_instance.display_available_quantity(inv))
        self.assertIn('Mavjud (18)', admin_instance.display_status(inv))

        # Test reset_reserved_quantity action
        admin_instance.reset_reserved_quantity(self.request, Inventory.objects.filter(pk=self.inventory.pk))
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, 0)

    def test_stock_status_filter(self):
        class DummyModelAdmin:
            pass

        filt = StockStatusFilter(
            self.request,
            {'stock_status': ['in_stock']},
            Inventory,
            DummyModelAdmin(),
        )
        qs = filt.queryset(self.request, Inventory.objects.filter(pk=self.inventory.pk))
        self.assertEqual(qs.count(), 1)

        filt_out = StockStatusFilter(
            self.request,
            {'stock_status': ['out_of_stock']},
            Inventory,
            DummyModelAdmin(),
        )
        qs_out = filt_out.queryset(self.request, Inventory.objects.filter(pk=self.inventory.pk))
        self.assertEqual(qs_out.count(), 0)

    def test_attribute_admin(self):
        attr_admin = AttributeAdmin(Attribute, self.site)
        qs = attr_admin.get_queryset(self.request)
        attr_obj = qs.get(pk=self.attr.pk)

        self.assertIn('Qora', attr_admin.display_values_badges(attr_obj))
        self.assertIn('1 ta', attr_admin.display_values_count(attr_obj))

        val_admin = AttributeValueAdmin(AttributeValue, self.site)
        self.assertIn('Rang', val_admin.attribute_badge(self.attr_val))

    def test_inline_previews(self):
        inline = ProductMediaInline(Product, self.site)
        preview = inline.media_preview(self.media)
        self.assertIn('<span', preview)

        inv_inline = InventoryInline(ProductVariant, self.site)
        avail = inv_inline.display_available_quantity(self.inventory)
        self.assertIn('18 dona', avail)
        health = inv_inline.display_stock_health(self.inventory)
        self.assertIn('Mavjud (18)', health)
