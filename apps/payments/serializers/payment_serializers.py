from decimal import Decimal
from rest_framework import serializers

from apps.orders.models import Order
from apps.payments.models import Payment


class PaymentOrderSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'order_number',
            'status',
            'payment_status',
            'total_price',
            'currency',
        ]


class PaymentInitializeInputSerializer(serializers.Serializer):
    order_number = serializers.CharField(
        max_length=32,
        required=True,
        help_text="Order number to pay for (e.g. ORD-20261022-8F9B2C).",
    )
    provider = serializers.ChoiceField(
        choices=Payment.PaymentProvider.choices,
        required=True,
        help_text="Selected payment gateway or method (PAYME, CLICK, UZUM, CASH_ON_DELIVERY, CARD_ON_DELIVERY).",
    )
    return_url = serializers.URLField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional callback redirect URL after payment completion.",
    )


class PaymentListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_number',
            'order_number',
            'amount',
            'currency',
            'provider',
            'provider_display',
            'status',
            'status_display',
            'checkout_url',
            'paid_at',
            'created_at',
        ]


class PaymentDetailSerializer(serializers.ModelSerializer):
    order = PaymentOrderSummarySerializer(read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_number',
            'order_number',
            'order',
            'amount',
            'currency',
            'provider',
            'provider_display',
            'status',
            'status_display',
            'provider_transaction_id',
            'provider_state',
            'fee_amount',
            'refunded_amount',
            'checkout_url',
            'metadata',
            'failure_reason',
            'paid_at',
            'failed_at',
            'cancelled_at',
            'created_at',
            'updated_at',
        ]


class PaymentCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="Cancelled by customer",
        help_text="Reason for cancellation.",
    )
