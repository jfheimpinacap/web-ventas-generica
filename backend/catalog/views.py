from rest_framework import filters, mixins, permissions, viewsets

from .models import Brand, Category, Product, ProductImage, ProductSpec, Promotion, QuoteRequest, Supplier
from .serializers import (
    BrandSerializer,
    BrandWriteSerializer,
    CategorySerializer,
    CategoryWriteSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductImageWriteSerializer,
    ProductListSerializer,
    ProductSpecSerializer,
    ProductSpecWriteSerializer,
    ProductWriteSerializer,
    PromotionSerializer,
    PromotionWriteSerializer,
    QuoteRequestSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
)


def _include_inactive_for_authenticated(request):
    include_inactive = request.query_params.get('include_inactive') in {'1', 'true', 'True'}
    return request.user.is_authenticated and include_inactive


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return CategoryWriteSerializer
        return CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.select_related('parent')
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)


class BrandViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return BrandWriteSerializer
        return BrandSerializer

    def get_queryset(self):
        queryset = Brand.objects.all()
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)


class SupplierViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return SupplierWriteSerializer
        return SupplierSerializer

    def get_queryset(self):
        queryset = Supplier.objects.all()
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)


class ProductViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    queryset = Product.objects.select_related('category', 'brand', 'supplier').prefetch_related('images', 'specs')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'model', 'sku', 'short_description']
    ordering_fields = ['name', 'created_at', 'updated_at', 'price']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductWriteSerializer
        return ProductListSerializer

    def get_queryset(self):
        queryset = self.queryset
        params = self.request.query_params

        include_unpublished = params.get('include_unpublished') in {'1', 'true', 'True'}
        if not (self.request.user.is_authenticated and include_unpublished):
            queryset = queryset.filter(is_published=True)

        filters_map = {
            'category': 'category_id',
            'brand': 'brand_id',
            'product_type': 'product_type',
            'condition': 'condition',
            'stock_status': 'stock_status',
        }
        for param_name, model_lookup in filters_map.items():
            value = params.get(param_name)
            if value:
                queryset = queryset.filter(**{model_lookup: value})

        for bool_param in ['is_featured', 'is_published']:
            value = params.get(bool_param)
            if value in {'true', 'True', '1'}:
                queryset = queryset.filter(**{bool_param: True})
            elif value in {'false', 'False', '0'}:
                queryset = queryset.filter(**{bool_param: False})

        return queryset


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related('product').order_by('order', 'id')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductImageWriteSerializer
        return ProductImageSerializer

    def get_queryset(self):
        queryset = self.queryset
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        image = serializer.save()
        if image.is_main:
            ProductImage.objects.filter(product=image.product, is_main=True).exclude(pk=image.pk).update(is_main=False)

    def perform_update(self, serializer):
        image = serializer.save()
        if image.is_main:
            ProductImage.objects.filter(product=image.product, is_main=True).exclude(pk=image.pk).update(is_main=False)


class ProductSpecViewSet(viewsets.ModelViewSet):
    queryset = ProductSpec.objects.select_related('product').order_by('order', 'id')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductSpecWriteSerializer
        return ProductSpecSerializer

    def get_queryset(self):
        queryset = self.queryset
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset


class PromotionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return PromotionWriteSerializer
        return PromotionSerializer

    def get_queryset(self):
        queryset = Promotion.objects.select_related('product__category', 'product__brand')
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)


class QuoteRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = QuoteRequest.objects.select_related('product')
    serializer_class = QuoteRequestSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
