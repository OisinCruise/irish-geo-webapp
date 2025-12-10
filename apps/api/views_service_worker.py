"""
Service Worker view - serves the PWA service worker file

I had to create a custom view for this because the service worker needs special
headers to work properly. The browser requires a Service-Worker-Allowed header
to allow the worker to control the entire site even though the file is in a
subdirectory.
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
    Serves the service worker JavaScript file with the right headers
    
    The service worker file is in /static/js/sw.js but needs to control the
    whole site. The Service-Worker-Allowed header tells the browser it's okay
    to do that. I also disable caching so updates to the SW file work immediately.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    sw_path = None
    
    # Try STATIC_ROOT first (production - after collectstatic)
    # In production, static files are collected to STATIC_ROOT
    if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
        # Django 3.1+ uses Path objects, need to convert to string
        static_root = settings.STATIC_ROOT
        if hasattr(static_root, '__fspath__'):
            static_root = str(static_root)
        else:
            static_root = str(static_root)
        static_root_path = os.path.join(static_root, 'js', 'sw.js')
        if os.path.exists(static_root_path):
            sw_path = static_root_path
    
    # Fallback to STATICFILES_DIRS (development)
    # In development, files are in STATICFILES_DIRS
    if not sw_path and hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        try:
            # STATICFILES_DIRS can be a list or tuple
            static_dirs = settings.STATICFILES_DIRS
            if isinstance(static_dirs, (list, tuple)) and len(static_dirs) > 0:
                static_dir = static_dirs[0]
                # Handle Path objects
                if hasattr(static_dir, '__fspath__'):
                    static_dir = str(static_dir)
                elif isinstance(static_dir, (list, tuple)):
                    static_dir = static_dir[0]  # Handle tuple format
                    if hasattr(static_dir, '__fspath__'):
                        static_dir = str(static_dir)
                else:
                    static_dir = str(static_dir)
                potential_path = os.path.join(static_dir, 'js', 'sw.js')
                if os.path.exists(potential_path):
                    sw_path = potential_path
        except (IndexError, TypeError, AttributeError, OSError) as e:
            logger.warning(f'Error accessing STATICFILES_DIRS: {e}')
    
    # Last resort: try Django's static file finder
    # This might not work in production but worth trying
    if not sw_path:
        try:
            from django.contrib.staticfiles import finders
            found_path = finders.find('js/sw.js')
            if found_path and os.path.exists(found_path):
                sw_path = found_path
        except Exception as e:
            logger.warning(f'Error using static file finder: {e}')
    
    # If we still can't find it, return a minimal SW instead of 404
    # This prevents browser errors and lets the app still work
    if not sw_path or not os.path.exists(sw_path):
        logger.error(f'Service Worker not found. STATIC_ROOT: {getattr(settings, "STATIC_ROOT", None)}, STATICFILES_DIRS: {getattr(settings, "STATICFILES_DIRS", None)}')
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
    
    # Read the actual service worker file
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (FileNotFoundError, IOError, PermissionError) as e:
        logger.error(f'Error reading Service Worker file: {e}')
        return HttpResponse('Error reading Service Worker', status=500, content_type='text/plain')
    
    response = HttpResponse(content, content_type='application/javascript')
    
    # Set the header that allows the SW to control the whole site
    response['Service-Worker-Allowed'] = '/'
    
    # Disable caching so SW updates work immediately
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

