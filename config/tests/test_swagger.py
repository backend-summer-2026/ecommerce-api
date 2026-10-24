import json
from django.test import TestCase
from django.urls import reverse
from rest_framework import status


class SwaggerDocumentationTests(TestCase):
    """
    Test suite for OpenAPI 3.0 Schema and Interactive Documentation (Swagger UI & Redoc).
    """

    def test_schema_endpoint_returns_200_and_valid_spec(self):
        """Verify that /api/schema/ produces valid OpenAPI 3.0 schema."""
        url = reverse('schema')
        response = self.client.get(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response content should be valid JSON
        data = response.json() if hasattr(response, 'json') else json.loads(response.content.decode('utf-8'))

        # Check OpenAPI version and core metadata
        self.assertTrue(data.get('openapi', '').startswith('3.0'))
        self.assertEqual(data.get('info', {}).get('title'), 'Ecommerce Platform REST API')
        self.assertEqual(data.get('info', {}).get('version'), '1.0.0')

        # Check that security scheme BearerAuth is defined
        security_schemes = data.get('components', {}).get('securitySchemes', {})
        self.assertIn('BearerAuth', security_schemes)
        self.assertEqual(security_schemes['BearerAuth'].get('scheme'), 'bearer')
        self.assertEqual(security_schemes['BearerAuth'].get('bearerFormat'), 'JWT')

        # Check that paths exist
        paths = data.get('paths', {})
        self.assertIn('/api/v1/auth/login/', paths)
        self.assertIn('/api/v1/auth/register/', paths)

    def test_schema_tags_organization_and_no_v1_tag(self):
        """
        Verify that:
        1. The generic 'v1' tag is completely eliminated from all operations.
        2. All endpoints are mapped to the canonical thematic tags.
        3. Every canonical tag has at least one associated endpoint.
        """
        url = reverse('schema')
        response = self.client.get(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json() if hasattr(response, 'json') else json.loads(response.content.decode('utf-8'))
        paths = data.get('paths', {})

        expected_tags = {
            'Auth',
            'Catalog',
            'Cart',
            'Orders',
            'Payments',
            'Notifications',
            'Reviews',
            'Dashboard',
        }

        found_tags = set()
        tag_counts = {}

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if isinstance(operation, dict) and 'tags' in operation:
                    tags = operation['tags']
                    # 'v1' must not exist
                    self.assertNotIn('v1', tags, f"Endpoint {method.upper()} {path} still has 'v1' tag!")
                    self.assertNotIn('V1', tags, f"Endpoint {method.upper()} {path} still has 'V1' tag!")
                    for tag in tags:
                        found_tags.add(tag)
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Check that all expected canonical tags are present and populated
        for expected in expected_tags:
            self.assertIn(expected, found_tags, f"Expected tag '{expected}' not found in any endpoint!")
            self.assertGreaterEqual(
                tag_counts.get(expected, 0),
                1,
                f"Tag '{expected}' has 0 endpoints!",
            )

    def test_swagger_ui_endpoint_returns_200(self):
        """Verify that /api/docs/swagger/ loads the Swagger UI bundle."""
        url = reverse('swagger-ui')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8')
        self.assertIn('swagger-ui', content.lower())
        self.assertIn('swaggeruibundle', content.lower())

    def test_redoc_endpoint_returns_200(self):
        """Verify that /api/docs/redoc/ loads the Redoc bundle."""
        url = reverse('redoc')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8')
        self.assertIn('redoc', content.lower())
