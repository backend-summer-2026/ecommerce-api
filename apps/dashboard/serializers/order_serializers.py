from rest_framework import serializers
from apps.orders.models import Order, OrderItem, OrderAddress
from apps.dashboard.models import OrderInternalNote


class DashboardOrderItemSerializer(serializers.ModelSerializer):
    """
    Line item snapshot inside dashboard order detail.
    """
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_name',
            'variant_sku',
            'variant_attributes_display',
            'unit_price',
            'quantity',
            'total_price',
        ]


class OrderInternalNoteSerializer(serializers.ModelSerializer):
    """
    Internal note on an order, visible only to operators.
    """
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    author_email = serializers.EmailField(source='author.email', read_only=True)

    class Meta:
        model = OrderInternalNote
        fields = [
            'id',
            'order_id',
            'order_number',
            'author_email',
            'note',
            'is_pinned',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order_id', 'order_number', 'author_email', 'created_at', 'updated_at']


class DashboardOrderAddressSerializer(serializers.ModelSerializer):
    """
    Customer shipping destination snapshot.
    """
    class Meta:
        model = OrderAddress
        fields = [
            'recipient_name',
            'phone_number',
            'alternative_phone_number',
            'region',
            'district',
            'street_address',
            'apartment_office',
            'postal_code',
            'delivery_instructions',
        ]


class DashboardOrderListSerializer(serializers.ModelSerializer):
    """
    Backoffice table view for orders.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    customer_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    items_count = serializers.SerializerMethodField()
    internal_notes_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'user_email',
            'customer_name',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'total_price',
            'currency',
            'items_count',
            'internal_notes_count',
            'created_at',
        ]

    def get_customer_name(self, obj) -> str:
        name = f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()
        return name or obj.user.phone_number or obj.user.email

    def get_items_count(self, obj) -> int:
        return obj.items.count()

    def get_internal_notes_count(self, obj) -> int:
        return obj.internal_notes.count()


class DashboardOrderDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive backoffice view of an order with full shipping, items, and internal notes.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    customer_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    shipping_address = DashboardOrderAddressSerializer(read_only=True)
    items = DashboardOrderItemSerializer(many=True, read_only=True)
    internal_notes = OrderInternalNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'user_id',
            'user_email',
            'user_phone',
            'customer_name',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'payment_method',
            'shipping_method',
            'subtotal',
            'shipping_fee',
            'discount_amount',
            'total_price',
            'currency',
            'tracking_number',
            'customer_notes',
            'admin_notes',
            'shipping_address',
            'items',
            'internal_notes',
            'paid_at',
            'delivered_at',
            'cancelled_at',
            'created_at',
            'updated_at',
        ]

    def get_customer_name(self, obj) -> str:
        name = f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()
        return name or obj.user.phone_number or obj.user.email


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    Payload for updating order fulfillment status and internal note.
    """
    status = serializers.ChoiceField(
        choices=Order.OrderStatus.choices,
        required=True,
    )
    admin_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    tracking_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )
