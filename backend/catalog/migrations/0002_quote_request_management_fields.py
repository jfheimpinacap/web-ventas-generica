from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='quoterequest',
            name='city',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='company_name',
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='contacted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='internal_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='preferred_contact_method',
            field=models.CharField(
                blank=True,
                choices=[('phone', 'Phone'), ('email', 'Email'), ('whatsapp', 'WhatsApp')],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='quoted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='seller_response',
            field=models.TextField(blank=True),
        ),
    ]
