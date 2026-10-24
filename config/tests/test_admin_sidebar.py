from django.test import TestCase, Client
from django.conf import settings
from apps.users.models import User
from pathlib import Path


class AdminSidebarAccordionTests(TestCase):
    """
    Test suite for Django Admin sidebar collapsible menu, accordion, and custom JS.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            phone_number='+998901234567',
            email='admin@test.com',
            password='password123',
            is_staff=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_jazzmin_settings_sidebar_collapsed(self):
        """Test that navigation_expanded is False and custom_js is configured."""
        jazzmin_settings = getattr(settings, 'JAZZMIN_SETTINGS', {})
        self.assertFalse(jazzmin_settings.get('navigation_expanded', True))
        self.assertEqual(jazzmin_settings.get('custom_js'), 'admin/js/custom_sidebar.js')

    def test_staticfiles_dirs_configured(self):
        """Test that STATICFILES_DIRS includes project static directory."""
        staticfiles_dirs = getattr(settings, 'STATICFILES_DIRS', [])
        expected_dir = settings.BASE_DIR / 'static'
        self.assertIn(expected_dir, staticfiles_dirs)

    def test_custom_sidebar_js_file_exists(self):
        """Test that custom_sidebar.js exists and contains accordion logic."""
        js_file = settings.BASE_DIR / 'static' / 'admin' / 'js' / 'custom_sidebar.js'
        self.assertTrue(js_file.exists(), f"File {js_file} does not exist")
        content = js_file.read_text(encoding='utf-8')
        self.assertIn('data-accordion', content)
        self.assertIn('has-treeview', content)
        self.assertIn('initAccordion', content)
        self.assertIn('autoExpandActiveApp', content)

    def test_admin_index_sidebar_renders_treeview(self):
        """Test that /admin/ renders collapsible treeview items instead of flat nav-headers."""
        response = self.client.get('/admin/', HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Should contain has-treeview for apps
        self.assertGreater(content.count('has-treeview'), 0)
        # Should not contain flat nav-headers
        self.assertEqual(content.count('nav-header'), 0)
        # Should include custom_sidebar.js script
        self.assertIn('admin/js/custom_sidebar.js', content)

    def test_admin_changelist_sidebar_renders_treeview(self):
        """Test that /admin/orders/order/ renders treeview and includes custom_sidebar.js."""
        response = self.client.get('/admin/orders/order/', HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertGreater(content.count('has-treeview'), 0)
        self.assertEqual(content.count('nav-header'), 0)
        self.assertIn('admin/js/custom_sidebar.js', content)
