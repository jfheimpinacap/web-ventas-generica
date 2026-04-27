from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Category, Product, QuoteRequest


class ProductApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Maquinaria')
        self.published_product = Product.objects.create(
            name='Producto publicado',
            category=self.category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.USED,
            short_description='Visible',
            is_published=True,
            sku='SKU-PUBLISHED',
        )
        Product.objects.create(
            name='Producto oculto',
            category=self.category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.USED,
            short_description='Oculto',
            is_published=False,
            sku='SKU-HIDDEN',
        )

    def test_get_products_returns_published_only_by_default(self):
        response = self.client.get(reverse('product-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Producto publicado')

    def test_get_products_include_unpublished_requires_auth(self):
        response = self.client.get(reverse('product-list'), {'include_unpublished': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_product_detail_by_slug(self):
        response = self.client.get(reverse('product-detail', kwargs={'slug': self.published_product.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['slug'], self.published_product.slug)


class ProductWritePermissionsTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Equipos')
        User = get_user_model()
        self.user = User.objects.create_user(username='seller', password='seller123', is_staff=True)

    def _product_payload(self):
        return {
            'name': 'Producto nuevo',
            'category': self.category.id,
            'product_type': Product.ProductType.MACHINERY,
            'condition': Product.ProductCondition.NEW,
            'short_description': 'Texto corto',
            'sku': 'SKU-CREATE-1',
            'is_published': False,
        }

    def test_create_product_without_token_fails(self):
        response = self.client.post(reverse('product-list'), self._product_payload(), format='json')
        self.assertEqual(response.status_code, 401)

    def test_create_product_with_token_works(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'seller', 'password': 'seller123'},
            format='json',
        )
        token = token_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.post(reverse('product-list'), self._product_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.filter(name='Producto nuevo').count(), 1)


class QuoteRequestApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Repuestos')
        self.product = Product.objects.create(
            name='Repuesto demo',
            category=self.category,
            product_type=Product.ProductType.SPARE_PART,
            condition=Product.ProductCondition.NEW,
            sku='SKU-QUOTE-1',
            is_published=True,
        )

    def test_create_quote_request(self):
        payload = {
            'product': self.product.id,
            'customer_name': 'Juan Perez',
            'customer_phone': '+56 9 8888 9999',
            'customer_email': 'juan@example.com',
            'message': 'Necesito precio y plazo de entrega.',
        }
        response = self.client.post(reverse('quote-request-list'), payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuoteRequest.objects.count(), 1)
        created = QuoteRequest.objects.first()
        self.assertEqual(created.status, QuoteRequest.QuoteStatus.NEW)
