"""
Main URL configuration

This is the root URL config that ties everything together. It includes
the frontend pages, API routes, admin, health checks, and the service worker.
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
from apps.api.views_service_worker import service_worker

urlpatterns = [
    # Frontend pages - these serve the HTML templates
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('explore/', TemplateView.as_view(template_name='explore.html'), name='explore'),
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
    path('my-journey/', TemplateView.as_view(template_name='collage.html'), name='collage'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),

    # Django admin - for managing data
    path('admin/', admin.site.urls),

    # API endpoints - all under /api/v1/
    path('api/v1/', include('apps.api.urls')),

    # API documentation - Swagger UI and ReDoc
    # These generate interactive docs from the ViewSets
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Health check - Render uses this to monitor the app
    path('health/', include('apps.api.urls_health')),
    
    # Service Worker - needs to be at root with special headers
    # The custom view sets Service-Worker-Allowed header so it can control the whole site
    path('sw.js', service_worker, name='service_worker'),
]

# File serving - different for dev vs production
if settings.DEBUG:
    # In development, Django serves static and media files automatically
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # In production on Render, I need to serve media files manually
    # WhiteNoise handles static files, but media files (user uploads) need
    # to be served by Django. This is for bucket list photos and stuff.
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

# Customize the admin site header/title
admin.site.site_header = "Irish Historical Sites GIS Administration"
admin.site.site_title = "Irish GIS Admin"
admin.site.index_title = "Welcome to Irish Historical Sites GIS"
