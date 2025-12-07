"""
Irish Historical Sites GIS - URL Configuration
===============================================
Frontend routes, API v1 routing, and DRF Spectacular documentation
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    # ===========================================================================
    # FRONTEND PAGES
    # ===========================================================================
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('explore/', TemplateView.as_view(template_name='explore.html'), name='explore'),
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),

    # ===========================================================================
    # DJANGO ADMIN
    # ===========================================================================
    path('admin/', admin.site.urls),

    # ===========================================================================
    # API v1 ENDPOINTS
    # ===========================================================================
    path('api/v1/', include('apps.api.urls')),

    # ===========================================================================
    # API DOCUMENTATION (Swagger/OpenAPI)
    # ===========================================================================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ===========================================================================
    # HEALTH CHECK
    # ===========================================================================
    path('health/', include('apps.api.urls_health')),
]

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site headers
admin.site.site_header = "Irish Historical Sites GIS Administration"
admin.site.site_title = "Irish GIS Admin"
admin.site.index_title = "Welcome to Irish Historical Sites GIS"
