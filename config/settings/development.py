"""Development settings"""
from .base import *

DEBUG = True

# Development-specific CORS
CORS_ALLOW_ALL_ORIGINS = True

# Show SQL queries in console
LOGGING['loggers']['django.db.backends']['level'] = 'DEBUG'

# Disable some security for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Django Debug Toolbar (optional)
if 'debug_toolbar' in INSTALLED_APPS:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
