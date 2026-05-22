import importlib
import os

from django.contrib.auth import get_user_model
from copy import deepcopy
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.test import APIRequestFactory
from core.throttles import LoginRateThrottle


class HealthEndpointTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get(reverse('api-health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class AuthEndpointsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='vendedor_test',
            password='vendedor123',
            email='vendedor_test@example.com',
            first_name='Vendedor',
            last_name='Demo',
            is_staff=True,
        )

    def test_jwt_login_success(self):
        response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'vendedor_test', 'password': 'vendedor123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_auth_me_with_token(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'vendedor_test', 'password': 'vendedor123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'vendedor_test')
        self.assertEqual(response.data['email'], 'vendedor_test@example.com')
        self.assertTrue(response.data['is_staff'])

    def test_auth_me_without_token_returns_401(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, 401)

    @override_settings(
        TESTING=False,
        REST_FRAMEWORK=(lambda rf: {**rf, 'DEFAULT_THROTTLE_RATES': {**rf['DEFAULT_THROTTLE_RATES'], 'login': '2/minute'}})(deepcopy(settings.REST_FRAMEWORK)),
    )
    def test_login_throttling(self):
        factory = APIRequestFactory()
        throttle = LoginRateThrottle()
        throttle.rate = '2/min'
        throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)
        request1 = factory.post(reverse('token-obtain-pair'), {'username': 'u', 'password': 'x'}, format='json')
        request2 = factory.post(reverse('token-obtain-pair'), {'username': 'u', 'password': 'x'}, format='json')
        request3 = factory.post(reverse('token-obtain-pair'), {'username': 'u', 'password': 'x'}, format='json')
        request1.META['REMOTE_ADDR'] = '1.1.1.1'
        request2.META['REMOTE_ADDR'] = '1.1.1.1'
        request3.META['REMOTE_ADDR'] = '1.1.1.1'
        request1.user = AnonymousUser()
        request2.user = AnonymousUser()
        request3.user = AnonymousUser()
        self.assertTrue(throttle.allow_request(request1, None))
        self.assertTrue(throttle.allow_request(request2, None))
        self.assertFalse(throttle.allow_request(request3, None))


class SettingsSecurityTests(TestCase):
    def test_env_list_parses_comma_separated_values(self):
        settings_module = importlib.import_module('config.settings')
        with override_settings():
            self.assertEqual(
                settings_module.env_list('UNSET_LIST_TEST', 'a, b, ,c'),
                ['a', 'b', 'c'],
            )

    def test_debug_false_without_secret_key_raises(self):
        original_env = os.environ.copy()
        try:
            os.environ['DEBUG'] = 'false'
            os.environ.pop('SECRET_KEY', None)
            os.environ.pop('DJANGO_SECRET_KEY', None)
            with self.assertRaises(RuntimeError):
                importlib.reload(importlib.import_module('config.settings'))
        finally:
            os.environ.clear()
            os.environ.update(original_env)
            importlib.reload(importlib.import_module('config.settings'))


class SitemapXmlViewTests(TestCase):
    @override_settings(PUBLIC_SITE_URL='https://frontend.example.com/')
    def test_sitemap_xml_contains_public_routes_only(self):
        from catalog.models import Category, Product

        category_active = Category.objects.create(name='Categoria activa', is_active=True)
        Category.objects.create(name='Categoria inactiva', is_active=False)

        Product.objects.create(
            name='Publicado',
            category=category_active,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.NEW,
            is_published=True,
        )
        Product.objects.create(
            name='No publicado',
            category=category_active,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.NEW,
            is_published=False,
        )

        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')

        content = response.content.decode()
        self.assertIn('<loc>https://frontend.example.com/</loc>', content)
        self.assertIn('<loc>https://frontend.example.com/catalogo</loc>', content)
        self.assertIn('<loc>https://frontend.example.com/contacto</loc>', content)
        self.assertIn('<loc>https://frontend.example.com/sobre-nosotros</loc>', content)
        self.assertIn('<loc>https://frontend.example.com/preguntas-frecuentes</loc>', content)
        self.assertIn('https://frontend.example.com/producto/publicado', content)
        self.assertNotIn('https://frontend.example.com/producto/no-publicado', content)
        self.assertIn(f'https://frontend.example.com/catalogo?category={category_active.id}', content)
        self.assertNotIn('/login', content)
        self.assertNotIn('/admin', content)

