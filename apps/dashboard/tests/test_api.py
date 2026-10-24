from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.dashboard.models import OrderInternalNote, StaffActivityLog, SystemAlert
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class DashboardAPITestCase(APITestCase):
    def setUp(self):
        # 1. Admin user (full permissions)
        self.admin_user = User.objects.create_superuser(
            email='admin@ecommerce.test',
            password='password123',
            first_name='Admin',
            last_name='User',
            role='admin',
        )

        # 2. Staff user (operator permissions)
        self.staff_user = User.objects.create_user(
            email='staff@ecommerce.test',
            password='password123',
            first_name='Staff',
            last_name='Operator',
            role='customer',
            is_staff=True,
        )

        # 3. Regular customer (no dashboard access)
        self.customer = User.objects.create_user(
            email='customer@ecommerce.test',
            password='password123',
            first_name='John',
            last_name='Customer',
            role='customer',
            is_staff=False,
        )

        # 4. Catalog setup
        self.category = Category.objects.create(name='Computers', slug='computers')
        self.brand = Brand.objects.create(name='Dell', slug='dell')
        self.product = Product.objects.create(
            name='XPS 15',
            slug='xps-15',
            brand=self.brand,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='DELL-XPS-15-I7',
            title='Core i7 / 16GB / 512GB',
            price=Decimal('1500.00'),
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=15,
            reserved_quantity=2,
            low_stock_threshold=5,
        )

        # 5. Orders setup
        self.order = Order.objects.create(
            user=self.customer,
            order_number='ORD-DASH-1001',
            status=Order.OrderStatus.CONFIRMED,
            payment_status=Order.PaymentStatus.PAID,
            total_price=Decimal('3000.00'),
            subtotal=Decimal('3000.00'),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_sku=self.variant.sku,
            unit_price=Decimal('1500.00'),
            quantity=2,
            total_price=Decimal('3000.00'),
        )

        # 6. System alert setup
        self.alert = SystemAlert.objects.create(
            alert_type=SystemAlert.AlertType.LOW_STOCK,
            severity=SystemAlert.AlertSeverity.WARNING,
            title="Low stock test alert",
            message="Item is below low threshold",
        )

    # --------------------------------------------------------------------------
    # PERMISSIONS & ACCESS CONTROL TESTS
    # --------------------------------------------------------------------------

    def test_anonymous_access_denied(self):
        url = reverse('dashboard:analytics-overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_customer_access_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse('dashboard:analytics-overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_access_allowed(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:analytics-overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --------------------------------------------------------------------------
    # ANALYTICS ENDPOINTS TESTS
    # --------------------------------------------------------------------------

    def test_analytics_overview(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:analytics-overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('kpis', response.data)
        self.assertIn('growth', response.data)
        self.assertEqual(response.data['kpis']['total_orders'], 1)

    def test_analytics_sales_chart(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:analytics-sales-chart')
        response = self.client.get(url, {'days': 7})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)

    def test_analytics_top_products(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:analytics-top-products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'DELL-XPS-15-I7')

    def test_analytics_top_customers(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:analytics-top-customers')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['customer_id'], self.customer.id)

    # --------------------------------------------------------------------------
    # INVENTORY MANAGEMENT ENDPOINTS TESTS
    # --------------------------------------------------------------------------

    def test_inventory_list_and_stats(self):
        self.client.force_authenticate(user=self.staff_user)
        list_url = reverse('dashboard:inventory-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stats_url = reverse('dashboard:inventory-stats')
        stats_resp = self.client.get(stats_url)
        self.assertEqual(stats_resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_skus', stats_resp.data)

    def test_stock_adjustment_successful(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:inventory-adjust', kwargs={'variant_id': self.variant.id})
        payload = {
            'quantity_delta': 5,
            'reason': 'Kirim qabul qilindi',
            'movement_type': 'INCOMING',
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['previous_quantity'], 15)
        self.assertEqual(response.data['new_quantity'], 20)

        # Verify audit log created
        log_exists = StaffActivityLog.objects.filter(
            action=StaffActivityLog.ActivityAction.STOCK_ADJUSTMENT,
            module=StaffActivityLog.ActivityModule.INVENTORY,
        ).exists()
        self.assertTrue(log_exists)

    def test_stock_adjustment_insufficient_stock(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:inventory-adjust', kwargs={'variant_id': self.variant.id})
        payload = {
            'quantity_delta': -100,  # Only 15 available
            'reason': 'Hisobdan chiqarish',
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_stock_movement_logs_list(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:inventory-logs')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --------------------------------------------------------------------------
    # ORDER MANAGEMENT & NOTES ENDPOINTS TESTS
    # --------------------------------------------------------------------------

    def test_dashboard_order_list_and_detail(self):
        self.client.force_authenticate(user=self.staff_user)
        list_url = reverse('dashboard:order-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        detail_url = reverse('dashboard:order-detail', kwargs={'order_number': self.order.order_number})
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['order_number'], 'ORD-DASH-1001')

    def test_dashboard_order_status_update(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:order-status-update', kwargs={'order_number': self.order.order_number})
        payload = {
            'status': Order.OrderStatus.SHIPPED,
            'tracking_number': 'TRK-987654321',
            'admin_notes': 'Kuryerga topshirildi',
        }
        response = self.client.patch(url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['new_status'], Order.OrderStatus.SHIPPED)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.SHIPPED)
        self.assertEqual(self.order.tracking_number, 'TRK-987654321')

    def test_order_internal_notes_flow(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:order-notes', kwargs={'order_number': self.order.order_number})

        # Post note
        post_resp = self.client.post(url, {'note': 'Mijoz 18:00 dan keyin yetkazishni soradi', 'is_pinned': True})
        self.assertEqual(post_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(post_resp.data['is_pinned'])

        # Get notes
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_resp.data), 1)

    # --------------------------------------------------------------------------
    # CUSTOMER MANAGEMENT (CRM) ENDPOINTS TESTS
    # --------------------------------------------------------------------------

    def test_customer_list_and_detail(self):
        self.client.force_authenticate(user=self.staff_user)
        list_url = reverse('dashboard:customer-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        detail_url = reverse('dashboard:customer-detail', kwargs={'pk': self.customer.id})
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['email'], self.customer.email)

    def test_customer_toggle_status_admin_only(self):
        # Staff operator should be forbidden
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('dashboard:customer-toggle-status', kwargs={'pk': self.customer.id})
        forbidden_resp = self.client.patch(url, {'is_active': False, 'reason': 'Spam'})
        self.assertEqual(forbidden_resp.status_code, status.HTTP_403_FORBIDDEN)

        # Superuser / Admin should succeed
        self.client.force_authenticate(user=self.admin_user)
        success_resp = self.client.patch(url, {'is_active': False, 'reason': 'Shubhali faollik'})
        self.assertEqual(success_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(success_resp.data['is_active'])

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

    # --------------------------------------------------------------------------
    # AUDIT TRAIL & SYSTEM ALERTS TESTS
    # --------------------------------------------------------------------------

    def test_audit_logs_admin_only(self):
        url = reverse('dashboard:audit-logs')

        # Staff operator forbidden
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin user allowed
        self.client.force_authenticate(user=self.admin_user)
        admin_resp = self.client.get(url)
        self.assertEqual(admin_resp.status_code, status.HTTP_200_OK)

    def test_system_alerts_and_resolve(self):
        self.client.force_authenticate(user=self.staff_user)
        list_url = reverse('dashboard:alerts-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        resolve_url = reverse('dashboard:alert-resolve', kwargs={'pk': self.alert.id})
        resolve_resp = self.client.patch(resolve_url)
        self.assertEqual(resolve_resp.status_code, status.HTTP_200_OK)

        self.alert.refresh_from_db()
        self.assertTrue(self.alert.is_resolved)
        self.assertEqual(self.alert.resolved_by, self.staff_user)
