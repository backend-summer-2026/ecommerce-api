from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.carts.models import Cart, CartItem
from apps.products.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Inventory,
    Product,
    ProductVariant,
    ProductVariantAttributeValue,
)

User = get_user_model()


class CartAPITestCase(APITestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='TestPassword123!',
            first_name='Shopper',
            last_name='User',
            is_active=True,
        )
        self.client.force_authenticate(user=None)  # Start as guest

        # Create Catalog Base
        self.category = Category.objects.create(name='Laptops', slug='laptops')
        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.product = Product.objects.create(
            name='MacBook Pro 16',
            slug='macbook-pro-16',
            brand=self.brand,
            is_active=True,
        )

        # Attribute
        self.attr_ram = Attribute.objects.create(name='RAM', slug='ram')
        self.val_32gb = AttributeValue.objects.create(attribute=self.attr_ram, value='32GB')

        # Variant 1 (In Stock = 5)
        self.variant1 = ProductVariant.objects.create(
            product=self.product,
            title='M3 Pro / 32GB / 512GB SSD',
            sku='MBP-16-M3P-32-512',
            price=Decimal('25000000.00'),
            discount_price=Decimal('23000000.00'),
            is_active=True,
            is_default=True,
        )
        self.inv1 = Inventory.objects.create(
            variant=self.variant1,
            quantity=7,
            reserved_quantity=2,  # available = 5
        )
        ProductVariantAttributeValue.objects.create(
            variant=self.variant1,
            attribute_value=self.val_32gb,
        )

        # Variant 2 (In Stock = 2)
        self.variant2 = ProductVariant.objects.create(
            product=self.product,
            title='M3 Max / 64GB / 1TB SSD',
            sku='MBP-16-M3M-64-1TB',
            price=Decimal('35000000.00'),
            discount_price=None,
            is_active=True,
        )
        self.inv2 = Inventory.objects.create(
            variant=self.variant2,
            quantity=2,
            reserved_quantity=0,  # available = 2
        )

        # Inactive Variant
        self.inactive_variant = ProductVariant.objects.create(
            product=self.product,
            title='Inactive Model',
            sku='MBP-INACTIVE',
            price=Decimal('20000000.00'),
            is_active=False,
        )
        Inventory.objects.create(variant=self.inactive_variant, quantity=10, reserved_quantity=0)

    # ---------------------------------------------------------
    # 1. GET /api/v1/cart/ (Cart Detail)
    # ---------------------------------------------------------
    def test_get_cart_as_new_guest_creates_cart_and_sets_header(self):
        url = reverse('cart:cart-detail')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_empty'])
        self.assertEqual(response.data['total_items'], 0)
        self.assertIn('X-Session-Key', response.headers)
        self.assertIn('X-Cart-ID', response.headers)

    def test_get_cart_as_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('cart:cart-detail')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_items'], 0)
        self.assertTrue(response.data['is_empty'])

    # ---------------------------------------------------------
    # 2. GET /api/v1/cart/count/ (Cart Summary)
    # ---------------------------------------------------------
    def test_get_cart_count_empty(self):
        url = reverse('cart:cart-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_items'], 0)
        self.assertTrue(response.data['is_empty'])

    # ---------------------------------------------------------
    # 3. POST /api/v1/cart/items/ (Add to Cart)
    # ---------------------------------------------------------
    def test_add_item_to_cart_guest_success(self):
        url = reverse('cart:cart-add-item')
        payload = {
            'variant_id': self.variant1.id,
            'quantity': 2,
        }
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_items'], 2)
        self.assertEqual(response.data['unique_items_count'], 1)
        self.assertFalse(response.data['is_empty'])
        # Subtotal: 2 * 25,000,000 = 50,000,000
        self.assertEqual(Decimal(response.data['subtotal']), Decimal('50000000.00'))
        # Total Price: 2 * 23,000,000 = 46,000,000
        self.assertEqual(Decimal(response.data['total_price']), Decimal('46000000.00'))
        # Total Discount: 4,000,000
        self.assertEqual(Decimal(response.data['total_discount']), Decimal('4000000.00'))

        # Check item structure
        item = response.data['items'][0]
        self.assertEqual(item['quantity'], 2)
        self.assertEqual(item['variant']['sku'], self.variant1.sku)
        self.assertEqual(item['variant']['product_name'], 'MacBook Pro 16')
        self.assertEqual(item['variant']['attributes']['RAM'], '32GB')

    def test_add_item_increments_existing_quantity(self):
        session_key = 'test_session_123'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        url = reverse('cart:cart-add-item')
        self.client.post(url, data={'variant_id': self.variant1.id, 'quantity': 1}, format='json')
        response = self.client.post(url, data={'variant_id': self.variant1.id, 'quantity': 2}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_items'], 3)
        self.assertEqual(response.data['unique_items_count'], 1)
        self.assertEqual(response.data['items'][0]['quantity'], 3)

    def test_add_item_exceeding_inventory_fails(self):
        url = reverse('cart:cart-add-item')
        # available is 5, requesting 6
        payload = {'variant_id': self.variant1.id, 'quantity': 6}
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)

    def test_add_inactive_variant_fails(self):
        url = reverse('cart:cart-add-item')
        payload = {'variant_id': self.inactive_variant.id, 'quantity': 1}
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('variant_id', response.data)

    def test_add_item_invalid_quantity_fails(self):
        url = reverse('cart:cart-add-item')
        payload = {'variant_id': self.variant1.id, 'quantity': 0}
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------------------------------------
    # 4. PATCH /api/v1/cart/items/<id>/ (Update Item Quantity)
    # ---------------------------------------------------------
    def test_update_item_quantity_success(self):
        session_key = 'test_patch_session'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        # Add item first
        add_resp = self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant1.id, 'quantity': 1},
            format='json',
        )
        item_id = add_resp.data['items'][0]['id']

        # Update to 4
        patch_url = reverse('cart:cart-item-detail', kwargs={'item_id': item_id})
        response = self.client.patch(patch_url, data={'quantity': 4}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_items'], 4)
        self.assertEqual(response.data['items'][0]['quantity'], 4)

    def test_update_item_quantity_exceeding_stock_fails(self):
        session_key = 'test_patch_stock'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        add_resp = self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant1.id, 'quantity': 1},
            format='json',
        )
        item_id = add_resp.data['items'][0]['id']

        patch_url = reverse('cart:cart-item-detail', kwargs={'item_id': item_id})
        # Stock is 5, requesting 6
        response = self.client.patch(patch_url, data={'quantity': 6}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_non_existent_item_fails(self):
        session_key = 'test_patch_404'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        # Initialize cart
        self.client.get(reverse('cart:cart-detail'))

        patch_url = reverse('cart:cart-item-detail', kwargs={'item_id': 99999})
        response = self.client.patch(patch_url, data={'quantity': 2}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---------------------------------------------------------
    # 5. DELETE /api/v1/cart/items/<id>/ (Remove Item)
    # ---------------------------------------------------------
    def test_remove_item_success(self):
        session_key = 'test_remove_session'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        add_resp = self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant1.id, 'quantity': 2},
            format='json',
        )
        item_id = add_resp.data['items'][0]['id']

        delete_url = reverse('cart:cart-item-detail', kwargs={'item_id': item_id})
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_empty'])
        self.assertEqual(response.data['total_items'], 0)

    # ---------------------------------------------------------
    # 6. POST /api/v1/cart/clear/ (Clear Entire Cart)
    # ---------------------------------------------------------
    def test_clear_cart_success(self):
        session_key = 'test_clear_session'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        self.client.post(reverse('cart:cart-add-item'), data={'variant_id': self.variant1.id, 'quantity': 1})
        self.client.post(reverse('cart:cart-add-item'), data={'variant_id': self.variant2.id, 'quantity': 1})

        clear_url = reverse('cart:cart-clear')
        response = self.client.post(clear_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_empty'])
        self.assertEqual(response.data['total_items'], 0)

    # ---------------------------------------------------------
    # 7. POST /api/v1/cart/merge/ (Merge Guest Cart)
    # ---------------------------------------------------------
    def test_merge_cart_requires_authentication(self):
        url = reverse('cart:cart-merge')
        response = self.client.post(url, data={'guest_session_key': 'abc'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_merge_guest_cart_into_authenticated_user_cart(self):
        # 1. Create a guest cart with variant1 (2 units)
        guest_session_key = 'guest_merge_session'
        guest_cart = Cart.objects.create(session_key=guest_session_key)
        CartItem.objects.create(cart=guest_cart, variant=self.variant1, quantity=2)
        CartItem.objects.create(cart=guest_cart, variant=self.variant2, quantity=1)

        # 2. Authenticated user already has variant1 (1 unit) in their active cart
        user_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=user_cart, variant=self.variant1, quantity=1)

        # 3. Perform merge request as authenticated user
        self.client.force_authenticate(user=self.user)
        merge_url = reverse('cart:cart-merge')
        payload = {'guest_session_key': guest_session_key}
        response = self.client.post(merge_url, data=payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Variant 1 should now be 1 + 2 = 3
        # Variant 2 should now be 1
        # Total items = 4, unique = 2
        self.assertEqual(response.data['total_items'], 4)
        self.assertEqual(response.data['unique_items_count'], 2)

        # Verify guest cart status in DB is MERGED
        guest_cart.refresh_from_db()
        self.assertEqual(guest_cart.status, Cart.CartStatus.MERGED)

    # ---------------------------------------------------------
    # 8. Dynamic Price Change Warning Test
    # ---------------------------------------------------------
    def test_cart_warnings_on_price_change(self):
        session_key = 'test_warning_session'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        # Add item at 23,000,000
        self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant1.id, 'quantity': 1},
            format='json',
        )

        # Price changes to 21,000,000
        self.variant1.discount_price = Decimal('21000000.00')
        self.variant1.save()

        # Fetch cart
        response = self.client.get(reverse('cart:cart-detail'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['warnings']) > 0)
        self.assertTrue(response.data['items'][0]['is_price_changed'])
        self.assertIn('decreased', response.data['warnings'][0])

    # ---------------------------------------------------------
    # 9. Query Optimization (N+1 Prevention Assertion)
    # ---------------------------------------------------------
    def test_cart_detail_query_count_optimization(self):
        session_key = 'test_perf_session'
        self.client.credentials(HTTP_X_SESSION_KEY=session_key)

        # Add both variants
        self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant1.id, 'quantity': 2},
            format='json',
        )
        self.client.post(
            reverse('cart:cart-add-item'),
            data={'variant_id': self.variant2.id, 'quantity': 1},
            format='json',
        )

        url = reverse('cart:cart-detail')
        # Optimized retrieval executes constant queries (7 queries) regardless of item count
        with self.assertNumQueries(7):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['total_items'], 3)
