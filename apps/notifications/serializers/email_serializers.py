from rest_framework import serializers

from apps.notifications.models import EmailNotification


class EmailNotificationListSerializer(serializers.ModelSerializer):
    """
    List serializer for outbound email notifications queue & logs.
    """

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = EmailNotification
        fields = [
            'id',
            'user',
            'recipient_email',
            'subject',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'attempts',
            'max_retries',
            'template_code',
            'last_attempt_at',
            'sent_at',
            'scheduled_at',
            'created_at',
        ]
        read_only_fields = fields


class EmailNotificationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for email log inspection and troubleshooting.
    """

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = EmailNotification
        fields = [
            'id',
            'user',
            'recipient_email',
            'subject',
            'body_text',
            'body_html',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'attempts',
            'max_retries',
            'last_attempt_at',
            'sent_at',
            'scheduled_at',
            'error_message',
            'provider_message_id',
            'template_code',
            'context_data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
