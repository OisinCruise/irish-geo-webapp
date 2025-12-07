"""
API v1 URL Routing
==================
RESTful API endpoints for Irish Historical Sites GIS.
All endpoints are versioned under /api/v1/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    HistoricalSiteViewSet,
    ProvinceViewSet,
    CountyViewSet,
    HistoricalEraViewSet,
    SiteImageViewSet,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'sites', HistoricalSiteViewSet, basename='site')
router.register(r'provinces', ProvinceViewSet, basename='province')
router.register(r'counties', CountyViewSet, basename='county')
router.register(r'eras', HistoricalEraViewSet, basename='era')
router.register(r'images', SiteImageViewSet, basename='image')

# API URL patterns
urlpatterns = [
    # Router-generated URLs
    path('', include(router.urls)),
]

"""
Generated API Endpoints:
========================

Historical Sites:
    GET  /api/v1/sites/                     - List all approved sites (GeoJSON)
    GET  /api/v1/sites/{id}/                - Site detail
    GET  /api/v1/sites/nearby/              - Find sites near point (?lat=&lon=&distance=)
    GET  /api/v1/sites/in_bbox/             - Sites in bounding box (?minx=&miny=&maxx=&maxy=)
    GET  /api/v1/sites/by_era/{era_id}/     - Sites from specific era
    GET  /api/v1/sites/by_county/{county_id}/ - Sites in specific county
    GET  /api/v1/sites/{id}/popup/          - Popup-optimized site data
    GET  /api/v1/sites/statistics/          - Aggregate statistics

Provinces:
    GET  /api/v1/provinces/                 - All province boundaries (GeoJSON)
    GET  /api/v1/provinces/{id}/            - Province detail
    GET  /api/v1/provinces/list_simple/     - Simple list (no geometry)

Counties:
    GET  /api/v1/counties/                  - All county boundaries (GeoJSON)
    GET  /api/v1/counties/{id}/             - County detail
    GET  /api/v1/counties/list_simple/      - Simple list (no geometry)
    GET  /api/v1/counties/by_province/{id}/ - Counties in province

Historical Eras:
    GET  /api/v1/eras/                      - All eras (chronological)
    GET  /api/v1/eras/{id}/                 - Era detail
    GET  /api/v1/eras/timeline/             - Eras with site counts

Site Images:
    GET  /api/v1/images/                    - All images
    GET  /api/v1/images/{id}/               - Image detail
    GET  /api/v1/images/by_site/{site_id}/  - Images for a site
"""
