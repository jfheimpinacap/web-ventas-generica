from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Category, Product, ProductImage, ProductSpec, QuoteRequest


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
        self.hidden_product = Product.objects.create(
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

    def test_get_hidden_product_detail_without_auth_fails(self):
        response = self.client.get(reverse('product-detail', kwargs={'slug': self.hidden_product.slug}))
        self.assertEqual(response.status_code, 404)


class ProductWritePermissionsTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Equipos')
        User = get_user_model()
        self.user = User.objects.create_user(username='seller', password='seller123', is_staff=True)
        self.existing_product = Product.objects.create(
            name='Producto editable',
            category=self.category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.NEW,
            stock_status=Product.StockStatus.ON_REQUEST,
            is_published=False,
        )

    def authenticate(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'seller', 'password': 'seller123'},
            format='json',
        )
        token = token_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _product_payload(self):
        return {
            'name': 'Producto nuevo',
            'category': self.category.id,
            'product_type': Product.ProductType.MACHINERY,
            'condition': Product.ProductCondition.NEW,
            'short_description': 'Texto corto',
            'sku': 'SKU-CREATE-1',
            'stock_status': Product.StockStatus.AVAILABLE,
            'is_published': False,
        }

    def test_create_product_without_token_fails(self):
        response = self.client.post(reverse('product-list'), self._product_payload(), format='json')
        self.assertEqual(response.status_code, 401)

    def test_create_product_with_token_works(self):
        self.authenticate()
        response = self.client.post(reverse('product-list'), self._product_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.filter(name='Producto nuevo').count(), 1)
        created = Product.objects.get(name='Producto nuevo')
        self.assertTrue(created.slug)

    def test_edit_product_without_token_fails(self):
        payload = {'name': 'Sin permiso'}
        response = self.client.patch(
            reverse('product-detail', kwargs={'slug': self.existing_product.slug}),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_edit_product_with_token_works_and_keeps_slug(self):
        self.authenticate()
        original_slug = self.existing_product.slug
        payload = {'name': 'Producto editado', 'is_published': True}
        response = self.client.patch(
            reverse('product-detail', kwargs={'slug': self.existing_product.slug}),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.existing_product.refresh_from_db()
        self.assertEqual(self.existing_product.name, 'Producto editado')
        self.assertEqual(self.existing_product.slug, original_slug)
        self.assertTrue(self.existing_product.is_published)

    def test_delete_product_with_token_works(self):
        self.authenticate()
        response = self.client.delete(reverse('product-detail', kwargs={'slug': self.existing_product.slug}))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Product.objects.filter(pk=self.existing_product.pk).exists())

    def test_include_unpublished_with_token_returns_hidden_products(self):
        self.authenticate()
        response = self.client.get(reverse('product-list'), {'include_unpublished': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)


class ProductMediaAndSpecsApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Implementos')
        self.product = Product.objects.create(
            name='Producto con recursos',
            category=self.category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.NEW,
            stock_status=Product.StockStatus.AVAILABLE,
            is_published=True,
        )
        User = get_user_model()
        self.user = User.objects.create_user(username='seller_media', password='seller123', is_staff=True)

    def authenticate(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'seller_media', 'password': 'seller123'},
            format='json',
        )
        token = token_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _sample_image(self, name='test.gif'):
        return SimpleUploadedFile(name, b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;', content_type='image/gif')

    def test_create_product_image_authenticated(self):
        self.authenticate()
        payload = {
            'product': self.product.id,
            'image': self._sample_image(),
            'alt_text': 'Vista lateral',
            'order': 2,
            'is_main': True,
        }
        response = self.client.post(reverse('product-image-list'), payload, format='multipart')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ProductImage.objects.count(), 1)
        created = ProductImage.objects.first()
        self.assertEqual(created.product_id, self.product.id)
        self.assertTrue(created.is_main)

    def test_create_product_image_without_token_fails(self):
        payload = {
            'product': self.product.id,
            'image': self._sample_image(),
            'alt_text': 'Sin token',
        }
        response = self.client.post(reverse('product-image-list'), payload, format='multipart')
        self.assertEqual(response.status_code, 401)

    def test_setting_new_main_image_unsets_old_one(self):
        self.authenticate()
        first = ProductImage.objects.create(product=self.product, image=self._sample_image('first.gif'), is_main=True, order=0)
        second = ProductImage.objects.create(product=self.product, image=self._sample_image('second.gif'), is_main=False, order=1)

        response = self.client.patch(
            reverse('product-image-detail', kwargs={'pk': second.pk}),
            {'is_main': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_main)
        self.assertTrue(second.is_main)

    def test_create_product_spec_authenticated(self):
        self.authenticate()
        payload = {
            'product': self.product.id,
            'name': 'Potencia',
            'value': '100',
            'unit': 'HP',
            'order': 1,
        }
        response = self.client.post(reverse('product-spec-list'), payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ProductSpec.objects.count(), 1)

    def test_update_product_spec_authenticated(self):
        self.authenticate()
        spec = ProductSpec.objects.create(product=self.product, name='Peso', value='1000', unit='kg', order=1)

        response = self.client.patch(
            reverse('product-spec-detail', kwargs={'pk': spec.pk}),
            {'value': '1200', 'unit': 'kg'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        spec.refresh_from_db()
        self.assertEqual(spec.value, '1200')

    def test_delete_product_spec_authenticated(self):
        self.authenticate()
        spec = ProductSpec.objects.create(product=self.product, name='Altura', value='5', unit='m', order=3)

        response = self.client.delete(reverse('product-spec-detail', kwargs={'pk': spec.pk}))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ProductSpec.objects.filter(pk=spec.pk).exists())

    def test_create_product_spec_without_token_fails(self):
        payload = {
            'product': self.product.id,
            'name': 'Torque',
            'value': '50',
        }
        response = self.client.post(reverse('product-spec-list'), payload, format='json')
        self.assertEqual(response.status_code, 401)


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
