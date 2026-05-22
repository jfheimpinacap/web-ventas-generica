from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import escape
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .throttles import LoginRateThrottle



from catalog.models import Category, Product


def _normalize_public_site_url() -> str:
    return settings.PUBLIC_SITE_URL.rstrip('/')


def _build_absolute_url(path: str) -> str:
    base_url = _normalize_public_site_url()
    normalized_path = path if path.startswith('/') else f'/{path}'
    return f'{base_url}{normalized_path}'


def _format_lastmod(value):
    if not value:
        return None

    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            return None
        value = parsed

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)

    return value.date().isoformat()


class SitemapXmlView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        urls: list[dict[str, str]] = [
            {
                'loc': _build_absolute_url('/'),
                'changefreq': 'weekly',
                'priority': '1.0',
            },
            {
                'loc': _build_absolute_url('/catalogo'),
                'changefreq': 'daily',
                'priority': '0.8',
            },
        ]

        published_products = Product.objects.filter(is_published=True).only('slug', 'updated_at').order_by('slug')
        for product in published_products:
            item = {
                'loc': _build_absolute_url(f'/producto/{product.slug}'),
                'changefreq': 'weekly',
                'priority': '0.7',
            }
            lastmod = _format_lastmod(product.updated_at)
            if lastmod:
                item['lastmod'] = lastmod
            urls.append(item)

        active_categories = Category.objects.filter(is_active=True).only('id', 'updated_at').order_by('id')
        for category in active_categories:
            item = {
                'loc': f"{_build_absolute_url('/catalogo')}?category={category.id}",
                'changefreq': 'weekly',
                'priority': '0.6',
            }
            lastmod = _format_lastmod(category.updated_at)
            if lastmod:
                item['lastmod'] = lastmod
            urls.append(item)

        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for url in urls:
            xml_lines.append('  <url>')
            xml_lines.append(f"    <loc>{escape(url['loc'])}</loc>")
            if 'lastmod' in url:
                xml_lines.append(f"    <lastmod>{url['lastmod']}</lastmod>")
            xml_lines.append(f"    <changefreq>{url['changefreq']}</changefreq>")
            xml_lines.append(f"    <priority>{url['priority']}</priority>")
            xml_lines.append('  </url>')
        xml_lines.append('</urlset>')

        return HttpResponse('\n'.join(xml_lines), content_type='application/xml')


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({'status': 'ok'})


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser']


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class LoginTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]
