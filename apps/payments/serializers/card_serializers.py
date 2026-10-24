from rest_framework import serializers

from apps.payments.models import Payment, SavedCard


class SavedCardSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    card_type_display = serializers.CharField(source='get_card_type_display', read_only=True)

    class Meta:
        model = SavedCard
        fields = [
            'id',
            'provider',
            'provider_display',
            'card_mask',
            'card_holder',
            'card_type',
            'card_type_display',
            'expire_month',
            'expire_year',
            'is_default',
            'is_verified',
            'created_at',
        ]


class SavedCardCreateInputSerializer(serializers.Serializer):
    card_number = serializers.CharField(
        min_length=16,
        max_length=19,
        required=True,
        help_text="16-digit card number (PAN). NEVER stored in database.",
    )
    expire_month = serializers.CharField(
        min_length=2,
        max_length=2,
        required=True,
        help_text="Card expiry month (e.g. 08).",
    )
    expire_year = serializers.CharField(
        min_length=2,
        max_length=4,
        required=True,
        help_text="Card expiry year (e.g. 28 or 2028).",
    )
    card_holder = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Cardholder embossed name.",
    )
    provider = serializers.ChoiceField(
        choices=[
            Payment.PaymentProvider.PAYME,
            Payment.PaymentProvider.CLICK,
            Payment.PaymentProvider.UZUM,
        ],
        default=Payment.PaymentProvider.PAYME,
        help_text="Gateway used for card tokenization.",
    )


class SavedCardVerifyInputSerializer(serializers.Serializer):
    otp_code = serializers.CharField(
        min_length=4,
        max_length=8,
        required=True,
        help_text="SMS OTP code sent to cardholder's mobile phone.",
    )


class PayWithSavedCardInputSerializer(serializers.Serializer):
    order_number = serializers.CharField(
        max_length=32,
        required=True,
        help_text="Order number to pay for (e.g. ORD-20261022-8F9B2C).",
    )
    card_id = serializers.IntegerField(
        required=True,
        help_text="ID of the verified SavedCard belonging to current user.",
    )
