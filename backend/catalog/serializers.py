from rest_framework import serializers

from .models import (
    Brand,
    Category,
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


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_main', 'order', 'created_at']


class ProductSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        fields = ['id', 'name', 'value', 'unit', 'order']


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


class QuoteRequestSerializer(serializers.ModelSerializer):
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
            'message',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']
