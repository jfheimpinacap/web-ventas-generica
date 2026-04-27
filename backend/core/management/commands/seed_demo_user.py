from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update demo seller user (vendedor).'

    def handle(self, *args, **options):
        User = get_user_model()
        username = 'vendedor'
        defaults = {
            'email': 'vendedor@example.com',
            'is_staff': True,
            'is_active': True,
        }

        user, created = User.objects.get_or_create(username=username, defaults=defaults)

        if not created:
            changed = False
            for field, value in defaults.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if changed:
                user.save(update_fields=list(defaults.keys()))

        user.set_password('vendedor123')
        user.save(update_fields=['password'])

        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Demo user {action}: {username}'))
