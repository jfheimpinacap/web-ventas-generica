from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def _generate_unique_slug(instance, source_value: str, slug_field: str = 'slug') -> str:
    base_slug = slugify(source_value) or 'item'
    slug = base_slug
    model_class = instance.__class__
    index = 1

    while model_class.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk).exists():
        slug = f'{base_slug}-{index}'
        index += 1

    return slug


class Category(TimestampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(TimestampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    logo = models.FileField(upload_to='brands/logos/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Supplier(TimestampedModel):
    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(TimestampedModel):
    class ProductType(models.TextChoices):
        MACHINERY = 'machinery', 'Machinery'
        SPARE_PART = 'spare_part', 'Spare part'
        SERVICE = 'service', 'Service'
        OTHER = 'other', 'Other'

    class ProductCondition(models.TextChoices):
        NEW = 'new', 'New'
        USED = 'used', 'Used'
        REFURBISHED = 'refurbished', 'Refurbished'
        NOT_APPLICABLE = 'not_applicable', 'Not applicable'

    class StockStatus(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        ON_REQUEST = 'on_request', 'On request'
        SOLD = 'sold', 'Sold'
        RESERVED = 'reserved', 'Reserved'

    name = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.MACHINERY)
    condition = models.CharField(max_length=20, choices=ProductCondition.choices, default=ProductCondition.NOT_APPLICABLE)
    short_description = models.CharField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    model = models.CharField(max_length=120, blank=True)
    sku = models.CharField(max_length=120, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    hours_meter = models.PositiveIntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_visible = models.BooleanField(default=True)
    stock_status = models.CharField(max_length=20, choices=StockStatus.choices, default=StockStatus.ON_REQUEST)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def main_image(self):
        return self.images.filter(is_main=True).order_by('order', 'id').first() or self.images.order_by('order', 'id').first()

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.FileField(upload_to='products/images/')
    alt_text = models.CharField(max_length=220, blank=True)
    is_main = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'Image for {self.product.name}'


class ProductSpec(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specs')
    name = models.CharField(max_length=120)
    value = models.CharField(max_length=220)
    unit = models.CharField(max_length=40, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.product.name} - {self.name}'


class Promotion(TimestampedModel):
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=280, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions')
    image = models.FileField(upload_to='promotions/', blank=True, null=True)
    button_text = models.CharField(max_length=80, blank=True)
    button_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title


class HomeSectionItem(TimestampedModel):
    class Section(models.TextChoices):
        MACHINERY_PROMOTIONS = 'machinery_promotions', 'Promociones en maquinarias'
        SPARE_PARTS_OFFERS = 'spare_parts_offers', 'Oferta en repuestos'
        REPAIR_SERVICES = 'repair_services', 'Servicios de reparación'

    SECTION_LIMITS = {
        Section.MACHINERY_PROMOTIONS: 10,
        Section.SPARE_PARTS_OFFERS: 6,
        Section.REPAIR_SERVICES: 12,
    }

    section = models.CharField(max_length=40, choices=Section.choices)
    position = models.PositiveIntegerField(default=1)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='home_section_items')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['section', 'position', 'id']
        unique_together = [('section', 'position'), ('section', 'product')]

    def clean(self):
        super().clean()
        max_items = self.SECTION_LIMITS.get(self.section)
        if not max_items:
            return

        total_items = HomeSectionItem.objects.filter(section=self.section, is_active=True).exclude(pk=self.pk).count()
        if self.is_active and total_items >= max_items:
            raise ValidationError({'section': f'La sección "{self.get_section_display()}" permite máximo {max_items} elementos activos.'})

        if self.position > max_items:
            raise ValidationError({'position': f'La posición máxima para esta sección es {max_items}.'})

    def __str__(self):
        return f'{self.get_section_display()} - {self.position} - {self.product.name}'


class QuoteRequest(TimestampedModel):
    class QuoteStatus(models.TextChoices):
        NEW = 'new', 'New'
        CONTACTED = 'contacted', 'Contacted'
        QUOTED = 'quoted', 'Quoted'
        CLOSED = 'closed', 'Closed'
        DISCARDED = 'discarded', 'Discarded'

    class PreferredContactMethod(models.TextChoices):
        PHONE = 'phone', 'Phone'
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='quote_requests')
    customer_name = models.CharField(max_length=160)
    customer_phone = models.CharField(max_length=40)
    customer_email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=120, blank=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=PreferredContactMethod.choices,
        blank=True,
    )
    message = models.TextField()
    status = models.CharField(max_length=20, choices=QuoteStatus.choices, default=QuoteStatus.NEW)
    internal_notes = models.TextField(blank=True)
    seller_response = models.TextField(blank=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    quoted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Quote #{self.pk} - {self.customer_name}'
