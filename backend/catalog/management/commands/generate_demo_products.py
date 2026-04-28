import random
import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Brand, Category, Product, ProductSpec, Supplier


class Command(BaseCommand):
    help = 'Genera productos demo variables por tipo (interactivo o con flags).'

    TYPE_CONFIG = {
        'tijeras': {
            'question': '¿Cuántos elevadores tipo tijera crear?',
            'category_slug': 'elevadores-tipo-tijera',
            'category_name': 'Elevadores tipo tijera',
            'parent_slug': 'maquinaria',
            'parent_name': 'Maquinaria',
            'product_type': Product.ProductType.MACHINERY,
            'prefix': 'TIJ',
        },
        'brazos': {
            'question': '¿Cuántos brazos articulados crear?',
            'category_slug': 'brazos-articulados',
            'category_name': 'Brazos articulados',
            'parent_slug': 'maquinaria',
            'parent_name': 'Maquinaria',
            'product_type': Product.ProductType.MACHINERY,
            'prefix': 'BRA',
        },
        'baterias': {
            'question': '¿Cuántas baterías crear?',
            'category_slug': 'baterias',
            'category_name': 'Baterías',
            'parent_slug': 'repuestos',
            'parent_name': 'Repuestos',
            'product_type': Product.ProductType.SPARE_PART,
            'prefix': 'BAT',
        },
        'ruedas': {
            'question': '¿Cuántas ruedas crear?',
            'category_slug': 'ruedas',
            'category_name': 'Ruedas',
            'parent_slug': 'repuestos',
            'parent_name': 'Repuestos',
            'product_type': Product.ProductType.SPARE_PART,
            'prefix': 'RUE',
        },
        'controles': {
            'question': '¿Cuántos controles crear?',
            'category_slug': 'controles',
            'category_name': 'Controles',
            'parent_slug': 'repuestos',
            'parent_name': 'Repuestos',
            'product_type': Product.ProductType.SPARE_PART,
            'prefix': 'CON',
        },
    }

    SCISSOR_MODELS = [
        ('Genie', 'GS-1930'),
        ('JLG', '2632ES'),
        ('Skyjack', 'SJ3219'),
        ('Haulotte', 'Compact 12'),
        ('Sinoboom', 'GTJZ0608'),
        ('Dingli', 'JCPT0808AC'),
        ('Manitou', 'SE0808'),
    ]
    BOOM_MODELS = [
        ('JLG', '450AJ'),
        ('Genie', 'Z-45/25'),
        ('Haulotte', 'HA16PX'),
        ('Sinoboom', 'AB14EJ'),
        ('Dingli', 'BA18CRT2'),
        ('Manitou', '160 ATJ+'),
        ('Skyjack', 'SJ45 AJ+'),
    ]
    BATTERY_MODELS = [
        ('Batería tracción', '6V 225Ah'),
        ('Batería ciclo profundo', '12V 150Ah'),
        ('Pack baterías plataforma eléctrica', '48V 200Ah'),
        ('Batería AGM industrial', '24V 180Ah'),
        ('Batería litio LiFePO4', '24V 105Ah'),
    ]
    WHEEL_MODELS = [
        ('Rueda sólida antihuella', '16x5x10.5'),
        ('Rueda plataforma tijera', '15x5'),
        ('Rueda dirección plataforma aérea', '12x4.5'),
        ('Rueda tracción no marcante', '18x7'),
        ('Rueda poliuretano reforzada', '14x5'),
    ]
    CONTROL_MODELS = [
        ('Joystick plataforma aérea', 'JSK-PRO-01'),
        ('Control proporcional elevador', 'CTRL-PP-220'),
        ('Caja control plataforma', 'BOX-CTRL-72'),
        ('Módulo botonera superior', 'BTN-TOP-15'),
        ('Control remoto diagnóstico', 'RMT-DIAG-09'),
    ]

    BRAND_NAMES = ['Genie', 'JLG', 'Haulotte', 'Skyjack', 'Sinoboom', 'Dingli', 'Manitou']

    def add_arguments(self, parser):
        parser.add_argument('--tijeras', type=int, default=None)
        parser.add_argument('--brazos', type=int, default=None)
        parser.add_argument('--baterias', type=int, default=None)
        parser.add_argument('--ruedas', type=int, default=None)
        parser.add_argument('--controles', type=int, default=None)
        parser.add_argument('--no-input', action='store_true', help='No solicitar entradas interactivas.')

    def handle(self, *args, **options):
        counts = self._resolve_counts(options)

        categories = self._ensure_categories()
        brands = self._ensure_brands()
        suppliers = self._ensure_suppliers()

        created_counts = {key: 0 for key in self.TYPE_CONFIG}
        used_categories = set()
        used_brands = set()

        for type_key, amount in counts.items():
            for _ in range(amount):
                product = self._create_product(type_key, categories, brands, suppliers)
                self._create_specs(product, type_key)
                created_counts[type_key] += 1
                used_categories.add(product.category.name)
                if product.brand:
                    used_brands.add(product.brand.name)

        total_created = sum(created_counts.values())
        self.stdout.write(self.style.SUCCESS('Generación demo completada.'))
        self.stdout.write('Resumen:')
        for type_key in self.TYPE_CONFIG:
            self.stdout.write(f"- {type_key}: {created_counts[type_key]}")
        self.stdout.write(f'- total: {total_created}')
        self.stdout.write(f"- categorías usadas: {', '.join(sorted(used_categories)) if used_categories else 'Ninguna'}")
        self.stdout.write(f"- marcas usadas: {', '.join(sorted(used_brands)) if used_brands else 'Ninguna'}")

    def _resolve_counts(self, options):
        counts = {}
        for type_key, config in self.TYPE_CONFIG.items():
            value = options.get(type_key)
            if value is not None and value < 0:
                raise CommandError(f'El valor para {type_key} no puede ser negativo.')

            if value is None:
                value = 0 if options['no_input'] else self._prompt_non_negative_int(config['question'])

            counts[type_key] = value
        return counts

    def _prompt_non_negative_int(self, question):
        while True:
            raw_value = input(f'{question} ').strip()
            if raw_value == '':
                return 0
            try:
                parsed = int(raw_value)
            except ValueError:
                self.stdout.write(self.style.WARNING('Ingresa un número entero válido (0 o mayor).'))
                continue
            if parsed < 0:
                self.stdout.write(self.style.WARNING('Ingresa un número 0 o mayor.'))
                continue
            return parsed

    def _ensure_categories(self):
        maquinaria, _ = Category.objects.update_or_create(
            slug='maquinaria',
            defaults={'name': 'Maquinaria', 'parent': None, 'description': 'Equipos de elevación y acceso en altura.', 'order': 1, 'is_active': True},
        )
        repuestos, _ = Category.objects.update_or_create(
            slug='repuestos',
            defaults={'name': 'Repuestos', 'parent': None, 'description': 'Repuestos y consumibles para plataformas.', 'order': 2, 'is_active': True},
        )
        servicios, _ = Category.objects.update_or_create(
            slug='servicios',
            defaults={'name': 'Servicios', 'parent': None, 'description': 'Servicios técnicos especializados para equipos industriales.', 'order': 3, 'is_active': True},
        )
        legacy_services = Category.objects.filter(slug='servicios-y-accesorios').first()
        if legacy_services and legacy_services.id != servicios.id:
            Product.objects.filter(category=legacy_services).update(category=servicios)
            Category.objects.filter(parent=legacy_services).update(parent=servicios)
            legacy_services.delete()

        Category.objects.update_or_create(
            slug='reparacion-motores-electricos',
            defaults={
                'name': 'Reparación motores eléctricos',
                'parent': servicios,
                'description': 'Diagnóstico, bobinado y reparación de motores eléctricos industriales.',
                'is_active': True,
                'order': 1,
            },
        )
        Category.objects.update_or_create(
            slug='reparacion-bombas',
            defaults={
                'name': 'Reparación bombas',
                'parent': servicios,
                'description': 'Reparación y calibración de bombas hidráulicas e industriales.',
                'is_active': True,
                'order': 2,
            },
        )
        Category.objects.update_or_create(
            slug='mantenciones-general',
            defaults={
                'name': 'Mantenciones general',
                'parent': servicios,
                'description': 'Mantenciones preventivas y correctivas de equipos en terreno y taller.',
                'is_active': True,
                'order': 3,
            },
        )

        data = {'maquinaria': maquinaria, 'repuestos': repuestos, 'servicios': servicios}
        for type_key, config in self.TYPE_CONFIG.items():
            parent = maquinaria if config['parent_slug'] == 'maquinaria' else repuestos
            category, _ = Category.objects.update_or_create(
                slug=config['category_slug'],
                defaults={
                    'name': config['category_name'],
                    'parent': parent,
                    'description': f"Categoría demo: {config['category_name']}",
                    'is_active': True,
                    'order': list(self.TYPE_CONFIG).index(type_key) + 1,
                },
            )
            data[type_key] = category
        return data

    def _ensure_brands(self):
        brands = {}
        for name in self.BRAND_NAMES:
            brand, _ = Brand.objects.update_or_create(
                slug=name.lower(),
                defaults={'name': name, 'description': f'Marca demo {name}', 'is_active': True},
            )
            brands[name] = brand
        return brands

    def _ensure_suppliers(self):
        supplier_defs = [
            ('Altura Norte Supply', 'Daniel Paredes', '+56 9 5010 1001', 'daniel@alturanorte.demo', 'Proveedor demo de maquinaria.'),
            ('Repuestos Plataforma Pro', 'Andrea Molina', '+56 9 5020 1002', 'andrea@plataformapro.demo', 'Proveedor demo de repuestos.'),
            ('Servicio Técnico Vertical', 'Marco Díaz', '+56 9 5030 1003', 'marco@vertical.demo', 'Soporte técnico y revisiones.'),
        ]
        suppliers = []
        for name, contact, phone, email, notes in supplier_defs:
            supplier, _ = Supplier.objects.update_or_create(
                name=name,
                defaults={'contact_name': contact, 'phone': phone, 'email': email, 'notes': notes, 'is_active': True},
            )
            suppliers.append(supplier)
        return suppliers

    def _create_product(self, type_key, categories, brands, suppliers):
        if type_key == 'tijeras':
            brand_name, model = random.choice(self.SCISSOR_MODELS)
            name = f'Elevador tijera {brand_name} {model}'
        elif type_key == 'brazos':
            brand_name, model = random.choice(self.BOOM_MODELS)
            name = f'Brazo articulado {brand_name} {model}'
        elif type_key == 'baterias':
            base_name, model = random.choice(self.BATTERY_MODELS)
            brand_name = random.choice(self.BRAND_NAMES)
            name = f'{base_name} {model}'
        elif type_key == 'ruedas':
            base_name, model = random.choice(self.WHEEL_MODELS)
            brand_name = random.choice(self.BRAND_NAMES)
            name = f'{base_name} {model}'
        else:
            base_name, model = random.choice(self.CONTROL_MODELS)
            brand_name = random.choice(self.BRAND_NAMES)
            name = f'{base_name} {model}'

        product_type = self.TYPE_CONFIG[type_key]['product_type']
        condition = self._random_condition(product_type)
        show_price = random.random() > 0.15
        price = self._random_price(type_key) if show_price else None

        payload = {
            'name': name,
            'category': categories[type_key],
            'brand': brands[brand_name],
            'supplier': random.choice(suppliers),
            'product_type': product_type,
            'condition': condition,
            'short_description': self._random_short_description(type_key, model),
            'description': self._random_description(type_key, model),
            'model': model,
            'sku': self._generate_unique_sku(self.TYPE_CONFIG[type_key]['prefix']),
            'year': self._random_year() if product_type == Product.ProductType.MACHINERY else None,
            'hours_meter': self._random_hours(condition) if product_type == Product.ProductType.MACHINERY else None,
            'price': price,
            'price_visible': show_price,
            'stock_status': random.choice([
                Product.StockStatus.AVAILABLE,
                Product.StockStatus.AVAILABLE,
                Product.StockStatus.ON_REQUEST,
                Product.StockStatus.RESERVED,
            ]),
            'is_featured': random.random() < 0.2,
            'is_published': True,
        }

        return Product.objects.create(**payload)

    def _create_specs(self, product, type_key):
        specs = []
        if type_key == 'tijeras':
            specs = [
                ('Altura de trabajo', str(random.choice([8, 10, 12, 14])), 'm'),
                ('Capacidad', str(random.choice([227, 320, 454])), 'kg'),
                ('Energía', random.choice(['Eléctrica', 'Diésel']), ''),
                ('Peso aproximado', str(random.choice([1450, 2200, 3100])), 'kg'),
            ]
        elif type_key == 'brazos':
            specs = [
                ('Altura de trabajo', str(random.choice([14, 16, 18, 20])), 'm'),
                ('Alcance horizontal', str(random.choice([7, 9, 11, 12])), 'm'),
                ('Capacidad', str(random.choice([227, 250, 300])), 'kg'),
                ('Motorización', random.choice(['Diésel', 'Eléctrica', 'Híbrida']), ''),
            ]
        elif type_key == 'baterias':
            specs = [
                ('Voltaje', random.choice(['6', '12', '24', '48']), 'V'),
                ('Amperaje', str(random.choice([105, 150, 180, 225])), 'Ah'),
                ('Tecnología', random.choice(['Plomo-ácido', 'AGM', 'Gel', 'LiFePO4']), ''),
            ]
        elif type_key == 'ruedas':
            specs = [
                ('Diámetro', random.choice(['12', '14', '15', '16', '18']), 'in'),
                ('Material', random.choice(['Caucho sólido', 'Poliuretano', 'Caucho no marcante']), ''),
                ('Compatibilidad', random.choice(['Tijeras eléctricas', 'Brazos articulados', 'Plataformas mixtas']), ''),
            ]
        elif type_key == 'controles':
            specs = [
                ('Compatibilidad', random.choice(['Genie/JLG', 'Skyjack/Haulotte', 'Universal configurable']), ''),
                ('Tipo de conector', random.choice(['Deutsch 8 pines', 'Molex 12 pines', 'Conector rápido IP67']), ''),
                ('Uso', random.choice(['Control superior', 'Control inferior', 'Diagnóstico/mantenimiento']), ''),
            ]

        for order, (name, value, unit) in enumerate(specs, start=1):
            ProductSpec.objects.create(product=product, name=name, value=value, unit=unit, order=order)

    def _generate_unique_sku(self, prefix):
        base = f"{prefix}-{int(time.time() % 100000):05d}"
        while True:
            suffix = random.randint(100, 999)
            candidate = f'{base}-{suffix}'
            if not Product.objects.filter(sku=candidate).exists():
                return candidate

    def _random_condition(self, product_type):
        if product_type == Product.ProductType.MACHINERY:
            return random.choice(
                [
                    Product.ProductCondition.USED,
                    Product.ProductCondition.USED,
                    Product.ProductCondition.REFURBISHED,
                    Product.ProductCondition.NEW,
                ]
            )
        return random.choice(
            [
                Product.ProductCondition.NEW,
                Product.ProductCondition.NEW,
                Product.ProductCondition.REFURBISHED,
            ]
        )

    def _random_year(self):
        return random.randint(2014, 2025)

    def _random_hours(self, condition):
        if condition == Product.ProductCondition.NEW:
            return random.randint(0, 50)
        return random.randint(300, 5200)

    def _random_price(self, type_key):
        ranges = {
            'tijeras': (8000, 38000),
            'brazos': (18000, 62000),
            'baterias': (280, 2800),
            'ruedas': (90, 620),
            'controles': (120, 1200),
        }
        min_value, max_value = ranges[type_key]
        value = random.randint(min_value, max_value)
        return Decimal(value).quantize(Decimal('1.00'))

    def _random_short_description(self, type_key, model):
        snippets = {
            'tijeras': f'Equipo tijera modelo {model} con inspección demo y disponibilidad inmediata.',
            'brazos': f'Brazo articulado {model} con alcance optimizado para trabajos industriales.',
            'baterias': f'Batería modelo {model} para operación continua en plataformas eléctricas.',
            'ruedas': f'Rueda {model} de alta resistencia para trabajo intensivo.',
            'controles': f'Control {model} para reposición rápida en plataforma aérea.',
        }
        return snippets[type_key]

    def _random_description(self, type_key, model):
        descriptions = {
            'tijeras': f'Maquinaria demo {model} para faena interior/exterior, revisada y lista para entrega con respaldo técnico.',
            'brazos': f'Brazo demo {model} con mantenimiento preventivo realizado y configuración operativa para acceso en altura.',
            'baterias': f'Repuesto energético {model} con buen desempeño cíclico y compatibilidad comercial sujeta a validación.',
            'ruedas': f'Repuesto de rodado {model} diseñado para estabilidad y tracción en plataformas elevadoras.',
            'controles': f'Componente de mando {model} para reemplazo de tablero, joystick o caja de control.',
        }
        return descriptions[type_key]
