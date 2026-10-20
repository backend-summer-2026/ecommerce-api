from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

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


class CatalogAPITestCase(TestCase):
    """
    Test suite for all 10 Product Catalog REST API endpoints.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Setup Categories hierarchy
        self.cat_electronics = Category.objects.create(
            name="Electronics",
            slug="electronics",
        )
        self.cat_computers = Category.objects.create(
            name="Computers",
            slug="computers",
            parent=self.cat_electronics,
        )
        self.cat_laptops = Category.objects.create(
            name="Laptops",
            slug="laptops",
            parent=self.cat_computers,
        )
        self.cat_clothing = Category.objects.create(
            name="Clothing",
            slug="clothing",
        )

        # 2. Setup Brands
        self.brand_apple = Brand.objects.create(
            name="Apple",
            slug="apple",
            website="https://apple.com",
        )
        self.brand_dell = Brand.objects.create(
            name="Dell",
            slug="dell",
            website="https://dell.com",
        )

        # 3. Setup Attributes & Values
        self.attr_color = Attribute.objects.create(name="Color", slug="color")
        self.attr_ram = Attribute.objects.create(name="RAM", slug="ram")

        self.val_space_gray = AttributeValue.objects.create(
            attribute=self.attr_color, value="Space Gray", slug="space-gray"
        )
        self.val_silver = AttributeValue.objects.create(
            attribute=self.attr_color, value="Silver", slug="silver"
        )
        self.val_16gb = AttributeValue.objects.create(
            attribute=self.attr_ram, value="16GB", slug="16gb"
        )

        # 4. Setup Products
        self.product_macbook = Product.objects.create(
            name="MacBook Pro 16",
            slug="macbook-pro-16",
            brand=self.brand_apple,
            description="Supercharged by M3 Max chip.",
            short_description="Flagship pro laptop.",
            is_active=True,
        )
        ProductCategory.objects.create(
            product=self.product_macbook,
            category=self.cat_laptops,
            is_primary=True,
        )

        self.product_xps = Product.objects.create(
            name="Dell XPS 15",
            slug="dell-xps-15",
            brand=self.brand_dell,
            description="High performance creator laptop.",
            short_description="Premium Windows laptop.",
            is_active=True,
        )
        ProductCategory.objects.create(
            product=self.product_xps,
            category=self.cat_laptops,
            is_primary=True,
        )

        # 5. Setup Product Variants & Inventory
        # MacBook Variant 1 (Default, in stock, discounted)
        self.mb_v1 = ProductVariant.objects.create(
            product=self.product_macbook,
            title="16GB / Space Gray",
            sku="MBP-16-SG-16",
            price=Decimal("2499.00"),
            discount_price=Decimal("2299.00"),
            is_default=True,
            is_active=True,
        )
        ProductVariantAttributeValue.objects.create(
            variant=self.mb_v1,
            attribute_value=self.val_space_gray,
        )
        ProductVariantAttributeValue.objects.create(
            variant=self.mb_v1,
            attribute_value=self.val_16gb,
        )
        self.mb_v1_inv = Inventory.objects.create(
            variant=self.mb_v1,
            quantity=15,
            reserved_quantity=2,
            low_stock_threshold=3,
        )

        # MacBook Variant 2 (Silver, out of stock)
        self.mb_v2 = ProductVariant.objects.create(
            product=self.product_macbook,
            title="16GB / Silver",
            sku="MBP-16-SL-16",
            price=Decimal("2499.00"),
            is_default=False,
            is_active=True,
        )
        ProductVariantAttributeValue.objects.create(
            variant=self.mb_v2,
            attribute_value=self.val_silver,
        )
        self.mb_v2_inv = Inventory.objects.create(
            variant=self.mb_v2,
            quantity=0,
            reserved_quantity=0,
        )

        # Dell XPS Variant (in stock, regular price)
        self.xps_v1 = ProductVariant.objects.create(
            product=self.product_xps,
            title="16GB / Silver",
            sku="XPS-15-SL-16",
            price=Decimal("1899.00"),
            is_default=True,
            is_active=True,
        )
        self.xps_v1_inv = Inventory.objects.create(
            variant=self.xps_v1,
            quantity=10,
            reserved_quantity=0,
        )

        # Media
        dummy_image = SimpleUploadedFile("laptop.jpg", b"fake-content", content_type="image/jpeg")
        self.media_mb = ProductMedia.objects.create(
            product=self.product_macbook,
            file=dummy_image,
            alt_text="MacBook Pro 16 Space Gray",
            is_main=True,
        )

    # 1. Categories Tree Endpoint
    def test_category_tree_endpoint(self):
        url = reverse('catalog:category-tree')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should contain Electronics and Clothing as root categories
        root_slugs = [c['slug'] for c in response.data]
        self.assertIn('electronics', root_slugs)
        self.assertIn('clothing', root_slugs)
        # Verify nested children
        electronics_cat = next(c for c in response.data if c['slug'] == 'electronics')
        self.assertEqual(len(electronics_cat['children']), 1)
        self.assertEqual(electronics_cat['children'][0]['slug'], 'computers')
        self.assertEqual(len(electronics_cat['children'][0]['children']), 1)
        self.assertEqual(electronics_cat['children'][0]['children'][0]['slug'], 'laptops')

    # 2. Category Detail Endpoint
    def test_category_detail_endpoint(self):
        url = reverse('catalog:category-detail', kwargs={'slug': 'laptops'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'laptops')
        self.assertEqual(response.data['name'], 'Laptops')
        self.assertEqual(response.data['products_count'], 2)
        # Check breadcrumbs: Electronics -> Computers
        crumbs = response.data['breadcrumbs']
        self.assertEqual(len(crumbs), 2)
        self.assertEqual(crumbs[0]['slug'], 'electronics')
        self.assertEqual(crumbs[1]['slug'], 'computers')

    # 3. Brand List Endpoint
    def test_brand_list_endpoint(self):
        url = reverse('catalog:brand-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [b['slug'] for b in response.data]
        self.assertIn('apple', slugs)
        self.assertIn('dell', slugs)

        # Test search query on brands
        res_search = self.client.get(url, {'q': 'App'})
        self.assertEqual(len(res_search.data), 1)
        self.assertEqual(res_search.data[0]['slug'], 'apple')

    # 4. Brand Detail Endpoint
    def test_brand_detail_endpoint(self):
        url = reverse('catalog:brand-detail', kwargs={'slug': 'apple'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'apple')
        self.assertEqual(response.data['products_count'], 1)

    # 5. Product List & Filtering Endpoints
    def test_product_list_basic(self):
        url = reverse('catalog:product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_product_list_category_hierarchy_filter(self):
        url = reverse('catalog:product-list')
        # Filter by root category 'electronics' should return laptops!
        res_root = self.client.get(url, {'category': 'electronics'})
        self.assertEqual(res_root.data['count'], 2)

        # Filter by clothing should return 0
        res_clothing = self.client.get(url, {'category': 'clothing'})
        self.assertEqual(res_clothing.data['count'], 0)

    def test_product_list_brand_filter(self):
        url = reverse('catalog:product-list')
        res_apple = self.client.get(url, {'brand': 'apple'})
        self.assertEqual(res_apple.data['count'], 1)
        self.assertEqual(res_apple.data['results'][0]['slug'], 'macbook-pro-16')

    def test_product_list_price_range_filter(self):
        url = reverse('catalog:product-list')
        # Dell XPS is 1899, MacBook effective price is 2299
        res_cheap = self.client.get(url, {'max_price': '2000'})
        self.assertEqual(res_cheap.data['count'], 1)
        self.assertEqual(res_cheap.data['results'][0]['slug'], 'dell-xps-15')

    def test_product_list_search_filter(self):
        url = reverse('catalog:product-list')
        res_search = self.client.get(url, {'q': 'MacBook'})
        self.assertEqual(res_search.data['count'], 1)
        self.assertEqual(res_search.data['results'][0]['slug'], 'macbook-pro-16')

    def test_product_list_dynamic_attribute_filter(self):
        url = reverse('catalog:product-list')
        res_attr = self.client.get(url, {'attr_color': 'space-gray'})
        self.assertEqual(res_attr.data['count'], 1)
        self.assertEqual(res_attr.data['results'][0]['slug'], 'macbook-pro-16')

    def test_product_list_ordering(self):
        url = reverse('catalog:product-list')
        # Order by price ascending: Dell XPS (1899) should come before MacBook (2299)
        res_price_asc = self.client.get(url, {'ordering': 'price'})
        self.assertEqual(res_price_asc.data['results'][0]['slug'], 'dell-xps-15')

        # Order by price descending
        res_price_desc = self.client.get(url, {'ordering': '-price'})
        self.assertEqual(res_price_desc.data['results'][0]['slug'], 'macbook-pro-16')

    # 6. Product Detail Endpoint
    def test_product_detail_endpoint(self):
        url = reverse('catalog:product-detail', kwargs={'slug': 'macbook-pro-16'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'macbook-pro-16')
        self.assertEqual(response.data['brand']['name'], 'Apple')
        self.assertEqual(len(response.data['variants']), 2)
        self.assertEqual(len(response.data['media']), 1)
        self.assertTrue(response.data['is_in_stock'])
        self.assertIsNotNone(response.data['default_variant'])
        self.assertEqual(response.data['default_variant']['sku'], 'MBP-16-SG-16')

    # 7. Product Variant Detail Endpoint
    def test_product_variant_detail_endpoint(self):
        url = reverse(
            'catalog:product-variant-detail',
            kwargs={'slug': 'macbook-pro-16', 'sku': 'MBP-16-SG-16'}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sku'], 'MBP-16-SG-16')
        self.assertEqual(response.data['final_price'], '2299.00')
        self.assertTrue(response.data['is_on_sale'])
        self.assertEqual(response.data['available_quantity'], 13)
        self.assertTrue(response.data['is_in_stock'])

    # 8. Dynamic Filters Endpoint
    def test_catalog_filters_endpoint(self):
        url = reverse('catalog:catalog-filters')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('price_range', response.data)
        self.assertIn('brands', response.data)
        self.assertIn('categories', response.data)
        self.assertIn('attributes', response.data)
        # Verify min price (Dell XPS 1899) and max price (MacBook 2499)
        self.assertEqual(response.data['price_range']['min'], '1899.00')
        self.assertEqual(response.data['price_range']['max'], '2499.00')

    # 9. Search Suggestion Endpoint
    def test_search_suggest_endpoint(self):
        url = reverse('catalog:search-suggest')
        response = self.client.get(url, {'q': 'Mac'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['products']) >= 1)
        self.assertEqual(response.data['products'][0]['slug'], 'macbook-pro-16')

    # 10. Featured Products Endpoint
    def test_featured_products_endpoint(self):
        url = reverse('catalog:featured-products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('new_arrivals', response.data)
        self.assertIn('on_sale', response.data)
        # MacBook has discount_price so it must be in on_sale
        on_sale_slugs = [p['slug'] for p in response.data['on_sale']]
        self.assertIn('macbook-pro-16', on_sale_slugs)
