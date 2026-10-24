from decimal import Decimal
from rest_framework import serializers


class PaymeRpcSerializer(serializers.Serializer):
    method = serializers.CharField(
        required=True,
        help_text="Payme JSON-RPC 2.0 method name.",
    )
    params = serializers.DictField(
        required=False,
        default=dict,
        help_text="Method specific input parameters.",
    )
    id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="RPC Request ID for response correlation.",
    )


class ClickWebhookSerializer(serializers.Serializer):
    click_trans_id = serializers.IntegerField(
        required=True,
        help_text="Click external transaction identifier.",
    )
    service_id = serializers.IntegerField(
        required=True,
        help_text="Merchant service ID in Click system.",
    )
    click_paydoc_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Payment document ID.",
    )
    merchant_trans_id = serializers.CharField(
        required=True,
        help_text="Our internal order number (e.g. ORD-20261022-8F9B2C).",
    )
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=True,
        help_text="Transaction amount in UZS.",
    )
    action = serializers.IntegerField(
        required=True,
        help_text="Click Action: 0 for Prepare, 1 for Complete.",
    )
    error = serializers.IntegerField(
        required=True,
        help_text="Status code: 0 for success, negative for failure.",
    )
    error_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Description of error if any.",
    )
    sign_time = serializers.CharField(
        required=True,
        help_text="Timestamp of request signature generation.",
    )
    sign_string = serializers.CharField(
        required=True,
        help_text="MD5 digest signature string for authorization.",
    )
    merchant_prepare_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID returned by our system during Prepare action.",
    )


class UzumWebhookSerializer(serializers.Serializer):
    order_id = serializers.CharField(
        required=True,
        help_text="Order number (e.g. ORD-20261022-8F9B2C).",
    )
    payment_id = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="External payment identifier in Uzum Bank.",
    )
    status = serializers.CharField(
        required=True,
        help_text="Transaction status (SUCCESS, FAILED, CANCELLED).",
    )
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        help_text="Payment amount.",
    )
    failure_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Failure or cancellation reason.",
    )
