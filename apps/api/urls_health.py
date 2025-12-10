"""
Health check endpoints

Render uses these to check if the app is running. The /api/health/ endpoint
just returns OK, and /api/health/db/ also checks if the database is connected.
"""
from django.urls import path
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """
    Basic health check - just returns OK
    
    Render calls this to see if the app is up. If it returns 200, Render
    knows the app is running.
    """
    return JsonResponse({'status': 'healthy', 'service': 'Irish GIS API'})

def db_check(request):
    """
    Checks if the database is connected
    
    Tries to run a simple query. If it works, database is connected.
    If it fails, returns an error so I know there's a database problem.
    """
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
