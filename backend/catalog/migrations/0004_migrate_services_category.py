from django.db import migrations


def migrate_services_category(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Product = apps.get_model('catalog', 'Product')

    legacy = Category.objects.filter(slug='servicios-y-accesorios').first()
    services = Category.objects.filter(slug='servicios').first()

    if services is None:
        if legacy is not None:
            legacy.slug = 'servicios'
            legacy.name = 'Servicios'
            legacy.parent_id = None
            legacy.description = 'Servicios técnicos especializados para equipos industriales.'
            legacy.order = 3
            legacy.is_active = True
            legacy.save(update_fields=['slug', 'name', 'parent', 'description', 'order', 'is_active'])
            services = legacy
        else:
            services = Category.objects.create(
                name='Servicios',
                slug='servicios',
                parent_id=None,
                description='Servicios técnicos especializados para equipos industriales.',
                order=3,
                is_active=True,
            )

    if legacy is not None and legacy.id != services.id:
        Product.objects.filter(category_id=legacy.id).update(category_id=services.id)
        Category.objects.filter(parent_id=legacy.id).update(parent_id=services.id)
        legacy.delete()

    children = [
        (
            'reparacion-motores-electricos',
            'Reparación motores eléctricos',
            'Diagnóstico, bobinado y reparación de motores eléctricos industriales.',
            1,
        ),
        (
            'reparacion-bombas',
            'Reparación bombas',
            'Reparación y calibración de bombas hidráulicas e industriales.',
            2,
        ),
        (
            'mantenciones-general',
            'Mantenciones general',
            'Mantenciones preventivas y correctivas de equipos en terreno y taller.',
            3,
        ),
    ]

    for slug, name, description, order in children:
        Category.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'parent_id': services.id,
                'description': description,
                'order': order,
                'is_active': True,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_homesectionitem'),
    ]

    operations = [
        migrations.RunPython(migrate_services_category, noop_reverse),
    ]
