from decimal import Decimal
from rest_framework import serializers
from apps.products.models import ProductVariant
from apps.products.serializers.attribute_serializers import VariantAttributeValueOutputSerializer
from apps.products.serializers.media_serializers import ProductMediaSerializer


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer for product variants with attributes, pricing, media, and inventory status.
    """
    final_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    available_quantity = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    attributes = VariantAttributeValueOutputSerializer(source='variant_attributes', many=True, read_only=True)
    media = ProductMediaSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            'id',
            'sku',
            'title',
            'price',
            'discount_price',
            'final_price',
            'is_on_sale',
            'is_default',
            'is_active',
            'available_quantity',
            'is_in_stock',
            'attributes',
            'media',
        ]

    def get_available_quantity(self, obj) -> int:
        if hasattr(obj, 'inventory') and obj.inventory is not None:
            return obj.inventory.available_quantity
        return 0

    def get_is_in_stock(self, obj) -> bool:
        if hasattr(obj, 'inventory') and obj.inventory is not None:
            return obj.inventory.is_in_stock
        return False
