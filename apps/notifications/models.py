from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    """
    Custom queryset providing helper filters and batch operations
    for account / in-app notifications.
    """

    def unread(self):
        """Returns only notifications that have not been read."""
        return self.filter(is_read=False)

    def read(self):
        """Returns only notifications that have been marked as read."""
        return self.filter(is_read=True)

    def mark_all_as_read(self):
        """
        Marks all matching notifications as read in a single SQL UPDATE query.
        Returns the count of updated records.
        """
        return self.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )

    def mark_all_as_unread(self):
        """
        Marks all matching notifications as unread in a single SQL UPDATE query.
        Returns the count of updated records.
        """
        return self.filter(is_read=True).update(
            is_read=False,
            read_at=None,
        )

    def for_user(self, user):
        """Filters notifications for a given user."""
        return self.filter(user=user)


class Notification(models.Model):
    """
    Account / In-App notification model for customers and administrators.
    Represents personal alerts displayed in the platform header (bell icon)
    or account notification center with read/unread tracking.
    """

    class NotificationType(models.TextChoices):
        ORDER = 'ORDER', 'Order'
        PAYMENT = 'PAYMENT', 'Payment'
        ACCOUNT = 'ACCOUNT', 'Account'
        PROMOTION = 'PROMOTION', 'Promotion'
        SYSTEM = 'SYSTEM', 'System'

    class NotificationPriority(models.TextChoices):
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
        help_text="Recipient customer account.",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
        help_text="Functional category of notification.",
    )
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
        help_text="Urgency priority level.",
    )
    title = models.CharField(
        max_length=255,
        help_text="Short notification headline.",
    )
    message = models.TextField(
        help_text="Detailed notification content body.",
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether the recipient has read this notification.",
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was marked as read.",
    )
    action_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Optional deep-link target URL or application route.",
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary structured metadata (e.g. order_id, order_number).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when notification was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of latest modification.",
    )

    objects = NotificationQuerySet.as_manager()

    class Meta:
        db_table = 'account_notifications'
        verbose_name = 'Account Notification'
        verbose_name_plural = 'Account Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at'], name='notif_user_read_created_idx'),
            models.Index(fields=['user', '-created_at'], name='notif_user_created_idx'),
        ]

    def __str__(self) -> str:
        status_str = "Read" if self.is_read else "Unread"
        return f"[{self.get_notification_type_display()}] {self.title} ({status_str}) -> {self.user}"

    def mark_as_read(self, save: bool = True):
        """
        Marks this notification as read and records current timestamp.
        """
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def mark_as_unread(self, save: bool = True):
        """
        Reverts this notification back to unread status.
        """
        if self.is_read:
            self.is_read = False
            self.read_at = None
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])


class EmailNotification(models.Model):
    """
    Email notification log, dispatch queue, and audit trail.
    Tracks outbound transactional and promotional emails with retry counters,
    error logging, delivery status, and provider message identifiers.
    """

    class EmailStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENDING = 'SENDING', 'Sending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_notifications',
        db_index=True,
        help_text="Recipient customer account if registered.",
    )
    recipient_email = models.EmailField(
        max_length=255,
        db_index=True,
        help_text="Destination email address.",
    )
    subject = models.CharField(
        max_length=255,
        help_text="Email subject line.",
    )
    body_text = models.TextField(
        blank=True,
        help_text="Plain text email body for email clients without HTML support.",
    )
    body_html = models.TextField(
        blank=True,
        help_text="Rendered HTML email body markup.",
    )
    template_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Identifier code of template used (e.g. order_confirmed, welcome_email).",
    )
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variables passed into email template renderer.",
    )
    status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
        db_index=True,
        help_text="Current dispatch lifecycle status.",
    )
    priority = models.CharField(
        max_length=20,
        choices=Notification.NotificationPriority.choices,
        default=Notification.NotificationPriority.NORMAL,
        help_text="Urgency priority.",
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Total number of dispatch attempts executed.",
    )
    max_retries = models.PositiveSmallIntegerField(
        default=3,
        help_text="Maximum allowed retry attempts before marking permanently failed.",
    )
    last_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of latest dispatch attempt.",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was successfully delivered to SMTP server / gateway.",
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Earliest scheduled dispatch timestamp for deferred messages.",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Latest error traceback or SMTP failure description.",
    )
    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Message ID assigned by provider (SMTP Message-ID, SendGrid, SES).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when email record was generated.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of latest update.",
    )

    class Meta:
        db_table = 'email_notifications'
        verbose_name = 'Email Notification'
        verbose_name_plural = 'Email Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at'], name='email_status_sched_idx'),
            models.Index(fields=['recipient_email', '-created_at'], name='email_recipient_created_idx'),
        ]

    def __str__(self) -> str:
        return f"[{self.get_status_display()}] {self.subject} -> {self.recipient_email}"

    def mark_as_sent(self, provider_message_id: str = None, save: bool = True):
        """
        Marks message as SENT, sets sent_at timestamp, and stores provider message ID.
        """
        self.status = self.EmailStatus.SENT
        self.sent_at = timezone.now()
        if provider_message_id:
            self.provider_message_id = provider_message_id
        if save:
            update_fields = ['status', 'sent_at', 'updated_at']
            if provider_message_id:
                update_fields.append('provider_message_id')
            self.save(update_fields=update_fields)

    def mark_as_failed(self, error_message: str, save: bool = True):
        """
        Increments attempt counter, records error message and last attempt timestamp.
        If attempts exceed max_retries, sets status to FAILED, otherwise leaves as PENDING.
        """
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.error_message = error_message
        if self.attempts >= self.max_retries:
            self.status = self.EmailStatus.FAILED
        else:
            self.status = self.EmailStatus.PENDING

        if save:
            self.save(update_fields=['attempts', 'last_attempt_at', 'error_message', 'status', 'updated_at'])

    def can_retry(self) -> bool:
        """
        Checks whether message is eligible for another dispatch attempt.
        """
        return self.status in [self.EmailStatus.PENDING, self.EmailStatus.FAILED] and self.attempts < self.max_retries


class NotificationPreference(models.Model):
    """
    Customer notification preference settings.
    Grants granular opt-in/opt-out control over email and in-app channels
    for transactional, marketing, and security notifications.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
        help_text="Account owner.",
    )
    email_order_updates = models.BooleanField(
        default=True,
        help_text="Receive order confirmations and delivery tracking updates via email.",
    )
    email_payment_receipts = models.BooleanField(
        default=True,
        help_text="Receive payment and refund confirmation receipts via email.",
    )
    email_promotions = models.BooleanField(
        default=False,
        help_text="Receive promotional discount codes and special offer newsletters.",
    )
    email_security_alerts = models.BooleanField(
        default=True,
        help_text="Receive security notifications such as password resets and new logins.",
    )
    in_app_order_updates = models.BooleanField(
        default=True,
        help_text="Show real-time order status changes inside the customer portal.",
    )
    in_app_payment_updates = models.BooleanField(
        default=True,
        help_text="Show payment success and refund alerts inside the customer portal.",
    )
    in_app_promotions = models.BooleanField(
        default=True,
        help_text="Show promotional announcements and coupon alerts inside the customer portal.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when preferences were created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of latest modification.",
    )

    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self) -> str:
        return f"Notification Preferences for {self.user}"


class NotificationTemplate(models.Model):
    """
    Template definition for dynamic notifications across channels.
    Provides database-driven subject, HTML, text, and in-app message templates.
    """

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique programmatic template identifier (e.g. order_confirmed, welcome_email).",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable template name.",
    )
    description = models.TextField(
        blank=True,
        help_text="Usage context and description of template parameters.",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=Notification.NotificationType.choices,
        default=Notification.NotificationType.SYSTEM,
        help_text="Notification category.",
    )
    email_subject_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Template string for email subject line.",
    )
    email_body_html_template = models.TextField(
        blank=True,
        help_text="HTML email body template markup.",
    )
    email_body_text_template = models.TextField(
        blank=True,
        help_text="Plain text email fallback template.",
    )
    in_app_title_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Template for in-app notification headline.",
    )
    in_app_message_template = models.TextField(
        blank=True,
        help_text="Template for in-app notification message content.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Controls whether this template can be rendered for dispatch.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Latest update timestamp.",
    )

    class Meta:
        db_table = 'notification_templates'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        ordering = ['code']

    def __str__(self) -> str:
        status_str = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({self.code}) [{status_str}]"
