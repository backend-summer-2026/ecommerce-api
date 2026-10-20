from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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
    ProductVariantAttributeValue,
)


class CategoryModelTests(TestCase):
    """
    Tests for Category model hierarchy, slugs, and methods.
    """

    def test_category_creation_and_full_path(self):
        root = Category.objects.create(name='Electronics', slug='electronics')
        sub = Category.objects.create(name='Computers', slug='computers', parent=root)
        leaf = Category.objects.create(name='Laptops', slug='laptops', parent=sub)

        self.assertEqual(root.get_full_path(), 'Electronics')
        self.assertEqual(sub.get_full_path(), 'Electronics > Computers')
        self.assertEqual(leaf.get_full_path(), 'Electronics > Computers > Laptops')
        self.assertEqual(str(leaf), 'Electronics > Computers > Laptops')

    def test_category_slug_uniqueness(self):
        Category.objects.create(name='Smartphones', slug='smartphones')
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='Another Smartphones', slug='smartphones')


class BrandModelTests(TestCase):
    """
    Tests for Brand model.
    """

    def test_brand_creation_and_str(self):
        brand = Brand.objects.create(
            name='Apple',
            slug='apple',
            website='https://apple.com',
            description='Apple Inc. electronics',
        )
        self.assertEqual(str(brand), 'Apple')
        self.assertTrue(brand.is_active)

    def test_brand_name_uniqueness(self):
        Brand.objects.create(name='Samsung', slug='samsung')
        with self.assertRaises(IntegrityError):
            Brand.objects.create(name='Samsung', slug='samsung-new')


class ProductModelTests(TestCase):
    """
    Tests for Product model and ProductCategory relationship.
    """

    def setUp(self):
        self.brand = Brand.objects.create(name='Sony', slug='sony')
        self.root_cat = Category.objects.create(name='Audio', slug='audio')
        self.sub_cat = Category.objects.create(name='Headphones', slug='headphones', parent=self.root_cat)

    def test_product_creation_and_categories(self):
        product = Product.objects.create(
            name='Sony WH-1000XM5',
            slug='sony-wh-1000xm5',
            brand=self.brand,
            description='Noise cancelling wireless headphones',
        )
        ProductCategory.objects.create(product=product, category=self.root_cat, is_primary=False)
        ProductCategory.objects.create(product=product, category=self.sub_cat, is_primary=True)

        self.assertEqual(str(product), 'Sony WH-1000XM5')
        self.assertEqual(product.categories.count(), 2)

        primary_cat = product.product_categories.filter(is_primary=True).first()
        self.assertIsNotNone(primary_cat)
        self.assertEqual(primary_cat.category, self.sub_cat)

    def test_product_category_unique_constraint(self):
        product = Product.objects.create(
            name='Sony WH-1000XM5',
            slug='sony-wh-1000xm5',
            brand=self.brand,
        )
        ProductCategory.objects.create(product=product, category=self.sub_cat, is_primary=True)
        with self.assertRaises(IntegrityError):
            ProductCategory.objects.create(product=product, category=self.sub_cat, is_primary=False)


class ProductVariantModelTests(TestCase):
    """
    Tests for ProductVariant price calculations and properties.
    """

    def setUp(self):
        self.product = Product.objects.create(name='MacBook Pro 16', slug='macbook-pro-16')

    def test_variant_final_price_without_discount(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            title='16GB / 512GB',
            sku='MBP16-16-512',
            price=Decimal('2499.00'),
            discount_price=None,
        )
        self.assertEqual(variant.final_price, Decimal('2499.00'))
        self.assertFalse(variant.is_on_sale)

    def test_variant_final_price_with_valid_discount(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            title='32GB / 1TB',
            sku='MBP16-32-1TB',
            price=Decimal('3199.00'),
            discount_price=Decimal('2899.00'),
        )
        self.assertEqual(variant.final_price, Decimal('2899.00'))
        self.assertTrue(variant.is_on_sale)

    def test_variant_final_price_with_invalid_higher_discount(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            title='64GB / 2TB',
            sku='MBP16-64-2TB',
            price=Decimal('3999.00'),
            discount_price=Decimal('4500.00'),
        )
        self.assertEqual(variant.final_price, Decimal('3999.00'))
        self.assertFalse(variant.is_on_sale)

    def test_variant_sku_uniqueness(self):
        ProductVariant.objects.create(
            product=self.product,
            sku='UNIQUE-SKU-001',
            price=Decimal('100.00'),
        )
        with self.assertRaises(IntegrityError):
            ProductVariant.objects.create(
                product=self.product,
                sku='UNIQUE-SKU-001',
                price=Decimal('120.00'),
            )


class ProductMediaModelTests(TestCase):
    """
    Tests for ProductMedia ordering and relations.
    """

    def setUp(self):
        self.product = Product.objects.create(name='iPhone 15', slug='iphone-15')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='IPHONE15-128-BLK',
            price=Decimal('899.00'),
        )

    def test_product_media_ordering(self):
        m1 = ProductMedia.objects.create(
            product=self.product,
            file='products/test1.jpg',
            order=2,
            is_main=False,
        )
        m2 = ProductMedia.objects.create(
            product=self.product,
            file='products/test2.jpg',
            order=1,
            is_main=False,
        )
        m3 = ProductMedia.objects.create(
            product=self.product,
            file='products/test3.jpg',
            order=1,
            is_main=True,
        )

        media_list = list(self.product.media.all())
        # Expected ordering: order asc, -is_main, id
        # Order 1 main first, then Order 1 non-main, then Order 2
        self.assertEqual(media_list[0], m3)
        self.assertEqual(media_list[1], m2)
        self.assertEqual(media_list[2], m1)


class DynamicAttributeModelTests(TestCase):
    """
    Tests for Attribute, AttributeValue, and ProductVariantAttributeValue (EAV).
    """

    def setUp(self):
        self.product = Product.objects.create(name='T-Shirt', slug='t-shirt')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='TSHIRT-RED-M',
            price=Decimal('19.99'),
        )

    def test_attribute_and_values(self):
        color_attr = Attribute.objects.create(name='Color', slug='color')
        red_val = AttributeValue.objects.create(attribute=color_attr, value='Red', slug='red')
        blue_val = AttributeValue.objects.create(attribute=color_attr, value='Blue', slug='blue')

        self.assertEqual(str(color_attr), 'Color')
        self.assertEqual(str(red_val), 'Color: Red')
        self.assertEqual(color_attr.values.count(), 2)

        # Test attribute value uniqueness per attribute
        with self.assertRaises(IntegrityError):
            AttributeValue.objects.create(attribute=color_attr, value='Red', slug='red-duplicate')

    def test_variant_attribute_assignment(self):
        color_attr = Attribute.objects.create(name='Color', slug='color')
        red_val = AttributeValue.objects.create(attribute=color_attr, value='Red', slug='red')

        p_attr = ProductVariantAttributeValue.objects.create(
            variant=self.variant,
            attribute_value=red_val,
        )
        self.assertIn(red_val, self.variant.attributes.all())

        # Test duplicate assignment prevention
        with self.assertRaises(IntegrityError):
            ProductVariantAttributeValue.objects.create(
                variant=self.variant,
                attribute_value=red_val,
            )


class InventoryModelTests(TestCase):
    """
    Tests for Inventory stock reservation, deduction, and availability.
    """

    def setUp(self):
        self.product = Product.objects.create(name='Sneakers', slug='sneakers')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='SNK-42-BLK',
            price=Decimal('89.00'),
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=20,
            reserved_quantity=5,
            low_stock_threshold=5,
        )

    def test_available_quantity_and_stock_status(self):
        self.assertEqual(self.inventory.available_quantity, 15)
        self.assertTrue(self.inventory.is_in_stock)
        self.assertFalse(self.inventory.is_low_stock)

    def test_low_stock_status(self):
        self.inventory.quantity = 7
        self.inventory.reserved_quantity = 3
        self.inventory.save()
        # available: 4, threshold: 5 -> is_low_stock = True
        self.assertEqual(self.inventory.available_quantity, 4)
        self.assertTrue(self.inventory.is_in_stock)
        self.assertTrue(self.inventory.is_low_stock)

    def test_out_of_stock_status(self):
        self.inventory.quantity = 5
        self.inventory.reserved_quantity = 5
        self.inventory.save()
        self.assertEqual(self.inventory.available_quantity, 0)
        self.assertFalse(self.inventory.is_in_stock)
        self.assertFalse(self.inventory.is_low_stock)

    def test_reserve_success(self):
        self.inventory.reserve(10)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, 15)
        self.assertEqual(self.inventory.available_quantity, 5)

    def test_reserve_insufficient_stock_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.reserve(16)  # only 15 available

    def test_reserve_invalid_amount_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.reserve(0)
        with self.assertRaises(ValidationError):
            self.inventory.reserve(-5)

    def test_release_success(self):
        self.inventory.release(3)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.reserved_quantity, 2)
        self.assertEqual(self.inventory.available_quantity, 18)

    def test_release_exceeding_reserved_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.release(6)  # only 5 reserved

    def test_release_invalid_amount_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.release(0)
        with self.assertRaises(ValidationError):
            self.inventory.release(-2)

    def test_deduct_success(self):
        # 20 total, 5 reserved -> deduct 5 reserved items
        self.inventory.deduct(5)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 15)
        self.assertEqual(self.inventory.reserved_quantity, 0)
        self.assertEqual(self.inventory.available_quantity, 15)

    def test_deduct_more_than_reserved(self):
        # 20 total, 5 reserved -> deduct 8
        self.inventory.deduct(8)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 12)
        self.assertEqual(self.inventory.reserved_quantity, 0)
        self.assertEqual(self.inventory.available_quantity, 12)

    def test_deduct_exceeding_total_stock_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.deduct(21)  # only 20 total

    def test_deduct_invalid_amount_raises_error(self):
        with self.assertRaises(ValidationError):
            self.inventory.deduct(0)
        with self.assertRaises(ValidationError):
            self.inventory.deduct(-1)
