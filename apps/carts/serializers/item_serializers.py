from rest_framework import serializers

from apps.carts.models import CartItem
from apps.carts.serializers.variant_serializers import CartItemVariantSerializer


class CartItemSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for CartItem line in cart.
    Contains embedded variant details, unit pricing, total amounts,
    real-time stock availability, and price change flags.
    """

    variant = CartItemVariantSerializer(read_only=True)
    current_unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_price_changed = serializers.BooleanField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id',
            'variant',
            'quantity',
            'unit_price_at_addition',
            'current_unit_price',
            'subtotal',
            'total_price',
            'discount_amount',
            'is_price_changed',
            'is_available',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'variant',
            'unit_price_at_addition',
            'current_unit_price',
            'subtotal',
            'total_price',
            'discount_amount',
            'is_price_changed',
            'is_available',
            'created_at',
            'updated_at',
        ]


class AddToCartSerializer(serializers.Serializer):
    """
    Input serializer for adding a product variant to the cart.
    """

    variant_id = serializers.IntegerField(
        required=True,
        help_text="Primary key of the ProductVariant (SKU) to add.",
    )
    quantity = serializers.IntegerField(
        default=1,
        min_value=1,
        required=False,
        help_text="Quantity to add (default: 1, minimum: 1).",
    )


class UpdateCartItemSerializer(serializers.Serializer):
    """
    Input serializer for updating an existing cart item's quantity.
    """

    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="New exact quantity for the item (minimum: 1).",
    )
