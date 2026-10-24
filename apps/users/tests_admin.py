from datetime import timedelta
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.orders.models import Order
from apps.users.admin import (
    HasOrdersFilter,
    OTPCodeAdmin,
    OTPCodeInline,
    UserAdmin,
)
from apps.users.forms import UserAdminChangeForm, UserAdminCreationForm
from apps.users.models import OTPCode, User


class MockRequest:
    def __init__(self, user=None):
        self.user = user


class UsersAdminTestCase(TestCase):
    """
    Test suite for enhanced UserAdmin and OTPCodeAdmin with Jazzmin interface.
    """

    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

        # Create admin user
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='Chief',
            phone_number='+998901112233',
        )

        # Create regular customer
        self.customer_user = User.objects.create_user(
            email='customer@example.com',
            password='Password123!',
            first_name='Ali',
            last_name='Valiyev',
            phone_number='+998909998877',
        )
        self.customer_user.is_active = True
        self.customer_user.save()

        # Create inactive user without name
        self.inactive_user = User.objects.create_user(
            email='inactive@example.com',
            password='Password123!',
            phone_number=None,
        )

        # Create staff user
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='Password123!',
            first_name='Staff',
            last_name='Member',
            is_staff=True,
            is_active=True,
        )

        # Create OTP codes
        self.valid_otp = OTPCode.objects.create(
            user=self.customer_user,
            code='123456',
            otp_type=OTPCode.OTPType.REGISTER,
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=False,
        )

        self.used_otp = OTPCode.objects.create(
            user=self.customer_user,
            code='654321',
            otp_type=OTPCode.OTPType.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=True,
        )

        self.expired_otp = OTPCode.objects.create(
            user=self.customer_user,
            code='999999',
            otp_type=OTPCode.OTPType.PASSWORD_RESET,
            expires_at=timezone.now() - timedelta(minutes=10),
            is_used=False,
        )

        self.user_admin = UserAdmin(User, self.site)
        self.otp_admin = OTPCodeAdmin(OTPCode, self.site)
        self.otp_inline = OTPCodeInline(User, self.site)

    def _get_request_with_messages(self):
        request = self.factory.get('/admin/')
        request.user = self.admin_user
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    def test_user_admin_displays(self):
        # email_display
        email_html = self.user_admin.email_display(self.customer_user)
        self.assertIn('customer@example.com', email_html)
        self.assertIn('fa-user-circle', email_html)

        # full_name_display
        full_name_html = self.user_admin.full_name_display(self.customer_user)
        self.assertIn('Ali Valiyev', full_name_html)

        # full_name_display fallback when no name
        empty_name_html = self.user_admin.full_name_display(self.inactive_user)
        self.assertIn('-', empty_name_html)

        # phone_number_display
        phone_html = self.user_admin.phone_number_display(self.customer_user)
        self.assertIn('+998909998877', phone_html)
        self.assertIn('fa-phone-alt', phone_html)

        empty_phone_html = self.user_admin.phone_number_display(self.inactive_user)
        self.assertIn('-', empty_phone_html)

        # role_badge
        admin_badge = self.user_admin.role_badge(self.admin_user)
        self.assertIn('badge-danger', admin_badge)
        self.assertIn('Admin', admin_badge)

        customer_badge = self.user_admin.role_badge(self.customer_user)
        self.assertIn('badge-info', customer_badge)
        self.assertIn('Mijoz', customer_badge)

        # status_badge
        active_badge = self.user_admin.status_badge(self.customer_user)
        self.assertIn('badge-success', active_badge)
        self.assertIn('Faol', active_badge)

        inactive_badge = self.user_admin.status_badge(self.inactive_user)
        self.assertIn('badge-secondary', inactive_badge)
        self.assertIn('Nofaol', inactive_badge)

        # staff_badge
        superadmin_badge = self.user_admin.staff_badge(self.admin_user)
        self.assertIn('Superadmin', superadmin_badge)

        staff_badge = self.user_admin.staff_badge(self.staff_user)
        self.assertIn('Xodim', staff_badge)

        regular_badge = self.user_admin.staff_badge(self.customer_user)
        self.assertIn('-', regular_badge)

        # created_at_display
        created_display = self.user_admin.created_at_display(self.customer_user)
        self.assertIn(self.customer_user.created_at.strftime('%Y-%m-%d'), created_display)

    def test_user_admin_orders_count_display(self):
        # When 0 orders
        count_zero = self.user_admin.orders_count_display(self.customer_user)
        self.assertIn('0 ta', count_zero)

        # Create an order for the user
        Order.objects.create(
            user=self.customer_user,
            order_number='ORD-TEST-001',
            status=Order.OrderStatus.PENDING,
            subtotal=100.0,
            total_price=100.0,
        )

        request = self.factory.get('/admin/users/user/')
        request.user = self.admin_user
        qs = self.user_admin.get_queryset(request)
        user_with_order = qs.get(id=self.customer_user.id)

        count_display = self.user_admin.orders_count_display(user_with_order)
        self.assertIn('1 ta', count_display)
        self.assertIn('badge-primary', count_display)
        self.assertIn('/admin/orders/order/?user__id__exact=', count_display)

        # orders_summary_display
        summary = self.user_admin.orders_summary_display(user_with_order)
        self.assertIn('Jami buyurtmalar soni: <strong>1 ta</strong>', summary)

    def test_user_admin_actions(self):
        req = self._get_request_with_messages()
        queryset = User.objects.filter(id=self.inactive_user.id)

        # Activate
        self.user_admin.activate_users(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_active)

        # Deactivate
        self.user_admin.deactivate_users(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertFalse(self.inactive_user.is_active)

        # Make Admin
        self.user_admin.make_admin_role(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertEqual(self.inactive_user.role, User.Role.ADMIN)

        # Make Customer
        self.user_admin.make_customer_role(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertEqual(self.inactive_user.role, User.Role.CUSTOMER)

        # Make Staff
        self.user_admin.make_staff_status(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_staff)

        # Remove Staff
        self.user_admin.remove_staff_status(req, queryset)
        self.inactive_user.refresh_from_db()
        self.assertFalse(self.inactive_user.is_staff)

    def test_has_orders_filter(self):
        # Create an order for customer_user
        Order.objects.create(
            user=self.customer_user,
            order_number='ORD-TEST-FILTER',
            status=Order.OrderStatus.PENDING,
            subtotal=50.0,
            total_price=50.0,
        )

        request = self.factory.get('/admin/users/user/')
        request.user = self.admin_user

        # Test filter lookups
        f = HasOrdersFilter(request, {}, User, self.user_admin)
        lookups = dict(f.lookups(request, self.user_admin))
        self.assertIn('yes', lookups)
        self.assertIn('no', lookups)

        # Filter 'yes'
        f_yes = HasOrdersFilter(request, {'has_orders': ['yes']}, User, self.user_admin)
        qs_yes = f_yes.queryset(request, User.objects.all())
        self.assertIn(self.customer_user, qs_yes)
        self.assertNotIn(self.inactive_user, qs_yes)

        # Filter 'no'
        f_no = HasOrdersFilter(request, {'has_orders': ['no']}, User, self.user_admin)
        qs_no = f_no.queryset(request, User.objects.all())
        self.assertNotIn(self.customer_user, qs_no)
        self.assertIn(self.inactive_user, qs_no)

        # Filter None
        f_all = HasOrdersFilter(request, {}, User, self.user_admin)
        qs_all = f_all.queryset(request, User.objects.all())
        self.assertEqual(qs_all.count(), User.objects.count())

    def test_otp_inline(self):
        request = self.factory.get('/admin/')
        request.user = self.admin_user

        # has_add_permission should be False
        self.assertFalse(self.otp_inline.has_add_permission(request))

        # code_display
        code_html = self.otp_inline.code_display(self.valid_otp)
        self.assertIn('123456', code_html)

        # otp_type_badge
        type_html = self.otp_inline.otp_type_badge(self.valid_otp)
        self.assertIn("Ro‘yxatdan o‘tish", type_html)

        # status_badge valid
        valid_badge = self.otp_inline.status_badge(self.valid_otp)
        self.assertIn('Yaroqli', valid_badge)

        # status_badge used
        used_badge = self.otp_inline.status_badge(self.used_otp)
        self.assertIn('Ishlatilgan', used_badge)

        # status_badge expired
        expired_badge = self.otp_inline.status_badge(self.expired_otp)
        self.assertIn('Muddati o‘tgan', expired_badge)

    def test_otp_code_admin(self):
        req = self._get_request_with_messages()

        # user_link
        user_link_html = self.otp_admin.user_link(self.valid_otp)
        self.assertIn(self.customer_user.email, user_link_html)
        self.assertIn(f"/admin/users/user/{self.customer_user.id}/change/", user_link_html)

        # code_display
        code_html = self.otp_admin.code_display(self.valid_otp)
        self.assertIn('123456', code_html)

        # otp_type_badge
        reg_badge = self.otp_admin.otp_type_badge(self.valid_otp)
        self.assertIn("Ro‘yxatdan o‘tish", reg_badge)
        self.assertIn("badge-info", reg_badge)

        login_badge = self.otp_admin.otp_type_badge(self.used_otp)
        self.assertIn("Tizimga kirish", login_badge)
        self.assertIn("badge-success", login_badge)

        pw_badge = self.otp_admin.otp_type_badge(self.expired_otp)
        self.assertIn("Parolni tiklash", pw_badge)
        self.assertIn("badge-warning", pw_badge)

        # status_badge & status_display
        status_disp = self.otp_admin.status_display(self.valid_otp)
        self.assertIn("Yaroqli", status_disp)

        # action: mark_as_used
        otp_qs = OTPCode.objects.filter(id=self.valid_otp.id)
        self.otp_admin.mark_as_used(req, otp_qs)
        self.valid_otp.refresh_from_db()
        self.assertTrue(self.valid_otp.is_used)

        # action: invalidate_codes
        new_otp = OTPCode.objects.create(
            user=self.customer_user,
            code='777777',
            otp_type=OTPCode.OTPType.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=15),
            is_used=False,
        )
        self.assertTrue(new_otp.is_valid())
        self.otp_admin.invalidate_codes(req, OTPCode.objects.filter(id=new_otp.id))
        new_otp.refresh_from_db()
        self.assertFalse(new_otp.is_valid())

    def test_user_admin_forms(self):
        # Test UserAdminCreationForm
        form_data = {
            'email': 'new_created@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '+998901234567',
            'role': User.Role.CUSTOMER,
            'password1': 'SecretP@ss123',
            'password2': 'SecretP@ss123',
        }
        form = UserAdminCreationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        created_user = form.save()
        self.assertEqual(created_user.email, 'new_created@example.com')
        self.assertTrue(created_user.check_password('SecretP@ss123'))

        # Test UserAdminChangeForm
        change_data = {
            'email': 'new_created@example.com',
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone_number': '+998901234567',
            'role': User.Role.ADMIN,
            'is_active': True,
            'is_staff': True,
        }
        change_form = UserAdminChangeForm(data=change_data, instance=created_user)
        self.assertTrue(change_form.is_valid(), change_form.errors)
        updated_user = change_form.save()
        self.assertEqual(updated_user.first_name, 'Updated')
        self.assertEqual(updated_user.role, User.Role.ADMIN)
