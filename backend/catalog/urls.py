from rest_framework.routers import DefaultRouter

from .views import (
    BrandViewSet,
    CategoryViewSet,
    HomeSectionItemViewSet,
    ProductImageViewSet,
    ProductSpecViewSet,
    ProductViewSet,
    PromotionViewSet,
    QuoteRequestViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('brands', BrandViewSet, basename='brand')
router.register('suppliers', SupplierViewSet, basename='supplier')
router.register('products', ProductViewSet, basename='product')
router.register('product-images', ProductImageViewSet, basename='product-image')
router.register('product-specs', ProductSpecViewSet, basename='product-spec')
router.register('promotions', PromotionViewSet, basename='promotion')
router.register('home-section-items', HomeSectionItemViewSet, basename='home-section-item')
router.register('quote-requests', QuoteRequestViewSet, basename='quote-request')

urlpatterns = router.urls
