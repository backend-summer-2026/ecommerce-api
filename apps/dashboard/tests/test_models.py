from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.dashboard.models import (
    DailyMetricSnapshot,
    StaffActivityLog,
    StockMovementLog,
    OrderInternalNote,
    SystemAlert,
)
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Inventory, Product, ProductCategory, ProductVariant

User = get_user_model()


class DashboardModelsTestCase(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email='staff@test.com',
            password='password123',
            first_name='Staff',
            last_name='User',
            role='admin',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email='customer@test.com',
            password='password123',
            first_name='John',
            last_name='Doe',
            role='customer',
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.brand = Brand.objects.create(name='TechCorp', slug='techcorp')
        self.product = Product.objects.create(
            name='Smartphone Pro',
            slug='smartphone-pro',
            brand=self.brand,
        )
        ProductCategory.objects.create(product=self.product, category=self.category, is_primary=True)
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku='PHONE-PRO-BLK',
            title='Black 128GB',
            price=Decimal('500.00'),
        )
        self.inventory = Inventory.objects.create(
            variant=self.variant,
            quantity=20,
            reserved_quantity=2,
            low_stock_threshold=5,
        )

    def test_daily_metric_snapshot_creation_and_recalculate(self):
        today = timezone.localdate()
        order = Order.objects.create(
            user=self.customer,
            order_number='ORD-TEST-001',
            status=Order.OrderStatus.CONFIRMED,
            payment_status=Order.PaymentStatus.PAID,
            total_price=Decimal('1000.00'),
            subtotal=Decimal('1000.00'),
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name=self.product.name,
            variant_sku=self.variant.sku,
            unit_price=Decimal('500.00'),
            quantity=2,
            total_price=Decimal('1000.00'),
        )

        snapshot = DailyMetricSnapshot.recalculate_for_date(today)
        self.assertEqual(snapshot.date, today)
        self.assertEqual(snapshot.total_orders, 1)
        self.assertEqual(snapshot.total_revenue, Decimal('1000.00'))
        self.assertEqual(snapshot.total_items_sold, 2)
        self.assertIn("DailyMetrics", str(snapshot))

    def test_staff_activity_log_creation(self):
        log = StaffActivityLog.objects.create(
            actor=self.staff_user,
            action=StaffActivityLog.ActivityAction.STATUS_CHANGE,
            module=StaffActivityLog.ActivityModule.ORDERS,
            target_model='Order',
            target_id='ORD-TEST-001',
            target_repr='Order #ORD-TEST-001',
            description="Status changed to CONFIRMED",
            changes={'status': {'old': 'PENDING', 'new': 'CONFIRMED'}},
            ip_address='127.0.0.1',
        )
        self.assertEqual(log.actor, self.staff_user)
        self.assertEqual(log.action, StaffActivityLog.ActivityAction.STATUS_CHANGE)
        self.assertIn("staff@test.com", str(log))

    def test_stock_movement_log_creation(self):
        movement = StockMovementLog.objects.create(
            variant=self.variant,
            actor=self.staff_user,
            movement_type=StockMovementLog.StockMovementType.ADJUSTMENT,
            quantity_delta=10,
            previous_quantity=20,
            new_quantity=30,
            reason="Inventarizatsiya natijasida to'ldirildi",
        )
        self.assertEqual(movement.variant, self.variant)
        self.assertEqual(movement.quantity_delta, 10)
        self.assertEqual(movement.new_quantity, 30)
        self.assertIn("StockLog", str(movement))

    def test_order_internal_note(self):
        order = Order.objects.create(
            user=self.customer,
            order_number='ORD-NOTE-001',
            total_price=Decimal('250.00'),
        )
        note = OrderInternalNote.objects.create(
            order=order,
            author=self.staff_user,
            note="Mijozga qo'ng'iroq qilindi, yetkazib berish vaqti kelishildi.",
            is_pinned=True,
        )
        self.assertTrue(note.is_pinned)
        self.assertEqual(note.author, self.staff_user)
        self.assertIn("ORD-NOTE-001", str(note))

    def test_system_alert_lifecycle(self):
        alert = SystemAlert.objects.create(
            alert_type=SystemAlert.AlertType.LOW_STOCK,
            severity=SystemAlert.AlertSeverity.WARNING,
            title="Kam qolgan zaxira",
            message="PHONE-PRO-BLK qoldig'i 2 ta qoldi",
        )
        self.assertFalse(alert.is_resolved)
        self.assertIsNone(alert.resolved_by)

        alert.resolve(self.staff_user)
        self.assertTrue(alert.is_resolved)
        self.assertEqual(alert.resolved_by, self.staff_user)
        self.assertIsNotNone(alert.resolved_at)
        self.assertIn("RESOLVED", str(alert))
