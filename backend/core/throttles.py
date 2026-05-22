from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle
from django.conf import settings


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'

    def allow_request(self, request, view):
        if settings.TESTING:
            return True
        return super().allow_request(request, view)


class QuoteRequestCreateThrottle(AnonRateThrottle):
    scope = 'quote_requests_create'


class PublicCatalogReadThrottle(AnonRateThrottle):
    scope = 'public_catalog_read'


class AuthenticatedUserThrottle(UserRateThrottle):
    scope = 'authenticated_user'


class AdminApiThrottle(ScopedRateThrottle):
    scope = 'admin_api'
