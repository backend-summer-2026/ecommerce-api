from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.payments.models import (
    Payment,
    PaymentTransaction,
    Refund,
    SavedCard,
)


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    can_delete = False
    fields = (
        'transaction_type',
        'amount',
        'status',
        'provider_transaction_id',
        'idempotency_key',
        'ip_address',
        'created_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    fields = (
        'refund_number',
        'amount',
        'currency',
        'status',
        'reason',
        'created_by',
        'created_at',
    )
    readonly_fields = ('refund_number', 'amount', 'currency', 'status', 'created_by', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_number',
        'order_link',
        'user_display',
        'amount_display',
        'provider_badge',
        'status_badge',
        'paid_at',
        'created_at',
    )
    list_filter = (
        'status',
        'provider',
        'currency',
        'created_at',
    )
    search_fields = (
        'payment_number',
        'order__order_number',
        'user__email',
        'user__phone_number',
        'provider_transaction_id',
    )
    readonly_fields = (
        'payment_number',
        'order_link',
        'amount',
        'currency',
        'fee_amount',
        'refunded_amount',
        'paid_at',
        'failed_at',
        'cancelled_at',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (
            'General Info',
            {
                'fields': (
                    'payment_number',
                    'order',
                    'user',
                    'amount',
                    'currency',
                    'provider',
                    'status',
                )
            },
        ),
        (
            'Gateway & Reconciliation',
            {
                'fields': (
                    'provider_transaction_id',
                    'provider_state',
                    'fee_amount',
                    'refunded_amount',
                    'checkout_url',
                    'metadata',
                )
            },
        ),
        (
            'Status & Timestamps',
            {
                'fields': (
                    'failure_reason',
                    'paid_at',
                    'failed_at',
                    'cancelled_at',
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )
    inlines = [PaymentTransactionInline, RefundInline]

    @admin.display(description='Order')
    def order_link(self, obj: Payment):
        if not obj.order:
            return '-'
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)

    @admin.display(description='Customer')
    def user_display(self, obj: Payment):
        if not obj.user:
            return 'Guest / Deleted'
        return obj.user.email or obj.user.phone_number

    @admin.display(description='Amount', ordering='amount')
    def amount_display(self, obj: Payment):
        return f"{obj.amount:,.2f} {obj.currency}"

    @admin.display(description='Provider', ordering='provider')
    def provider_badge(self, obj: Payment):
        colors = {
            Payment.PaymentProvider.PAYME: '#18a0fb',
            Payment.PaymentProvider.CLICK: '#008ae4',
            Payment.PaymentProvider.UZUM: '#7b2cbf',
            Payment.PaymentProvider.CASH_ON_DELIVERY: '#2b9348',
            Payment.PaymentProvider.CARD_ON_DELIVERY: '#0077b6',
        }
        color = colors.get(obj.provider, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_provider_display(),
        )

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj: Payment):
        colors = {
            Payment.PaymentStatus.PENDING: '#f59e0b',
            Payment.PaymentStatus.PROCESSING: '#3b82f6',
            Payment.PaymentStatus.SUCCESS: '#10b981',
            Payment.PaymentStatus.FAILED: '#ef4444',
            Payment.PaymentStatus.CANCELLED: '#6b7280',
            Payment.PaymentStatus.REFUNDED: '#8b5cf6',
            Payment.PaymentStatus.PARTIALLY_REFUNDED: '#d97706',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'payment_link',
        'transaction_type',
        'amount_display',
        'status_badge',
        'provider_transaction_id',
        'ip_address',
        'created_at',
    )
    list_filter = (
        'transaction_type',
        'status',
        'created_at',
    )
    search_fields = (
        'payment__payment_number',
        'idempotency_key',
        'provider_transaction_id',
        'ip_address',
    )
    readonly_fields = (
        'payment',
        'transaction_type',
        'amount',
        'status',
        'idempotency_key',
        'provider_transaction_id',
        'request_payload',
        'response_payload',
        'error_code',
        'error_message',
        'ip_address',
        'created_at',
    )

    @admin.display(description='Payment')
    def payment_link(self, obj: PaymentTransaction):
        url = reverse('admin:payments_payment_change', args=[obj.payment.pk])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)

    @admin.display(description='Amount', ordering='amount')
    def amount_display(self, obj: PaymentTransaction):
        return f"{obj.amount:,.2f}"

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj: PaymentTransaction):
        colors = {
            PaymentTransaction.TransactionStatus.PENDING: '#f59e0b',
            PaymentTransaction.TransactionStatus.SUCCESS: '#10b981',
            PaymentTransaction.TransactionStatus.FAILED: '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        'refund_number',
        'payment_link',
        'order_link',
        'amount_display',
        'status_badge',
        'created_by',
        'processed_at',
        'created_at',
    )
    list_filter = (
        'status',
        'currency',
        'created_at',
    )
    search_fields = (
        'refund_number',
        'payment__payment_number',
        'order__order_number',
        'provider_refund_id',
    )
    readonly_fields = (
        'refund_number',
        'payment',
        'order',
        'amount',
        'currency',
        'created_by',
        'processed_at',
        'created_at',
        'updated_at',
    )

    @admin.display(description='Payment')
    def payment_link(self, obj: Refund):
        url = reverse('admin:payments_payment_change', args=[obj.payment.pk])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)

    @admin.display(description='Order')
    def order_link(self, obj: Refund):
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)

    @admin.display(description='Amount', ordering='amount')
    def amount_display(self, obj: Refund):
        return f"{obj.amount:,.2f} {obj.currency}"

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj: Refund):
        colors = {
            Refund.RefundStatus.PENDING: '#f59e0b',
            Refund.RefundStatus.COMPLETED: '#10b981',
            Refund.RefundStatus.FAILED: '#ef4444',
            Refund.RefundStatus.CANCELLED: '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(SavedCard)
class SavedCardAdmin(admin.ModelAdmin):
    list_display = (
        'user_display',
        'card_mask',
        'card_type_badge',
        'provider',
        'expiry_display',
        'is_default',
        'is_verified',
        'created_at',
    )
    list_filter = (
        'provider',
        'card_type',
        'is_default',
        'is_verified',
    )
    search_fields = (
        'user__email',
        'user__phone_number',
        'card_mask',
        'card_holder',
    )
    readonly_fields = (
        'card_token',
        'created_at',
        'updated_at',
    )

    @admin.display(description='User')
    def user_display(self, obj: SavedCard):
        return obj.user.email or obj.user.phone_number

    @admin.display(description='Card Type')
    def card_type_badge(self, obj: SavedCard):
        colors = {
            SavedCard.CardType.UZCARD: '#0052cc',
            SavedCard.CardType.HUMO: '#ffab00',
            SavedCard.CardType.VISA: '#003087',
            SavedCard.CardType.MASTERCARD: '#eb001b',
            SavedCard.CardType.OTHER: '#6b7280',
        }
        color = colors.get(obj.card_type, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px;">{}</span>',
            color,
            obj.get_card_type_display(),
        )

    @admin.display(description='Expiry')
    def expiry_display(self, obj: SavedCard):
        return f"{obj.expire_month}/{obj.expire_year}"
