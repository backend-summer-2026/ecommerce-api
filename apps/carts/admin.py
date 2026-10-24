from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, F, Q, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.carts.models import Cart, CartItem


def get_product_thumbnail(variant):
    """
    Renders a 36x36px image thumbnail for a product variant or product fallback.
    Returns a clean placeholder if no image exists.
    """
    if not variant:
        return mark_safe(
            '<span style="display:inline-block; width:36px; height:36px; line-height:36px; text-align:center; '
            'background:#e9ecef; border-radius:4px; color:#6c757d;"><i class="fas fa-box"></i></span>'
        )

    media_obj = variant.media.filter(media_type='image').first()
    if not media_obj and hasattr(variant, 'product'):
        media_obj = variant.product.media.filter(media_type='image', is_main=True).first()
        if not media_obj:
            media_obj = variant.product.media.filter(media_type='image').first()

    if media_obj and media_obj.file:
        try:
            return format_html(
                '<img src="{}" style="width:36px; height:36px; object-fit:cover; border-radius:4px; '
                'border:1px solid #dee2e6; box-shadow:0 1px 2px rgba(0,0,0,0.05);" />',
                media_obj.file.url,
            )
        except Exception:
            pass

    return mark_safe(
        '<span style="display:inline-block; width:36px; height:36px; line-height:36px; text-align:center; '
        'background:#e9ecef; border-radius:4px; color:#6c757d;"><i class="fas fa-box"></i></span>'
    )


class CartOwnerTypeFilter(admin.SimpleListFilter):
    """
    Filters carts by owner type: Registered user vs Guest shopper.
    """
    title = 'Foydalanuvchi turi'
    parameter_name = 'owner_type'

    def lookups(self, request, model_admin):
        return (
            ('registered', 'Ro\'yxatdan o\'tgan (User)'),
            ('guest', 'Mehmon (Guest session)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'registered':
            return queryset.filter(user__isnull=False)
        if self.value() == 'guest':
            return queryset.filter(user__isnull=True)
        return queryset


class CartHasItemsFilter(admin.SimpleListFilter):
    """
    Filters carts by whether they contain items or are empty.
    """
    title = 'Savat holati (Mahsulotlar)'
    parameter_name = 'has_items'

    def lookups(self, request, model_admin):
        return (
            ('with_items', 'Mahsulotlari bor'),
            ('empty', 'Bo\'sh savat'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'with_items':
            return queryset.filter(items__isnull=False).distinct()
        if self.value() == 'empty':
            return queryset.filter(items__isnull=True)
        return queryset


class CartAvailabilityFilter(admin.SimpleListFilter):
    """
    Filters carts by availability status of products within the cart.
    """
    title = 'Tovarlar mavjudligi'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('available', 'Barchasi sotuvda mavjud'),
            ('issues', 'Mavjud bo\'lmagan tovarlar mavjud'),
        )

    def queryset(self, request, queryset):
        issue_condition = (
            Q(items__variant__is_active=False)
            | Q(items__variant__product__is_active=False)
            | Q(
                items__variant__inventory__isnull=False,
                items__quantity__gt=F('items__variant__inventory__quantity')
                - F('items__variant__inventory__reserved_quantity'),
            )
        )
        if self.value() == 'available':
            return queryset.exclude(issue_condition).filter(items__isnull=False).distinct()
        if self.value() == 'issues':
            return queryset.filter(issue_condition).distinct()
        return queryset


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    show_change_link = True
    autocomplete_fields = ['variant']
    fields = (
        'product_thumbnail',
        'variant',
        'quantity',
        'unit_price_at_addition_display',
        'current_price_display',
        'price_status_display',
        'total_price_display',
        'stock_status_display',
        'created_at',
    )
    readonly_fields = (
        'product_thumbnail',
        'unit_price_at_addition_display',
        'current_price_display',
        'price_status_display',
        'total_price_display',
        'stock_status_display',
        'created_at',
    )

    @admin.display(description='Rasm')
    def product_thumbnail(self, obj):
        if not obj or not obj.variant_id:
            return "—"
        return get_product_thumbnail(obj.variant)

    @admin.display(description='Qo\'shilgandagi narx')
    def unit_price_at_addition_display(self, obj):
        if not obj or obj.unit_price_at_addition is None:
            return "—"
        return format_html('{} <small class="text-muted">UZS</small>', f"{obj.unit_price_at_addition:,.2f}")

    @admin.display(description='Hozirgi narx')
    def current_price_display(self, obj):
        if not obj or not obj.variant_id:
            return "—"
        return format_html('<strong>{}</strong> <small class="text-muted">UZS</small>', f"{obj.current_unit_price:,.2f}")

    @admin.display(description='Narx holati')
    def price_status_display(self, obj):
        if not obj or obj.unit_price_at_addition is None:
            return "—"
        if obj.is_price_changed:
            diff = obj.current_unit_price - obj.unit_price_at_addition
            direction = f"+{diff:,.2f}" if diff > 0 else f"{diff:,.2f}"
            return format_html(
                '<span class="badge badge-warning" style="font-size:11px;" title="Qo\'shilganda: {} UZS | Hozir: {} UZS">'
                '<i class="fas fa-exchange-alt mr-1"></i>{} UZS'
                '</span>',
                f"{obj.unit_price_at_addition:,.2f}",
                f"{obj.current_unit_price:,.2f}",
                direction,
            )
        return format_html(
            '<span class="badge badge-light border text-muted" style="font-size:11px;">'
            '<i class="fas fa-check mr-1 text-success"></i>O\'zgarmagan'
            '</span>'
        )

    @admin.display(description='Jami narx')
    def total_price_display(self, obj):
        if not obj or not obj.variant_id:
            return "—"
        return format_html(
            '<strong style="color:#27ae60;">{}</strong> <small class="text-muted">UZS</small>',
            f"{obj.total_price:,.2f}",
        )

    @admin.display(description='Ombor holati')
    def stock_status_display(self, obj):
        if not obj or not obj.variant_id:
            return "—"
        if not obj.variant.is_active or not obj.variant.product.is_active:
            return format_html('<span class="badge badge-danger" style="font-size:11px;"><i class="fas fa-ban mr-1"></i>Faol emas</span>')
        if hasattr(obj.variant, 'inventory'):
            avail = obj.variant.inventory.available_quantity
            if avail < obj.quantity:
                return format_html(
                    '<span class="badge badge-danger" style="font-size:11px;"><i class="fas fa-times-circle mr-1"></i>Yetarli emas ({}/{})</span>',
                    avail,
                    obj.quantity,
                )
            return format_html(
                '<span class="badge badge-success" style="font-size:11px;"><i class="fas fa-check-circle mr-1"></i>Mavjud ({} dona)</span>',
                avail,
            )
        return format_html('<span class="badge badge-success" style="font-size:11px;"><i class="fas fa-check mr-1"></i>Mavjud</span>')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'cart_id_display',
        'customer_display',
        'status_badge',
        'total_items_display',
        'unique_items_display',
        'total_price_display',
        'availability_badge',
        'created_at',
    )
    list_filter = (
        'status',
        CartOwnerTypeFilter,
        CartHasItemsFilter,
        CartAvailabilityFilter,
        'created_at',
    )
    search_fields = (
        'id',
        'user__email',
        'user__first_name',
        'user__last_name',
        'session_key',
    )
    autocomplete_fields = ['user']
    readonly_fields = (
        'id',
        'cart_id_display',
        'total_items_display',
        'unique_items_display',
        'subtotal_display',
        'total_discount_display',
        'total_price_display',
        'availability_badge',
        'created_at',
        'updated_at',
    )
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = ['mark_as_abandoned', 'mark_as_open', 'clear_empty_carts']
    inlines = [CartItemInline]

    fieldsets = (
        ('Savatcha Tafsilotlari', {
            'fields': (('id', 'status'), ('user', 'session_key')),
        }),
        ('Moliyaviy Ko\'rsatkichlar', {
            'fields': (
                ('total_items_display', 'unique_items_display'),
                ('subtotal_display', 'total_discount_display'),
                ('total_price_display', 'availability_badge'),
            ),
        }),
        ('Tizim Vaqtlari', {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').prefetch_related(
            'items__variant__product__media',
            'items__variant__media',
            'items__variant__inventory',
        ).annotate(
            _items_count=Count('items', distinct=True),
            _total_qty=Sum('items__quantity'),
        )

    @admin.display(description='Savat ID', ordering='id')
    def cart_id_display(self, obj):
        full_id = str(obj.id)
        short_id = full_id[:8]
        return format_html(
            '<code style="font-size:11px; font-weight:bold; color:#2c3e50; background:#f8f9fa; padding:2px 6px; border-radius:4px; border:1px solid #dee2e6;" title="{}">{}</code>',
            full_id,
            short_id,
        )

    @admin.display(description='Mijoz / Foydalanuvchi', ordering='user__email')
    def customer_display(self, obj):
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.pk])
            full_name = obj.user.full_name
            display_text = (
                f"{full_name} ({obj.user.email})"
                if full_name and full_name != obj.user.email
                else obj.user.email
            )
            return format_html(
                '<a href="{}" style="font-weight:600; text-decoration:none;">'
                '<i class="fas fa-user-circle text-primary mr-1"></i>{}'
                '</a>',
                url,
                display_text,
            )
        session = (obj.session_key or '—')
        short_session = f"{session[:12]}..." if len(session) > 12 else session
        return format_html(
            '<span class="badge badge-light border text-muted" style="font-size:11px;" title="Sessiya: {}">'
            '<i class="fas fa-user-secret mr-1"></i>Mehmon ({})'
            '</span>',
            session,
            short_session,
        )

    @admin.display(description='Holat', ordering='status')
    def status_badge(self, obj):
        status_styles = {
            Cart.CartStatus.OPEN: ('badge-success', 'fa-shopping-cart', 'Ochiq'),
            Cart.CartStatus.MERGED: ('badge-info', 'fa-code-branch', 'Birlashtirilgan'),
            Cart.CartStatus.CONVERTED: ('badge-primary', 'fa-check-circle', 'Xarid qilingan'),
            Cart.CartStatus.ABANDONED: ('badge-secondary', 'fa-clock', 'Tashlab ketilgan'),
        }
        badge_cls, icon_cls, label = status_styles.get(
            obj.status, ('badge-dark', 'fa-question-circle', obj.status)
        )
        return format_html(
            '<span class="badge {}" style="font-size:11px; padding:4px 8px;">'
            '<i class="fas {} mr-1"></i>{}'
            '</span>',
            badge_cls,
            icon_cls,
            label,
        )

    @admin.display(description='Tovarlar soni', ordering='_total_qty')
    def total_items_display(self, obj):
        qty = getattr(obj, '_total_qty', None)
        if qty is None:
            qty = obj.total_items
        if qty == 0:
            return format_html('<span class="text-muted"><i class="fas fa-inbox mr-1"></i>Bo\'sh</span>')
        return format_html(
            '<span class="badge badge-secondary" style="font-size:11px;"><i class="fas fa-box mr-1"></i>{} dona</span>',
            qty,
        )

    @admin.display(description='Noyob tovarlar (SKU)', ordering='_items_count')
    def unique_items_display(self, obj):
        count = getattr(obj, '_items_count', None)
        if count is None:
            count = obj.unique_items_count
        return format_html(
            '<span class="badge badge-light border" style="font-size:11px;">{} xil tovar</span>',
            count,
        )

    @admin.display(description='Oraliq summa')
    def subtotal_display(self, obj):
        return format_html('<strong>{}</strong> <small class="text-muted">UZS</small>', f"{obj.subtotal:,.2f}")

    @admin.display(description='Jami chegirma')
    def total_discount_display(self, obj):
        if obj.total_discount > 0:
            return format_html(
                '<span class="badge badge-danger" style="font-size:11px;">-{} UZS</span>',
                f"{obj.total_discount:,.2f}",
            )
        return format_html('<span class="text-muted">0.00 UZS</span>')

    @admin.display(description='Jami summa')
    def total_price_display(self, obj):
        return format_html(
            '<strong style="color:#27ae60; font-size:13px;">{}</strong> <small class="text-muted">UZS</small>',
            f"{obj.total_price:,.2f}",
        )

    @admin.display(description='Zaxira holati')
    def availability_badge(self, obj):
        if obj.is_empty:
            return format_html('<span class="text-muted">—</span>')
        if obj.has_unavailable_items:
            return format_html(
                '<span class="badge badge-danger" style="font-size:11px;">'
                '<i class="fas fa-exclamation-triangle mr-1"></i>Muammoli tovar bor'
                '</span>'
            )
        return format_html(
            '<span class="badge badge-success" style="font-size:11px;">'
            '<i class="fas fa-check-circle mr-1"></i>Barchasi mavjud'
            '</span>'
        )

    @admin.action(description="Tanlangan savatlarni 'Tashlab ketilgan' (Abandoned) deb belgilash")
    def mark_as_abandoned(self, request, queryset):
        updated = queryset.update(status=Cart.CartStatus.ABANDONED)
        self.message_user(request, f"{updated} ta savat holati 'Tashlab ketilgan' ga o'zgartirildi.")

    @admin.action(description="Tanlangan savatlarni 'Ochiq' (Open) deb belgilash")
    def mark_as_open(self, request, queryset):
        updated = queryset.update(status=Cart.CartStatus.OPEN)
        self.message_user(request, f"{updated} ta savat holati 'Ochiq' ga o'zgartirildi.")

    @admin.action(description="Tanlangan bo'sh savatlarni o'chirish")
    def clear_empty_carts(self, request, queryset):
        empty_carts = queryset.filter(items__isnull=True)
        count = empty_carts.count()
        empty_carts.delete()
        self.message_user(request, f"{count} ta bo'sh savat muvaffaqiyatli o'chirildi.")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cart_link',
        'product_thumbnail',
        'variant_display',
        'quantity',
        'unit_price_at_addition_display',
        'current_unit_price_display',
        'price_status_display',
        'total_price_display',
        'stock_status_display',
        'created_at',
    )
    list_filter = ('created_at', 'variant__is_active')
    search_fields = (
        'id',
        'cart__id',
        'cart__user__email',
        'cart__session_key',
        'variant__sku',
        'variant__title',
        'variant__product__name',
    )
    autocomplete_fields = ['cart', 'variant']
    readonly_fields = (
        'product_thumbnail',
        'unit_price_at_addition_display',
        'current_unit_price_display',
        'price_status_display',
        'total_price_display',
        'stock_status_display',
        'created_at',
        'updated_at',
    )
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Asosiy bog\'lanishlar', {
            'fields': (('cart', 'variant'), ('quantity', 'product_thumbnail')),
        }),
        ('Narx va Moliya', {
            'fields': (
                ('unit_price_at_addition_display', 'current_unit_price_display'),
                ('price_status_display', 'total_price_display'),
                'stock_status_display',
            ),
        }),
        ('Tizim vaqtlari', {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'cart',
            'cart__user',
            'variant__product',
            'variant__inventory',
        ).prefetch_related(
            'variant__media',
            'variant__product__media',
        )

    @admin.display(description='Rasm')
    def product_thumbnail(self, obj):
        if not obj or not obj.variant_id:
            return "—"
        return get_product_thumbnail(obj.variant)

    @admin.display(description='Savat', ordering='cart__id')
    def cart_link(self, obj):
        url = reverse('admin:carts_cart_change', args=[obj.cart.pk])
        short_id = str(obj.cart.id)[:8]
        user_str = obj.cart.user.email if obj.cart.user else f"Guest ({obj.cart.session_key[:6] if obj.cart.session_key else ''})"
        return format_html(
            '<a href="{}" style="font-weight:600; text-decoration:none;">'
            '<i class="fas fa-shopping-cart text-info mr-1"></i>#{} <small class="text-muted">({})</small>'
            '</a>',
            url,
            short_id,
            user_str,
        )

    @admin.display(description='Variant', ordering='variant__sku')
    def variant_display(self, obj):
        url = reverse('admin:products_productvariant_change', args=[obj.variant.pk])
        return format_html(
            '<a href="{}" style="text-decoration:none;">'
            '<strong>{}</strong> <small class="text-muted">[{}]</small>'
            '</a>',
            url,
            obj.variant.product.name,
            obj.variant.sku,
        )

    @admin.display(description='Qo\'shilgandagi narx')
    def unit_price_at_addition_display(self, obj):
        if obj.unit_price_at_addition is None:
            return "—"
        return format_html('{} <small class="text-muted">UZS</small>', f"{obj.unit_price_at_addition:,.2f}")

    @admin.display(description='Hozirgi narx')
    def current_unit_price_display(self, obj):
        return format_html('<strong>{}</strong> <small class="text-muted">UZS</small>', f"{obj.current_unit_price:,.2f}")

    @admin.display(description='Narx holati')
    def price_status_display(self, obj):
        if obj.unit_price_at_addition is None:
            return "—"
        if obj.is_price_changed:
            diff = obj.current_unit_price - obj.unit_price_at_addition
            direction = f"+{diff:,.2f}" if diff > 0 else f"{diff:,.2f}"
            return format_html(
                '<span class="badge badge-warning" style="font-size:11px;" title="Qo\'shilganda: {} UZS | Hozir: {} UZS">'
                '<i class="fas fa-exchange-alt mr-1"></i>{} UZS'
                '</span>',
                f"{obj.unit_price_at_addition:,.2f}",
                f"{obj.current_unit_price:,.2f}",
                direction,
            )
        return format_html(
            '<span class="badge badge-light border text-muted" style="font-size:11px;">'
            '<i class="fas fa-check mr-1 text-success"></i>O\'zgarmagan'
            '</span>'
        )

    @admin.display(description='Jami narx')
    def total_price_display(self, obj):
        return format_html(
            '<strong style="color:#27ae60;">{}</strong> <small class="text-muted">UZS</small>',
            f"{obj.total_price:,.2f}",
        )

    @admin.display(description='Ombor holati')
    def stock_status_display(self, obj):
        if not obj.variant.is_active or not obj.variant.product.is_active:
            return format_html('<span class="badge badge-danger" style="font-size:11px;"><i class="fas fa-ban mr-1"></i>Faol emas</span>')
        if hasattr(obj.variant, 'inventory'):
            avail = obj.variant.inventory.available_quantity
            if avail < obj.quantity:
                return format_html(
                    '<span class="badge badge-danger" style="font-size:11px;"><i class="fas fa-times-circle mr-1"></i>Yetarli emas ({}/{})</span>',
                    avail,
                    obj.quantity,
                )
            return format_html(
                '<span class="badge badge-success" style="font-size:11px;"><i class="fas fa-check-circle mr-1"></i>Mavjud ({} dona)</span>',
                avail,
            )
        return format_html('<span class="badge badge-success" style="font-size:11px;"><i class="fas fa-check mr-1"></i>Mavjud</span>')
