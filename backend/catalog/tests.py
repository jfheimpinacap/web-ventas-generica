from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Brand, Category, Product, ProductImage, ProductSpec, Promotion, QuoteRequest, Supplier


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

    def test_filter_by_parent_category_includes_products_from_children(self):
        child_category = Category.objects.create(name='Elevadores tipo tijera', parent=self.category)
        Product.objects.create(
            name='Elevador de prueba',
            category=child_category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.USED,
            short_description='Subcategoría',
            is_published=True,
            sku='SKU-CHILD-1',
        )

        response = self.client.get(reverse('product-list'), {'category': self.category.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertSetEqual({product['name'] for product in response.data}, {'Producto publicado', 'Elevador de prueba'})


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


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', QUOTE_NOTIFICATION_EMAIL='vendedor@example.com')
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
        User = get_user_model()
        self.user = User.objects.create_user(username='seller_quotes', password='seller123', is_staff=True)

    def authenticate(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'seller_quotes', 'password': 'seller123'},
            format='json',
        )
        token = token_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_quote_request_with_new_fields(self):
        payload = {
            'product': self.product.id,
            'customer_name': 'Juan Perez',
            'customer_phone': '+56 9 8888 9999',
            'customer_email': 'juan@example.com',
            'company_name': 'Agro Juan',
            'city': 'Talca',
            'preferred_contact_method': 'whatsapp',
            'message': 'Necesito precio y plazo de entrega.',
        }
        response = self.client.post(reverse('quote-request-list'), payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuoteRequest.objects.count(), 1)
        created = QuoteRequest.objects.first()
        self.assertEqual(created.status, QuoteRequest.QuoteStatus.NEW)
        self.assertEqual(created.company_name, 'Agro Juan')
        self.assertEqual(created.preferred_contact_method, 'whatsapp')
        self.assertEqual(len(mail.outbox), 2)

    def test_get_quote_requests_without_token_fails(self):
        response = self.client.get(reverse('quote-request-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_quote_requests_with_token_works(self):
        QuoteRequest.objects.create(
            product=self.product,
            customer_name='Mario',
            customer_phone='12345',
            message='Demo',
        )
        self.authenticate()
        response = self.client.get(reverse('quote-request-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_patch_status_to_contacted_sets_contacted_at(self):
        quote = QuoteRequest.objects.create(
            product=self.product,
            customer_name='Pedro',
            customer_phone='321',
            message='contactar',
        )
        self.authenticate()
        response = self.client.patch(
            reverse('quote-request-detail', kwargs={'pk': quote.pk}),
            {'status': QuoteRequest.QuoteStatus.CONTACTED},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertIsNotNone(quote.contacted_at)

    def test_patch_status_to_quoted_sets_quoted_at(self):
        quote = QuoteRequest.objects.create(
            product=self.product,
            customer_name='Pedro',
            customer_phone='321',
            message='cotizar',
        )
        self.authenticate()
        response = self.client.patch(
            reverse('quote-request-detail', kwargs={'pk': quote.pk}),
            {'status': QuoteRequest.QuoteStatus.QUOTED},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertIsNotNone(quote.quoted_at)

    def test_patch_status_to_closed_sets_closed_at(self):
        quote = QuoteRequest.objects.create(
            product=self.product,
            customer_name='Pedro',
            customer_phone='321',
            message='cerrar',
        )
        self.authenticate()
        response = self.client.patch(
            reverse('quote-request-detail', kwargs={'pk': quote.pk}),
            {'status': QuoteRequest.QuoteStatus.CLOSED},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertIsNotNone(quote.closed_at)

    def test_filter_by_status(self):
        QuoteRequest.objects.create(product=self.product, customer_name='A', customer_phone='1', message='x', status='new')
        QuoteRequest.objects.create(product=self.product, customer_name='B', customer_phone='2', message='y', status='quoted')
        self.authenticate()
        response = self.client.get(reverse('quote-request-list'), {'status': 'quoted'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], 'quoted')

    def test_search_by_name_email_phone(self):
        QuoteRequest.objects.create(
            product=self.product,
            customer_name='Cliente Uno',
            customer_phone='999111',
            customer_email='uno@example.com',
            message='Solicitud uno',
        )
        QuoteRequest.objects.create(
            product=self.product,
            customer_name='Cliente Dos',
            customer_phone='888222',
            customer_email='dos@example.com',
            message='Solicitud dos',
        )
        self.authenticate()

        response_name = self.client.get(reverse('quote-request-list'), {'search': 'Uno'})
        response_email = self.client.get(reverse('quote-request-list'), {'search': 'dos@example.com'})
        response_phone = self.client.get(reverse('quote-request-list'), {'search': '999111'})

        self.assertEqual(len(response_name.data), 1)
        self.assertEqual(len(response_email.data), 1)
        self.assertEqual(len(response_phone.data), 1)


class CatalogEntitiesAdminApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='seller_entities', password='seller123', is_staff=True)
        self.parent_category = Category.objects.create(name='Padre', is_active=True)
        self.inactive_category = Category.objects.create(name='Categoria inactiva', is_active=False)
        self.inactive_brand = Brand.objects.create(name='Marca inactiva', is_active=False)
        self.inactive_supplier = Supplier.objects.create(name='Proveedor inactivo', is_active=False)
        self.category = Category.objects.create(name='Categoria activa', is_active=True)
        self.product = Product.objects.create(
            name='Producto promo',
            category=self.category,
            product_type=Product.ProductType.MACHINERY,
            condition=Product.ProductCondition.NEW,
            stock_status=Product.StockStatus.AVAILABLE,
            is_published=True,
        )
        self.active_promotion = Promotion.objects.create(title='Promo activa', is_active=True, order=1)
        self.inactive_promotion = Promotion.objects.create(title='Promo inactiva', is_active=False, order=2)

    def authenticate(self):
        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'seller_entities', 'password': 'seller123'},
            format='json',
        )
        token = token_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_category_authenticated(self):
        self.authenticate()
        response = self.client.post(
            reverse('category-list'),
            {
                'name': 'Nueva categoria',
                'parent': self.parent_category.id,
                'description': 'Descripcion',
                'is_active': True,
                'order': 3,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        created = Category.objects.get(name='Nueva categoria')
        self.assertTrue(created.slug)

    def test_edit_category_authenticated(self):
        self.authenticate()
        category = Category.objects.create(name='Editar categoria', is_active=True)
        original_slug = category.slug
        response = self.client.patch(
            reverse('category-detail', kwargs={'pk': category.pk}),
            {'name': 'Categoria editada', 'order': 8},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        category.refresh_from_db()
        self.assertEqual(category.name, 'Categoria editada')
        self.assertEqual(category.order, 8)
        self.assertEqual(category.slug, original_slug)

    def test_create_category_without_token_fails(self):
        response = self.client.post(reverse('category-list'), {'name': 'Sin token'}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_create_brand_authenticated(self):
        self.authenticate()
        response = self.client.post(reverse('brand-list'), {'name': 'Marca admin', 'is_active': True}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Brand.objects.filter(name='Marca admin').count(), 1)

    def test_create_supplier_authenticated(self):
        self.authenticate()
        payload = {
            'name': 'Proveedor admin',
            'contact_name': 'Ana',
            'phone': '12345',
            'email': 'ana@example.com',
            'notes': 'Preferente',
            'is_active': True,
        }
        response = self.client.post(reverse('supplier-list'), payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Supplier.objects.filter(name='Proveedor admin').count(), 1)

    def test_create_promotion_authenticated(self):
        self.authenticate()
        payload = {
            'title': 'Promo admin',
            'subtitle': 'Subtitulo',
            'product': self.product.id,
            'button_text': 'Cotizar',
            'button_url': 'https://example.com/promo',
            'is_active': True,
            'order': 5,
        }
        response = self.client.post(reverse('promotion-list'), payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Promotion.objects.filter(title='Promo admin').count(), 1)

    def test_edit_promotion_authenticated(self):
        self.authenticate()
        response = self.client.patch(
            reverse('promotion-detail', kwargs={'pk': self.active_promotion.pk}),
            {'title': 'Promo editada', 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.active_promotion.refresh_from_db()
        self.assertEqual(self.active_promotion.title, 'Promo editada')
        self.assertFalse(self.active_promotion.is_active)

    def test_inactive_promotions_are_hidden_for_public(self):
        response = self.client.get(reverse('promotion-list'))
        self.assertEqual(response.status_code, 200)
        ids = [item['id'] for item in response.data]
        self.assertIn(self.active_promotion.id, ids)
        self.assertNotIn(self.inactive_promotion.id, ids)

    def test_include_inactive_without_token_does_not_expose_restricted_data(self):
        checks = [
            ('category-list', self.inactive_category.id),
            ('brand-list', self.inactive_brand.id),
            ('supplier-list', self.inactive_supplier.id),
            ('promotion-list', self.inactive_promotion.id),
        ]
        for route_name, inactive_id in checks:
            response = self.client.get(reverse(route_name), {'include_inactive': 'true'})
            self.assertEqual(response.status_code, 200)
            ids = [item['id'] for item in response.data]
            self.assertNotIn(inactive_id, ids)

    def test_include_inactive_with_token_allows_admin_panel(self):
        self.authenticate()
        checks = [
            ('category-list', self.inactive_category.id),
            ('brand-list', self.inactive_brand.id),
            ('supplier-list', self.inactive_supplier.id),
            ('promotion-list', self.inactive_promotion.id),
        ]
        for route_name, inactive_id in checks:
            response = self.client.get(reverse(route_name), {'include_inactive': 'true'})
            self.assertEqual(response.status_code, 200)
            ids = [item['id'] for item in response.data]
            self.assertIn(inactive_id, ids)

class GenerateDemoProductsCommandTests(TestCase):
    def test_non_interactive_command_creates_products_specs_categories_and_brands(self):
        out = StringIO()

        call_command(
            'generate_demo_products',
            '--no-input',
            '--tijeras',
            '2',
            '--brazos',
            '1',
            '--baterias',
            '3',
            '--ruedas',
            '2',
            '--controles',
            '1',
            stdout=out,
        )

        self.assertEqual(Product.objects.count(), 9)
        self.assertEqual(ProductSpec.objects.count(), 30)

        for category_name in [
            'Maquinaria',
            'Elevadores tipo tijera',
            'Brazos articulados',
            'Repuestos',
            'Baterías',
            'Ruedas',
            'Controles',
        ]:
            self.assertTrue(Category.objects.filter(name=category_name).exists())

        for brand_name in ['Genie', 'JLG', 'Haulotte', 'Skyjack', 'Sinoboom', 'Dingli', 'Manitou']:
            self.assertTrue(Brand.objects.filter(name=brand_name).exists())

        output = out.getvalue()
        self.assertIn('Generación demo completada.', output)
        self.assertIn('- total: 9', output)
