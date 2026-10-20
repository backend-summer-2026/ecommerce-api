from rest_framework import serializers

from apps.products.models import ProductVariant


class CartItemVariantSerializer(serializers.ModelSerializer):
    """
    Lightweight, optimized representation of ProductVariant for cart items.
    Pre-resolves primary image, dynamic attribute map, and live inventory.
    """

    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    main_image = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id',
            'sku',
            'title',
            'product_id',
            'product_name',
            'product_slug',
            'main_image',
            'attributes',
            'price',
            'discount_price',
            'final_price',
            'is_in_stock',
            'available_quantity',
        ]

    def get_main_image(self, obj) -> str | None:
        request = self.context.get('request')
        # Check variant-specific media first
        variant_media = list(obj.media.all())
        main_img = next((m for m in variant_media if m.is_main), None) or (variant_media[0] if variant_media else None)

        # Fallback to product media
        if not main_img and hasattr(obj, 'product'):
            product_media = list(obj.product.media.all())
            main_img = next((m for m in product_media if m.is_main), None) or (product_media[0] if product_media else None)

        if main_img and main_img.file:
            return request.build_absolute_uri(main_img.file.url) if request else main_img.file.url
        return None

    def get_attributes(self, obj) -> dict:
        attr_map = {}
        for av in obj.attributes.all():
            attr_map[av.attribute.name] = av.value
        return attr_map

    def get_available_quantity(self, obj) -> int:
        if hasattr(obj, 'inventory') and obj.inventory:
            return obj.inventory.available_quantity
        return 0

    def get_is_in_stock(self, obj) -> bool:
        return self.get_available_quantity(obj) > 0
