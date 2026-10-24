from rest_framework import serializers

from apps.notifications.models import NotificationTemplate


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for managing database-driven dynamic notification templates.
    """

    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = [
            'id',
            'code',
            'name',
            'description',
            'notification_type',
            'notification_type_display',
            'email_subject_template',
            'email_body_html_template',
            'email_body_text_template',
            'in_app_title_template',
            'in_app_message_template',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TemplateTestSendSerializer(serializers.Serializer):
    """
    Input serializer for previewing and testing dynamic template rendering.
    """

    test_email = serializers.EmailField(required=False, allow_blank=True, default='')
    user_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    context_data = serializers.JSONField(required=False, default=dict)
    send_email = serializers.BooleanField(required=False, default=True)
    send_in_app = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        send_email = attrs.get('send_email', True)
        test_email = attrs.get('test_email', '')
        send_in_app = attrs.get('send_in_app', False)
        user_id = attrs.get('user_id')

        if send_email and not test_email:
            raise serializers.ValidationError({"test_email": "test_email is required when send_email is True."})
        if send_in_app and not user_id:
            raise serializers.ValidationError({"user_id": "user_id is required when send_in_app is True."})
        return attrs
