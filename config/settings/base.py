"""
Base Django settings

This has all the common settings that are used in both development and
production. The production.py file overrides some of these for deployment.
I'm using GeoDjango because the app needs to work with geographic data.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Figure out where the project root is
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security settings
# These get the secret key and debug mode from environment variables
# In production, these should be set in Render's environment settings
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-CHANGE-THIS-IN-PRODUCTION')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Security headers to prevent XSS and clickjacking
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Installed apps - these are the Django apps that are active
INSTALLED_APPS = [
    # Standard Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # GeoDjango - needed for spatial database fields and queries
    'django.contrib.gis',
    
    # Third-party packages
    'rest_framework',  # For building the API
    'rest_framework_gis',  # GeoJSON serializers
    'corsheaders',  # Allows frontend to call the API
    'django_filters',  # For filtering API results
    'drf_spectacular',  # Auto-generates API documentation
    
    # My apps
    'apps.geography',  # Provinces, counties, eras
    'apps.sites',  # Historical sites, images, sources
    'apps.api',  # API views and serializers
]

# Middleware - these process requests in order
# Order matters! CORS needs to be early, WhiteNoise serves static files
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serves static files in production
    'corsheaders.middleware.CorsMiddleware',  # Handles CORS headers - must be early
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# URL configuration - points to the main urls.py file
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database configuration
# Using PostGIS (PostgreSQL with spatial extensions) for geographic data
# In production, production.py overrides this to use DATABASE_URL from Render
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME', 'irish_geo_db'),
        'USER': os.getenv('DB_USER', 'geo_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'options': '-c search_path=public,postgis'
        },
        'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
    }
}

# PostGIS version - tells Django which PostGIS functions are available
POSTGIS_VERSION = (3, 6, 0)

# Django REST Framework settings
# These configure how the API works - what formats it accepts, pagination, etc.
REST_FRAMEWORK = {
    # What formats the API can return (JSON and browsable HTML)
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    
    # What formats the API can accept (JSON, form data, file uploads)
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    
    # Default pagination - individual viewsets can override this
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'MAX_PAGE_SIZE': 1000,
    
    # How filtering works - can filter, search, and order results
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    
    # Rate limiting - prevents abuse
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',
        'user': '5000/hour',
    },
    
    # Auto-generates OpenAPI schema for documentation
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    
    # Date format for API responses
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
    'DATE_FORMAT': '%Y-%m-%d',
}

# API documentation settings
# These configure the Swagger/OpenAPI docs that get auto-generated
SPECTACULAR_SETTINGS = {
    'TITLE': 'Irish Historical Sites GIS API',
    'DESCRIPTION': 'RESTful API for Irish historical sites, monuments, and archaeological data',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
}

# CORS settings - allows the frontend to call the API
# In production, this should be set to the actual frontend URL
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://localhost:5173'
).split(',')

CORS_ALLOW_CREDENTIALS = True  # Allows cookies/sessions to work

# What HTTP methods are allowed
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# What headers the frontend can send
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Password validation rules
# Not really used since the app doesn't have user accounts, but Django
# requires this setting anyway
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization settings
# Set to Ireland timezone and support English/Irish
LANGUAGE_CODE = 'en-ie'
TIME_ZONE = 'Europe/Dublin'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ga', 'Irish'),
]

# Static files - CSS, JavaScript, images that are part of the app
# STATIC_ROOT is where collectstatic puts them for production
# STATICFILES_DIRS is where they are during development
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files - user-uploaded content like bucket list photos
# These get served differently in production (see urls.py)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Limit file upload size to prevent huge uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880

# Logging configuration
# Logs go to both console (for Render logs) and a file
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Change to DEBUG if you want to see all SQL queries
            'propagate': False,
        },
    },
}

# Default primary key type for new models
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
