from rest_framework import filters, mixins, permissions, viewsets

from .models import Brand, Category, Product, Promotion, QuoteRequest, Supplier
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    PromotionSerializer,
    QuoteRequestSerializer,
    SupplierSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.select_related('parent')
        if self.request.user.is_authenticated:
            return queryset
        return queryset.filter(is_active=True)


class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Brand.objects.all()
        if self.request.user.is_authenticated:
            return queryset
        return queryset.filter(is_active=True)


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Supplier.objects.all()
        if self.request.user.is_authenticated:
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


class PromotionViewSet(viewsets.ModelViewSet):
    serializer_class = PromotionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Promotion.objects.select_related('product__category', 'product__brand')
        if self.request.user.is_authenticated:
            return queryset
        return queryset.filter(is_active=True)


class QuoteRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = QuoteRequest.objects.select_related('product')
    serializer_class = QuoteRequestSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
