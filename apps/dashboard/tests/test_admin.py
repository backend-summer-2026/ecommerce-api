from decimal import Decimal
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.dashboard.admin import (
    DailyMetricSnapshotAdmin,
    OrderInternalNoteAdmin,
    StaffActivityLogAdmin,
    StockMovementLogAdmin,
    SystemAlertAdmin,
)
from apps.dashboard.models import (
    DailyMetricSnapshot,
    OrderInternalNote,
    StaffActivityLog,
    StockMovementLog,
    SystemAlert,
)
from apps.orders.models import Order
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class DashboardAdminTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email='admin@test.com',
            password='password123',
            first_name='Super',
            last_name='Admin',
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics-admin')
        self.brand = Brand.objects.create(name='Apple', slug='apple')
        self.product = Product.objects.create(
            name='MacBook Pro',
            slug='macbook-pro',
            brand=self.brand,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='MBP-M3-16',
            title='16-inch M3 Pro',
            price=Decimal('2500.00'),
        )

    def test_daily_metric_snapshot_admin(self):
        model_admin = DailyMetricSnapshotAdmin(DailyMetricSnapshot, site)
        snapshot = DailyMetricSnapshot.objects.create(
            date='2026-10-24',
            total_revenue=Decimal('15000.00'),
            average_order_value=Decimal('150.00'),
            refunded_amount=Decimal('200.00'),
        )
        self.assertIn('$15,000.00', model_admin.revenue_display(snapshot))
        self.assertIn('$150.00', model_admin.aov_display(snapshot))
        self.assertIn('$200.00', model_admin.refunded_display(snapshot))

    def test_staff_activity_log_admin_readonly(self):
        model_admin = StaffActivityLogAdmin(StaffActivityLog, site)
        request = self.factory.get('/admin/')
        request.user = self.admin_user

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

        log = StaffActivityLog.objects.create(
            actor=self.admin_user,
            action=StaffActivityLog.ActivityAction.UPDATE,
            module=StaffActivityLog.ActivityModule.PRODUCTS,
            description="Updated product price",
        )
        badge = model_admin.action_badge(log)
        self.assertIn('background-color', badge)
        self.assertEqual(model_admin.actor_display(log), 'admin@test.com')

    def test_stock_movement_log_admin(self):
        model_admin = StockMovementLogAdmin(StockMovementLog, site)
        request = self.factory.get('/admin/')
        request.user = self.admin_user

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))

        movement = StockMovementLog.objects.create(
            variant=self.variant,
            actor=self.admin_user,
            movement_type=StockMovementLog.StockMovementType.INCOMING,
            quantity_delta=50,
            previous_quantity=10,
            new_quantity=60,
        )
        self.assertEqual(model_admin.variant_sku(movement), 'MBP-M3-16')
        self.assertIn('+50', model_admin.quantity_delta_display(movement))

    def test_order_internal_note_admin(self):
        model_admin = OrderInternalNoteAdmin(OrderInternalNote, site)
        order = Order.objects.create(
            user=self.admin_user,
            order_number='ORD-ADM-001',
            total_price=Decimal('100.00'),
        )
        note = OrderInternalNote.objects.create(
            order=order,
            author=self.admin_user,
            note="Test note for admin order representation checking.",
            is_pinned=True,
        )
        self.assertEqual(model_admin.order_number_display(note), 'ORD-ADM-001')
        self.assertEqual(model_admin.short_note(note), note.note)

    def test_system_alert_admin_action(self):
        model_admin = SystemAlertAdmin(SystemAlert, site)
        alert = SystemAlert.objects.create(
            alert_type=SystemAlert.AlertType.LOW_STOCK,
            severity=SystemAlert.AlertSeverity.CRITICAL,
            title="Out of stock",
            message="No units remaining",
        )
        request = self.factory.post('/admin/')
        request.user = self.admin_user
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, '_messages', FallbackStorage(request))

        queryset = SystemAlert.objects.filter(pk=alert.pk)
        model_admin.mark_as_resolved(request, queryset)

        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)
        self.assertEqual(alert.resolved_by, self.admin_user)
