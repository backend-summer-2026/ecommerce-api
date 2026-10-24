from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.dashboard.models import (
    DailyMetricSnapshot,
    StaffActivityLog,
    StockMovementLog,
    OrderInternalNote,
    SystemAlert,
)


@admin.register(DailyMetricSnapshot)
class DailyMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'revenue_display',
        'total_orders',
        'completed_orders_count',
        'cancelled_orders_count',
        'aov_display',
        'new_customers_count',
        'total_items_sold',
        'refunded_display',
    )
    list_filter = ('date',)
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')
    actions = ['recalculate_metrics']

    @admin.display(description='Daromad', ordering='total_revenue')
    def revenue_display(self, obj):
        return f"${obj.total_revenue:,.2f}"

    @admin.display(description="O'rtacha Chek (AOV)", ordering='average_order_value')
    def aov_display(self, obj):
        return f"${obj.average_order_value:,.2f}"

    @admin.display(description='Qaytarilgan', ordering='refunded_amount')
    def refunded_display(self, obj):
        return f"${obj.refunded_amount:,.2f}"

    @admin.action(description="Tanlangan sanalar uchun metrikalarni qayta hisoblash")
    def recalculate_metrics(self, request, queryset):
        count = 0
        for snapshot in queryset:
            DailyMetricSnapshot.recalculate_for_date(snapshot.date)
            count += 1
        self.message_user(request, f"{count} ta sana uchun metrikalar qayta hisoblandi.")


@admin.register(StaffActivityLog)
class StaffActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'actor_display',
        'action_badge',
        'module_badge',
        'target_repr',
        'ip_address',
    )
    list_filter = ('action', 'module', 'created_at')
    search_fields = (
        'actor__email',
        'actor__first_name',
        'actor__last_name',
        'target_repr',
        'description',
        'ip_address',
    )
    readonly_fields = (
        'actor',
        'action',
        'module',
        'target_model',
        'target_id',
        'target_repr',
        'description',
        'changes',
        'ip_address',
        'user_agent',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Foydalanuvchi')
    def actor_display(self, obj):
        return obj.actor.email if obj.actor else 'Tizim (System)'

    @admin.display(description='Amal')
    def action_badge(self, obj):
        colors = {
            StaffActivityLog.ActivityAction.CREATE: '#10B981',  # green
            StaffActivityLog.ActivityAction.UPDATE: '#3B82F6',  # blue
            StaffActivityLog.ActivityAction.DELETE: '#EF4444',  # red
            StaffActivityLog.ActivityAction.STATUS_CHANGE: '#F59E0B',  # amber
            StaffActivityLog.ActivityAction.STOCK_ADJUSTMENT: '#8B5CF6',  # purple
            StaffActivityLog.ActivityAction.REFUND: '#EC4899',  # pink
            StaffActivityLog.ActivityAction.LOGIN: '#06B6D4',  # cyan
            StaffActivityLog.ActivityAction.EXPORT: '#6B7280',  # gray
        }
        bg = colors.get(obj.action, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            bg,
            obj.get_action_display(),
        )

    @admin.display(description='Modul')
    def module_badge(self, obj):
        return format_html(
            '<span style="background-color: #374151; color: #F3F4F6; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_module_display(),
        )


@admin.register(StockMovementLog)
class StockMovementLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'variant_sku',
        'movement_type_badge',
        'quantity_delta_display',
        'previous_quantity',
        'new_quantity',
        'actor_display',
        'reference_order',
    )
    list_filter = ('movement_type', 'created_at')
    search_fields = (
        'variant__sku',
        'variant__product__name',
        'reason',
        'actor__email',
        'reference_order__order_number',
    )
    readonly_fields = (
        'variant',
        'actor',
        'movement_type',
        'quantity_delta',
        'previous_quantity',
        'new_quantity',
        'reference_order',
        'reason',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='SKU')
    def variant_sku(self, obj):
        return obj.variant.sku

    @admin.display(description='Xodim')
    def actor_display(self, obj):
        return obj.actor.email if obj.actor else 'Avtomatlashtirilgan'

    @admin.display(description='Harakat turi')
    def movement_type_badge(self, obj):
        colors = {
            StockMovementLog.StockMovementType.INCOMING: '#10B981',
            StockMovementLog.StockMovementType.OUTGOING: '#3B82F6',
            StockMovementLog.StockMovementType.ADJUSTMENT: '#8B5CF6',
            StockMovementLog.StockMovementType.RETURN: '#06B6D4',
            StockMovementLog.StockMovementType.DAMAGED: '#EF4444',
            StockMovementLog.StockMovementType.RESERVED: '#F59E0B',
        }
        bg = colors.get(obj.movement_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            bg,
            obj.get_movement_type_display(),
        )

    @admin.display(description="O'zgarish")
    def quantity_delta_display(self, obj):
        color = '#10B981' if obj.quantity_delta > 0 else '#EF4444'
        prefix = '+' if obj.quantity_delta > 0 else ''
        delta_str = f"{prefix}{obj.quantity_delta:,}"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            delta_str,
        )


@admin.register(OrderInternalNote)
class OrderInternalNoteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order_number_display',
        'author',
        'short_note',
        'is_pinned',
        'created_at',
    )
    list_filter = ('is_pinned', 'created_at')
    search_fields = (
        'order__order_number',
        'author__email',
        'note',
    )
    list_editable = ('is_pinned',)
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Buyurtma raqami')
    def order_number_display(self, obj):
        return obj.order.order_number

    @admin.display(description='Izoh matni')
    def short_note(self, obj):
        if len(obj.note) > 60:
            return obj.note[:57] + '...'
        return obj.note


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'severity_badge',
        'alert_type_display',
        'title',
        'resolution_status',
        'resolved_by',
        'resolved_at',
    )
    list_filter = ('severity', 'alert_type', 'is_resolved', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at',)
    actions = ['mark_as_resolved']

    @admin.display(description='Daraja')
    def severity_badge(self, obj):
        colors = {
            SystemAlert.AlertSeverity.INFO: '#3B82F6',
            SystemAlert.AlertSeverity.WARNING: '#F59E0B',
            SystemAlert.AlertSeverity.CRITICAL: '#EF4444',
        }
        bg = colors.get(obj.severity, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            bg,
            obj.get_severity_display(),
        )

    @admin.display(description='Turi')
    def alert_type_display(self, obj):
        return obj.get_alert_type_display()

    @admin.display(description='Holati')
    def resolution_status(self, obj):
        if obj.is_resolved:
            return format_html('<span style="color: #10B981; font-weight: bold;">✔ Bartaraf etilgan</span>')
        return format_html('<span style="color: #EF4444; font-weight: bold;">● Faol ogohlantirish</span>')

    @admin.action(description="Tanlangan ogohlantirishlarni bartaraf etilgan deb belgilash")
    def mark_as_resolved(self, request, queryset):
        now = timezone.now()
        count = queryset.update(is_resolved=True, resolved_by=request.user, resolved_at=now)
        self.message_user(request, f"{count} ta ogohlantirish bartaraf etildi.")
