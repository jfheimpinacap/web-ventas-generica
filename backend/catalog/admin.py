from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductSpec, Promotion, QuoteRequest, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'order', 'updated_at')
    search_fields = ('name', 'slug', 'description')
    list_filter = ('is_active', 'parent')
    ordering = ('order', 'name')


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'updated_at')
    search_fields = ('name', 'slug', 'description')
    list_filter = ('is_active',)
    ordering = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'phone', 'email', 'is_active', 'updated_at')
    search_fields = ('name', 'contact_name', 'phone', 'email')
    list_filter = ('is_active',)
    ordering = ('name',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'brand',
        'product_type',
        'condition',
        'stock_status',
        'is_featured',
        'is_published',
        'updated_at',
    )
    search_fields = ('name', 'slug', 'model', 'sku', 'short_description')
    list_filter = ('category', 'brand', 'product_type', 'condition', 'stock_status', 'is_featured', 'is_published')
    ordering = ('-updated_at',)
    inlines = [ProductImageInline, ProductSpecInline]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_main', 'order', 'created_at')
    search_fields = ('product__name', 'alt_text')
    list_filter = ('is_main',)
    ordering = ('product', 'order')


@admin.register(ProductSpec)
class ProductSpecAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'value', 'unit', 'order')
    search_fields = ('product__name', 'name', 'value', 'unit')
    list_filter = ('name',)
    ordering = ('product', 'order')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'is_active', 'order', 'starts_at', 'ends_at', 'updated_at')
    search_fields = ('title', 'subtitle', 'button_text', 'button_url')
    list_filter = ('is_active',)
    ordering = ('order', '-updated_at')


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'customer_phone', 'customer_email', 'product', 'status', 'created_at')
    search_fields = ('customer_name', 'customer_phone', 'customer_email', 'message')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)
