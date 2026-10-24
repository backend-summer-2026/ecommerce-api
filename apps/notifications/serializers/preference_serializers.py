from rest_framework import serializers

from apps.notifications.models import NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for managing user notification opt-in/opt-out preferences.
    """

    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'email_order_updates',
            'email_payment_receipts',
            'email_promotions',
            'email_security_alerts',
            'in_app_order_updates',
            'in_app_payment_updates',
            'in_app_promotions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
