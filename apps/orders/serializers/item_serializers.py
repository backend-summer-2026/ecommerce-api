from rest_framework import serializers

from apps.orders.models import OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for immutable order line item snapshot.
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'variant_id',
            'product_name',
            'variant_sku',
            'variant_attributes_display',
            'attributes_snapshot',
            'unit_price',
            'quantity',
            'total_price',
            'image_url',
        ]
        read_only_fields = fields

    def get_image_url(self, obj) -> str | None:
        request = self.context.get('request')
        if not obj.variant:
            return None

        # Check variant media first
        variant_media = list(obj.variant.media.all())
        main_img = next((m for m in variant_media if m.is_main), None) or (
            variant_media[0] if variant_media else None
        )

        # Fallback to product media
        if not main_img and hasattr(obj.variant, 'product'):
            prod_media = list(obj.variant.product.media.all())
            main_img = next((m for m in prod_media if m.is_main), None) or (
                prod_media[0] if prod_media else None
            )

        if main_img and main_img.file:
            return request.build_absolute_uri(main_img.file.url) if request else main_img.file.url
        return None
