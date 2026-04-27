from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Category, Product, QuoteRequest


class ProductApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Maquinaria')
        Product.objects.create(
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

    def test_get_products_can_include_unpublished_in_dev(self):
        response = self.client.get(reverse('product-list'), {'include_unpublished': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)


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
