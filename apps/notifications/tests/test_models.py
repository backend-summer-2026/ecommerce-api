from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)

User = get_user_model()


class NotificationModelTests(TestCase):
    """
    Unit tests for the in-app / account Notification model and NotificationQuerySet.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='SecretPassword123!',
            first_name='Ali',
            last_name='Valiyev',
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='SecretPassword123!',
            first_name='Bobur',
            last_name='Toshmatov',
        )

    def test_create_notification_defaults(self):
        """Notification should be created with correct defaults."""
        notification = Notification.objects.create(
            user=self.user,
            title='Order Confirmed',
            message='Your order #ORD-1001 has been confirmed.',
        )

        self.assertEqual(notification.notification_type, Notification.NotificationType.SYSTEM)
        self.assertEqual(notification.priority, Notification.NotificationPriority.NORMAL)
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        self.assertIsNone(notification.action_url)
        self.assertEqual(notification.data, {})
        self.assertIn('Unread', str(notification))

    def test_mark_as_read(self):
        """mark_as_read should set is_read=True and update read_at timestamp."""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.ORDER,
            title='Order Shipped',
            message='Your package is on its way.',
        )
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

        notification.mark_as_read()
        notification.refresh_from_db()

        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
        self.assertIn('Read', str(notification))

    def test_mark_as_unread(self):
        """mark_as_unread should revert is_read=False and clear read_at."""
        notification = Notification.objects.create(
            user=self.user,
            title='Security Alert',
            message='New login detected.',
            is_read=True,
            read_at=timezone.now(),
        )
        self.assertTrue(notification.is_read)

        notification.mark_as_unread()
        notification.refresh_from_db()

        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_notification_queryset_unread_and_read(self):
        """QuerySet unread and read methods filter correctly."""
        n1 = Notification.objects.create(user=self.user, title='N1', message='M1', is_read=False)
        n2 = Notification.objects.create(user=self.user, title='N2', message='M2', is_read=True, read_at=timezone.now())
        n3 = Notification.objects.create(user=self.other_user, title='N3', message='M3', is_read=False)

        user_notifications = Notification.objects.for_user(self.user)
        self.assertEqual(user_notifications.count(), 2)

        unread_notifications = Notification.objects.for_user(self.user).unread()
        self.assertEqual(unread_notifications.count(), 1)
        self.assertEqual(unread_notifications.first(), n1)

        read_notifications = Notification.objects.for_user(self.user).read()
        self.assertEqual(read_notifications.count(), 1)
        self.assertEqual(read_notifications.first(), n2)

    def test_mark_all_as_read_and_unread(self):
        """QuerySet batch operations mark_all_as_read and mark_all_as_unread work."""
        Notification.objects.create(user=self.user, title='N1', message='M1', is_read=False)
        Notification.objects.create(user=self.user, title='N2', message='M2', is_read=False)

        # Batch mark read
        updated = Notification.objects.for_user(self.user).mark_all_as_read()
        self.assertEqual(updated, 2)
        self.assertEqual(Notification.objects.for_user(self.user).unread().count(), 0)
        self.assertEqual(Notification.objects.for_user(self.user).read().count(), 2)

        # Batch mark unread
        reverted = Notification.objects.for_user(self.user).mark_all_as_unread()
        self.assertEqual(reverted, 2)
        self.assertEqual(Notification.objects.for_user(self.user).unread().count(), 2)
        self.assertEqual(Notification.objects.for_user(self.user).read().count(), 0)

    def test_notification_with_payload_and_action(self):
        """Notification preserves action_url and JSON data payload."""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.PAYMENT,
            priority=Notification.NotificationPriority.HIGH,
            title='Payment Received',
            message='Payment of 250,000 UZS processed successfully.',
            action_url='/orders/ORD-20261022-8F9B2C/',
            data={'payment_id': 12, 'order_number': 'ORD-20261022-8F9B2C', 'amount': '250000.00'},
        )

        notification.refresh_from_db()
        self.assertEqual(notification.action_url, '/orders/ORD-20261022-8F9B2C/')
        self.assertEqual(notification.data['order_number'], 'ORD-20261022-8F9B2C')
        self.assertEqual(notification.priority, Notification.NotificationPriority.HIGH)


class EmailNotificationModelTests(TestCase):
    """
    Unit tests for the EmailNotification model.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com',
            password='SecurePassword123!',
        )

    def test_create_email_notification_defaults(self):
        """EmailNotification should be created with PENDING status and zero attempts."""
        email = EmailNotification.objects.create(
            user=self.user,
            recipient_email=self.user.email,
            subject='Welcome to our store!',
            body_text='Thank you for registering.',
            body_html='<h1>Thank you for registering.</h1>',
            template_code='welcome_email',
        )

        self.assertEqual(email.status, EmailNotification.EmailStatus.PENDING)
        self.assertEqual(email.attempts, 0)
        self.assertEqual(email.max_retries, 3)
        self.assertIsNone(email.sent_at)
        self.assertIsNone(email.last_attempt_at)
        self.assertIsNone(email.provider_message_id)
        self.assertTrue(email.can_retry())
        self.assertIn('Pending', str(email))

    def test_mark_as_sent(self):
        """mark_as_sent should update status to SENT, record sent_at and provider message ID."""
        email = EmailNotification.objects.create(
            recipient_email='guest@example.com',
            subject='Your receipt',
            body_text='Receipt details.',
        )

        email.mark_as_sent(provider_message_id='msg-ses-123456')
        email.refresh_from_db()

        self.assertEqual(email.status, EmailNotification.EmailStatus.SENT)
        self.assertIsNotNone(email.sent_at)
        self.assertEqual(email.provider_message_id, 'msg-ses-123456')
        self.assertFalse(email.can_retry())

    def test_mark_as_failed_and_retry_lifecycle(self):
        """mark_as_failed increments attempts and transitions to FAILED when max_retries reached."""
        email = EmailNotification.objects.create(
            recipient_email='customer@example.com',
            subject='Invoice',
            max_retries=2,
        )

        # Attempt 1: Failed
        email.mark_as_failed('SMTP connection timed out')
        email.refresh_from_db()

        self.assertEqual(email.attempts, 1)
        self.assertEqual(email.status, EmailNotification.EmailStatus.PENDING)
        self.assertTrue(email.can_retry())
        self.assertEqual(email.error_message, 'SMTP connection timed out')

        # Attempt 2: Reaches max_retries
        email.mark_as_failed('550 Mailbox does not exist')
        email.refresh_from_db()

        self.assertEqual(email.attempts, 2)
        self.assertEqual(email.status, EmailNotification.EmailStatus.FAILED)
        self.assertFalse(email.can_retry())
        self.assertEqual(email.error_message, '550 Mailbox does not exist')


class NotificationPreferenceModelTests(TestCase):
    """
    Unit tests for the NotificationPreference model.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='prefs@example.com',
            password='SecurePassword123!',
        )

    def test_create_and_access_preferences(self):
        """Preferences should have expected default flags and OneToOne relationship."""
        pref = NotificationPreference.objects.create(user=self.user)

        self.assertTrue(pref.email_order_updates)
        self.assertTrue(pref.email_payment_receipts)
        self.assertFalse(pref.email_promotions)
        self.assertTrue(pref.email_security_alerts)
        self.assertTrue(pref.in_app_order_updates)
        self.assertTrue(pref.in_app_payment_updates)
        self.assertTrue(pref.in_app_promotions)

        # Accessible through related_name
        self.assertEqual(self.user.notification_preference, pref)
        self.assertIn(self.user.email, str(pref))


class NotificationTemplateModelTests(TestCase):
    """
    Unit tests for the NotificationTemplate model.
    """

    def test_create_notification_template(self):
        """NotificationTemplate stores templates and enforces unique code constraint."""
        template = NotificationTemplate.objects.create(
            code='order_confirmed',
            name='Order Confirmation',
            notification_type=Notification.NotificationType.ORDER,
            email_subject_template='Order Confirmed: {{ order.order_number }}',
            email_body_html_template='<p>Hello {{ user.first_name }}, your order is placed.</p>',
            in_app_title_template='Order {{ order.order_number }} Confirmed',
            in_app_message_template='Your order has been confirmed and is being processed.',
            is_active=True,
        )

        self.assertEqual(template.code, 'order_confirmed')
        self.assertTrue(template.is_active)
        self.assertIn('order_confirmed', str(template))

        # Enforce unique code
        with self.assertRaises(IntegrityError):
            NotificationTemplate.objects.create(
                code='order_confirmed',
                name='Duplicate Order Confirmation',
            )
