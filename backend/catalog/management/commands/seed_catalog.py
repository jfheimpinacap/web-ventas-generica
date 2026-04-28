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
        self.stdout.write(self.style.SUCCESS(f'Seed de catálogo completado. Productos demo: {len(products)} | Promociones demo: 5'))

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
        plataformas, _ = Category.objects.update_or_create(
            slug='plataformas-telescopicas',
            defaults={'name': 'Plataformas telescópicas', 'parent': maquinaria, 'description': 'Plataformas de alto alcance y trabajo exterior', 'order': 3, 'is_active': True},
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
        cargadores, _ = Category.objects.update_or_create(
            slug='cargadores',
            defaults={'name': 'Cargadores', 'parent': repuestos, 'description': 'Cargadores y fuentes de energía', 'order': 4, 'is_active': True},
        )
        componentes, _ = Category.objects.update_or_create(
            slug='componentes-electricos-hidraulicos',
            defaults={
                'name': 'Componentes eléctricos e hidráulicos',
                'parent': repuestos,
                'description': 'Módulos, válvulas, sensores y cableado para equipos de altura',
                'order': 5,
                'is_active': True,
            },
        )

        legacy_services = Category.objects.filter(slug='servicios-y-accesorios').first()
        servicios, _ = Category.objects.update_or_create(
            slug='servicios',
            defaults={
                'name': 'Servicios',
                'parent': None,
                'description': 'Servicios técnicos especializados para equipos industriales.',
                'order': 3,
                'is_active': True,
            },
        )
        if legacy_services and legacy_services.id != servicios.id:
            Product.objects.filter(category=legacy_services).update(category=servicios)
            Category.objects.filter(parent=legacy_services).update(parent=servicios)
            legacy_services.delete()

        reparacion_motores, _ = Category.objects.update_or_create(
            slug='reparacion-motores-electricos',
            defaults={
                'name': 'Reparación motores eléctricos',
                'parent': servicios,
                'description': 'Diagnóstico, bobinado y reparación de motores eléctricos industriales.',
                'order': 1,
                'is_active': True,
            },
        )
        reparacion_bombas, _ = Category.objects.update_or_create(
            slug='reparacion-bombas',
            defaults={
                'name': 'Reparación bombas',
                'parent': servicios,
                'description': 'Reparación y calibración de bombas hidráulicas e industriales.',
                'order': 2,
                'is_active': True,
            },
        )
        mantenciones, _ = Category.objects.update_or_create(
            slug='mantenciones-general',
            defaults={
                'name': 'Mantenciones general',
                'parent': servicios,
                'description': 'Mantenciones preventivas y correctivas de equipos en terreno y taller.',
                'order': 3,
                'is_active': True,
            },
        )

        return {
            'elevadores': elevadores,
            'brazos': brazos,
            'plataformas': plataformas,
            'baterias': baterias,
            'ruedas': ruedas,
            'controles': controles,
            'cargadores': cargadores,
            'componentes': componentes,
            'servicios': servicios,
            'servicios_motores': reparacion_motores,
            'servicios_bombas': reparacion_bombas,
            'servicios_mantenciones': mantenciones,
        }

    def _seed_brands(self):
        names = ['Genie', 'JLG', 'Haulotte', 'Skyjack', 'Snorkel', 'LGMG', 'Zoomlion', 'Hyster']
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
        supplier_c, _ = Supplier.objects.update_or_create(
            name='Servicio Técnico Altura 360',
            defaults={
                'contact_name': 'María Salazar',
                'phone': '+56 9 3333 3333',
                'email': 'maria@altura360.test',
                'notes': 'Servicios de mantenimiento, inspección y soporte técnico especializado.',
                'is_active': True,
            },
        )
        return {'a': supplier_a, 'b': supplier_b, 'c': supplier_c}

    def _seed_products(self, categories, brands, suppliers):
        products_data = []

        machinery_items = [
            ('GENIE', 'GS-1930', 'Elevador tijera'), ('GENIE', 'GS-2632', 'Elevador tijera'), ('GENIE', 'GS-3246', 'Elevador tijera'),
            ('JLG', '1932R', 'Elevador tijera'), ('JLG', '2646ES', 'Elevador tijera'), ('JLG', '3394RT', 'Elevador tijera'),
            ('HAULOTTE', 'Compact 12', 'Elevador tijera'), ('HAULOTTE', 'Optimum 8', 'Elevador tijera'), ('SKYJACK', 'SJIII 3219', 'Elevador tijera'), ('SKYJACK', 'SJ6832RT', 'Elevador tijera'),
            ('JLG', '450AJ', 'Brazo articulado'), ('JLG', '600AJ', 'Brazo articulado'), ('GENIE', 'Z-45/25J', 'Brazo articulado'), ('GENIE', 'Z-60/34', 'Brazo articulado'),
            ('HAULOTTE', 'HA16 RTJ', 'Brazo articulado'), ('SNORKEL', 'A46JE', 'Brazo articulado'),
            ('JLG', '860SJ', 'Plataforma telescópica'), ('GENIE', 'S-65', 'Plataforma telescópica'), ('LGMG', 'T26J', 'Plataforma telescópica'), ('ZOOMLION', 'ZT34J', 'Plataforma telescópica'),
        ]
        machinery_brand_map = {
            'GENIE': 'Genie',
            'JLG': 'JLG',
            'HAULOTTE': 'Haulotte',
            'SKYJACK': 'Skyjack',
            'SNORKEL': 'Snorkel',
            'LGMG': 'LGMG',
            'ZOOMLION': 'Zoomlion',
        }

        for index, (brand_key, model, label) in enumerate(machinery_items, start=1):
            product_type = Product.ProductType.MACHINERY
            category_key = 'elevadores' if 'tijera' in label.lower() else 'brazos' if 'brazo' in label.lower() else 'plataformas'
            brand_name = machinery_brand_map[brand_key]
            condition = Product.ProductCondition.USED if index % 3 else Product.ProductCondition.REFURBISHED
            show_price = index % 4 != 0
            products_data.append(
                {
                    'sku': f'MAQ-{brand_key}-{index:03d}',
                    'name': f'{label} {brand_name} {model}',
                    'category': categories[category_key],
                    'brand': brands[brand_name],
                    'supplier': suppliers['a'],
                    'product_type': product_type,
                    'condition': condition,
                    'short_description': f'{label} confiable para operación continua en faena y bodega.',
                    'description': f'{label} modelo {model} con mantención al día, revisión mecánica y respaldo comercial para entrega rápida.',
                    'model': model,
                    'year': 2016 + (index % 8),
                    'hours_meter': 680 + (index * 73),
                    'price': f'{12000 + index * 950:.2f}' if show_price else None,
                    'price_visible': show_price,
                    'stock_status': Product.StockStatus.AVAILABLE if index % 5 else Product.StockStatus.ON_REQUEST,
                    'is_featured': index in {1, 5, 11, 17},
                    'is_published': True,
                }
            )

        spare_parts = [
            ('BAT', 'Batería tracción 48V 220Ah', 'BAT-48V-220AH', 'baterias', 'new', 1150),
            ('BAT', 'Batería AGM 24V 180Ah', 'BAT-24V-180AH', 'baterias', 'new', 760),
            ('BAT', 'Batería litio 48V 150Ah', 'BAT-LI-48V-150', 'baterias', 'new', 2490),
            ('BAT', 'Kit cableado batería industrial', 'KIT-BAT-CAB-01', 'baterias', 'new', 210),
            ('RUE', 'Rueda sólida no marcante 16"', 'WH-16-SOLID', 'ruedas', 'new', 180),
            ('RUE', 'Rueda tracción reforzada 18"', 'WH-18-TRAC', 'ruedas', 'new', 265),
            ('RUE', 'Rueda directriz poliuretano 12"', 'WH-12-PU', 'ruedas', 'new', 145),
            ('CTRL', 'Joystick proporcional multifunción', 'JOY-PRO-10', 'controles', 'new', 320),
            ('CTRL', 'Control de plataforma superior', 'CTRL-TOP-220', 'controles', 'new', 540),
            ('CTRL', 'Tarjeta electrónica de mando', 'PCB-CMD-804', 'componentes', 'refurbished', 680),
            ('CHG', 'Cargador inteligente 48V 30A', 'CHG-48V-30A', 'cargadores', 'new', 590),
            ('CHG', 'Cargador rápido 24V 40A', 'CHG-24V-40A', 'cargadores', 'new', 460),
            ('CHG', 'Fuente de poder panel control', 'PSU-PANEL-24', 'componentes', 'new', 190),
            ('ELE', 'Sensor inclinación plataforma', 'SNS-INCL-01', 'componentes', 'new', 215),
            ('ELE', 'Relé de potencia principal', 'RLY-PWR-80', 'componentes', 'new', 78),
            ('ELE', 'Arnés eléctrico completo', 'HRN-EL-SET', 'componentes', 'new', 355),
            ('HYD', 'Válvula hidráulica proporcional', 'VLV-HYD-PRO', 'componentes', 'new', 420),
            ('HYD', 'Cilindro elevación compacto', 'CYL-LIFT-C12', 'componentes', 'refurbished', 610),
            ('HYD', 'Filtro hidráulico retorno', 'FLT-HYD-RET', 'componentes', 'new', 55),
            ('ELE', 'Botonera paro emergencia', 'ESTOP-RED-01', 'controles', 'new', 68),
        ]

        for index, (prefix, name, model, category_key, condition, price) in enumerate(spare_parts, start=1):
            brand_name = ['Genie', 'JLG', 'Haulotte', 'Skyjack', 'Snorkel'][index % 5]
            show_price = index % 6 != 0
            products_data.append(
                {
                    'sku': f'REP-{prefix}-{index:03d}',
                    'name': name,
                    'category': categories[category_key],
                    'brand': brands[brand_name],
                    'supplier': suppliers['b'],
                    'product_type': Product.ProductType.SPARE_PART,
                    'condition': Product.ProductCondition.NEW if condition == 'new' else Product.ProductCondition.REFURBISHED,
                    'short_description': f'{name} para plataformas elevadoras y equipos de altura.',
                    'description': f'Repuesto demo {name.lower()} con compatibilidades múltiples y disponibilidad sujeta a verificación comercial.',
                    'model': model,
                    'price': f'{price:.2f}' if show_price else None,
                    'price_visible': show_price,
                    'stock_status': Product.StockStatus.AVAILABLE if index % 4 else Product.StockStatus.ON_REQUEST,
                    'is_featured': index in {1, 8, 14},
                    'is_published': True,
                }
            )

        extras = [
            ('SRV-MOT-001', 'Diagnóstico y rebobinado de motor trifásico', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_motores', 890),
            ('SRV-BOM-002', 'Reparación integral de bomba hidráulica', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_bombas', 620),
            ('SRV-MAN-003', 'Mantención general preventiva en planta', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_mantenciones', 420),
            ('SRV-MOT-004', 'Alineación y pruebas de motor eléctrico en banco', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_motores', 360),
            ('SRV-BOM-005', 'Inspección y cambio de sello mecánico de bomba', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_bombas', 280),
            ('SRV-MAN-006', 'Programa trimestral de mantenciones general', Product.ProductType.SERVICE, Product.ProductCondition.NOT_APPLICABLE, 'servicios_mantenciones', 1120),
            ('VAR-EQP-007', 'Torre de iluminación LED portátil', Product.ProductType.MACHINERY, Product.ProductCondition.USED, 'plataformas', 4800),
            ('VAR-EQP-008', 'Compresor industrial móvil 185 CFM', Product.ProductType.MACHINERY, Product.ProductCondition.USED, 'plataformas', 7300),
            ('VAR-REP-009', 'Pack mangueras hidráulicas alta presión', Product.ProductType.SPARE_PART, Product.ProductCondition.NEW, 'componentes', 280),
            ('VAR-INT-010', 'Producto interno no publicado demo', Product.ProductType.OTHER, Product.ProductCondition.NOT_APPLICABLE, 'servicios', 0),
        ]

        for index, (sku, name, product_type, condition, category_key, price) in enumerate(extras, start=1):
            is_internal = sku == 'VAR-INT-010'
            show_price = not is_internal and index % 3 != 0
            products_data.append(
                {
                    'sku': sku,
                    'name': name,
                    'category': categories[category_key],
                    'brand': brands[['Genie', 'JLG', 'Haulotte', 'Skyjack', 'Snorkel', 'Hyster'][index % 6]],
                    'supplier': suppliers['c'] if product_type == Product.ProductType.SERVICE else suppliers['b'],
                    'product_type': product_type,
                    'condition': condition,
                    'short_description': f'{name} disponible para cotización comercial.',
                    'description': f'{name} incluido como dataset demo para validar listados, filtros y tarjetas con volumen realista.',
                    'model': f'VAR-{index:03d}',
                    'price': f'{price:.2f}' if show_price else None,
                    'price_visible': show_price,
                    'stock_status': Product.StockStatus.RESERVED if is_internal else Product.StockStatus.AVAILABLE,
                    'is_featured': index in {1, 7},
                    'is_published': not is_internal,
                }
            )

        products = {}
        for product_data in products_data:
            sku = product_data['sku']
            product, _ = Product.objects.update_or_create(sku=sku, defaults=product_data)
            products[sku] = product
        return products

    def _seed_specs(self, products):
        specs_map = {
            'MAQ-GENIE-001': [('Altura de trabajo', '7.8', 'm', 1), ('Capacidad de carga', '227', 'kg', 2), ('Energía', 'Eléctrico', '', 3)],
            'MAQ-JLG-011': [('Altura de trabajo', '15.7', 'm', 1), ('Alcance horizontal', '7.6', 'm', 2), ('Capacidad', '250', 'kg', 3)],
            'MAQ-HAULOTTE-007': [('Altura de trabajo', '12', 'm', 1), ('Ancho de equipo', '1.2', 'm', 2), ('Peso operativo', '2720', 'kg', 3)],
            'MAQ-GENIE-018': [('Altura de plataforma', '19.8', 'm', 1), ('Tracción', '4x4', '', 2), ('Motor', 'Diésel', '', 3)],
            'REP-BAT-001': [('Voltaje', '48', 'V', 1), ('Capacidad', '220', 'Ah', 2), ('Tipo', 'Ciclo profundo', '', 3)],
            'REP-CTRL-008': [('Tipo de señal', 'Proporcional', '', 1), ('Compatibilidad', 'Controladores CAN', '', 2)],
            'REP-CHG-011': [('Entrada', '220', 'V', 1), ('Salida', '48V / 30A', '', 2), ('Protección', 'IP54', '', 3)],
            'REP-HYD-017': [('Presión máx.', '250', 'bar', 1), ('Caudal nominal', '60', 'L/min', 2)],
            'VAR-EQP-007': [('Potencia de torre', '4x350', 'W', 1), ('Autonomía', '10', 'h', 2)],
            'SRV-MOT-001': [('Cobertura', 'Motor hasta 75HP', '', 1), ('Tiempo de respuesta', '48', 'h', 2)],
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
        promotions_data = [
            {
                'title': 'Campaña maquinaria lista para despacho',
                'subtitle': 'Stock seleccionado de elevadores y brazos articulados con revisión técnica al día.',
                'product': products.get('MAQ-GENIE-001'),
                'button_text': 'Ver maquinaria',
                'button_url': 'http://localhost:5174/catalogo?product_type=machinery',
                'order': 1,
            },
            {
                'title': 'Semana de repuestos críticos',
                'subtitle': 'Baterías, joysticks, cargadores y componentes con disponibilidad prioritaria.',
                'product': products.get('REP-BAT-001'),
                'button_text': 'Revisar repuestos',
                'button_url': 'http://localhost:5174/catalogo?product_type=spare_part',
                'order': 2,
            },
            {
                'title': 'Oferta temporal por renovación de flota',
                'subtitle': 'Equipos reacondicionados con condiciones comerciales preferentes por tiempo limitado.',
                'product': products.get('MAQ-JLG-011'),
                'button_text': 'Cotizar promoción',
                'button_url': 'http://localhost:5174/cotizar',
                'order': 3,
            },
            {
                'title': 'Mantenimiento y soporte en terreno',
                'subtitle': 'Servicio técnico preventivo/correctivo para mantener tu operación activa y segura.',
                'product': products.get('SRV-MOT-001'),
                'button_text': 'Solicitar soporte',
                'button_url': 'http://localhost:5174/cotizar',
                'order': 4,
            },
            {
                'title': 'Cotización rápida con asesor dedicado',
                'subtitle': 'Comparte tu requerimiento y recibe recomendación de equipo/repuesto en el mismo día hábil.',
                'product': None,
                'button_text': 'Iniciar cotización',
                'button_url': 'http://localhost:5174/cotizar',
                'order': 5,
            },
        ]

        for promo in promotions_data:
            title = promo['title']
            Promotion.objects.update_or_create(
                title=title,
                defaults={
                    'subtitle': promo['subtitle'],
                    'product': promo['product'],
                    'button_text': promo['button_text'],
                    'button_url': promo['button_url'],
                    'is_active': True,
                    'order': promo['order'],
                },
            )
