from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone


class DailyMetricSnapshot(models.Model):
    """
    Stores pre-calculated daily KPI metrics for high-performance dashboard analytics
    without heavy queries on production transactions.
    """
    date = models.DateField(unique=True, db_index=True, help_text="Metrics calculation date")
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total revenue from paid orders on this date",
    )
    total_orders = models.PositiveIntegerField(
        default=0,
        help_text="Total orders created on this date",
    )
    completed_orders_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of orders completed or delivered",
    )
    cancelled_orders_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of orders cancelled",
    )
    new_customers_count = models.PositiveIntegerField(
        default=0,
        help_text="New customers registered on this date",
    )
    total_items_sold = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity of product units sold",
    )
    average_order_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Average order value (AOV)",
    )
    refunded_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total refunded amount on this date",
    )
    extra_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured metadata or breakdown statistics",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboard_daily_metrics'
        verbose_name = 'Daily Metric Snapshot'
        verbose_name_plural = 'Daily Metric Snapshots'
        ordering = ['-date']

    def __str__(self) -> str:
        return f"DailyMetrics ({self.date}): Revenue={self.total_revenue}, Orders={self.total_orders}"

    @classmethod
    def recalculate_for_date(cls, target_date):
        """
        Calculates and updates or creates the metric snapshot for a specific date.
        """
        from apps.orders.models import Order, OrderItem
        from apps.payments.models import Refund
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Orders created on target_date
        orders_qs = Order.objects.filter(created_at__date=target_date)
        total_orders = orders_qs.count()

        # Paid orders for revenue calculation
        paid_orders = orders_qs.filter(payment_status='PAID')
        revenue_agg = paid_orders.aggregate(total=Sum('total_price'), aov=Avg('total_price'))
        total_revenue = revenue_agg['total'] or Decimal('0.00')
        aov = revenue_agg['aov'] or Decimal('0.00')

        # Status breakdowns
        completed_orders = orders_qs.filter(status__in=['DELIVERED', 'CONFIRMED', 'PROCESSING', 'SHIPPED']).count()
        cancelled_orders = orders_qs.filter(status='CANCELLED').count()

        # Sold items
        items_sold_agg = OrderItem.objects.filter(order__created_at__date=target_date).aggregate(
            total_qty=Sum('quantity')
        )
        total_items_sold = items_sold_agg['total_qty'] or 0

        # New customers
        new_customers = User.objects.filter(created_at__date=target_date, role='CUSTOMER').count()

        # Refunds on this date
        refund_agg = Refund.objects.filter(created_at__date=target_date, status='COMPLETED').aggregate(
            total_refunded=Sum('amount')
        )
        refunded_amount = refund_agg['total_refunded'] or Decimal('0.00')

        snapshot, _ = cls.objects.update_or_create(
            date=target_date,
            defaults={
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'completed_orders_count': completed_orders,
                'cancelled_orders_count': cancelled_orders,
                'new_customers_count': new_customers,
                'total_items_sold': total_items_sold,
                'average_order_value': aov,
                'refunded_amount': refunded_amount,
            },
        )
        return snapshot


class StaffActivityLog(models.Model):
    """
    Immutable audit trail recording administrative and back-office staff actions.
    """
    class ActivityAction(models.TextChoices):
        CREATE = 'CREATE', 'Yaratish'
        UPDATE = 'UPDATE', 'Yangilash'
        DELETE = 'DELETE', 'O\'chirish'
        STATUS_CHANGE = 'STATUS_CHANGE', 'Statusni o\'zgartirish'
        STOCK_ADJUSTMENT = 'STOCK_ADJUSTMENT', 'Zaxirani to\'g\'rilash'
        REFUND = 'REFUND', 'To\'lovni qaytarish'
        LOGIN = 'LOGIN', 'Tizimga kirish'
        EXPORT = 'EXPORT', 'Eksport qilish'

    class ActivityModule(models.TextChoices):
        ORDERS = 'ORDERS', 'Buyurtmalar'
        PRODUCTS = 'PRODUCTS', 'Mahsulotlar'
        INVENTORY = 'INVENTORY', 'Ombor va Zaxira'
        USERS = 'USERS', 'Mijozlar va Foydalanuvchilar'
        COUPONS = 'COUPONS', 'Kuponlar va Aksiya'
        PAYMENTS = 'PAYMENTS', 'To\'lovlar'
        REVIEWS = 'REVIEWS', 'Sharhlar'
        SETTINGS = 'SETTINGS', 'Tizim Sozlamalari'

    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_activities',
        help_text="Staff or admin user performing the action",
    )
    action = models.CharField(
        max_length=32,
        choices=ActivityAction.choices,
        db_index=True,
        help_text="Type of action performed",
    )
    module = models.CharField(
        max_length=32,
        choices=ActivityModule.choices,
        db_index=True,
        help_text="System module where action occurred",
    )
    target_model = models.CharField(
        max_length=64,
        blank=True,
        help_text="Model name of the target entity",
    )
    target_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Primary key or identifier of the target object",
    )
    target_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="Readable label of the target object",
    )
    description = models.TextField(
        help_text="Human-readable explanation of the action",
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field-level difference between before and after values",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address",
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Client browser user agent",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the activity occurred",
    )

    class Meta:
        db_table = 'dashboard_staff_activity_logs'
        verbose_name = 'Staff Activity Log'
        verbose_name_plural = 'Staff Activity Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        actor_name = self.actor.email if self.actor else 'System'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {actor_name} - {self.get_action_display()} on {self.module}"


class StockMovementLog(models.Model):
    """
    Detailed audit log tracking inventory movements (receipt, sale, adjustment, damage, return).
    """
    class StockMovementType(models.TextChoices):
        INCOMING = 'INCOMING', 'Kirim (Yetkazib berish)'
        OUTGOING = 'OUTGOING', 'Chiqim (Sotuv)'
        ADJUSTMENT = 'ADJUSTMENT', 'Qo\'lda to\'g\'rilash (Inventarizatsiya)'
        RETURN = 'RETURN', 'Mijoz qaytargan tovar'
        DAMAGED = 'DAMAGED', 'Brak / Yaroqsiz'
        RESERVED = 'RESERVED', 'Buyurtmaga band qilingan'

    id = models.BigAutoField(primary_key=True)
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        related_name='stock_movements',
        help_text="Product variant affected by movement",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text="Staff member who executed or approved the adjustment",
    )
    movement_type = models.CharField(
        max_length=20,
        choices=StockMovementType.choices,
        db_index=True,
        help_text="Classification of stock movement",
    )
    quantity_delta = models.IntegerField(
        help_text="Stock quantity change (+ for addition, - for reduction)",
    )
    previous_quantity = models.PositiveIntegerField(
        help_text="Stock balance before this movement",
    )
    new_quantity = models.PositiveIntegerField(
        help_text="Stock balance after this movement",
    )
    reference_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text="Linked customer order if movement is related to a sale or return",
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason or note explaining this stock movement",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp of stock movement",
    )

    class Meta:
        db_table = 'dashboard_stock_movement_logs'
        verbose_name = 'Stock Movement Log'
        verbose_name_plural = 'Stock Movement Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        delta = f"+{self.quantity_delta}" if self.quantity_delta > 0 else f"{self.quantity_delta}"
        return f"StockLog #{self.id}: {self.variant.sku} ({delta}) -> {self.new_quantity}"


class OrderInternalNote(models.Model):
    """
    Internal notes and customer service memos attached to an order.
    Visible only to store staff and operators.
    """
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='internal_notes',
        help_text="Order to which note belongs",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='order_internal_notes',
        help_text="Staff operator who posted the note",
    )
    note = models.TextField(
        help_text="Internal remark or instruction for operators",
    )
    is_pinned = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Pin note at top for maximum operator visibility",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboard_order_internal_notes'
        verbose_name = 'Order Internal Note'
        verbose_name_plural = 'Order Internal Notes'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self) -> str:
        return f"Note by {self.author.email} on Order #{self.order.order_number}"


class SystemAlert(models.Model):
    """
    Automated administrative alerts for low stock, payment failures, and security events.
    """
    class AlertType(models.TextChoices):
        LOW_STOCK = 'LOW_STOCK', 'Zaxira tugamoqda'
        PAYMENT_FAILURE = 'PAYMENT_FAILURE', 'To\'lov xatosi'
        HIGH_ORDER_VOLUME = 'HIGH_ORDER_VOLUME', 'Yuqori buyurtma faolligi'
        SECURITY = 'SECURITY', 'Xavfsizlik hodisasi'
        SYSTEM_ERROR = 'SYSTEM_ERROR', 'Tizim xatoligi'

    class AlertSeverity(models.TextChoices):
        INFO = 'INFO', 'Ma\'lumot'
        WARNING = 'WARNING', 'Ogohlantirish'
        CRITICAL = 'CRITICAL', 'Kritik'

    id = models.BigAutoField(primary_key=True)
    alert_type = models.CharField(
        max_length=32,
        choices=AlertType.choices,
        db_index=True,
        help_text="Category of system alert",
    )
    severity = models.CharField(
        max_length=16,
        choices=AlertSeverity.choices,
        default=AlertSeverity.WARNING,
        db_index=True,
        help_text="Urgency level",
    )
    title = models.CharField(
        max_length=255,
        help_text="Alert headline",
    )
    message = models.TextField(
        help_text="Detailed alert information",
    )
    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this alert has been reviewed and resolved",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts',
        help_text="Staff user who marked the alert as resolved",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when alert was resolved",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when alert was triggered",
    )

    class Meta:
        db_table = 'dashboard_system_alerts'
        verbose_name = 'System Alert'
        verbose_name_plural = 'System Alerts'
        ordering = ['is_resolved', '-created_at']

    def __str__(self) -> str:
        status = 'RESOLVED' if self.is_resolved else 'ACTIVE'
        return f"[{self.severity}] [{status}] {self.title}"

    def resolve(self, user):
        """
        Marks this alert as resolved by user.
        """
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at'])
