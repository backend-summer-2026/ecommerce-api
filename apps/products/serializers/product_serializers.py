from decimal import Decimal
from rest_framework import serializers
from apps.products.models import Product, ProductCategory, ProductMedia, ProductVariant
from apps.products.serializers.brand_serializers import BrandSerializer
from apps.products.serializers.category_serializers import CategorySimpleSerializer
from apps.products.serializers.media_serializers import ProductMediaSerializer
from apps.products.serializers.variant_serializers import ProductVariantSerializer


class ProductListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for product catalog grid/listing.
    Uses prefetched relations to avoid N+1 queries.
    """
    brand = serializers.SerializerMethodField()
    primary_category = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'short_description',
            'brand',
            'primary_category',
            'main_image',
            'price',
            'is_in_stock',
            'created_at',
        ]

    def get_brand(self, obj):
        if obj.brand:
            return {
                'id': obj.brand.id,
                'name': obj.brand.name,
                'slug': obj.brand.slug,
                'logo': obj.brand.logo.url if obj.brand.logo else None,
            }
        return None

    def get_primary_category(self, obj):
        # Read from prefetched product_categories
        if hasattr(obj, 'product_categories'):
            for pc in obj.product_categories.all():
                if pc.is_primary:
                    return {
                        'id': pc.category.id,
                        'name': pc.category.name,
                        'slug': pc.category.slug,
                    }
            # Fallback to first category if no explicit primary
            first_pc = obj.product_categories.first()
            if first_pc:
                return {
                    'id': first_pc.category.id,
                    'name': first_pc.category.name,
                    'slug': first_pc.category.slug,
                }
        return None

    def get_main_image(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'media'):
            media_list = list(obj.media.all())
            main_m = next((m for m in media_list if m.is_main and m.file), None)
            if not main_m and media_list:
                main_m = media_list[0]
            if main_m and main_m.file:
                if request is not None:
                    return request.build_absolute_uri(main_m.file.url)
                return main_m.file.url
        return None

    def get_price(self, obj):
        # Calculate min price and discount price across active variants
        active_variants = [v for v in obj.variants.all() if v.is_active]
        if not active_variants:
            return None

        # Check default variant first
        default_variant = next((v for v in active_variants if v.is_default), active_variants[0])

        prices = [v.price for v in active_variants]
        final_prices = [v.final_price for v in active_variants]

        return {
            'min_price': str(min(prices)),
            'max_price': str(max(prices)),
            'min_final_price': str(min(final_prices)),
            'default_price': str(default_variant.price),
            'default_discount_price': str(default_variant.discount_price) if default_variant.discount_price else None,
            'default_final_price': str(default_variant.final_price),
            'is_on_sale': any(v.is_on_sale for v in active_variants),
        }

    def get_is_in_stock(self, obj) -> bool:
        active_variants = [v for v in obj.variants.all() if v.is_active]
        return any(
            hasattr(v, 'inventory') and v.inventory is not None and v.inventory.is_in_stock
            for v in active_variants
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for single product detail page.
    Includes variants, media gallery, dynamic attribute breakdown, and categories.
    """
    brand = BrandSerializer(read_only=True)
    categories = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()
    media = ProductMediaSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    default_variant = serializers.SerializerMethodField()
    dynamic_attributes = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'brand',
            'categories',
            'breadcrumbs',
            'short_description',
            'description',
            'media',
            'variants',
            'default_variant',
            'dynamic_attributes',
            'is_in_stock',
            'created_at',
            'updated_at',
        ]

    def get_categories(self, obj):
        categories_data = []
        for pc in obj.product_categories.select_related('category').all():
            categories_data.append({
                'id': pc.category.id,
                'name': pc.category.name,
                'slug': pc.category.slug,
                'is_primary': pc.is_primary,
            })
        return categories_data

    def get_breadcrumbs(self, obj):
        # Breadcrumbs based on primary category
        primary_pc = obj.product_categories.filter(is_primary=True).first()
        if not primary_pc:
            primary_pc = obj.product_categories.first()
        if not primary_pc:
            return []

        breadcrumbs = []
        current = primary_pc.category
        while current is not None:
            breadcrumbs.append({
                'id': current.id,
                'name': current.name,
                'slug': current.slug,
            })
            current = current.parent
        breadcrumbs.reverse()
        return breadcrumbs

    def get_default_variant(self, obj):
        active_variants = [v for v in obj.variants.all() if v.is_active]
        if not active_variants:
            return None
        default_v = next((v for v in active_variants if v.is_default), active_variants[0])
        return ProductVariantSerializer(default_v, context=self.context).data

    def get_dynamic_attributes(self, obj):
        # Aggregate all unique attributes and values across this product's variants
        attributes_map = {}
        for variant in obj.variants.filter(is_active=True).prefetch_related('variant_attributes__attribute_value__attribute'):
            for pva in variant.variant_attributes.all():
                attr_name = pva.attribute_value.attribute.name
                attr_slug = pva.attribute_value.attribute.slug
                val = pva.attribute_value.value
                val_slug = pva.attribute_value.slug

                if attr_slug not in attributes_map:
                    attributes_map[attr_slug] = {
                        'name': attr_name,
                        'slug': attr_slug,
                        'values': set(),
                    }
                attributes_map[attr_slug]['values'].add(val)

        return [
            {
                'name': item['name'],
                'slug': item['slug'],
                'values': sorted(list(item['values'])),
            }
            for item in attributes_map.values()
        ]

    def get_is_in_stock(self, obj) -> bool:
        active_variants = [v for v in obj.variants.all() if v.is_active]
        return any(
            hasattr(v, 'inventory') and v.inventory is not None and v.inventory.is_in_stock
            for v in active_variants
        )
