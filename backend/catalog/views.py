from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, mixins, permissions, viewsets

from .models import Brand, Category, HomeSectionItem, Product, ProductImage, ProductSpec, Promotion, QuoteRequest, Supplier
from .services import send_quote_request_notifications
from .serializers import (
    BrandSerializer,
    BrandWriteSerializer,
    CategorySerializer,
    CategoryWriteSerializer,
    HomeSectionItemSerializer,
    HomeSectionItemWriteSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductImageWriteSerializer,
    ProductListSerializer,
    ProductSpecSerializer,
    ProductSpecWriteSerializer,
    ProductWriteSerializer,
    PromotionSerializer,
    PromotionWriteSerializer,
    QuoteRequestAdminSerializer,
    QuoteRequestPublicSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
)


def _include_inactive_for_authenticated(request):
    include_inactive = request.query_params.get('include_inactive') in {'1', 'true', 'True'}
    return request.user.is_authenticated and include_inactive


def _get_category_descendant_ids(category_id: int):
    descendants = [category_id]
    pending_ids = [category_id]

    while pending_ids:
        child_ids = list(Category.objects.filter(parent_id__in=pending_ids).values_list('id', flat=True))
        if not child_ids:
            break
        descendants.extend(child_ids)
        pending_ids = child_ids

    return descendants


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
        can_see_unpublished = self.request.user.is_authenticated and (
            include_unpublished or self.action in {'retrieve', 'update', 'partial_update', 'destroy'}
        )
        if not can_see_unpublished:
            queryset = queryset.filter(is_published=True)

        filters_map = {
            'brand': 'brand_id',
            'product_type': 'product_type',
            'condition': 'condition',
            'stock_status': 'stock_status',
        }

        category_filter = params.get('category')
        if category_filter:
            try:
                category_id = int(category_filter)
            except (TypeError, ValueError):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(category_id__in=_get_category_descendant_ids(category_id))

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


class QuoteRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = QuoteRequest.objects.select_related('product')

    def get_serializer_class(self):
        if self.action == 'create':
            return QuoteRequestPublicSerializer
        return QuoteRequestAdminSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset
        if not self.request.user.is_authenticated:
            return queryset.none()

        params = self.request.query_params
        status_value = params.get('status')
        if status_value:
            queryset = queryset.filter(status=status_value)

        product_value = params.get('product')
        if product_value:
            queryset = queryset.filter(product_id=product_value)

        search = params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(customer_name__icontains=search)
                | Q(customer_email__icontains=search)
                | Q(customer_phone__icontains=search)
                | Q(company_name__icontains=search)
                | Q(message__icontains=search)
            )

        ordering = params.get('ordering', '-created_at')
        allowed_ordering = {'created_at', '-created_at', 'updated_at', '-updated_at', 'status', '-status'}
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        quote_request = serializer.save()
        send_quote_request_notifications(quote_request)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        quote_request = serializer.save()
        next_status = quote_request.status

        if previous_status == next_status:
            return

        updates = []
        if next_status == QuoteRequest.QuoteStatus.CONTACTED and quote_request.contacted_at is None:
            quote_request.contacted_at = timezone.now()
            updates.append('contacted_at')
        if next_status == QuoteRequest.QuoteStatus.QUOTED and quote_request.quoted_at is None:
            quote_request.quoted_at = timezone.now()
            updates.append('quoted_at')
        if next_status == QuoteRequest.QuoteStatus.CLOSED and quote_request.closed_at is None:
            quote_request.closed_at = timezone.now()
            updates.append('closed_at')

        if updates:
            quote_request.save(update_fields=updates)


class HomeSectionItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return HomeSectionItemWriteSerializer
        return HomeSectionItemSerializer

    def get_queryset(self):
        queryset = HomeSectionItem.objects.select_related('product__category', 'product__brand', 'product__supplier', 'product')
        if not _include_inactive_for_authenticated(self.request):
            queryset = queryset.filter(is_active=True, product__is_published=True)

        section = self.request.query_params.get('section')
        if section:
            queryset = queryset.filter(section=section)

        return queryset.order_by('section', 'position', 'id')
