from rest_framework import serializers

from apps.orders.models import OrderAddress


class OrderAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for order shipping destination address snapshot.
    """

    full_address = serializers.CharField(read_only=True)

    class Meta:
        model = OrderAddress
        fields = [
            'id',
            'recipient_name',
            'phone_number',
            'alternative_phone_number',
            'region',
            'district',
            'street_address',
            'apartment_office',
            'postal_code',
            'landmark',
            'latitude',
            'longitude',
            'delivery_instructions',
            'full_address',
        ]
        read_only_fields = ['id', 'full_address']
