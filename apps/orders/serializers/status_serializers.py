from rest_framework import serializers

from apps.orders.models import Order, OrderStatusHistory


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for customer-visible tracking timeline and audit trail events.
    """

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusHistory
        fields = [
            'id',
            'old_status',
            'new_status',
            'comment',
            'created_by_name',
            'is_customer_visible',
            'created_at',
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj) -> str | None:
        if obj.created_by:
            return obj.created_by.full_name
        return "System"


class AdminStatusUpdateSerializer(serializers.Serializer):
    """
    Input serializer for staff administrators to progress an order's lifecycle state.
    """

    new_status = serializers.ChoiceField(choices=Order.OrderStatus.choices, required=True)
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default=None)
    is_customer_visible = serializers.BooleanField(default=True)


class AdminNotesUpdateSerializer(serializers.Serializer):
    """
    Input serializer for staff to append or modify internal order notes.
    """

    admin_notes = serializers.CharField(required=True, allow_blank=False)
