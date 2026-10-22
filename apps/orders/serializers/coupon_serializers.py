from decimal import Decimal

from rest_framework import serializers

from apps.orders.models import Coupon


class CouponValidateInputSerializer(serializers.Serializer):
    """
    Input serializer for coupon voucher validation.
    """

    code = serializers.CharField(max_length=50, required=True)
    subtotal = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        default=Decimal('0.00'),
    )


class CouponDetailSerializer(serializers.ModelSerializer):
    """
    Read-only serializer exposing coupon metadata and discount terms.
    """

    class Meta:
        model = Coupon
        fields = [
            'code',
            'discount_type',
            'discount_value',
            'min_order_amount',
            'max_discount_amount',
            'valid_from',
            'valid_until',
            'is_active',
        ]
        read_only_fields = fields


class CouponValidationResponseSerializer(serializers.Serializer):
    """
    Response serializer returning validation outcome and discount breakdown.
    """

    is_valid = serializers.BooleanField()
    message = serializers.CharField()
    code = serializers.CharField(allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    coupon = CouponDetailSerializer(allow_null=True, required=False)
