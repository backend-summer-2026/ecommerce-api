from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.models import (
    EmailNotification,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)

User = get_user_model()


class CustomerNotificationAPITests(TestCase):
    """
    Integration tests for customer in-app notifications and preferences endpoints.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            first_name='Jasur',
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='Password123!',
            first_name='Sardor',
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        # Create notifications for self.user
        self.notif1 = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.ORDER,
            priority=Notification.NotificationPriority.NORMAL,
            title='Order Placed #101',
            message='Your order has been placed.',
            is_read=False,
        )
        self.notif2 = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.PAYMENT,
            priority=Notification.NotificationPriority.URGENT,
            title='Payment Received #101',
            message='Payment of 500,000 UZS received.',
            is_read=False,
        )
        self.notif3 = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.PROMOTION,
            priority=Notification.NotificationPriority.LOW,
            title='Weekend Discount',
            message='Get 10% off everything.',
            is_read=True,
        )

        # Other user's notification
        self.other_notif = Notification.objects.create(
            user=self.other_user,
            title='Other User Notification',
            message='Private alert',
        )

    def test_list_notifications_unauthenticated(self):
        self.client.force_authenticate(user=None)
        url = reverse('notifications:notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_notifications_authenticated_and_filters(self):
        url = reverse('notifications:notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

        # Filter by is_read=false
        response = self.client.get(url, {'is_read': 'false'})
        self.assertEqual(response.data['count'], 2)

        # Filter by type=ORDER
        response = self.client.get(url, {'type': 'ORDER'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Order Placed #101')

        # Filter by priority=URGENT
        response = self.client.get(url, {'priority': 'URGENT'})
        self.assertEqual(response.data['count'], 1)

        # Text search q
        response = self.client.get(url, {'q': 'Discount'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Weekend Discount')

    def test_unread_count(self):
        url = reverse('notifications:unread-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)
        self.assertEqual(response.data['urgent_count'], 1)

    def test_notification_detail(self):
        url = reverse('notifications:notification-detail', kwargs={'pk': self.notif1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Order Placed #101')

        # Accessing other user's notification returns 404
        other_url = reverse('notifications:notification-detail', kwargs={'pk': self.other_notif.pk})
        response = self.client.get(other_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_as_read_and_unread(self):
        read_url = reverse('notifications:mark-read', kwargs={'pk': self.notif1.pk})
        response = self.client.post(read_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_read'])
        self.assertIsNotNone(response.data['read_at'])

        unread_url = reverse('notifications:mark-unread', kwargs={'pk': self.notif1.pk})
        response = self.client.post(unread_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_read'])
        self.assertIsNone(response.data['read_at'])

    def test_mark_all_read(self):
        url = reverse('notifications:mark-all-read')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['marked_read_count'], 2)

        # Unread count should now be 0
        self.assertEqual(Notification.objects.for_user(self.user).unread().count(), 0)

    def test_delete_and_clear_read(self):
        # Delete single notification
        url = reverse('notifications:notification-detail', kwargs={'pk': self.notif3.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(pk=self.notif3.pk).exists())

        # Clear read
        clear_url = reverse('notifications:clear-read')
        # Mark one as read first
        self.notif1.mark_as_read()
        response = self.client.delete(clear_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 1)

    def test_preferences_get_and_update(self):
        url = reverse('notifications:preferences')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['email_order_updates'])
        self.assertFalse(response.data['email_promotions'])

        # Patch preferences
        response = self.client.patch(url, {
            'email_promotions': True,
            'in_app_promotions': False,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['email_promotions'])
        self.assertFalse(response.data['in_app_promotions'])


class AdminNotificationAPITests(TestCase):
    """
    Integration tests for administrative staff endpoints.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
        )
        self.customer = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            is_active=True,
        )
        self.client.force_authenticate(user=self.admin_user)

        self.template = NotificationTemplate.objects.create(
            code='order_ready',
            name='Order Ready for Pickup',
            notification_type=Notification.NotificationType.ORDER,
            email_subject_template='Order #{{ order_number }} is Ready',
            email_body_html_template='<p>Your order is ready!</p>',
            email_body_text_template='Your order is ready!',
            in_app_title_template='Order Ready',
            in_app_message_template='Your order #{{ order_number }} is ready for pickup.',
            is_active=True,
        )

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse('notifications:admin-in-app-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_list_in_app(self):
        Notification.objects.create(
            user=self.customer,
            title='Customer alert',
            message='Alert text',
        )
        url = reverse('notifications:admin-in-app-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_admin_broadcast_notification(self):
        url = reverse('notifications:admin-broadcast')
        payload = {
            'title': 'System Maintenance',
            'message': 'We will undergo 10 minutes maintenance tonight.',
            'notification_type': 'SYSTEM',
            'priority': 'HIGH',
            'broadcast': True,
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(response.data['created_count'], 2)  # admin and customer

    def test_admin_emails_queue_and_actions(self):
        email_record = EmailNotification.objects.create(
            recipient_email='user@example.com',
            subject='Queued Email',
            body_text='Body text',
            status=EmailNotification.EmailStatus.PENDING,
        )

        list_url = reverse('notifications:admin-email-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

        detail_url = reverse('notifications:admin-email-detail', kwargs={'pk': email_record.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subject'], 'Queued Email')

        # Cancel pending email
        cancel_url = reverse('notifications:admin-email-cancel', kwargs={'pk': email_record.pk})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        email_record.refresh_from_db()
        self.assertEqual(email_record.status, EmailNotification.EmailStatus.CANCELLED)

        # Retry failed email
        failed_email = EmailNotification.objects.create(
            recipient_email='failed@example.com',
            subject='Failed Email',
            body_text='Body text',
            status=EmailNotification.EmailStatus.FAILED,
            attempts=1,
            max_retries=3,
        )
        retry_url = reverse('notifications:admin-email-retry', kwargs={'pk': failed_email.pk})
        response = self.client.post(retry_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        failed_email.refresh_from_db()
        self.assertEqual(failed_email.status, EmailNotification.EmailStatus.SENT)

    def test_admin_templates_crud(self):
        # List
        list_url = reverse('notifications:admin-template-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

        # Create
        create_payload = {
            'code': 'pwd_reset',
            'name': 'Password Reset Template',
            'notification_type': 'ACCOUNT',
            'email_subject_template': 'Reset your password',
            'email_body_html_template': '<p>Reset link: {{ link }}</p>',
            'email_body_text_template': 'Reset link: {{ link }}',
            'is_active': True,
        }
        response = self.client.post(list_url, create_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(NotificationTemplate.objects.filter(code='pwd_reset').exists())

        # Detail & Update
        detail_url = reverse('notifications:admin-template-detail', kwargs={'code': 'pwd_reset'})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(detail_url, {'name': 'Updated Password Reset'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Password Reset')

        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(NotificationTemplate.objects.filter(code='pwd_reset').exists())

    def test_admin_template_test_send(self):
        url = reverse('notifications:admin-template-test-send', kwargs={'code': self.template.code})
        payload = {
            'test_email': 'testrecipient@example.com',
            'user_id': self.customer.id,
            'context_data': {'order_number': 'ORD-888'},
            'send_email': True,
            'send_in_app': True,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rendered_preview']['email_subject'], 'Order #ORD-888 is Ready')
        self.assertIsNotNone(response.data['dispatched']['email']['id'])
        self.assertIsNotNone(response.data['dispatched']['in_app']['id'])
        self.assertEqual(len(mail.outbox), 1)
