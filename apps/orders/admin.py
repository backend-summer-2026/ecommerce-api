from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ('variant',)
    fields = (
        'variant',
        'product_name',
        'variant_sku',
        'variant_attributes_display',
        'unit_price',
        'quantity',
        'total_price',
    )
    readonly_fields = ('total_price',)


class OrderAddressInline(admin.StackedInline):
    model = OrderAddress
    can_delete = False
    extra = 0
    fields = (
        ('recipient_name', 'phone_number', 'alternative_phone_number'),
        ('region', 'district'),
        ('street_address', 'apartment_office', 'postal_code'),
        ('landmark', 'latitude', 'longitude'),
        'delivery_instructions',
    )


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    fields = ('old_status', 'new_status', 'comment', 'created_by', 'is_customer_visible', 'created_at')
    readonly_fields = ('old_status', 'new_status', 'comment', 'created_by', 'is_customer_visible', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer_display',
        'status_badge',
        'payment_status_badge',
        'payment_method',
        'shipping_method',
        'total_items_display',
        'total_price_display',
        'created_at',
    )
    list_filter = (
        'status',
        'payment_status',
        'payment_method',
        'shipping_method',
        'created_at',
    )
    search_fields = (
        'order_number',
        'user__email',
        'user__first_name',
        'user__last_name',
        'shipping_address__recipient_name',
        'shipping_address__phone_number',
        'tracking_number',
    )
    readonly_fields = (
        'order_number',
        'subtotal_display',
        'total_price_display',
        'total_items_display',
        'created_at',
        'updated_at',
        'paid_at',
        'delivered_at',
        'cancelled_at',
    )
    raw_id_fields = ('user', 'cart', 'coupon')
    inlines = [OrderAddressInline, OrderItemInline, OrderStatusHistoryInline]

    fieldsets = (
        ('Order Identification', {
            'fields': (
                'order_number',
                'user',
                'cart',
                'coupon',
                'tracking_number',
            ),
        }),
        ('Status & Fulfilment', {
            'fields': (
                'status',
                'payment_status',
                'payment_method',
                'shipping_method',
            ),
        }),
        ('Financial Totals', {
            'fields': (
                'subtotal_display',
                'shipping_fee',
                'discount_amount',
                'total_price_display',
                'currency',
            ),
        }),
        ('Customer & Administrative Notes', {
            'fields': (
                'customer_notes',
                'cancellation_reason',
                'admin_notes',
            ),
        }),
        ('Lifecycle Milestones', {
            'fields': (
                'paid_at',
                'delivered_at',
                'cancelled_at',
                'created_at',
                'updated_at',
            ),
        }),
    )

    @admin.display(description='Customer')
    def customer_display(self, obj):
        if obj.user:
            return obj.user.email
        if hasattr(obj, 'shipping_address') and obj.shipping_address:
            return f"Guest ({obj.shipping_address.recipient_name})"
        return "Guest"

    @admin.display(description='Status')
    def status_badge(self, obj):
        color_map = {
            Order.OrderStatus.PENDING: '#f39c12',  # Orange
            Order.OrderStatus.AWAITING_PAYMENT: '#e67e22',  # Amber
            Order.OrderStatus.CONFIRMED: '#27ae60',  # Green
            Order.OrderStatus.PROCESSING: '#2980b9',  # Blue
            Order.OrderStatus.SHIPPED: '#8e44ad',  # Purple
            Order.OrderStatus.DELIVERED: '#2ecc71',  # Bright green
            Order.OrderStatus.CANCELLED: '#c0392b',  # Red
            Order.OrderStatus.REFUNDED: '#7f8c8d',  # Grey
        }
        color = color_map.get(obj.status, '#333333')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description='Payment')
    def payment_status_badge(self, obj):
        color_map = {
            Order.PaymentStatus.PENDING: '#f39c12',
            Order.PaymentStatus.PAID: '#27ae60',
            Order.PaymentStatus.FAILED: '#c0392b',
            Order.PaymentStatus.REFUNDED: '#7f8c8d',
            Order.PaymentStatus.PARTIALLY_REFUNDED: '#d35400',
        }
        color = color_map.get(obj.payment_status, '#333333')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_payment_status_display(),
        )

    @admin.display(description='Items')
    def total_items_display(self, obj):
        return obj.total_items

    @admin.display(description='Subtotal')
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,.2f} {obj.currency}"

    @admin.display(description='Total')
    def total_price_display(self, obj):
        return format_html(
            '<strong>{} {}</strong>',
            f"{obj.total_price:,.2f}",
            obj.currency,
        )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'discount_display',
        'min_order_amount_display',
        'usage_display',
        'validity_display',
        'is_active_badge',
        'created_at',
    )
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('code',)
    readonly_fields = ('used_count', 'created_at', 'updated_at')

    fieldsets = (
        ('Coupon Code & Type', {
            'fields': (
                'code',
                'discount_type',
                'discount_value',
                'min_order_amount',
                'max_discount_amount',
            ),
        }),
        ('Redemption Limits', {
            'fields': (
                'usage_limit',
                'usage_limit_per_user',
                'used_count',
            ),
        }),
        ('Validity Window & Status', {
            'fields': (
                'valid_from',
                'valid_until',
                'is_active',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Discount')
    def discount_display(self, obj):
        if obj.discount_type == Coupon.DiscountType.PERCENTAGE:
            cap = f" (max {obj.max_discount_amount:,.2f})" if obj.max_discount_amount else ""
            return f"{obj.discount_value}%{cap}"
        return f"{obj.discount_value:,.2f} UZS"

    @admin.display(description='Min Order')
    def min_order_amount_display(self, obj):
        return f"{obj.min_order_amount:,.2f} UZS"

    @admin.display(description='Usage Count')
    def usage_display(self, obj):
        limit = obj.usage_limit if obj.usage_limit is not None else "∞"
        return f"{obj.used_count} / {limit}"

    @admin.display(description='Validity Window')
    def validity_display(self, obj):
        return f"{obj.valid_from:%Y-%m-%d} to {obj.valid_until:%Y-%m-%d}"

    @admin.display(description='Active')
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✔ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✖ Inactive</span>')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order', 'discount_amount_display', 'used_at')
    list_filter = ('used_at',)
    search_fields = ('coupon__code', 'user__email', 'order__order_number')
    readonly_fields = ('coupon', 'user', 'order', 'discount_amount', 'used_at')

    @admin.display(description='Discount Granted')
    def discount_amount_display(self, obj):
        return f"{obj.discount_amount:,.2f} UZS"
