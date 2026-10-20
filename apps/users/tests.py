from datetime import timedelta
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import OTPCode, User
from .services import create_otp_for_user


class UserModelTests(APITestCase):
    """
    Unit tests for custom User model and UserManager.
    """

    def test_create_user_successful(self):
        user = User.objects.create_user(
            email='testuser@example.com',
            password='StrongPassword123!',
            first_name='Ali',
            last_name='Valiyev',
        )
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertTrue(user.check_password('StrongPassword123!'))
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.full_name, 'Ali Valiyev')

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='password123')

    def test_create_superuser_successful(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='User',
        )
        self.assertEqual(admin.email, 'admin@example.com')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
        self.assertEqual(admin.role, User.Role.ADMIN)


class OTPCodeModelTests(APITestCase):
    """
    Unit tests for OTPCode model.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='otpuser@example.com',
            password='password123',
        )

    def test_otp_is_valid(self):
        otp = create_otp_for_user(self.user)
        self.assertTrue(otp.is_valid())

    def test_otp_expired_is_not_valid(self):
        otp = create_otp_for_user(self.user)
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        self.assertFalse(otp.is_valid())

    def test_otp_used_is_not_valid(self):
        otp = create_otp_for_user(self.user)
        otp.is_used = True
        otp.save()
        self.assertFalse(otp.is_valid())


class AuthenticationAPITests(APITestCase):
    """
    Integration tests for registration, OTP verification, resend, login, and profile.
    """

    def test_register_creates_inactive_user_and_sends_email(self):
        url = reverse('users:register')
        payload = {
            'email': 'customer@example.com',
            'first_name': 'Botir',
            'last_name': 'Zokirov',
            'phone_number': '+998901234567',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.filter(email='customer@example.com').first()
        self.assertIsNotNone(user)
        self.assertFalse(user.is_active)

        # Check OTP created
        otp = OTPCode.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.code), 6)

        # Check email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(otp.code, mail.outbox[0].body)
        self.assertIn('customer@example.com', mail.outbox[0].to)

    def test_register_password_mismatch(self):
        url = reverse('users:register')
        payload = {
            'email': 'mismatch@example.com',
            'password': 'Password123!',
            'password_confirm': 'DifferentPassword123!',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_verify_otp_activates_user_and_issues_jwt(self):
        user = User.objects.create_user(
            email='verify@example.com',
            password='StrongPassword123!',
            is_active=False,
        )
        otp = create_otp_for_user(user)

        url = reverse('users:verify-otp')
        payload = {
            'email': 'verify@example.com',
            'code': otp.code,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])

    def test_verify_otp_invalid_code(self):
        user = User.objects.create_user(
            email='invalidcode@example.com',
            password='StrongPassword123!',
            is_active=False,
        )
        create_otp_for_user(user)

        url = reverse('users:verify-otp')
        payload = {
            'email': 'invalidcode@example.com',
            'code': '000000',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_resend_otp_cooldown_enforced(self):
        user = User.objects.create_user(
            email='cooldown@example.com',
            password='StrongPassword123!',
            is_active=False,
        )
        create_otp_for_user(user)

        url = reverse('users:resend-otp')
        payload = {'email': 'cooldown@example.com'}

        # Immediate resend should be blocked by cooldown
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_resend_otp_after_cooldown_success(self):
        user = User.objects.create_user(
            email='resendok@example.com',
            password='StrongPassword123!',
            is_active=False,
        )
        otp = create_otp_for_user(user)
        # Simulate elapsed time past cooldown
        OTPCode.objects.filter(id=otp.id).update(
            created_at=timezone.now() - timedelta(seconds=70)
        )

        mail.outbox.clear()
        url = reverse('users:resend-otp')
        payload = {'email': 'resendok@example.com'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_login_inactive_user_fails(self):
        User.objects.create_user(
            email='inactive@example.com',
            password='StrongPassword123!',
            is_active=False,
        )
        url = reverse('users:login')
        payload = {
            'email': 'inactive@example.com',
            'password': 'StrongPassword123!',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_active_user_success(self):
        User.objects.create_user(
            email='active@example.com',
            password='StrongPassword123!',
            is_active=True,
        )
        url = reverse('users:login')
        payload = {
            'email': 'active@example.com',
            'password': 'StrongPassword123!',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])

    def test_user_profile_me_endpoint(self):
        user = User.objects.create_user(
            email='profile@example.com',
            password='StrongPassword123!',
            first_name='Anvar',
            last_name='Toshmatov',
            is_active=True,
        )
        url = reverse('users:profile-me')

        # Unauthenticated request should be 401
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated request
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertEqual(response.data['first_name'], 'Anvar')
