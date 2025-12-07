"""Health check endpoints"""
from django.urls import path
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """Basic health check"""
    return JsonResponse({'status': 'healthy', 'service': 'Irish GIS API'})

def db_check(request):
    """Database connectivity check"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({'database': 'connected', 'status': 'healthy'})
    except Exception as e:
        return JsonResponse({'database': 'error', 'message': str(e)}, status=500)

urlpatterns = [
    path('', health_check, name='health'),
    path('db/', db_check, name='health-db'),
]
