from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CurrentUserView, HealthView, LoginTokenObtainPairView

urlpatterns = [
    path('health/', HealthView.as_view(), name='api-health'),
    path('auth/login/', LoginTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),
    path('', include('catalog.urls')),
]
