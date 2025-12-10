"""
Service Worker View
===================
Custom view to serve Service Worker with proper headers
"""
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
from django.conf import settings
import os


@require_GET
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """
    Serve Service Worker file with proper headers.
    
    Sets Service-Worker-Allowed header to allow scope '/' even though
    the file is served from a subdirectory.
    """
    from django.contrib.staticfiles import finders
    
    # Try to find the Service Worker file using Django's static file finders
    # This works in both development and production
    sw_path = finders.find('js/sw.js')
    
    # Fallback: try STATIC_ROOT (production) or STATICFILES_DIRS (development)
    if not sw_path:
        if settings.STATIC_ROOT and os.path.exists(settings.STATIC_ROOT):
            sw_path = os.path.join(settings.STATIC_ROOT, 'js', 'sw.js')
        elif settings.STATICFILES_DIRS:
            sw_path = os.path.join(settings.STATICFILES_DIRS[0], 'js', 'sw.js')
    
    if not sw_path or not os.path.exists(sw_path):
        return HttpResponse('Service Worker not found', status=404, content_type='text/plain')
    
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (FileNotFoundError, IOError) as e:
        return HttpResponse(f'Error reading Service Worker: {str(e)}', status=500, content_type='text/plain')
    
    response = HttpResponse(content, content_type='application/javascript')
    
    # CRITICAL: Set Service-Worker-Allowed header to allow scope '/' 
    # even though the file is in /static/js/
    response['Service-Worker-Allowed'] = '/'
    
    # Set other important headers for Service Worker
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

