from django.contrib.auth.models import Group
from rest_framework.permissions import SAFE_METHODS, BasePermission

SELLER_GROUPS = {"vendedor", "admin_comercial"}


def is_seller_or_admin_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=SELLER_GROUPS).exists()


class IsSellerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_seller_or_admin_user(request.user)


class IsPublicReadSellerWrite(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_seller_or_admin_user(request.user)


class IsQuoteCreatePublicSellerManage(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return True
        return is_seller_or_admin_user(request.user)
