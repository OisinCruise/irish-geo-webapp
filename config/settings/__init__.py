"""
Django settings package - automatically loads correct environment
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine which settings to use
environment = os.getenv('DJANGO_ENVIRONMENT', 'development')

if environment == 'production':
    from .production import *
elif environment == 'testing':
    from .testing import *
else:
    from .development import *
