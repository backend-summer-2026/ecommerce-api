from decimal import Decimal

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderAddress,
    OrderItem,
    OrderStatusHistory,
)


def order_status_badge(status: str, display_text: str = None) -> str:
    """
    Renders a modern Bootstrap 4 badge with FontAwesome icon for Order status.
    """
    default_labels = dict(Order.OrderStatus.choices)
    label = display_text or default_labels.get(status, status)
    badge_config = {
        Order.OrderStatus.PENDING: ('badge-warning', 'fas fa-clock'),
        Order.OrderStatus.AWAITING_PAYMENT: ('badge-info', 'fas fa-hourglass-half'),
        Order.OrderStatus.CONFIRMED: ('badge-primary', 'fas fa-check-circle'),
        Order.OrderStatus.PROCESSING: ('badge-secondary', 'fas fa-box'),
        Order.OrderStatus.SHIPPED: ('badge-dark', 'fas fa-shipping-fast'),
        Order.OrderStatus.DELIVERED: ('badge-success', 'fas fa-check-double'),
        Order.OrderStatus.CANCELLED: ('badge-danger', 'fas fa-times-circle'),
        Order.OrderStatus.REFUNDED: ('badge-secondary', 'fas fa-undo'),
    }
    css_class, icon = badge_config.get(status, ('badge-light border', 'fas fa-circle'))
    return format_html(
        '<span class="badge {}" style="font-size: 11px; padding: 4px 8px;">'
        '<i class="{} mr-1"></i>{}'
        '</span>',
        css_class,
        icon,
        label,
    )


def payment_status_badge(status: str, display_text: str = None) -> str:
    """
    Renders a modern Bootstrap 4 badge with FontAwesome icon for Payment status.
    """
    default_labels = dict(Order.PaymentStatus.choices)
    label = display_text or default_labels.get(status, status)
    badge_config = {
        Order.PaymentStatus.PAID: ('badge-success', 'fas fa-check-circle'),
        Order.PaymentStatus.PENDING: ('badge-warning', 'fas fa-clock'),
        Order.PaymentStatus.PARTIALLY_REFUNDED: ('badge-info', 'fas fa-adjust'),
        Order.PaymentStatus.REFUNDED: ('badge-secondary', 'fas fa-undo'),
        Order.PaymentStatus.FAILED: ('badge-danger', 'fas fa-exclamation-triangle'),
    }
    css_class, icon = badge_config.get(status, ('badge-light border', 'fas fa-circle'))
    return format_html(
        '<span class="badge {}" style="font-size: 11px; padding: 4px 8px;">'
        '<i class="{} mr-1"></i>{}'
        '</span>',
        css_class,
        icon,
        label,
    )


def payment_method_badge(method: str, display_text: str = None) -> str:
    """
    Renders styled badges for different payment gateways and methods.
    """
    default_labels = dict(Order.PaymentMethod.choices)
    label = display_text or default_labels.get(method, method)
    badge_config = {
        Order.PaymentMethod.PAYME: ('badge-info', 'fas fa-credit-card'),
        Order.PaymentMethod.CLICK: ('badge-primary', 'fas fa-mobile-alt'),
        Order.PaymentMethod.UZUM: ('text-white', 'fas fa-university', '#6c2bd9'),
        Order.PaymentMethod.CASH_ON_DELIVERY: ('badge-secondary', 'fas fa-money-bill-wave'),
        Order.PaymentMethod.CARD_ON_DELIVERY: ('badge-secondary', 'fas fa-credit-card'),
    }
    config = badge_config.get(method)
    if config:
        if len(config) == 3:
            css_class, icon, bg_color = config
            return format_html(
                '<span class="badge {}" style="background-color: {}; font-size: 11px; padding: 4px 8px;">'
                '<i class="{} mr-1"></i>{}'
                '</span>',
                css_class,
                bg_color,
                icon,
                label,
            )
        css_class, icon = config
        return format_html(
            '<span class="badge {}" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="{} mr-1"></i>{}'
            '</span>',
            css_class,
            icon,
            label,
        )
    return format_html('<span class="badge badge-light border">{}</span>', label)


def shipping_method_badge(method: str, display_text: str = None) -> str:
    """
    Renders styled badges for shipping methods.
    """
    default_labels = {
        Order.ShippingMethod.STANDARD: 'Standart yetkazish',
        Order.ShippingMethod.EXPRESS: 'Tezkor yetkazish',
        Order.ShippingMethod.PICKUP: 'Olib ketish',
    }
    label = display_text or default_labels.get(method, method)
    badge_config = {
        Order.ShippingMethod.STANDARD: ('badge-light border', 'fas fa-truck'),
        Order.ShippingMethod.EXPRESS: ('badge-warning text-dark', 'fas fa-bolt'),
        Order.ShippingMethod.PICKUP: ('badge-info', 'fas fa-store'),
    }
    css_class, icon = badge_config.get(method, ('badge-light border', 'fas fa-box'))
    return format_html(
        '<span class="badge {}" style="font-size: 11px; padding: 4px 8px;">'
        '<i class="{} mr-1"></i>{}'
        '</span>',
        css_class,
        icon,
        label,
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ('variant',)
    fields = (
        'variant_link',
        'product_name',
        'variant_sku',
        'variant_attributes_display',
        'unit_price_display',
        'quantity',
        'total_price_display',
    )
    readonly_fields = ('variant_link', 'unit_price_display', 'total_price_display')

    @admin.display(description='Variant')
    def variant_link(self, obj):
        if obj and obj.variant_id:
            url = reverse('admin:products_productvariant_change', args=[obj.variant_id])
            variant_title = str(obj.variant)
            sku = obj.variant_sku or (obj.variant.sku if hasattr(obj.variant, 'sku') else "")
            sku_display = f" ({sku})" if sku else ""
            return format_html(
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-primary">'
                '<i class="fas fa-external-link-alt mr-1"></i> {}{}</a>',
                url,
                variant_title,
                sku_display,
            )
        return "-"

    @admin.display(description='Birlik narxi')
    def unit_price_display(self, obj):
        if obj and obj.unit_price is not None:
            return f"{obj.unit_price:,.2f} UZS"
        return "-"

    @admin.display(description='Jami summa')
    def total_price_display(self, obj):
        if obj and obj.total_price is not None:
            return format_html('<strong>{} UZS</strong>', f"{obj.total_price:,.2f}")
        return "-"


class OrderAddressInline(admin.StackedInline):
    model = OrderAddress
    can_delete = False
    extra = 0
    fields = (
        ('recipient_name', 'phone_link', 'alternative_phone_number'),
        ('region', 'district'),
        ('street_address', 'apartment_office', 'postal_code'),
        ('landmark', 'map_link'),
        'delivery_instructions',
    )
    readonly_fields = ('phone_link', 'map_link')

    @admin.display(description='Telefon (Qo\'ng\'iroq)')
    def phone_link(self, obj):
        if obj and obj.phone_number:
            return format_html(
                '<a href="tel:{}" class="btn btn-xs btn-outline-success font-weight-bold">'
                '<i class="fas fa-phone mr-1"></i> {}</a>',
                obj.phone_number,
                obj.phone_number,
            )
        return "-"

    @admin.display(description='Xaritada joylashuv')
    def map_link(self, obj):
        if obj and obj.latitude and obj.longitude:
            google_url = f"https://www.google.com/maps/search/?api=1&query={obj.latitude},{obj.longitude}"
            yandex_url = f"https://yandex.com/maps/?pt={obj.longitude},{obj.latitude}&z=16&l=map"
            return format_html(
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-danger mr-1">'
                '<i class="fab fa-google mr-1"></i> Google Maps</a>'
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-warning">'
                '<i class="fas fa-map-marked-alt mr-1"></i> Yandex Maps</a>'
                '<span class="text-muted ml-2 font-italic">({}, {})</span>',
                google_url,
                yandex_url,
                obj.latitude,
                obj.longitude,
            )
        return format_html('<span class="text-muted"><i class="fas fa-map-marker-slash mr-1"></i> Koordinatalar kiritilmagan</span>')


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    fields = (
        'created_at',
        'old_status_badge',
        'arrow_icon',
        'new_status_badge',
        'comment',
        'created_by_display',
        'is_customer_visible',
    )
    readonly_fields = (
        'created_at',
        'old_status_badge',
        'arrow_icon',
        'new_status_badge',
        'comment',
        'created_by_display',
        'is_customer_visible',
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Eski holat')
    def old_status_badge(self, obj):
        if not obj or not obj.old_status:
            return format_html('<span class="badge badge-light border text-muted">Boshlang\'ich</span>')
        return order_status_badge(obj.old_status, obj.get_old_status_display())

    @admin.display(description='')
    def arrow_icon(self, obj):
        return format_html('<i class="fas fa-arrow-right text-muted"></i>')

    @admin.display(description='Yangi holat')
    def new_status_badge(self, obj):
        if not obj:
            return "-"
        return order_status_badge(obj.new_status, obj.get_new_status_display())

    @admin.display(description='Bajaruvchi')
    def created_by_display(self, obj):
        if obj and obj.created_by:
            user_url = reverse('admin:users_user_change', args=[obj.created_by_id])
            return format_html(
                '<a href="{}" target="_blank"><i class="fas fa-user-shield text-info mr-1"></i> {}</a>',
                user_url,
                obj.created_by.email,
            )
        return format_html('<span class="badge badge-light text-muted"><i class="fas fa-robot mr-1"></i> Tizim (Avtomatik)</span>')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    changeform_format = "horizontal_tabs"
    date_hierarchy = 'created_at'
    list_per_page = 25
    list_select_related = ('user', 'cart', 'coupon')

    list_display = (
        'order_number_display',
        'customer_display',
        'status_badge',
        'payment_status_badge',
        'payment_method_badge',
        'shipping_method_badge',
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
        'user__phone_number',
        'shipping_address__recipient_name',
        'shipping_address__phone_number',
        'tracking_number',
    )
    readonly_fields = (
        'order_number',
        'customer_link',
        'cart_link',
        'coupon_link',
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

    actions = [
        'mark_as_confirmed',
        'mark_as_processing',
        'mark_as_shipped',
        'mark_as_delivered',
        'mark_as_paid',
        'cancel_orders',
    ]

    fieldsets = (
        ("📋 Buyurtma identifikatsiyasi", {
            'fields': (
                'order_number',
                'user',
                'customer_link',
                'cart',
                'cart_link',
                'coupon',
                'coupon_link',
                'tracking_number',
            ),
        }),
        ("🔄 Holat va Yetkazib berish", {
            'fields': (
                'status',
                'payment_status',
                'payment_method',
                'shipping_method',
            ),
        }),
        ("💰 Moliyaviy hisob-kitob", {
            'fields': (
                'subtotal_display',
                'shipping_fee',
                'discount_amount',
                'total_price_display',
                'currency',
            ),
        }),
        ("📝 Izohlar va Eslatmalar", {
            'fields': (
                'customer_notes',
                'admin_notes',
                'cancellation_reason',
            ),
        }),
        ("⏱ Tizim vaqtlari (Audit)", {
            'classes': ('collapse',),
            'fields': (
                'paid_at',
                'delivered_at',
                'cancelled_at',
                'created_at',
                'updated_at',
            ),
        }),
    )

    @admin.display(description='Buyurtma №', ordering='order_number')
    def order_number_display(self, obj):
        return format_html(
            '<strong class="text-primary"><i class="fas fa-shopping-bag mr-1"></i> {}</strong>',
            obj.order_number,
        )

    @admin.display(description='Mijoz')
    def customer_display(self, obj):
        if obj.user:
            user_url = reverse('admin:users_user_change', args=[obj.user_id])
            name = getattr(obj.user, 'full_name', None) or obj.user.email
            return format_html(
                '<a href="{}" title="Profilni ochish"><i class="fas fa-user-circle text-primary mr-1"></i> {}</a>',
                user_url,
                name,
            )
        if hasattr(obj, 'shipping_address') and obj.shipping_address:
            return format_html(
                '<span class="badge badge-light border text-dark">'
                '<i class="fas fa-user-secret mr-1"></i> Mehmon ({})</span>',
                obj.shipping_address.recipient_name,
            )
        return format_html('<span class="badge badge-light text-muted"><i class="fas fa-user-secret mr-1"></i> Mehmon</span>')

    @admin.display(description='Mijoz profili')
    def customer_link(self, obj):
        if obj.user:
            user_url = reverse('admin:users_user_change', args=[obj.user_id])
            name = getattr(obj.user, 'full_name', None) or obj.user.email
            return format_html(
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-info">'
                '<i class="fas fa-external-link-alt mr-1"></i> {} ({})</a>',
                user_url,
                name,
                obj.user.email,
            )
        return "-"

    @admin.display(description='Savatcha sahifasi')
    def cart_link(self, obj):
        if obj.cart_id:
            cart_url = reverse('admin:carts_cart_change', args=[obj.cart_id])
            return format_html(
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-secondary">'
                '<i class="fas fa-shopping-cart mr-1"></i> Savatcha #{}</a>',
                cart_url,
                obj.cart_id,
            )
        return "-"

    @admin.display(description='Kupon tafsiloti')
    def coupon_link(self, obj):
        if obj.coupon:
            coupon_url = reverse('admin:orders_coupon_change', args=[obj.coupon_id])
            return format_html(
                '<a href="{}" target="_blank" class="btn btn-xs btn-outline-success font-weight-bold">'
                '<i class="fas fa-tag mr-1"></i> {}</a>',
                coupon_url,
                obj.coupon.code,
            )
        return "-"

    @admin.display(description='Holat', ordering='status')
    def status_badge(self, obj):
        return order_status_badge(obj.status, obj.get_status_display())

    @admin.display(description="To'lov holati", ordering='payment_status')
    def payment_status_badge(self, obj):
        return payment_status_badge(obj.payment_status, obj.get_payment_status_display())

    @admin.display(description="To'lov usuli", ordering='payment_method')
    def payment_method_badge(self, obj):
        return payment_method_badge(obj.payment_method)

    @admin.display(description='Yetkazib berish', ordering='shipping_method')
    def shipping_method_badge(self, obj):
        return shipping_method_badge(obj.shipping_method)

    @admin.display(description='Mahsulotlar')
    def total_items_display(self, obj):
        return format_html(
            '<span class="badge badge-light border"><i class="fas fa-boxes text-secondary mr-1"></i> {} ta</span>',
            obj.total_items,
        )

    @admin.display(description='Oraliq summa')
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,.2f} {obj.currency}"

    @admin.display(description='Jami summa', ordering='total_price')
    def total_price_display(self, obj):
        return format_html(
            '<strong style="color: #2c3e50; font-size: 13px;">{} {}</strong>',
            f"{obj.total_price:,.2f}",
            obj.currency,
        )

    # ---------------------------------------------------------
    # Batch Admin Actions
    # ---------------------------------------------------------
    @admin.action(description="Tanlangan buyurtmalarni tasdiqlash (Confirmed)")
    def mark_as_confirmed(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status in [Order.OrderStatus.PENDING, Order.OrderStatus.AWAITING_PAYMENT]:
                order.transition_status(
                    new_status=Order.OrderStatus.CONFIRMED,
                    comment="Admin panel orqali tasdiqlandi",
                    user=request.user,
                    is_customer_visible=True,
                )
                count += 1
        self.message_user(request, f"{count} ta buyurtma tasdiqlandi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan buyurtmalarni tayyorlashga o'tkazish (Processing)")
    def mark_as_processing(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status == Order.OrderStatus.CONFIRMED:
                order.transition_status(
                    new_status=Order.OrderStatus.PROCESSING,
                    comment="Buyurtma omborda tayyorlanmoqda",
                    user=request.user,
                    is_customer_visible=True,
                )
                count += 1
        self.message_user(request, f"{count} ta buyurtma tayyorlash holatiga o'tkazildi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan buyurtmalarni yetkazishga jo'natish (Shipped)")
    def mark_as_shipped(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status in [Order.OrderStatus.CONFIRMED, Order.OrderStatus.PROCESSING]:
                order.transition_status(
                    new_status=Order.OrderStatus.SHIPPED,
                    comment="Buyurtma kurerga yetkazish uchun topshirildi",
                    user=request.user,
                    is_customer_visible=True,
                )
                count += 1
        self.message_user(request, f"{count} ta buyurtma yetkazish holatiga o'tkazildi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan buyurtmalarni yetkazilgan deb belgilash (Delivered)")
    def mark_as_delivered(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status == Order.OrderStatus.SHIPPED:
                order.transition_status(
                    new_status=Order.OrderStatus.DELIVERED,
                    comment="Mijozga muvaffaqiyatli yetkazib berildi",
                    user=request.user,
                    is_customer_visible=True,
                )
                count += 1
        self.message_user(request, f"{count} ta buyurtma yetkazildi deb belgilandi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan buyurtmalarni to'langan deb belgilash (Paid)")
    def mark_as_paid(self, request, queryset):
        count = 0
        for order in queryset:
            if order.payment_status != Order.PaymentStatus.PAID:
                order.mark_as_paid(user=request.user, comment="Admin tomonidan to'lov qabul qilindi")
                count += 1
        self.message_user(request, f"{count} ta buyurtma to'langan deb belgilandi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan buyurtmalarni bekor qilish (Cancel)")
    def cancel_orders(self, request, queryset):
        cancelled_count = 0
        failed_count = 0
        for order in queryset:
            if order.can_cancel:
                order.cancel(reason="Admin tomonidan bekor qilindi", user=request.user)
                cancelled_count += 1
            else:
                failed_count += 1
        if cancelled_count:
            self.message_user(request, f"{cancelled_count} ta buyurtma bekor qilindi.", level=messages.SUCCESS)
        if failed_count:
            self.message_user(
                request,
                f"{failed_count} ta buyurtmani bekor qilib bo'lmadi (chunki ular yetkazilgan yoki allaqachon bekor qilingan).",
                level=messages.WARNING,
            )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    changeform_format = "horizontal_tabs"
    date_hierarchy = 'valid_from'
    list_per_page = 25

    list_display = (
        'code_display',
        'discount_display',
        'min_order_amount_display',
        'usage_display',
        'validity_display',
        'is_active_badge',
        'created_at',
    )
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('code',)
    readonly_fields = ('used_count', 'usage_progress', 'created_at', 'updated_at')

    actions = ['activate_coupons', 'deactivate_coupons']

    fieldsets = (
        ("🎟 Kupon kodi va Turi", {
            'fields': (
                'code',
                'discount_type',
                'discount_value',
                'min_order_amount',
                'max_discount_amount',
            ),
        }),
        ("📊 Cheklovlar va Ishlatilish", {
            'fields': (
                'usage_limit',
                'usage_limit_per_user',
                'used_count',
                'usage_progress',
            ),
        }),
        ("⏳ Amal qilish muddati va Holati", {
            'fields': (
                'valid_from',
                'valid_until',
                'is_active',
            ),
        }),
        ("⏱ Tizim vaqtlari", {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Kupon kodi', ordering='code')
    def code_display(self, obj):
        return format_html(
            '<code style="font-weight: bold; font-size: 13px; color: #1e88e5;">'
            '<i class="fas fa-ticket-alt mr-1"></i>{}'
            '</code>',
            obj.code,
        )

    @admin.display(description='Chegirma', ordering='discount_value')
    def discount_display(self, obj):
        if obj.discount_type == Coupon.DiscountType.PERCENTAGE:
            cap = f" (maks. {obj.max_discount_amount:,.2f} UZS)" if obj.max_discount_amount else ""
            return format_html(
                '<span class="badge badge-info"><i class="fas fa-percent mr-1"></i> {}%{}</span>',
                obj.discount_value,
                cap,
            )
        return format_html(
            '<span class="badge badge-success"><i class="fas fa-money-bill mr-1"></i> {} UZS</span>',
            f"{obj.discount_value:,.2f}",
        )

    @admin.display(description='Min Buyurtma', ordering='min_order_amount')
    def min_order_amount_display(self, obj):
        return f"{obj.min_order_amount:,.2f} UZS"

    @admin.display(description='Ishlatilish')
    def usage_display(self, obj):
        limit = obj.usage_limit if obj.usage_limit is not None else "∞"
        if obj.usage_limit and obj.used_count >= obj.usage_limit:
            return format_html('<span class="badge badge-danger">{} / {} (To\'lgan)</span>', obj.used_count, limit)
        return format_html('<span class="badge badge-light border font-weight-bold">{} / {}</span>', obj.used_count, limit)

    @admin.display(description='Ishlatilish foizi')
    def usage_progress(self, obj):
        if not obj.usage_limit:
            return format_html('<span class="text-muted"><i class="fas fa-infinity mr-1"></i> Cheklanmagan ({} marta ishlatilgan)</span>', obj.used_count)
        percent = min(100, int((obj.used_count / obj.usage_limit) * 100))
        bar_class = "bg-success" if percent < 75 else ("bg-warning" if percent < 95 else "bg-danger")
        return format_html(
            '<div class="progress" style="height: 18px; width: 220px; border-radius: 4px;">'
            '<div class="progress-bar {}" role="progressbar" style="width: {}%;" aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100">'
            '{}% ({} / {})'
            '</div></div>',
            bar_class,
            percent,
            percent,
            percent,
            obj.used_count,
            obj.usage_limit,
        )

    @admin.display(description='Amal qilish muddati')
    def validity_display(self, obj):
        now = timezone.now()
        if now < obj.valid_from:
            badge = '<span class="badge badge-warning ml-1">Kelgusi</span>'
        elif now > obj.valid_until:
            badge = '<span class="badge badge-danger ml-1">Tugagan</span>'
        else:
            badge = '<span class="badge badge-success ml-1">Aktiv</span>'
        return format_html(
            '{} &mdash; {} {}',
            obj.valid_from.strftime('%Y-%m-%d %H:%M'),
            obj.valid_until.strftime('%Y-%m-%d %H:%M'),
            mark_safe(badge),
        )

    @admin.display(description='Holati', ordering='is_active')
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success"><i class="fas fa-check mr-1"></i> Faol</span>')
        return format_html('<span class="badge badge-danger"><i class="fas fa-times mr-1"></i> Nofaol</span>')

    @admin.action(description="Tanlangan kuponlarni faollashtirish")
    def activate_coupons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta kupon faollashtirildi.", level=messages.SUCCESS)

    @admin.action(description="Tanlangan kuponlarni nofaol qilish")
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta kupon nofaol qilindi.", level=messages.SUCCESS)


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_select_related = ('coupon', 'user', 'order')
    date_hierarchy = 'used_at'
    list_per_page = 25

    list_display = (
        'coupon_link',
        'user_link',
        'order_link',
        'discount_amount_display',
        'used_at',
    )
    list_filter = ('used_at',)
    search_fields = ('coupon__code', 'user__email', 'order__order_number')
    readonly_fields = ('coupon', 'user', 'order', 'discount_amount', 'used_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Kupon')
    def coupon_link(self, obj):
        if obj and obj.coupon:
            url = reverse('admin:orders_coupon_change', args=[obj.coupon_id])
            return format_html(
                '<a href="{}"><code class="text-primary font-weight-bold">'
                '<i class="fas fa-ticket-alt mr-1"></i>{}</code></a>',
                url,
                obj.coupon.code,
            )
        return "-"

    @admin.display(description='Foydalanuvchi')
    def user_link(self, obj):
        if obj and obj.user:
            url = reverse('admin:users_user_change', args=[obj.user_id])
            return format_html(
                '<a href="{}"><i class="fas fa-user-circle text-info mr-1"></i>{}</a>',
                url,
                obj.user.email,
            )
        return "-"

    @admin.display(description='Buyurtma')
    def order_link(self, obj):
        if obj and obj.order:
            url = reverse('admin:orders_order_change', args=[obj.order_id])
            return format_html(
                '<a href="{}" class="font-weight-bold text-dark">'
                '<i class="fas fa-shopping-bag mr-1 text-primary"></i>{}</a>',
                url,
                obj.order.order_number,
            )
        return "-"

    @admin.display(description='Berilgan chegirma')
    def discount_amount_display(self, obj):
        if obj and obj.discount_amount is not None:
            return format_html('<span class="badge badge-success">+{} UZS</span>', f"{obj.discount_amount:,.2f}")
        return "-"
