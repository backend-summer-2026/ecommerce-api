from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)
from apps.notifications.services import (
    EmailService,
    NotificationService,
    TemplateRenderService,
)

User = get_user_model()


class TemplateRenderServiceTests(TestCase):
    """
    Unit tests for TemplateRenderService.
    """

    def setUp(self):
        self.template = NotificationTemplate.objects.create(
            code='order_confirmed_test',
            name='Order Confirmed Test',
            notification_type=Notification.NotificationType.ORDER,
            email_subject_template='Order #{{ order_number }} Confirmed',
            email_body_html_template='<h1>Hello {{ name }}</h1><p>Your order total is {{ total }}.</p>',
            email_body_text_template='Hello {{ name }}, your order total is {{ total }}.',
            in_app_title_template='Order #{{ order_number }} Placed',
            in_app_message_template='Thank you {{ name }}! Your order #{{ order_number }} is being processed.',
            is_active=True,
        )

    def test_render_template_success(self):
        context = {
            'name': 'Ali',
            'order_number': 'ORD-12345',
            'total': '150,000 UZS',
        }
        rendered = TemplateRenderService.render_template('order_confirmed_test', context)
        self.assertEqual(rendered['email_subject'], 'Order #ORD-12345 Confirmed')
        self.assertIn('<h1>Hello Ali</h1>', rendered['email_body_html'])
        self.assertIn('Hello Ali, your order total is 150,000 UZS.', rendered['email_body_text'])
        self.assertEqual(rendered['in_app_title'], 'Order #ORD-12345 Placed')
        self.assertIn('Thank you Ali!', rendered['in_app_message'])

    def test_render_nonexistent_or_inactive_template_raises(self):
        with self.assertRaises(ValidationError):
            TemplateRenderService.render_template('nonexistent_template', {})

        self.template.is_active = False
        self.template.save()

        with self.assertRaises(ValidationError):
            TemplateRenderService.render_template('order_confirmed_test', {})


class NotificationServiceTests(TestCase):
    """
    Unit tests for NotificationService.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            first_name='Anvar',
            is_active=True,
        )
        self.pref = NotificationPreference.objects.create(
            user=self.user,
            in_app_order_updates=True,
            in_app_promotions=False,  # opted out of in-app promotions
        )

    def test_send_in_app_allowed(self):
        notif = NotificationService.send_in_app(
            user=self.user,
            title='Order Shipped',
            message='Your order is on the way.',
            notification_type=Notification.NotificationType.ORDER,
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.user, self.user)
        self.assertEqual(notif.title, 'Order Shipped')

    def test_send_in_app_opted_out_skipped(self):
        notif = NotificationService.send_in_app(
            user=self.user,
            title='Big Sale 50% Off!',
            message='Check out our latest flash sale.',
            notification_type=Notification.NotificationType.PROMOTION,
        )
        self.assertIsNone(notif)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_send_in_app_urgent_or_forced_overrides_opt_out(self):
        notif = NotificationService.send_in_app(
            user=self.user,
            title='Urgent Promotion',
            message='Exclusive one-time deal',
            notification_type=Notification.NotificationType.PROMOTION,
            priority=Notification.NotificationPriority.URGENT,
        )
        self.assertIsNotNone(notif)

    def test_broadcast_notifications(self):
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='Password123!',
            is_active=True,
        )
        NotificationPreference.objects.create(
            user=user2,
            in_app_promotions=True,
        )

        count = NotificationService.broadcast(
            title='Holiday Discount!',
            message='Enjoy our holiday promotion.',
            notification_type=Notification.NotificationType.PROMOTION,
            priority=Notification.NotificationPriority.NORMAL,
        )
        # user1 has in_app_promotions=False, user2 has True
        self.assertEqual(count, 1)
        self.assertEqual(Notification.objects.filter(user=user2).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_read_unread_clear_operations(self):
        notif1 = Notification.objects.create(user=self.user, title='N1', message='M1')
        notif2 = Notification.objects.create(user=self.user, title='N2', message='M2')

        counters = NotificationService.get_unread_count(self.user)
        self.assertEqual(counters['unread_count'], 2)

        NotificationService.mark_as_read(notif1, self.user)
        notif1.refresh_from_db()
        self.assertTrue(notif1.is_read)
        self.assertIsNotNone(notif1.read_at)

        NotificationService.mark_as_unread(notif1, self.user)
        notif1.refresh_from_db()
        self.assertFalse(notif1.is_read)

        marked = NotificationService.mark_all_as_read(self.user)
        self.assertEqual(marked, 2)
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=True).count(), 2)

        deleted = NotificationService.clear_read_notifications(self.user)
        self.assertEqual(deleted, 2)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)


class EmailServiceTests(TestCase):
    """
    Unit tests for EmailService.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
        )
        self.pref = NotificationPreference.objects.create(
            user=self.user,
            email_order_updates=True,
            email_promotions=False,  # opted out
        )
        self.template = NotificationTemplate.objects.create(
            code='order_receipt',
            name='Order Receipt',
            notification_type=Notification.NotificationType.ORDER,
            email_subject_template='Receipt for Order {{ order_id }}',
            email_body_html_template='<p>Thanks for ordering #{{ order_id }}!</p>',
            email_body_text_template='Thanks for ordering #{{ order_id }}!',
            is_active=True,
        )

    def test_send_or_queue_email_success(self):
        email_record = EmailService.send_or_queue_email(
            recipient_email=self.user.email,
            user=self.user,
            template_code='order_receipt',
            context_data={'order_id': 999},
            send_immediately=True,
        )

        self.assertIsNotNone(email_record)
        self.assertEqual(email_record.status, EmailNotification.EmailStatus.SENT)
        self.assertEqual(email_record.subject, 'Receipt for Order 999')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Receipt for Order 999')
        self.assertIn('Thanks for ordering #999!', mail.outbox[0].body)

    def test_send_or_queue_email_opted_out_skipped(self):
        # Create marketing template
        promo_template = NotificationTemplate.objects.create(
            code='weekly_promo',
            name='Weekly Promo',
            notification_type=Notification.NotificationType.PROMOTION,
            email_subject_template='Weekly Sale',
            email_body_text_template='Save 20% today!',
            is_active=True,
        )

        email_record = EmailService.send_or_queue_email(
            recipient_email=self.user.email,
            user=self.user,
            template_code='weekly_promo',
            context_data={},
            send_immediately=True,
        )
        self.assertIsNone(email_record)
        self.assertEqual(len(mail.outbox), 0)

    def test_retry_and_cancel_email(self):
        email_record = EmailNotification.objects.create(
            recipient_email='test@example.com',
            subject='Failed Test',
            body_text='Failed body',
            status=EmailNotification.EmailStatus.FAILED,
            attempts=1,
            max_retries=3,
        )

        # Retry should dispatch
        success = EmailService.retry_email(email_record)
        self.assertTrue(success)
        email_record.refresh_from_db()
        self.assertEqual(email_record.status, EmailNotification.EmailStatus.SENT)
        self.assertEqual(email_record.attempts, 2)

        # Cancel pending email
        pending_email = EmailNotification.objects.create(
            recipient_email='pending@example.com',
            subject='Pending Subject',
            body_text='Pending body',
            status=EmailNotification.EmailStatus.PENDING,
        )
        EmailService.cancel_email(pending_email)
        pending_email.refresh_from_db()
        self.assertEqual(pending_email.status, EmailNotification.EmailStatus.CANCELLED)
