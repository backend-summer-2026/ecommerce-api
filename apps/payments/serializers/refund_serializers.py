from decimal import Decimal
from rest_framework import serializers

from apps.payments.models import Refund


class RefundCreateInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True,
        help_text="Monetary amount to refund (must not exceed unrefunded payment balance).",
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Administrative justification or customer return explanation.",
    )
    provider_refund_id = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="External payment gateway refund ID if pre-authorized.",
    )


class RefundListSerializer(serializers.ModelSerializer):
    payment_number = serializers.CharField(source='payment.payment_number', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id',
            'refund_number',
            'payment_number',
            'order_number',
            'amount',
            'currency',
            'status',
            'status_display',
            'reason',
            'created_by_username',
            'processed_at',
            'created_at',
        ]


class RefundDetailSerializer(serializers.ModelSerializer):
    payment_number = serializers.CharField(source='payment.payment_number', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id',
            'refund_number',
            'payment_number',
            'order_number',
            'amount',
            'currency',
            'status',
            'status_display',
            'reason',
            'provider_refund_id',
            'created_by_username',
            'processed_at',
            'metadata',
            'created_at',
            'updated_at',
        ]
