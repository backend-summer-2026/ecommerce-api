from decimal import Decimal

from rest_framework import serializers

from apps.orders.models import Order


class CheckoutPreviewItemSerializer(serializers.Serializer):
    """
    Representation of an individual line item inside the checkout preview.
    """

    item_id = serializers.IntegerField()
    variant_id = serializers.IntegerField()
    product_name = serializers.CharField()
    variant_sku = serializers.CharField()
    variant_title = serializers.CharField(allow_blank=True)
    variant_attributes_display = serializers.CharField(allow_blank=True)
    image_url = serializers.CharField(allow_null=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    available_quantity = serializers.IntegerField()
    is_available = serializers.BooleanField()
    is_price_changed = serializers.BooleanField()


class CheckoutPreviewInputSerializer(serializers.Serializer):
    """
    Input parameters to customize checkout calculations (shipping and discounts).
    """

    shipping_method = serializers.ChoiceField(
        choices=Order.ShippingMethod.choices,
        default=Order.ShippingMethod.STANDARD,
        required=False,
    )
    coupon_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    region = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        default='',
    )


class CheckoutPreviewResponseSerializer(serializers.Serializer):
    """
    Full preview calculation with pricing breakdown, stock health, and notifications.
    """

    cart_id = serializers.UUIDField()
    total_items = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    shipping_method = serializers.CharField()
    shipping_fee = serializers.DecimalField(max_digits=14, decimal_places=2)
    coupon_code = serializers.CharField(allow_null=True)
    coupon_message = serializers.CharField(allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(default='UZS')
    has_stock_issues = serializers.BooleanField()
    warnings = serializers.ListField(child=serializers.CharField())
    items = CheckoutPreviewItemSerializer(many=True)
