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
    import logging
    logger = logging.getLogger(__name__)
    
    sw_path = None
    
    # Try STATIC_ROOT first (production - after collectstatic)
    if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
        static_root_path = os.path.join(settings.STATIC_ROOT, 'js', 'sw.js')
        if os.path.exists(static_root_path):
            sw_path = static_root_path
    
    # Fallback to STATICFILES_DIRS (development)
    if not sw_path and hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        try:
            # STATICFILES_DIRS can be a list or tuple
            static_dirs = settings.STATICFILES_DIRS
            if isinstance(static_dirs, (list, tuple)) and len(static_dirs) > 0:
                static_dir = static_dirs[0]
                if isinstance(static_dir, (list, tuple)):
                    static_dir = static_dir[0]  # Handle tuple format
                potential_path = os.path.join(static_dir, 'js', 'sw.js')
                if os.path.exists(potential_path):
                    sw_path = potential_path
        except (IndexError, TypeError, AttributeError) as e:
            logger.warning(f'Error accessing STATICFILES_DIRS: {e}')
    
    # Last resort: try Django's static file finder (may not work in production)
    if not sw_path:
        try:
            from django.contrib.staticfiles import finders
            found_path = finders.find('js/sw.js')
            if found_path and os.path.exists(found_path):
                sw_path = found_path
        except Exception as e:
            logger.warning(f'Error using static file finder: {e}')
    
    if not sw_path or not os.path.exists(sw_path):
        logger.error(f'Service Worker not found. STATIC_ROOT: {getattr(settings, "STATIC_ROOT", None)}, STATICFILES_DIRS: {getattr(settings, "STATICFILES_DIRS", None)}')
        # Return a minimal Service Worker that does nothing rather than 404
        # This prevents the browser from showing errors
        minimal_sw = """
// Minimal Service Worker - file not found
self.addEventListener('install', () => {
    self.skipWaiting();
});
self.addEventListener('activate', () => {
    self.clients.claim();
});
"""
        response = HttpResponse(minimal_sw, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        return response
    
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (FileNotFoundError, IOError, PermissionError) as e:
        logger.error(f'Error reading Service Worker file: {e}')
        return HttpResponse('Error reading Service Worker', status=500, content_type='text/plain')
    
    response = HttpResponse(content, content_type='application/javascript')
    
    # CRITICAL: Set Service-Worker-Allowed header to allow scope '/' 
    # even though the file is in /static/js/
    response['Service-Worker-Allowed'] = '/'
    
    # Set other important headers for Service Worker
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

