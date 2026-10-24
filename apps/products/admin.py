"""
Django Admin configuration for products application.
Tailored for django-jazzmin theme with enhanced visual components,
Bootstrap 4 badges, media previews, editable lists, and optimized queries.
"""

from decimal import Decimal
from django.contrib import admin
from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.products.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Inventory,
    Product,
    ProductCategory,
    ProductMedia,
    ProductVariant,
    ProductVariantAttributeValue,
)


# ==============================================================================
# Helper Functions & UI Formatters for Jazzmin
# ==============================================================================

def render_image_thumbnail(file_field, default_icon='fa-box', width=42, height=42):
    """
    Renders an image thumbnail or a fallback FontAwesome icon badge.
    """
    if file_field and hasattr(file_field, 'url'):
        try:
            return format_html(
                '<img src="{}" style="width: {}px; height: {}px; object-fit: cover; '
                'border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.15); '
                'border: 1px solid #dee2e6;" />',
                file_field.url,
                width,
                height,
            )
        except Exception:
            pass

    return format_html(
        '<span style="display: inline-flex; align-items: center; justify-content: center; '
        'width: {}px; height: {}px; background: #f4f6f9; color: #adb5bd; '
        'border-radius: 6px; border: 1px solid #dee2e6;">'
        '<i class="fas {}"></i></span>',
        width,
        height,
        default_icon,
    )


def render_stock_badge(available: int, low_threshold: int):
    """
    Renders a Bootstrap 4 badge indicating stock health.
    """
    if available <= 0:
        return format_html(
            '<span class="badge badge-danger" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-times-circle"></i> Tugagan (0)'
            '</span>'
        )
    if available <= low_threshold:
        return format_html(
            '<span class="badge badge-warning" style="font-size: 11px; padding: 4px 8px; color: #212529;">'
            '<i class="fas fa-exclamation-triangle"></i> Oz qoldi ({})'
            '</span>',
            available,
        )
    return format_html(
        '<span class="badge badge-success" style="font-size: 11px; padding: 4px 8px;">'
        '<i class="fas fa-check-circle"></i> Mavjud ({})'
        '</span>',
        available,
    )


def render_status_pill(is_active: bool, active_text="Faol", inactive_text="Nofaol"):
    """
    Renders an active/inactive badge pill.
    """
    if is_active:
        return format_html(
            '<span class="badge badge-pill badge-success" style="font-size: 11px; padding: 4px 9px;">'
            '<i class="fas fa-check"></i> {}</span>',
            active_text,
        )
    return format_html(
        '<span class="badge badge-pill badge-secondary" style="font-size: 11px; padding: 4px 9px;">'
        '<i class="fas fa-ban"></i> {}</span>',
        inactive_text,
    )


# ==============================================================================
# Custom Filters
# ==============================================================================

class StockStatusFilter(admin.SimpleListFilter):
    """
    Custom filter for Inventory admin changelist to quickly filter by stock condition.
    """
    title = "Zaxira holati"
    parameter_name = "stock_status"

    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'Yetarli zaxira'),
            ('low_stock', 'Kam qolgan'),
            ('out_of_stock', 'Tugagan (0)'),
            ('has_reserved', 'Band qilingan qismi bor'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'in_stock':
            return queryset.filter(
                quantity__gt=models.F('reserved_quantity') + models.F('low_stock_threshold')
            )
        if self.value() == 'low_stock':
            return queryset.filter(
                quantity__gt=models.F('reserved_quantity'),
                quantity__lte=models.F('reserved_quantity') + models.F('low_stock_threshold'),
            )
        if self.value() == 'out_of_stock':
            return queryset.filter(quantity__lte=models.F('reserved_quantity'))
        if self.value() == 'has_reserved':
            return queryset.filter(reserved_quantity__gt=0)
        return queryset


# ==============================================================================
# Inlines
# ==============================================================================

class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 0
    autocomplete_fields = ['category']
    fields = ('category', 'is_primary', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True
    classes = ('collapse',)


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1
    fields = ('media_preview', 'file', 'media_type', 'alt_text', 'is_main', 'order')
    readonly_fields = ('media_preview',)
    ordering = ('order', '-is_main', 'id')

    @admin.display(description="Prevyu")
    def media_preview(self, obj):
        if not obj or not obj.file:
            return format_html('<span class="text-muted"><i class="fas fa-image"></i> Fayl yo\'q</span>')
        if obj.media_type == ProductMedia.MediaType.VIDEO:
            return format_html(
                '<span class="badge badge-dark" style="padding: 6px 10px;">'
                '<i class="fas fa-video"></i> Video fayl</span>'
            )
        return render_image_thumbnail(obj.file, default_icon='fa-image', width=50, height=50)


class ProductVariantInline(admin.StackedInline):
    model = ProductVariant
    extra = 0
    show_change_link = True
    classes = ('collapse',)
    fields = (
        ('sku', 'title'),
        ('price', 'discount_price', 'is_default', 'is_active'),
    )


class ProductVariantAttributeValueInline(admin.TabularInline):
    model = ProductVariantAttributeValue
    extra = 1
    autocomplete_fields = ['attribute_value']


class InventoryInline(admin.StackedInline):
    model = Inventory
    can_delete = False
    extra = 0
    fields = (
        ('quantity', 'reserved_quantity', 'low_stock_threshold'),
        ('display_available_quantity', 'display_stock_health'),
    )
    readonly_fields = ('display_available_quantity', 'display_stock_health')

    @admin.display(description="Mavjud miqdor (Sotuvga tayyor)")
    def display_available_quantity(self, obj):
        if not obj or not obj.pk:
            return "-"
        return format_html(
            '<span class="font-weight-bold" style="font-size: 15px;">{} dona</span>',
            obj.available_quantity,
        )

    @admin.display(description="Zaxira statusi")
    def display_stock_health(self, obj):
        if not obj or not obj.pk:
            return "-"
        return render_stock_badge(obj.available_quantity, obj.low_stock_threshold)


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ('value', 'slug')
    prepopulated_fields = {'slug': ('value',)}


# ==============================================================================
# ModelAdmins
# ==============================================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'image_preview',
        'name',
        'parent',
        'display_products_count',
        'is_active',
        'created_at',
    )
    list_display_links = ('image_preview', 'name')
    list_editable = ('is_active',)
    list_filter = ('is_active', ('parent', admin.EmptyFieldListFilter))
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['parent']
    ordering = ('name',)
    readonly_fields = ('image_detail_preview', 'icon_detail_preview', 'created_at', 'updated_at')

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            'fields': (
                ('name', 'slug'),
                'parent',
                'is_active',
            ),
        }),
        ("Media va Belgilar", {
            'fields': (
                ('image', 'image_detail_preview'),
                ('icon', 'icon_detail_preview'),
            ),
        }),
        ("Tavsif", {
            'fields': ('description',),
        }),
        ("Tizim ma'lumotlari", {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    actions = ['mark_active', 'mark_inactive']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('parent')
            .annotate(products_count=Count('product_categories', distinct=True))
        )

    @admin.display(description="Rasm")
    def image_preview(self, obj):
        file = obj.image or obj.icon
        return render_image_thumbnail(file, default_icon='fa-sitemap', width=38, height=38)

    @admin.display(description="Rasm ko'rinishi")
    def image_detail_preview(self, obj):
        return render_image_thumbnail(obj.image, default_icon='fa-image', width=120, height=120)

    @admin.display(description="Ikonka ko'rinishi")
    def icon_detail_preview(self, obj):
        return render_image_thumbnail(obj.icon, default_icon='fa-icons', width=80, height=80)

    @admin.display(description="Mahsulotlar", ordering='products_count')
    def display_products_count(self, obj):
        count = getattr(obj, 'products_count', 0)
        return format_html(
            '<span class="badge badge-info" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-boxes"></i> {} ta</span>',
            count,
        )

    @admin.action(description="Tanlangan toifalarni faollashtirish")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta toifa muvaffaqiyatli faollashtirildi.")

    @admin.action(description="Tanlangan toifalarni faolsizlantirish")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta toifa faolsizlantirildi.")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = (
        'logo_preview',
        'name',
        'website_button',
        'display_products_count',
        'is_active',
        'created_at',
    )
    list_display_links = ('logo_preview', 'name')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)
    readonly_fields = ('logo_detail_preview', 'created_at', 'updated_at')

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            'fields': (
                ('name', 'slug'),
                'is_active',
            ),
        }),
        ("Brend atributlari", {
            'fields': (
                'website',
                ('logo', 'logo_detail_preview'),
            ),
        }),
        ("Tavsif", {
            'fields': ('description',),
        }),
        ("Tizim ma'lumotlari", {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    actions = ['mark_active', 'mark_inactive']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(products_count=Count('products', distinct=True))
        )

    @admin.display(description="Logotip")
    def logo_preview(self, obj):
        return render_image_thumbnail(obj.logo, default_icon='fa-copyright', width=38, height=38)

    @admin.display(description="Logotip ko'rinishi")
    def logo_detail_preview(self, obj):
        return render_image_thumbnail(obj.logo, default_icon='fa-copyright', width=120, height=120)

    @admin.display(description="Veb-sayt")
    def website_button(self, obj):
        if obj.website:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer" '
                'class="btn btn-xs btn-outline-info" style="font-size: 11px; padding: 2px 7px;">'
                '<i class="fas fa-external-link-alt"></i> Sayt</a>',
                obj.website,
            )
        return format_html('<span class="text-muted">-</span>')

    @admin.display(description="Mahsulotlar", ordering='products_count')
    def display_products_count(self, obj):
        count = getattr(obj, 'products_count', 0)
        return format_html(
            '<span class="badge badge-info" style="font-size: 11px; padding: 4px 8px;">'
            '<i class="fas fa-box"></i> {} ta</span>',
            count,
        )

    @admin.action(description="Tanlangan brendlarni faollashtirish")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta brend faollashtirildi.")

    @admin.action(description="Tanlangan brendlarni faolsizlantirish")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta brend faolsizlantirildi.")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'thumbnail_preview',
        'name',
        'brand',
        'categories_badges',
        'price_range_display',
        'variants_count_badge',
        'stock_summary_badge',
        'is_active',
        'created_at',
    )
    list_display_links = ('thumbnail_preview', 'name')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'brand', 'categories', 'created_at')
    search_fields = ('name', 'slug', 'description', 'short_description', 'brand__name', 'variants__sku')
    autocomplete_fields = ['brand']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductCategoryInline, ProductVariantInline, ProductMediaInline]
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            'fields': (
                ('name', 'slug'),
                ('brand', 'is_active'),
            ),
        }),
        ("Tavsif va Matnlar", {
            'fields': (
                'short_description',
                'description',
            ),
        }),
        ("Tizim vaqt ma'lumotlari", {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    actions = ['mark_active', 'mark_inactive']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('brand')
            .prefetch_related('categories', 'media', 'variants__inventory')
        )

    @admin.display(description="Rasm")
    def thumbnail_preview(self, obj):
        media_items = list(obj.media.all())
        main_media = next((m for m in media_items if m.is_main and m.file), None)
        first_media = next((m for m in media_items if m.file), None)
        target = main_media or first_media
        file = target.file if target else None
        return render_image_thumbnail(file, default_icon='fa-box-open', width=45, height=45)

    @admin.display(description="Toifalar")
    def categories_badges(self, obj):
        cats = list(obj.categories.all())[:3]
        if not cats:
            return format_html('<span class="text-muted">-</span>')
        badges = [
            format_html(
                '<span class="badge badge-light border mr-1" style="font-size: 11px;">{}</span>',
                cat.name,
            )
            for cat in cats
        ]
        if len(obj.categories.all()) > 3:
            badges.append(
                format_html('<span class="text-muted" style="font-size: 11px;">+{}</span>', len(obj.categories.all()) - 3)
            )
        return mark_safe(' '.join(badges))

    @admin.display(description="Narx oralig'i")
    def price_range_display(self, obj):
        active_variants = [v for v in obj.variants.all() if v.is_active]
        if not active_variants:
            return format_html('<span class="text-muted">-</span>')
        prices = [v.final_price for v in active_variants]
        min_p = min(prices)
        max_p = max(prices)
        if min_p == max_p:
            return format_html('<span class="font-weight-bold">${}</span>', f'{min_p:,.2f}')
        return format_html(
            '<span class="font-weight-bold">${}</span> &ndash; '
            '<span class="font-weight-bold">${}</span>',
            f'{min_p:,.2f}',
            f'{max_p:,.2f}',
        )

    @admin.display(description="Variantlar")
    def variants_count_badge(self, obj):
        count = len(obj.variants.all())
        if count == 0:
            return format_html('<span class="badge badge-secondary" style="font-size: 11px;">0 variant</span>')
        return format_html(
            '<span class="badge badge-info" style="font-size: 11px; padding: 4px 7px;">'
            '<i class="fas fa-boxes"></i> {} ta</span>',
            count,
        )

    @admin.display(description="Umumiy zaxira")
    def stock_summary_badge(self, obj):
        variants = list(obj.variants.all())
        if not variants:
            return format_html('<span class="badge badge-secondary" style="font-size: 11px;">Variant yo\'q</span>')

        total_available = sum(
            v.inventory.available_quantity
            for v in variants
            if hasattr(v, 'inventory')
        )
        has_any_inventory = any(hasattr(v, 'inventory') for v in variants)
        if not has_any_inventory:
            return format_html('<span class="badge badge-secondary" style="font-size: 11px;">Zaxirasiz</span>')

        if total_available <= 0:
            return format_html(
                '<span class="badge badge-danger" style="font-size: 11px; padding: 4px 7px;">'
                '<i class="fas fa-times-circle"></i> Tugagan</span>'
            )
        if total_available <= 10:
            return format_html(
                '<span class="badge badge-warning" style="font-size: 11px; padding: 4px 7px; color: #212529;">'
                '<i class="fas fa-exclamation-triangle"></i> Oz ({})</span>',
                total_available,
            )
        return format_html(
            '<span class="badge badge-success" style="font-size: 11px; padding: 4px 7px;">'
            '<i class="fas fa-check-circle"></i> Mavjud ({})</span>',
            total_available,
        )

    @admin.action(description="Tanlangan mahsulotlarni faollashtirish")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta mahsulot muvaffaqiyatli faollashtirildi.")

    @admin.action(description="Tanlangan mahsulotlarni faolsizlantirish")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta mahsulot faolsizlantirildi.")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        'variant_image_preview',
        'sku',
        'title',
        'product_link',
        'price',
        'discount_price',
        'display_final_price',
        'is_default',
        'is_active',
        'display_stock_status',
    )
    list_display_links = ('variant_image_preview', 'sku')
    list_editable = ('price', 'discount_price', 'is_active', 'is_default')
    list_filter = ('is_active', 'is_default', 'product__brand')
    search_fields = ('sku', 'title', 'product__name', 'product__slug')
    autocomplete_fields = ['product']
    inlines = [InventoryInline, ProductVariantAttributeValueInline, ProductMediaInline]
    readonly_fields = ('display_computed_final_price', 'created_at', 'updated_at')

    fieldsets = (
        ("Variant identifikatsiyasi", {
            'fields': (
                ('product', 'sku'),
                'title',
            ),
        }),
        ("Narxlar va Chegirmalar", {
            'fields': (
                ('price', 'discount_price'),
                'display_computed_final_price',
            ),
        }),
        ("Holat va Sozlamalar", {
            'fields': (
                ('is_default', 'is_active'),
            ),
        }),
        ("Tizim vaqt ma'lumotlari", {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'),),
        }),
    )

    actions = ['mark_active', 'mark_inactive']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('product', 'product__brand', 'inventory')
            .prefetch_related('media', 'product__media')
        )

    @admin.display(description="Rasm")
    def variant_image_preview(self, obj):
        media_item = obj.media.filter(file__isnull=False).first()
        if not media_item:
            media_item = obj.product.media.filter(file__isnull=False).first()
        file = media_item.file if media_item else None
        return render_image_thumbnail(file, default_icon='fa-boxes', width=40, height=40)

    @admin.display(description="Mahsulot")
    def product_link(self, obj):
        url = reverse('admin:products_product_change', args=[obj.product.pk])
        return format_html(
            '<a href="{}" style="font-weight: 500;">{}</a>',
            url,
            obj.product.name,
        )

    @admin.display(description="Asl narx", ordering='price')
    def formatted_price(self, obj):
        price_str = f"${obj.price:,.2f}"
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration: line-through; color: #888;">{}</span>',
                price_str,
            )
        return format_html('<span style="font-weight: 600;">{}</span>', price_str)

    @admin.display(description="Yakuniy narx", ordering='discount_price')
    def display_final_price(self, obj):
        final = obj.final_price
        final_str = f"${final:,.2f}"
        if obj.is_on_sale:
            diff_pct = int(round((1 - (final / obj.price)) * 100))
            return format_html(
                '<span class="text-success font-weight-bold mr-1">{}</span> '
                '<span class="badge badge-danger" style="font-size: 10px;">-{}%</span>',
                final_str,
                diff_pct,
            )
        return format_html('<span class="font-weight-bold">{}</span>', final_str)

    @admin.display(description="Hisoblangan yakuniy narx")
    def display_computed_final_price(self, obj):
        if not obj or not obj.pk:
            return "-"
        return self.display_final_price(obj)

    @admin.display(description="Zaxira")
    def display_stock_status(self, obj):
        if hasattr(obj, 'inventory'):
            inv = obj.inventory
            return render_stock_badge(inv.available_quantity, inv.low_stock_threshold)
        return format_html('<span class="badge badge-secondary" style="font-size: 11px;">Zaxirasiz</span>')

    @admin.action(description="Tanlangan variantlarni faollashtirish")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta variant faollashtirildi.")

    @admin.action(description="Tanlangan variantlarni faolsizlantirish")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta variant faolsizlantirildi.")


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'display_values_badges',
        'display_values_count',
        'created_at',
    )
    list_display_links = ('name',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [AttributeValueInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(values_count=Count('values', distinct=True))
            .prefetch_related('values')
        )

    @admin.display(description="Qiymatlar namunasi")
    def display_values_badges(self, obj):
        values = list(obj.values.all())[:5]
        if not values:
            return format_html('<span class="text-muted">Qiymat yo\'q</span>')
        badges = [
            format_html(
                '<span class="badge badge-info mr-1" style="font-size: 11px;">{}</span>',
                val.value,
            )
            for val in values
        ]
        if len(obj.values.all()) > 5:
            badges.append(
                format_html('<span class="text-muted" style="font-size: 11px;">+{}</span>', len(obj.values.all()) - 5)
            )
        return mark_safe(' '.join(badges))

    @admin.display(description="Jami qiymatlar", ordering='values_count')
    def display_values_count(self, obj):
        count = getattr(obj, 'values_count', 0)
        return format_html(
            '<span class="badge badge-secondary" style="font-size: 11px; padding: 4px 7px;">'
            '{} ta</span>',
            count,
        )


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ('value', 'attribute_badge', 'slug', 'created_at')
    list_display_links = ('value',)
    list_filter = ('attribute',)
    search_fields = ('value', 'slug', 'attribute__name')
    autocomplete_fields = ['attribute']
    prepopulated_fields = {'slug': ('value',)}
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('attribute')

    @admin.display(description="Atribut", ordering='attribute__name')
    def attribute_badge(self, obj):
        return format_html(
            '<span class="badge badge-primary" style="font-size: 11px; padding: 4px 7px;">'
            '<i class="fas fa-sliders-h"></i> {}</span>',
            obj.attribute.name,
        )


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        'variant',
        'product_name',
        'quantity',
        'reserved_quantity',
        'display_available_quantity',
        'low_stock_threshold',
        'display_status',
        'updated_at',
    )
    list_display_links = ('variant',)
    list_editable = ('quantity', 'low_stock_threshold')
    list_filter = (StockStatusFilter, 'updated_at')
    search_fields = ('variant__sku', 'variant__title', 'variant__product__name')
    autocomplete_fields = ['variant']
    readonly_fields = ('display_available_quantity', 'display_status', 'updated_at')

    fieldsets = (
        ("Variant identifikatsiyasi", {
            'fields': ('variant',),
        }),
        ("Zaxira ma'lumotlari", {
            'fields': (
                ('quantity', 'reserved_quantity'),
                ('low_stock_threshold', 'display_available_quantity', 'display_status'),
            ),
        }),
        ("Tizim vaqt ma'lumotlari", {
            'classes': ('collapse',),
            'fields': ('updated_at',),
        }),
    )

    actions = ['reset_reserved_quantity']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('variant', 'variant__product')
        )

    @admin.display(description="Mahsulot", ordering='variant__product__name')
    def product_name(self, obj):
        url = reverse('admin:products_product_change', args=[obj.variant.product.pk])
        return format_html(
            '<a href="{}" style="font-weight: 500;">{}</a>',
            url,
            obj.variant.product.name,
        )

    @admin.display(description="Mavjud (Sotuvda)", ordering='quantity')
    def display_available_quantity(self, obj):
        return format_html(
            '<span class="font-weight-bold" style="font-size: 13px;">{} dona</span>',
            obj.available_quantity,
        )

    @admin.display(description="Holat")
    def display_status(self, obj):
        return render_stock_badge(obj.available_quantity, obj.low_stock_threshold)

    @admin.action(description="Tanlangan inventarlarda band qilingan miqdorni nolga tushirish")
    def reset_reserved_quantity(self, request, queryset):
        updated = queryset.update(reserved_quantity=0)
        self.message_user(request, f"{updated} ta inventarda band qilingan miqdor 0 qilindi.")
