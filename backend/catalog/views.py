from rest_framework import filters, mixins, viewsets

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


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).select_related('parent')
    serializer_class = CategorySerializer


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Supplier.objects.filter(is_active=True)
    serializer_class = SupplierSerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related('category', 'brand', 'supplier').prefetch_related('images', 'specs')
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
        if not include_unpublished:
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


class PromotionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Promotion.objects.filter(is_active=True).select_related('product__category', 'product__brand')
    serializer_class = PromotionSerializer


class QuoteRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = QuoteRequest.objects.select_related('product')
    serializer_class = QuoteRequestSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = self.queryset
        include_all = params.get('include_all') in {'1', 'true', 'True'}
        if not include_all:
            return queryset.none()
        return queryset
