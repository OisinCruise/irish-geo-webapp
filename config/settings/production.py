"""
Production settings for Azure deployment
"""
from .base import *
import os

# Security settings
DEBUG = False

# Get allowed hosts from environment
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS if host.strip()]

# Add Azure default domain pattern and internal IPs for health probes
ALLOWED_HOSTS.extend([
    '.azurewebsites.net',
    'localhost',
    '127.0.0.1',
])

# Allow all hosts for Azure internal health probes (169.254.x.x range)
# This is safe because Azure App Service handles external traffic filtering
ALLOWED_HOSTS.append('*')

# CSRF trusted origins for Azure
CSRF_TRUSTED_ORIGINS = [
    'https://*.azurewebsites.net',
]

# Security headers (extends base.py settings for production)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Database - Neon PostgreSQL with PostGIS
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME', 'irish_geo_db'),
        'USER': os.environ.get('DB_USER', 'geo_admin'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',  # Neon requires SSL
            'connect_timeout': '60',  # 60 second connection timeout for Neon auto-resume
            # Note: search_path and statement_timeout cannot be used with Neon's connection pooler
            # The public schema is the default, so this is not needed
        },
        'CONN_MAX_AGE': 600,  # Increased for S2 Standard tier - better connection reuse
    }
}

# Static files - use WhiteNoise for serving
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files - for production, consider Azure Blob Storage
# For now, use local storage (works for App Service)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Cache configuration - use local memory cache (simple, no file dependencies)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 1 week

# Email configuration (optional - for error reports)
# ADMINS = [('Your Name', 'your.email@example.com')]
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
