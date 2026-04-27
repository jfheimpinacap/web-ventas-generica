from django.core.management.base import BaseCommand

from catalog.models import Brand, Category, Product, ProductSpec, Promotion, Supplier


class Command(BaseCommand):
    help = 'Carga datos demo para el catálogo comercial.'

    def handle(self, *args, **options):
        categories = self._seed_categories()
        brands = self._seed_brands()
        suppliers = self._seed_suppliers()
        products = self._seed_products(categories, brands, suppliers)
        self._seed_specs(products)
        self._seed_promotions(products)
        self.stdout.write(self.style.SUCCESS('Seed de catálogo completado.'))

    def _seed_categories(self):
        maquinaria, _ = Category.objects.update_or_create(
            slug='maquinaria',
            defaults={'name': 'Maquinaria', 'parent': None, 'description': 'Equipos para trabajos en altura', 'order': 1, 'is_active': True},
        )
        elevadores, _ = Category.objects.update_or_create(
            slug='elevadores-tipo-tijera',
            defaults={'name': 'Elevadores tipo tijera', 'parent': maquinaria, 'description': 'Plataformas tipo tijera', 'order': 1, 'is_active': True},
        )
        brazos, _ = Category.objects.update_or_create(
            slug='brazos-articulados',
            defaults={'name': 'Brazos articulados', 'parent': maquinaria, 'description': 'Brazos para acceso de alto alcance', 'order': 2, 'is_active': True},
        )

        repuestos, _ = Category.objects.update_or_create(
            slug='repuestos',
            defaults={'name': 'Repuestos', 'parent': None, 'description': 'Partes y consumibles', 'order': 2, 'is_active': True},
        )
        baterias, _ = Category.objects.update_or_create(
            slug='baterias',
            defaults={'name': 'Baterías', 'parent': repuestos, 'description': 'Baterías para equipos eléctricos', 'order': 1, 'is_active': True},
        )
        ruedas, _ = Category.objects.update_or_create(
            slug='ruedas',
            defaults={'name': 'Ruedas', 'parent': repuestos, 'description': 'Ruedas sólidas e industriales', 'order': 2, 'is_active': True},
        )
        controles, _ = Category.objects.update_or_create(
            slug='controles',
            defaults={'name': 'Controles', 'parent': repuestos, 'description': 'Controles y joysticks', 'order': 3, 'is_active': True},
        )

        return {
            'elevadores': elevadores,
            'brazos': brazos,
            'baterias': baterias,
            'ruedas': ruedas,
            'controles': controles,
        }

    def _seed_brands(self):
        names = ['Genie', 'JLG', 'Haulotte', 'Skyjack']
        result = {}
        for name in names:
            brand, _ = Brand.objects.update_or_create(
                slug=name.lower(),
                defaults={'name': name, 'description': f'Marca demo {name}', 'is_active': True},
            )
            result[name] = brand
        return result

    def _seed_suppliers(self):
        supplier_a, _ = Supplier.objects.update_or_create(
            name='Andes Maquinaria Supply',
            defaults={
                'contact_name': 'Carla Rojas',
                'phone': '+56 9 1111 1111',
                'email': 'carla@andesmaquinaria.test',
                'notes': 'Proveedor demo para maquinaria usada',
                'is_active': True,
            },
        )
        supplier_b, _ = Supplier.objects.update_or_create(
            name='Repuestos Industriales Sur',
            defaults={
                'contact_name': 'Luis Méndez',
                'phone': '+56 9 2222 2222',
                'email': 'luis@repuestossur.test',
                'notes': 'Proveedor demo de partes y componentes',
                'is_active': True,
            },
        )
        return {'a': supplier_a, 'b': supplier_b}

    def _seed_products(self, categories, brands, suppliers):
        products_data = [
            {
                'sku': 'GENIE-GS1930',
                'name': 'Elevador tijera Genie GS-1930',
                'category': categories['elevadores'],
                'brand': brands['Genie'],
                'supplier': suppliers['a'],
                'product_type': Product.ProductType.MACHINERY,
                'condition': Product.ProductCondition.USED,
                'short_description': 'Compacto y eficiente para interior.',
                'description': 'Equipo ideal para tareas de mantención y bodegas.',
                'model': 'GS-1930',
                'year': 2019,
                'hours_meter': 890,
                'price': '9800.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.AVAILABLE,
                'is_featured': True,
                'is_published': True,
            },
            {
                'sku': 'JLG-450AJ',
                'name': 'Brazo articulado JLG 450AJ',
                'category': categories['brazos'],
                'brand': brands['JLG'],
                'supplier': suppliers['a'],
                'product_type': Product.ProductType.MACHINERY,
                'condition': Product.ProductCondition.USED,
                'short_description': 'Gran alcance para trabajos en altura.',
                'description': 'Brazo articulado robusto para aplicaciones exigentes.',
                'model': '450AJ',
                'year': 2018,
                'hours_meter': 1540,
                'price': '24500.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.ON_REQUEST,
                'is_featured': True,
                'is_published': True,
            },
            {
                'sku': 'HAULOTTE-C12',
                'name': 'Elevador tijera Haulotte Compact 12',
                'category': categories['elevadores'],
                'brand': brands['Haulotte'],
                'supplier': suppliers['a'],
                'product_type': Product.ProductType.MACHINERY,
                'condition': Product.ProductCondition.REFURBISHED,
                'short_description': 'Altura extra y excelente maniobrabilidad.',
                'description': 'Plataforma con reacondicionamiento reciente.',
                'model': 'Compact 12',
                'year': 2017,
                'hours_meter': 1260,
                'price': '16900.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.AVAILABLE,
                'is_featured': True,
                'is_published': True,
            },
            {
                'sku': 'PART-BAT-EL-001',
                'name': 'Batería para elevador eléctrico',
                'category': categories['baterias'],
                'brand': brands['Skyjack'],
                'supplier': suppliers['b'],
                'product_type': Product.ProductType.SPARE_PART,
                'condition': Product.ProductCondition.NEW,
                'short_description': 'Batería de ciclo profundo 48V.',
                'description': 'Compatible con múltiples plataformas eléctricas.',
                'model': 'BAT-48V-220AH',
                'price': '990.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.AVAILABLE,
                'is_featured': False,
                'is_published': True,
            },
            {
                'sku': 'PART-RUE-PLAT-002',
                'name': 'Rueda sólida para plataforma',
                'category': categories['ruedas'],
                'brand': brands['Genie'],
                'supplier': suppliers['b'],
                'product_type': Product.ProductType.SPARE_PART,
                'condition': Product.ProductCondition.NEW,
                'short_description': 'Rueda no marcante para uso industrial.',
                'description': 'Resistente al desgaste y fácil instalación.',
                'model': 'WH-16-SOLID',
                'price': '180.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.AVAILABLE,
                'is_featured': False,
                'is_published': True,
            },
            {
                'sku': 'PART-CTRL-JOY-003',
                'name': 'Control joystick plataforma aérea',
                'category': categories['controles'],
                'brand': brands['JLG'],
                'supplier': suppliers['b'],
                'product_type': Product.ProductType.SPARE_PART,
                'condition': Product.ProductCondition.NEW,
                'short_description': 'Joystick proporcional para maniobras precisas.',
                'description': 'Repuesto compatible con controladores estándar.',
                'model': 'JOY-PRO-10',
                'price': '320.00',
                'price_visible': True,
                'stock_status': Product.StockStatus.ON_REQUEST,
                'is_featured': True,
                'is_published': True,
            },
            {
                'sku': 'INTERNAL-HIDDEN-001',
                'name': 'Producto no publicado demo',
                'category': categories['controles'],
                'brand': brands['Skyjack'],
                'supplier': suppliers['b'],
                'product_type': Product.ProductType.OTHER,
                'condition': Product.ProductCondition.NOT_APPLICABLE,
                'short_description': 'No debe verse en catálogo público.',
                'description': 'Solo para comprobar filtros públicos.',
                'model': 'HIDDEN-1',
                'price_visible': False,
                'stock_status': Product.StockStatus.RESERVED,
                'is_featured': False,
                'is_published': False,
            },
        ]

        products = {}
        for product_data in products_data:
            sku = product_data['sku']
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults=product_data,
            )
            products[sku] = product
        return products

    def _seed_specs(self, products):
        specs_map = {
            'GENIE-GS1930': [
                ('Altura de trabajo', '7.8', 'm', 1),
                ('Capacidad', '227', 'kg', 2),
                ('Energía', 'Eléctrico', '', 3),
            ],
            'JLG-450AJ': [
                ('Altura de trabajo', '15.7', 'm', 1),
                ('Alcance horizontal', '7.6', 'm', 2),
                ('Capacidad', '250', 'kg', 3),
            ],
            'HAULOTTE-C12': [
                ('Altura de trabajo', '12', 'm', 1),
                ('Capacidad', '300', 'kg', 2),
            ],
        }

        for sku, specs in specs_map.items():
            product = products.get(sku)
            if not product:
                continue
            for name, value, unit, order in specs:
                ProductSpec.objects.update_or_create(
                    product=product,
                    name=name,
                    defaults={'value': value, 'unit': unit, 'order': order},
                )

    def _seed_promotions(self, products):
        Promotion.objects.update_or_create(
            title='Plataformas listas para despacho',
            defaults={
                'subtitle': 'Equipos revisados y con entrega rápida.',
                'product': products.get('GENIE-GS1930'),
                'button_text': 'Ver equipos',
                'button_url': 'http://localhost:5174/',
                'is_active': True,
                'order': 1,
            },
        )
        Promotion.objects.update_or_create(
            title='Repuestos y soporte técnico',
            defaults={
                'subtitle': 'Stock de partes para mantener tu operación activa.',
                'product': products.get('PART-BAT-EL-001'),
                'button_text': 'Cotizar ahora',
                'button_url': 'http://localhost:5174/cotizar',
                'is_active': True,
                'order': 2,
            },
        )
