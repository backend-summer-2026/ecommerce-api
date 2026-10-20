from django.contrib import admin
from django.utils.html import format_html

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


class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 1
    autocomplete_fields = ['category']


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1
    fields = ('file', 'media_type', 'alt_text', 'is_main', 'order')


class ProductVariantInline(admin.StackedInline):
    model = ProductVariant
    extra = 0
    show_change_link = True
    fields = ('sku', 'title', 'price', 'discount_price', 'is_default', 'is_active')


class ProductVariantAttributeValueInline(admin.TabularInline):
    model = ProductVariantAttributeValue
    extra = 1
    autocomplete_fields = ['attribute_value']


class InventoryInline(admin.StackedInline):
    model = Inventory
    can_delete = False
    extra = 0
    fields = ('quantity', 'reserved_quantity', 'low_stock_threshold')


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 2
    prepopulated_fields = {'slug': ('value',)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active', 'created_at')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'website', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'brand', 'is_active', 'created_at')
    list_filter = ('is_active', 'brand', 'created_at')
    search_fields = ('name', 'slug', 'description', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductCategoryInline, ProductVariantInline, ProductMediaInline]
    date_hierarchy = 'created_at'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'title',
        'product',
        'price',
        'discount_price',
        'display_final_price',
        'is_default',
        'is_active',
        'display_stock_status',
    )
    list_filter = ('is_active', 'is_default', 'product__brand')
    search_fields = ('sku', 'title', 'product__name')
    autocomplete_fields = ['product']
    inlines = [InventoryInline, ProductVariantAttributeValueInline, ProductMediaInline]

    @admin.display(description='Final Price')
    def display_final_price(self, obj):
        return obj.final_price

    @admin.display(description='Stock')
    def display_stock_status(self, obj):
        if hasattr(obj, 'inventory'):
            inv = obj.inventory
            if not inv.is_in_stock:
                return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
            if inv.is_low_stock:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">Low Stock ({})</span>',
                    inv.available_quantity,
                )
            return format_html(
                '<span style="color: green;">In Stock ({})</span>',
                inv.available_quantity,
            )
        return format_html('<span style="color: gray;">No inventory</span>')


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_values_count', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [AttributeValueInline]

    @admin.display(description='Values Count')
    def display_values_count(self, obj):
        return obj.values.count()


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ('value', 'attribute', 'slug', 'created_at')
    list_filter = ('attribute',)
    search_fields = ('value', 'slug', 'attribute__name')
    prepopulated_fields = {'slug': ('value',)}


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        'variant',
        'quantity',
        'reserved_quantity',
        'display_available_quantity',
        'low_stock_threshold',
        'display_status',
        'updated_at',
    )
    search_fields = ('variant__sku', 'variant__product__name')
    autocomplete_fields = ['variant']

    @admin.display(description='Available')
    def display_available_quantity(self, obj):
        return obj.available_quantity

    @admin.display(description='Status')
    def display_status(self, obj):
        if not obj.is_in_stock:
            return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
        if obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Low Stock</span>')
        return format_html('<span style="color: green; font-weight: bold;">In Stock</span>')
