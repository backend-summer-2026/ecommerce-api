from rest_framework import serializers

from apps.payments.models import PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    payment_number = serializers.CharField(source='payment.payment_number', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id',
            'payment',
            'payment_number',
            'transaction_type',
            'transaction_type_display',
            'amount',
            'status',
            'status_display',
            'idempotency_key',
            'provider_transaction_id',
            'request_payload',
            'response_payload',
            'error_code',
            'error_message',
            'ip_address',
            'created_at',
        ]
