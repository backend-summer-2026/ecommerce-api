from rest_framework import serializers
from apps.dashboard.models import StaffActivityLog, SystemAlert


class StaffActivityLogSerializer(serializers.ModelSerializer):
    """
    Serializer for the immutable administrative audit trail.
    """
    actor_email = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    module_display = serializers.CharField(source='get_module_display', read_only=True)

    class Meta:
        model = StaffActivityLog
        fields = [
            'id',
            'actor_id',
            'actor_email',
            'action',
            'action_display',
            'module',
            'module_display',
            'target_model',
            'target_id',
            'target_repr',
            'description',
            'changes',
            'ip_address',
            'user_agent',
            'created_at',
        ]

    def get_actor_email(self, obj) -> str:
        return obj.actor.email if obj.actor else 'Tizim (System)'


class SystemAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for operational and security system alerts.
    """
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    resolved_by_email = serializers.SerializerMethodField()

    class Meta:
        model = SystemAlert
        fields = [
            'id',
            'alert_type',
            'alert_type_display',
            'severity',
            'severity_display',
            'title',
            'message',
            'is_resolved',
            'resolved_by_email',
            'resolved_at',
            'created_at',
        ]

    def get_resolved_by_email(self, obj):
        return obj.resolved_by.email if obj.resolved_by else None
