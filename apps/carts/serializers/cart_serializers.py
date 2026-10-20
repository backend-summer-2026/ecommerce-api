from rest_framework import serializers

from apps.carts.models import Cart
from apps.carts.serializers.item_serializers import CartItemSerializer
from apps.carts.services import CartService


class CartSerializer(serializers.ModelSerializer):
    """
    Complete Cart representation with items, computed monetary totals,
    discounts, item counts, and real-time business warnings.
    """

    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    unique_items_count = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_discount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_empty = serializers.BooleanField(read_only=True)
    has_unavailable_items = serializers.BooleanField(read_only=True)
    warnings = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'status',
            'items',
            'total_items',
            'unique_items_count',
            'subtotal',
            'total_price',
            'total_discount',
            'is_empty',
            'has_unavailable_items',
            'warnings',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_warnings(self, obj) -> list[str]:
        return CartService.get_cart_warnings(obj)


class CartSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight summary for navbar badges or quick polling.
    """

    total_items = serializers.IntegerField(read_only=True)
    unique_items_count = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_empty = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cart
        fields = [
            'id',
            'total_items',
            'unique_items_count',
            'total_price',
            'is_empty',
        ]
        read_only_fields = fields


class MergeCartSerializer(serializers.Serializer):
    """
    Payload for merging an anonymous guest cart into an authenticated user's cart.
    Accepts guest_cart_id (UUID) or guest_session_key (string).
    """

    guest_cart_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="UUID of the guest cart to merge.",
    )
    guest_session_key = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=255,
        help_text="Session key of the guest cart to merge.",
    )

    def validate(self, attrs):
        if not attrs.get('guest_cart_id') and not attrs.get('guest_session_key'):
            raise serializers.ValidationError(
                "Either 'guest_cart_id' or 'guest_session_key' must be provided."
            )
        return attrs
