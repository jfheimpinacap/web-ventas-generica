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
