from django.contrib import admin
from django.utils.html import format_html

from apps.carts.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ('variant',)
    fields = (
        'variant',
        'quantity',
        'unit_price_at_addition',
        'get_current_price',
        'get_total_price',
        'get_availability',
        'created_at',
    )
    readonly_fields = (
        'unit_price_at_addition',
        'get_current_price',
        'get_total_price',
        'get_availability',
        'created_at',
    )

    @admin.display(description='Current Unit Price')
    def get_current_price(self, obj):
        return f"{obj.current_unit_price:,.2f} UZS"

    @admin.display(description='Total Price')
    def get_total_price(self, obj):
        return f"{obj.total_price:,.2f} UZS"

    @admin.display(description='Stock Status')
    def get_availability(self, obj):
        if obj.is_available:
            return format_html('<span style="color: green; font-weight: bold;">✔ In Stock</span>')
        return format_html('<span style="color: red; font-weight: bold;">✖ Unavailable / Out of Stock</span>')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id_short',
        'user',
        'session_key',
        'status',
        'total_items_display',
        'total_price_display',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__email', 'user__first_name', 'session_key')
    readonly_fields = (
        'id',
        'total_items_display',
        'unique_items_display',
        'subtotal_display',
        'total_price_display',
        'total_discount_display',
        'has_unavailable_items_display',
        'created_at',
        'updated_at',
    )
    inlines = [CartItemInline]
    fieldsets = (
        ('Cart Details', {
            'fields': ('id', 'user', 'session_key', 'status'),
        }),
        ('Totals & Financials', {
            'fields': (
                'total_items_display',
                'unique_items_display',
                'subtotal_display',
                'total_price_display',
                'total_discount_display',
                'has_unavailable_items_display',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Cart ID')
    def id_short(self, obj):
        return str(obj.id)[:8]

    @admin.display(description='Total Items')
    def total_items_display(self, obj):
        return obj.total_items

    @admin.display(description='Distinct SKUs')
    def unique_items_display(self, obj):
        return obj.unique_items_count

    @admin.display(description='Subtotal')
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,.2f} UZS"

    @admin.display(description='Total Price')
    def total_price_display(self, obj):
        return f"{obj.total_price:,.2f} UZS"

    @admin.display(description='Total Discount')
    def total_discount_display(self, obj):
        return f"{obj.total_discount:,.2f} UZS"

    @admin.display(description='Availability')
    def has_unavailable_items_display(self, obj):
        if obj.has_unavailable_items:
            return format_html('<span style="color: red; font-weight: bold;">⚠ Contains unavailable items</span>')
        return format_html('<span style="color: green; font-weight: bold;">✔ All items available</span>')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cart',
        'variant',
        'quantity',
        'unit_price_at_addition',
        'current_unit_price_display',
        'total_price_display',
        'created_at',
    )
    list_filter = ('created_at',)
    search_fields = ('cart__id', 'variant__sku', 'variant__product__name')
    raw_id_fields = ('cart', 'variant')
    readonly_fields = ('unit_price_at_addition', 'created_at', 'updated_at')

    @admin.display(description='Current Unit Price')
    def current_unit_price_display(self, obj):
        return f"{obj.current_unit_price:,.2f} UZS"

    @admin.display(description='Total Price')
    def total_price_display(self, obj):
        return f"{obj.total_price:,.2f} UZS"
