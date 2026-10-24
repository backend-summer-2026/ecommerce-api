from rest_framework import serializers

from apps.orders.models import Order
from apps.orders.serializers.address_serializers import OrderAddressSerializer
from apps.orders.serializers.item_serializers import OrderItemSerializer
from apps.orders.serializers.status_serializers import OrderStatusHistorySerializer


class OrderCreateSerializer(serializers.Serializer):
    """
    Input serializer for order checkout conversion from active cart.
    """

    shipping_address = OrderAddressSerializer(required=True)
    shipping_method = serializers.ChoiceField(
        choices=Order.ShippingMethod.choices,
        default=Order.ShippingMethod.STANDARD,
    )
    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices,
        default=Order.PaymentMethod.CASH_ON_DELIVERY,
    )
    coupon_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default=None,
    )
    customer_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )


class OrderListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for order summary listings and history tables.
    """

    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'payment_status',
            'payment_method',
            'shipping_method',
            'total_items',
            'total_price',
            'currency',
            'created_at',
        ]
        read_only_fields = fields


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for detailed single order inspection.
    """

    shipping_address = OrderAddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = serializers.SerializerMethodField()
    total_items = serializers.IntegerField(read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'payment_status',
            'payment_method',
            'shipping_method',
            'subtotal',
            'shipping_fee',
            'discount_amount',
            'total_price',
            'currency',
            'tracking_number',
            'customer_notes',
            'cancellation_reason',
            'can_cancel',
            'total_items',
            'paid_at',
            'delivered_at',
            'cancelled_at',
            'created_at',
            'updated_at',
            'shipping_address',
            'items',
            'status_history',
        ]
        read_only_fields = fields

    def get_status_history(self, obj) -> list:
        request = self.context.get('request')
        history_qs = obj.status_history.all()
        # If not staff, filter only customer-visible transitions
        if request and not request.user.is_staff:
            history_qs = history_qs.filter(is_customer_visible=True)
        return OrderStatusHistorySerializer(history_qs, many=True, context=self.context).data


class OrderCancelSerializer(serializers.Serializer):
    """
    Input serializer for order cancellation.
    """

    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default='Cancelled by customer.',
    )


class OrderInvoiceSerializer(serializers.ModelSerializer):
    """
    Formatted invoice representation for billing, accounting, and printable receipts.
    """

    customer_name = serializers.CharField(source='user.full_name', read_only=True)
    customer_email = serializers.CharField(source='user.email', read_only=True)
    customer_phone = serializers.CharField(source='user.phone_number', read_only=True)
    shipping_address = OrderAddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_number',
            'created_at',
            'paid_at',
            'customer_name',
            'customer_email',
            'customer_phone',
            'payment_method',
            'payment_status',
            'shipping_method',
            'shipping_address',
            'items',
            'total_items',
            'subtotal',
            'shipping_fee',
            'discount_amount',
            'total_price',
            'currency',
        ]
        read_only_fields = fields
