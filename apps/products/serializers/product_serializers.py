from decimal import Decimal
import base64
import uuid
import urllib.request
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from apps.products.models import (
    Brand,
    Category,
    Inventory,
    Attribute,
    AttributeValue,
    ProductVariantAttributeValue,
    Product,
    ProductCategory,
    ProductMedia,
    ProductVariant,
)
from apps.products.serializers.brand_serializers import BrandSerializer
from apps.products.serializers.category_serializers import CategorySimpleSerializer
from apps.products.serializers.media_serializers import ProductMediaSerializer
from apps.products.serializers.variant_serializers import ProductVariantSerializer
from apps.reviews.models import ProductRatingSummary


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


class ProductCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a new product with category, brand, image,
    default variant, and inventory in a single atomic transaction.
    """
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255, required=False, allow_blank=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    price = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    stock = serializers.IntegerField(required=False, default=10, min_value=0)
    image_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    short_description = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sku = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    variants = serializers.ListField(child=serializers.DictField(), required=False, allow_empty=True)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Mahsulot nomi kiritilishi shart.")
        return value.strip()

    def create(self, validated_data):
        name = validated_data['name']
        raw_slug = validated_data.get('slug')
        brand_raw = validated_data.get('brand')
        category_raw = validated_data.get('category')
        price = validated_data['price']
        discount_price = validated_data.get('discount_price')
        stock = validated_data.get('stock', 10)
        image_url = validated_data.get('image_url')
        short_description = validated_data.get('short_description') or ''
        description = validated_data.get('description') or ''
        custom_sku = validated_data.get('sku')
        variants_data = validated_data.get('variants', [])

        with transaction.atomic():
            # 1. Generate unique slug
            base_slug = slugify(raw_slug) if raw_slug else slugify(name)
            if not base_slug:
                base_slug = f"prod-{uuid.uuid4().hex[:6]}"
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # 2. Resolve Brand
            brand_obj = None
            if brand_raw:
                if str(brand_raw).isdigit():
                    brand_obj = Brand.objects.filter(id=int(brand_raw)).first()
                if not brand_obj:
                    brand_obj = Brand.objects.filter(slug=brand_raw).first()
                if not brand_obj:
                    brand_obj = Brand.objects.filter(name__iexact=brand_raw).first()

            # 3. Create Product
            product = Product.objects.create(
                name=name,
                slug=slug,
                brand=brand_obj,
                short_description=short_description or (description[:250] if description else ''),
                description=description,
                is_active=True,
            )

            # 4. Resolve & link Category
            if category_raw:
                cat_obj = None
                if str(category_raw).isdigit():
                    cat_obj = Category.objects.filter(id=int(category_raw)).first()
                if not cat_obj:
                    cat_obj = Category.objects.filter(slug=category_raw).first()
                if not cat_obj:
                    cat_obj = Category.objects.filter(name__iexact=category_raw).first()
                if cat_obj:
                    ProductCategory.objects.create(
                        product=product,
                        category=cat_obj,
                        is_primary=True,
                    )

            # 5. Handle Image / Media
            if image_url and image_url.strip():
                img_val = image_url.strip()
                if img_val.startswith('data:image/'):
                    try:
                        header, base64_str = img_val.split(';base64,', 1)
                        mime_ext = header.split('/')[-1]
                        if mime_ext == 'jpeg':
                            mime_ext = 'jpg'
                        elif '+' in mime_ext:
                            mime_ext = mime_ext.split('+')[0]
                        file_bytes = base64.b64decode(base64_str)
                        media_item = ProductMedia(
                            product=product,
                            alt_text=product.name,
                            media_type=ProductMedia.MediaType.IMAGE,
                            is_main=True,
                            order=1,
                        )
                        media_item.file.save(f"{slug}.{mime_ext}", ContentFile(file_bytes), save=True)
                    except Exception:
                        pass
                elif img_val.startswith('http://') or img_val.startswith('https://'):
                    try:
                        req = urllib.request.Request(img_val, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            file_bytes = response.read()
                            media_item = ProductMedia(
                                product=product,
                                alt_text=product.name,
                                media_type=ProductMedia.MediaType.IMAGE,
                                is_main=True,
                                order=1,
                            )
                            media_item.file.save(f"{slug}.jpg", ContentFile(file_bytes), save=True)
                    except Exception:
                        pass
                elif img_val.startswith('/media/') or img_val.startswith('media/'):
                    clean_path = img_val.lstrip('/')
                    if clean_path.startswith('media/'):
                        clean_path = clean_path[len('media/'):]
                    ProductMedia.objects.create(
                        product=product,
                        file=clean_path,
                        alt_text=product.name,
                        media_type=ProductMedia.MediaType.IMAGE,
                        is_main=True,
                        order=1,
                    )

            # 6. Create Variants & Inventory
            if variants_data:
                for idx, v in enumerate(variants_data):
                    v_sku = v.get('sku') or f"{slug.upper()[:8]}-{uuid.uuid4().hex[:4].upper()}"
                    sku_base = v_sku
                    sc = 1
                    while ProductVariant.objects.filter(sku=v_sku).exists():
                        v_sku = f"{sku_base}-{sc}"
                        sc += 1

                    v_title = v.get('title') or f"Variant {idx + 1}"
                    v_price = Decimal(str(v.get('price', price)))
                    v_disc_val = v.get('discountPrice') or v.get('discount_price')
                    v_disc = Decimal(str(v_disc_val)) if v_disc_val else None
                    v_stock = int(v.get('stock', stock or 10))
                    v_is_default = bool(v.get('isDefault', idx == 0))

                    variant = ProductVariant.objects.create(
                        product=product,
                        sku=v_sku,
                        title=v_title,
                        price=v_price,
                        discount_price=v_disc,
                        is_default=v_is_default,
                        is_active=True,
                    )
                    Inventory.objects.create(
                        variant=variant,
                        quantity=v_stock,
                        reserved_quantity=0,
                        low_stock_threshold=5,
                    )

                    # Atributlar
                    attrs = v.get('attributes') or {}
                    for a_name, a_val in attrs.items():
                        if not a_name or not a_val:
                            continue
                        attr_obj, _ = Attribute.objects.get_or_create(
                            slug=slugify(str(a_name)),
                            defaults={'name': str(a_name)},
                        )
                        val_obj, _ = AttributeValue.objects.get_or_create(
                            attribute=attr_obj,
                            value=str(a_val),
                            defaults={'slug': slugify(f"{attr_obj.slug}-{a_val}")},
                        )
                        ProductVariantAttributeValue.objects.create(
                            variant=variant,
                            attribute_value=val_obj,
                        )

                # Kamida bitta default variant bo'lishini ta'minlash
                if not product.variants.filter(is_default=True).exists() and product.variants.exists():
                    first_v = product.variants.first()
                    first_v.is_default = True
                    first_v.save(update_fields=['is_default'])
            else:
                sku_candidate = custom_sku or f"SKU-{slug.upper()[:10]}-{uuid.uuid4().hex[:4].upper()}"
                sku_base = sku_candidate
                sc = 1
                while ProductVariant.objects.filter(sku=sku_candidate).exists():
                    sku_candidate = f"{sku_base}-{sc}"
                    sc += 1

                variant = ProductVariant.objects.create(
                    product=product,
                    sku=sku_candidate,
                    title=product.name,
                    price=price,
                    discount_price=discount_price,
                    is_default=True,
                    is_active=True,
                )
                Inventory.objects.create(
                    variant=variant,
                    quantity=stock,
                    reserved_quantity=0,
                    low_stock_threshold=5,
                )

            # 7. Rating Summary
            ProductRatingSummary.objects.get_or_create(product=product)

            return product
