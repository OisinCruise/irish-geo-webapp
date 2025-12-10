"""
Production settings for Render deployment

This overrides base.py settings for production. Main differences are:
- DEBUG = False
- Uses DATABASE_URL from Render
- More security headers
- WhiteNoise for static files
- Logging to console (Render captures this)
"""
from .base import *
import os

# Security - always False in production
DEBUG = False

# Allowed hosts - Render provides the domain, but I also allow localhost
# for testing. The .onrender.com pattern matches any Render subdomain.
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS if host.strip()]

# Add Render domains
ALLOWED_HOSTS.extend([
    '.onrender.com',
    'localhost',
    '127.0.0.1',
])

# CSRF protection - only trust HTTPS requests from Render domains
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
]

# If there's a custom domain set, add it too
CUSTOM_DOMAIN = os.environ.get('CUSTOM_DOMAIN', '')
if CUSTOM_DOMAIN:
    ALLOWED_HOSTS.append(CUSTOM_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f'https://{CUSTOM_DOMAIN}')

# Security headers for production
# These force HTTPS and secure cookies
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS - tells browsers to always use HTTPS for a year
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Database configuration for Render
# Render automatically provides DATABASE_URL when you link a database
# I parse it to extract the connection details
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    # Parse the DATABASE_URL that Render provides
    # Format is: postgresql://user:password@host:port/dbname
    import urllib.parse
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': url.path[1:],  # Remove the leading slash
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or '5432',
            'OPTIONS': {
                'sslmode': 'require',  # Render requires SSL connections
            },
            'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
        }
    }
else:
    # Fallback if DATABASE_URL isn't set (shouldn't happen on Render)
    # This is for local testing or if someone sets it up manually
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': os.environ.get('DB_NAME', 'irish_geo_db'),
            'USER': os.environ.get('DB_USER', 'irish_geo_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': 'require',
            },
            'CONN_MAX_AGE': 600,
        }
    }

# Static files - WhiteNoise serves them directly from Django
# The CompressedManifest version compresses files and adds cache busting
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files - user uploads like bucket list photos
# For now storing locally on Render. Could move to cloud storage later
# if there are too many uploads, but for now this works fine.
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging - in production, logs go to console which Render captures
# This is simpler than file logging and Render shows them in the dashboard
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

# Cache - using in-memory cache since it's simple and works fine
# Could use Redis later if needed, but for now this is fine
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Sessions - stored in database, last for a week
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 1 week

# Email - not set up yet, but could add this to send error reports
# ADMINS = [('Your Name', 'your.email@example.com')]
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
