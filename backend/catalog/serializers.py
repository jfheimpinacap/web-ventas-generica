from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    Brand,
    Category,
    HomeSectionItem,
    Product,
    ProductImage,
    ProductSpec,
    Promotion,
    QuoteRequest,
    Supplier,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'parent',
            'description',
            'is_active',
            'order',
            'created_at',
            'updated_at',
        ]


class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'parent', 'description', 'is_active', 'order']
        extra_kwargs = {
            'name': {'required': True},
            'slug': {'required': False, 'allow_blank': True},
            'parent': {'required': False, 'allow_null': True},
            'description': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
            'order': {'required': False},
        }


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            'id',
            'name',
            'slug',
            'logo',
            'description',
            'is_active',
            'created_at',
            'updated_at',
        ]


class BrandWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['name', 'slug', 'logo', 'description', 'is_active']
        extra_kwargs = {
            'name': {'required': True},
            'slug': {'required': False, 'allow_blank': True},
            'logo': {'required': False, 'allow_null': True},
            'description': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'contact_name',
            'phone',
            'email',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        ]


class SupplierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'phone', 'email', 'notes', 'is_active']
        extra_kwargs = {
            'name': {'required': True},
            'contact_name': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
            'email': {'required': False, 'allow_blank': True},
            'notes': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image', 'alt_text', 'is_main', 'order', 'created_at']


class ProductImageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image', 'alt_text', 'is_main', 'order', 'created_at']
        read_only_fields = ['created_at']
        extra_kwargs = {
            'product': {'required': True},
            'image': {'required': True},
            'alt_text': {'required': False, 'allow_blank': True},
            'is_main': {'required': False},
            'order': {'required': False},
        }


class ProductSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        fields = ['id', 'product', 'name', 'value', 'unit', 'order']


class ProductSpecWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        fields = ['id', 'product', 'name', 'value', 'unit', 'order']
        extra_kwargs = {
            'product': {'required': True},
            'name': {'required': True},
            'value': {'required': True},
            'unit': {'required': False, 'allow_blank': True},
            'order': {'required': False},
        }


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'brand',
            'product_type',
            'condition',
            'short_description',
            'price',
            'price_visible',
            'stock_status',
            'is_featured',
            'is_published',
            'updated_at',
            'main_image',
        ]

    def get_main_image(self, obj):
        image = obj.main_image
        return ProductImageSerializer(image, context=self.context).data if image else None


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    specs = ProductSpecSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'brand',
            'supplier',
            'product_type',
            'condition',
            'short_description',
            'description',
            'model',
            'sku',
            'year',
            'hours_meter',
            'price',
            'price_visible',
            'stock_status',
            'is_featured',
            'is_published',
            'images',
            'specs',
            'created_at',
            'updated_at',
        ]


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name',
            'slug',
            'category',
            'brand',
            'supplier',
            'product_type',
            'condition',
            'short_description',
            'description',
            'model',
            'sku',
            'year',
            'hours_meter',
            'price',
            'price_visible',
            'stock_status',
            'is_featured',
            'is_published',
        ]
        extra_kwargs = {
            'name': {'required': True},
            'category': {'required': True},
            'product_type': {'required': True},
            'condition': {'required': True},
            'stock_status': {'required': True},
            'price': {'required': False, 'allow_null': True},
            'year': {'required': False, 'allow_null': True},
            'hours_meter': {'required': False, 'allow_null': True},
        }


class PromotionSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = Promotion
        fields = [
            'id',
            'title',
            'subtitle',
            'product',
            'image',
            'button_text',
            'button_url',
            'is_active',
            'order',
            'starts_at',
            'ends_at',
            'created_at',
            'updated_at',
        ]


class PromotionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = [
            'title',
            'subtitle',
            'product',
            'image',
            'button_text',
            'button_url',
            'is_active',
            'order',
            'starts_at',
            'ends_at',
        ]
        extra_kwargs = {
            'title': {'required': True},
            'subtitle': {'required': False, 'allow_blank': True},
            'product': {'required': False, 'allow_null': True},
            'image': {'required': False, 'allow_null': True},
            'button_text': {'required': False, 'allow_blank': True},
            'button_url': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
            'order': {'required': False},
            'starts_at': {'required': False, 'allow_null': True},
            'ends_at': {'required': False, 'allow_null': True},
        }


class HomeSectionItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    section_label = serializers.CharField(source='get_section_display', read_only=True)

    class Meta:
        model = HomeSectionItem
        fields = [
            'id',
            'section',
            'section_label',
            'position',
            'product',
            'is_active',
            'created_at',
            'updated_at',
        ]


class HomeSectionItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeSectionItem
        fields = ['section', 'position', 'product', 'is_active']
        extra_kwargs = {
            'section': {'required': True},
            'product': {'required': True},
        }

    def validate(self, attrs):
        data = attrs.copy()
        if self.instance:
            for field in ['section', 'position', 'product', 'is_active']:
                data.setdefault(field, getattr(self.instance, field))
        candidate = HomeSectionItem(**data)
        if self.instance:
            candidate.pk = self.instance.pk
        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class QuoteRequestPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteRequest
        fields = [
            'id',
            'product',
            'customer_name',
            'customer_phone',
            'customer_email',
            'company_name',
            'city',
            'preferred_contact_method',
            'message',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class QuoteRequestAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = QuoteRequest
        fields = [
            'id',
            'product',
            'product_name',
            'customer_name',
            'customer_phone',
            'customer_email',
            'company_name',
            'city',
            'preferred_contact_method',
            'message',
            'status',
            'internal_notes',
            'seller_response',
            'created_at',
            'updated_at',
            'contacted_at',
            'quoted_at',
            'closed_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'contacted_at', 'quoted_at', 'closed_at']
