from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import ValidationError

from .models import Brand, Category, HomeSectionItem, Product, ProductImage, ProductSpec, Promotion, QuoteRequest, Supplier
from .permissions import IsPublicReadSellerWrite, IsQuoteCreatePublicSellerManage, is_seller_or_admin_user
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
from core.throttles import PublicCatalogReadThrottle, QuoteRequestCreateThrottle

MAX_SEARCH_LENGTH = 120


def _audit_kwargs_for_create(request):
    if request.user.is_authenticated:
        return {'created_by': request.user, 'updated_by': request.user}
    return {}


def _audit_kwargs_for_update(request):
    if request.user.is_authenticated:
        return {'updated_by': request.user}
    return {}


def _include_inactive_for_authenticated(request):
    include_inactive = request.query_params.get('include_inactive') in {'1', 'true', 'True'}
    return is_seller_or_admin_user(request.user) and include_inactive


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
    permission_classes = [IsPublicReadSellerWrite]
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return CategoryWriteSerializer
        return CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.select_related('parent')
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class BrandViewSet(viewsets.ModelViewSet):
    permission_classes = [IsPublicReadSellerWrite]
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return BrandWriteSerializer
        return BrandSerializer

    def get_queryset(self):
        queryset = Brand.objects.all()
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class SupplierViewSet(viewsets.ModelViewSet):
    permission_classes = [IsPublicReadSellerWrite]
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return SupplierWriteSerializer
        return SupplierSerializer

    def get_queryset(self):
        queryset = Supplier.objects.all()
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class ProductViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    queryset = Product.objects.select_related('category', 'brand', 'supplier').prefetch_related('images', 'specs')
    permission_classes = [IsPublicReadSellerWrite]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'model', 'sku', 'short_description']
    ordering = ['-updated_at']
    ordering_fields = ['name', 'price', 'created_at', 'updated_at', 'is_featured']
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        if self.action in {'create', 'update', 'partial_update'}:
            return ProductWriteSerializer
        return ProductListSerializer

    def get_queryset(self):
        queryset = self.queryset
        params = self.request.query_params
        self._validate_query_params(params)

        include_unpublished = params.get('include_unpublished') in {'1', 'true', 'True'}
        can_see_unpublished = is_seller_or_admin_user(self.request.user) and (
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

    def _validate_query_params(self, params):
        search = params.get('search')
        if search is not None:
            normalized_search = search.strip()
            if len(normalized_search) > MAX_SEARCH_LENGTH:
                raise ValidationError({'search': f'El parámetro search no puede superar {MAX_SEARCH_LENGTH} caracteres.'})
        category_value = params.get('category')
        if category_value and not category_value.isdigit():
            raise ValidationError({'category': 'El parámetro category debe ser un ID numérico.'})
        brand_value = params.get('brand')
        if brand_value and not brand_value.isdigit():
            raise ValidationError({'brand': 'El parámetro brand debe ser un ID numérico.'})
        enum_values = {
            'product_type': {choice[0] for choice in Product.ProductType.choices},
            'condition': {choice[0] for choice in Product.ProductCondition.choices},
            'stock_status': {choice[0] for choice in Product.StockStatus.choices},
        }
        for key, allowed in enum_values.items():
            value = params.get(key)
            if value and value not in allowed:
                raise ValidationError({key: f'Valor inválido para {key}.'})
        bool_fields = ['include_unpublished', 'is_featured']
        for key in bool_fields:
            value = params.get(key)
            if value and value not in {'1', '0', 'true', 'false', 'True', 'False'}:
                raise ValidationError({key: f'Valor inválido para {key}.'})
        ordering = params.get('ordering')
        if ordering and ordering not in {field for item in self.ordering_fields for field in (item, f'-{item}')}:
            raise ValidationError({'ordering': 'Campo de ordering inválido.'})

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related('product').order_by('order', 'id')
    permission_classes = [IsPublicReadSellerWrite]

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
        image = serializer.save(**_audit_kwargs_for_create(self.request))
        if image.is_main:
            ProductImage.objects.filter(product=image.product, is_main=True).exclude(pk=image.pk).update(is_main=False)

    def perform_update(self, serializer):
        image = serializer.save(**_audit_kwargs_for_update(self.request))
        if image.is_main:
            ProductImage.objects.filter(product=image.product, is_main=True).exclude(pk=image.pk).update(is_main=False)


class ProductSpecViewSet(viewsets.ModelViewSet):
    queryset = ProductSpec.objects.select_related('product').order_by('order', 'id')
    permission_classes = [IsPublicReadSellerWrite]

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

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class PromotionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsPublicReadSellerWrite]
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return PromotionWriteSerializer
        return PromotionSerializer

    def get_queryset(self):
        queryset = Promotion.objects.select_related('product__category', 'product__brand')
        if _include_inactive_for_authenticated(self.request):
            return queryset
        return queryset.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(**_audit_kwargs_for_create(self.request))

    def perform_update(self, serializer):
        serializer.save(**_audit_kwargs_for_update(self.request))


class QuoteRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = QuoteRequest.objects.select_related('product')
    permission_classes = [IsQuoteCreatePublicSellerManage]
    throttle_scope = 'admin_api'

    def get_serializer_class(self):
        if self.action == 'create':
            return QuoteRequestPublicSerializer
        return QuoteRequestAdminSerializer


    def get_throttles(self):
        if self.action == 'create':
            return [QuoteRequestCreateThrottle()]
        return super().get_throttles()

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
        if len(search) > MAX_SEARCH_LENGTH:
            raise ValidationError({'search': f'El parámetro search no puede superar {MAX_SEARCH_LENGTH} caracteres.'})
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
        if ordering not in allowed_ordering:
            raise ValidationError({'ordering': 'Campo de ordering inválido para cotizaciones.'})
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        quote_request = serializer.save(**_audit_kwargs_for_create(self.request))
        send_quote_request_notifications(quote_request)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        quote_request = serializer.save(**_audit_kwargs_for_update(self.request))
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
    permission_classes = [IsPublicReadSellerWrite]
    throttle_classes = [PublicCatalogReadThrottle]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return HomeSectionItemWriteSerializer
        return HomeSectionItemSerializer

    def _reindex_section(self, section: str):
        section_items = list(HomeSectionItem.objects.filter(section=section).order_by('position', 'id'))
        for index, entry in enumerate(section_items, start=1):
            if entry.position != index:
                HomeSectionItem.objects.filter(pk=entry.pk).update(position=index)

    def _next_position(self, section: str):
        section_items = HomeSectionItem.objects.filter(section=section).order_by('position').values_list('position', flat=True)
        used_positions = set(section_items)
        max_items = HomeSectionItem.SECTION_LIMITS.get(section, 1)
        for position in range(1, max_items + 1):
            if position not in used_positions:
                return position
        return max_items + 1

    def perform_create(self, serializer):
        section = serializer.validated_data['section']
        serializer.save(position=self._next_position(section), is_active=True, **_audit_kwargs_for_create(self.request))

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        original_section = instance.section
        original_position = instance.position

        section = serializer.validated_data.get('section', instance.section)
        target_position = serializer.validated_data.get('position', instance.position)

        if section != original_section:
            serializer.save(position=self._next_position(section), **_audit_kwargs_for_update(self.request))
            self._reindex_section(original_section)
            self._reindex_section(section)
            return

        if target_position != original_position:
            section_limit = HomeSectionItem.SECTION_LIMITS.get(section, 1)
            target_position = max(1, min(target_position, section_limit))
            occupied_item = HomeSectionItem.objects.filter(section=section, position=target_position).exclude(pk=instance.pk).first()

            # Swap positions when target slot is already occupied (mainly for "Oferta en repuestos").
            if occupied_item:
                HomeSectionItem.objects.filter(pk=instance.pk).update(position=0)
                HomeSectionItem.objects.filter(pk=occupied_item.pk).update(position=original_position)
                serializer.save(position=target_position, **_audit_kwargs_for_update(self.request))
            else:
                serializer.save(position=target_position, **_audit_kwargs_for_update(self.request))

            return

        serializer.save(**_audit_kwargs_for_update(self.request))

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

    def get_queryset(self):
        queryset = HomeSectionItem.objects.select_related('product__category', 'product__brand', 'product__supplier', 'product')
        if not _include_inactive_for_authenticated(self.request):
            queryset = queryset.filter(is_active=True, product__is_published=True)

        section = self.request.query_params.get('section')
        if section:
            queryset = queryset.filter(section=section)

        return queryset.order_by('section', 'position', 'id')
