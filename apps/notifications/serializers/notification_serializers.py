from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing user in-app notifications.
    """

    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'notification_type_display',
            'priority',
            'priority_display',
            'title',
            'is_read',
            'read_at',
            'action_url',
            'created_at',
        ]
        read_only_fields = fields


class NotificationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer including full notification message and metadata.
    """

    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'user',
            'notification_type',
            'notification_type_display',
            'priority',
            'priority_display',
            'title',
            'message',
            'is_read',
            'read_at',
            'action_url',
            'data',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class NotificationUnreadCountSerializer(serializers.Serializer):
    """
    Output serializer for unread & urgent notification counters.
    """

    unread_count = serializers.IntegerField()
    urgent_count = serializers.IntegerField()


class NotificationBroadcastSerializer(serializers.Serializer):
    """
    Admin input serializer for dispatching broadcasts or multi-user alerts.
    """

    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=Notification.NotificationType.choices,
        default=Notification.NotificationType.SYSTEM,
    )
    priority = serializers.ChoiceField(
        choices=Notification.NotificationPriority.choices,
        default=Notification.NotificationPriority.NORMAL,
    )
    action_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    data = serializers.JSONField(required=False, default=dict)
    broadcast = serializers.BooleanField(required=False, default=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    recipient_type = serializers.ChoiceField(
        choices=['ALL', 'STAFF'],
        required=False,
        default='ALL',
    )

    def validate(self, attrs):
        broadcast = attrs.get('broadcast', False)
        user_ids = attrs.get('user_ids', [])
        if not broadcast and not user_ids:
            # If neither broadcast nor explicit user_ids, default to recipient_type selection
            pass
        return attrs
