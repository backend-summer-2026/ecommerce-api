import logging
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.utils import timezone

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class TemplateRenderService:
    """
    Service responsible for compiling and rendering dynamic notification templates
    using Django's Template Engine with context data.
    """

    @classmethod
    def render_string(cls, template_string: Optional[str], context: Dict[str, Any]) -> str:
        """
        Renders a single template string safely with context dictionary.
        """
        if not template_string:
            return ""
        django_template = Template(template_string)
        return django_template.render(Context(context or {}))

    @classmethod
    def render_template(cls, template_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches an active template by code and renders subject, HTML/text bodies,
        and in-app title and message strings.
        """
        try:
            template = NotificationTemplate.objects.get(code=template_code, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise ValidationError(f"Active notification template with code '{template_code}' does not exist.")

        return {
            'template': template,
            'email_subject': cls.render_string(template.email_subject_template, context),
            'email_body_html': cls.render_string(template.email_body_html_template, context),
            'email_body_text': cls.render_string(template.email_body_text_template, context),
            'in_app_title': cls.render_string(template.in_app_title_template, context),
            'in_app_message': cls.render_string(template.in_app_message_template, context),
        }


class NotificationService:
    """
    Centralized service for managing Account / In-App notifications:
    - User preference checks (opt-in/opt-out)
    - Targeted user dispatch and mass broadcasts using bulk_create
    - Real-time unread/urgent counter queries
    - Read/unread state transitions and batch mark-as-read/clear operations
    """

    @classmethod
    def _is_notification_allowed(cls, user: Any, notification_type: str) -> bool:
        """
        Verifies whether the recipient customer allows notifications of the given category.
        Urgent system/account alerts are always permitted.
        """
        if not user or not user.is_authenticated:
            return False

        preference, _ = NotificationPreference.objects.get_or_create(user=user)

        if notification_type == Notification.NotificationType.ORDER:
            return preference.in_app_order_updates
        elif notification_type == Notification.NotificationType.PAYMENT:
            return preference.in_app_payment_updates
        elif notification_type == Notification.NotificationType.PROMOTION:
            return preference.in_app_promotions

        # ACCOUNT and SYSTEM alerts are always delivered
        return True

    @classmethod
    def send_in_app(
        cls,
        user: Any,
        title: str,
        message: str,
        notification_type: str = Notification.NotificationType.SYSTEM,
        priority: str = Notification.NotificationPriority.NORMAL,
        action_url: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Optional[Notification]:
        """
        Sends an in-app notification to a single user if their preferences allow it.
        """
        if not force and priority != Notification.NotificationPriority.URGENT:
            if not cls._is_notification_allowed(user, notification_type):
                logger.info(
                    "Skipped in-app notification for user %s: opted out of %s",
                    user.id,
                    notification_type,
                )
                return None

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            action_url=action_url or "",
            data=data or {},
        )
        return notification

    @classmethod
    def broadcast(
        cls,
        title: str,
        message: str,
        notification_type: str = Notification.NotificationType.SYSTEM,
        priority: str = Notification.NotificationPriority.NORMAL,
        action_url: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        user_ids: Optional[Iterable[int]] = None,
        recipient_type: str = 'ALL',
    ) -> int:
        """
        Broadcasts notification to all active users or a specified list of user IDs.
        Uses bulk_create for optimal performance.
        """
        if user_ids is not None:
            users_qs = User.objects.filter(id__in=user_ids, is_active=True)
        elif recipient_type == 'STAFF':
            users_qs = User.objects.filter(is_staff=True, is_active=True)
        else:
            users_qs = User.objects.filter(is_active=True)

        user_list = list(users_qs)
        if not user_list:
            return 0

        # Fetch preferences for all target users in a single query
        user_ids_list = [u.id for u in user_list]
        prefs_map = {
            p.user_id: p
            for p in NotificationPreference.objects.filter(user_id__in=user_ids_list)
        }

        notifications_to_create: List[Notification] = []
        is_urgent = (priority == Notification.NotificationPriority.URGENT)

        for user in user_list:
            # Check user preference if not urgent and in filtered category
            if not is_urgent:
                pref = prefs_map.get(user.id)
                if pref:
                    if notification_type == Notification.NotificationType.ORDER and not pref.in_app_order_updates:
                        continue
                    if notification_type == Notification.NotificationType.PAYMENT and not pref.in_app_payment_updates:
                        continue
                    if notification_type == Notification.NotificationType.PROMOTION and not pref.in_app_promotions:
                        continue

            notifications_to_create.append(
                Notification(
                    user=user,
                    notification_type=notification_type,
                    priority=priority,
                    title=title,
                    message=message,
                    action_url=action_url or "",
                    data=data or {},
                )
            )

        if notifications_to_create:
            created = Notification.objects.bulk_create(notifications_to_create, batch_size=1000)
            return len(created)
        return 0

    @classmethod
    def mark_as_read(cls, notification: Notification, user: Any) -> Notification:
        """
        Marks single notification as read if owner matches.
        """
        if notification.user_id != user.id:
            raise ValidationError("You do not have permission to modify this notification.")
        notification.mark_as_read()
        return notification

    @classmethod
    def mark_as_unread(cls, notification: Notification, user: Any) -> Notification:
        """
        Reverts single notification to unread status if owner matches.
        """
        if notification.user_id != user.id:
            raise ValidationError("You do not have permission to modify this notification.")
        notification.mark_as_unread()
        return notification

    @classmethod
    def mark_all_as_read(cls, user: Any) -> int:
        """
        Marks all unread notifications of the user as read in a single SQL query.
        """
        return Notification.objects.for_user(user).mark_all_as_read()

    @classmethod
    def clear_read_notifications(cls, user: Any) -> int:
        """
        Deletes all notifications marked as read for the current user.
        """
        deleted_count, _ = Notification.objects.for_user(user).read().delete()
        return deleted_count

    @classmethod
    def get_unread_count(cls, user: Any) -> Dict[str, int]:
        """
        Returns total unread count and urgent notification count for header badge.
        """
        unread_qs = Notification.objects.for_user(user).unread()
        return {
            'unread_count': unread_qs.count(),
            'urgent_count': unread_qs.filter(priority=Notification.NotificationPriority.URGENT).count(),
        }


class EmailService:
    """
    Centralized service for outbound email dispatch, queuing, and lifecycle management:
    - User opt-in/opt-out preference validation
    - Dynamic template rendering
    - Immediate SMTP delivery with fallback error recording
    - Retry mechanism and administrative queue cancellation
    """

    @classmethod
    def _is_email_allowed(cls, user: Any, category: str) -> bool:
        """
        Checks recipient email preferences.
        """
        if not user or not user.is_authenticated:
            return True

        preference, _ = NotificationPreference.objects.get_or_create(user=user)

        cat_upper = category.upper()
        if cat_upper == 'ORDER':
            return preference.email_order_updates
        elif cat_upper == 'PAYMENT':
            return preference.email_payment_receipts
        elif cat_upper == 'PROMOTION':
            return preference.email_promotions
        elif cat_upper == 'SECURITY':
            return preference.email_security_alerts

        return True

    @classmethod
    def send_or_queue_email(
        cls,
        recipient_email: str,
        subject: str = "",
        body_text: str = "",
        body_html: str = "",
        user: Optional[Any] = None,
        template_code: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        priority: str = Notification.NotificationPriority.NORMAL,
        scheduled_at: Optional[Any] = None,
        send_immediately: bool = True,
        max_retries: int = 3,
        force: bool = False,
    ) -> Optional[EmailNotification]:
        """
        Creates an EmailNotification record and optionally dispatches it immediately.
        """
        context_data = context_data or {}
        category = "SYSTEM"

        # If dynamic template specified, render template
        if template_code:
            rendered = TemplateRenderService.render_template(template_code, context_data)
            subject = subject or rendered['email_subject']
            body_html = body_html or rendered['email_body_html']
            body_text = body_text or rendered['email_body_text']
            category = rendered['template'].notification_type

        # Check user email preference
        if user and not force and priority != Notification.NotificationPriority.URGENT:
            if not cls._is_email_allowed(user, category):
                logger.info(
                    "Skipped email to user %s (%s): opted out of %s emails",
                    user.id,
                    recipient_email,
                    category,
                )
                return None

        email_record = EmailNotification.objects.create(
            user=user,
            recipient_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            template_code=template_code,
            context_data=context_data,
            priority=priority,
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            status=EmailNotification.EmailStatus.PENDING,
        )

        # Dispatch immediately if not scheduled for future
        now = timezone.now()
        is_ready = scheduled_at is None or scheduled_at <= now
        if send_immediately and is_ready:
            cls.dispatch_email(email_record)

        return email_record

    @classmethod
    def dispatch_email(cls, email_record: EmailNotification) -> bool:
        """
        Sends an EmailNotification via Django mail backend and updates its lifecycle status.
        """
        email_record.status = EmailNotification.EmailStatus.SENDING
        email_record.last_attempt_at = timezone.now()
        email_record.attempts += 1
        email_record.save(update_fields=['status', 'last_attempt_at', 'attempts', 'updated_at'])

        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ecommerce.local')
            message = EmailMultiAlternatives(
                subject=email_record.subject,
                body=email_record.body_text or email_record.body_html,
                from_email=from_email,
                to=[email_record.recipient_email],
            )
            if email_record.body_html:
                message.attach_alternative(email_record.body_html, "text/html")

            message.send(fail_silently=False)
            email_record.mark_as_sent(provider_message_id=None)
            logger.info("Email notification #%s delivered successfully to %s", email_record.id, email_record.recipient_email)
            return True
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.warning("Failed to dispatch email #%s to %s: %s", email_record.id, email_record.recipient_email, error_msg)
            email_record.mark_as_failed(error_message=error_msg)
            return False

    @classmethod
    def retry_email(cls, email_record: EmailNotification) -> bool:
        """
        Manually re-triggers dispatch for a failed or pending email.
        """
        if not email_record.can_retry():
            raise ValidationError(
                f"Email notification #{email_record.id} cannot be retried (status={email_record.status}, attempts={email_record.attempts}/{email_record.max_retries})."
            )
        return cls.dispatch_email(email_record)

    @classmethod
    def cancel_email(cls, email_record: EmailNotification) -> bool:
        """
        Cancels a pending email before it is sent.
        """
        if email_record.status != EmailNotification.EmailStatus.PENDING:
            raise ValidationError(f"Only PENDING emails can be cancelled (current status={email_record.status}).")

        email_record.status = EmailNotification.EmailStatus.CANCELLED
        email_record.save(update_fields=['status', 'updated_at'])
        return True
