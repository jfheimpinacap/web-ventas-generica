from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase


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
