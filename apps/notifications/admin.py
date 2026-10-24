from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_display',
        'notification_type_badge',
        'priority_badge',
        'title',
        'is_read_badge',
        'read_at',
        'created_at',
    )
    list_filter = (
        'is_read',
        'notification_type',
        'priority',
        'created_at',
    )
    search_fields = (
        'user__email',
        'user__first_name',
        'user__last_name',
        'title',
        'message',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
    )
    actions = ['mark_as_read', 'mark_as_unread']
    fieldsets = (
        (
            'Recipient & Classification',
            {
                'fields': (
                    'user',
                    'notification_type',
                    'priority',
                )
            },
        ),
        (
            'Message Content',
            {
                'fields': (
                    'title',
                    'message',
                    'action_url',
                    'data',
                )
            },
        ),
        (
            'Read Status & Timestamps',
            {
                'fields': (
                    'is_read',
                    'read_at',
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )

    @admin.display(description='User')
    def user_display(self, obj: Notification):
        return obj.user.email if obj.user else '-'

    @admin.display(description='Type', ordering='notification_type')
    def notification_type_badge(self, obj: Notification):
        colors = {
            Notification.NotificationType.ORDER: '#0d6efd',
            Notification.NotificationType.PAYMENT: '#198754',
            Notification.NotificationType.ACCOUNT: '#6f42c1',
            Notification.NotificationType.PROMOTION: '#fd7e14',
            Notification.NotificationType.SYSTEM: '#6c757d',
        }
        color = colors.get(obj.notification_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_notification_type_display(),
        )

    @admin.display(description='Priority', ordering='priority')
    def priority_badge(self, obj: Notification):
        colors = {
            Notification.NotificationPriority.LOW: '#6c757d',
            Notification.NotificationPriority.NORMAL: '#0dcaf0',
            Notification.NotificationPriority.HIGH: '#fd7e14',
            Notification.NotificationPriority.URGENT: '#dc3545',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    @admin.display(description='Read Status', ordering='is_read')
    def is_read_badge(self, obj: Notification):
        if obj.is_read:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 500; font-size: 11px;">Read</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: #212529; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">Unread</span>'
        )

    @admin.action(description='Mark selected notifications as read')
    def mark_as_read(self, request, queryset):
        updated_count = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        self.message_user(request, f"{updated_count} notification(s) marked as read.")

    @admin.action(description='Mark selected notifications as unread')
    def mark_as_unread(self, request, queryset):
        updated_count = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None,
        )
        self.message_user(request, f"{updated_count} notification(s) marked as unread.")


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'recipient_email',
        'user_display',
        'subject',
        'status_badge',
        'priority',
        'attempts',
        'sent_at',
        'created_at',
    )
    list_filter = (
        'status',
        'priority',
        'created_at',
        'sent_at',
    )
    search_fields = (
        'recipient_email',
        'user__email',
        'subject',
        'provider_message_id',
        'error_message',
    )
    readonly_fields = (
        'attempts',
        'last_attempt_at',
        'sent_at',
        'created_at',
        'updated_at',
    )
    actions = ['retry_failed_emails', 'mark_as_cancelled']
    fieldsets = (
        (
            'Recipient & Subject',
            {
                'fields': (
                    'user',
                    'recipient_email',
                    'subject',
                    'template_code',
                )
            },
        ),
        (
            'Content & Dynamic Context',
            {
                'fields': (
                    'body_text',
                    'body_html',
                    'context_data',
                )
            },
        ),
        (
            'Delivery State & Provider',
            {
                'fields': (
                    'status',
                    'priority',
                    'attempts',
                    'max_retries',
                    'provider_message_id',
                    'error_message',
                )
            },
        ),
        (
            'Timestamps',
            {
                'fields': (
                    'scheduled_at',
                    'last_attempt_at',
                    'sent_at',
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )

    @admin.display(description='User')
    def user_display(self, obj: EmailNotification):
        return obj.user.email if obj.user else 'Guest / Anonymous'

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj: EmailNotification):
        colors = {
            EmailNotification.EmailStatus.PENDING: '#6c757d',
            EmailNotification.EmailStatus.SENDING: '#0dcaf0',
            EmailNotification.EmailStatus.SENT: '#198754',
            EmailNotification.EmailStatus.FAILED: '#dc3545',
            EmailNotification.EmailStatus.CANCELLED: '#343a40',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.action(description='Queue failed emails for retry')
    def retry_failed_emails(self, request, queryset):
        count = 0
        for email in queryset.filter(status=EmailNotification.EmailStatus.FAILED):
            if email.attempts < email.max_retries:
                email.status = EmailNotification.EmailStatus.PENDING
                email.save(update_fields=['status', 'updated_at'])
                count += 1
        self.message_user(request, f"{count} email(s) reset to PENDING for retry.")

    @admin.action(description='Cancel pending emails')
    def mark_as_cancelled(self, request, queryset):
        updated_count = queryset.filter(status=EmailNotification.EmailStatus.PENDING).update(
            status=EmailNotification.EmailStatus.CANCELLED
        )
        self.message_user(request, f"{updated_count} pending email(s) marked as CANCELLED.")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'email_order_updates',
        'email_payment_receipts',
        'email_promotions',
        'email_security_alerts',
        'in_app_order_updates',
        'in_app_payment_updates',
        'in_app_promotions',
        'updated_at',
    )
    search_fields = (
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'notification_type',
        'is_active',
        'updated_at',
    )
    list_filter = (
        'notification_type',
        'is_active',
        'created_at',
    )
    search_fields = (
        'code',
        'name',
        'description',
    )
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (
            'General Info',
            {
                'fields': (
                    'code',
                    'name',
                    'notification_type',
                    'description',
                    'is_active',
                )
            },
        ),
        (
            'Email Templates',
            {
                'fields': (
                    'email_subject_template',
                    'email_body_html_template',
                    'email_body_text_template',
                )
            },
        ),
        (
            'In-App Templates',
            {
                'fields': (
                    'in_app_title_template',
                    'in_app_message_template',
                )
            },
        ),
        (
            'Timestamps',
            {
                'fields': (
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )
