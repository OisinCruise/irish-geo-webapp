"""
API ViewSets for Irish Historical Sites GIS
============================================
RESTful API endpoints with spatial query capabilities.
Supports GeoJSON output for Leaflet.js frontend integration.
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from apps.sites.models import HistoricalSite, SiteImage, SiteSource
from apps.geography.models import Province, County, HistoricalEra
from .serializers import (
    # Site serializers
    HistoricalSiteListSerializer,
    HistoricalSiteDetailSerializer,
    HistoricalSitePopupSerializer,
    SiteImageSerializer,
    SiteSourceSerializer,
    # Geography serializers
    ProvinceBoundarySerializer,
    ProvinceMinimalSerializer,
    CountyBoundarySerializer,
    CountyMinimalSerializer,
    # Era serializers
    HistoricalEraSerializer,
    HistoricalEraMinimalSerializer,
    # Query serializers
    NearbySearchSerializer,
    BboxSearchSerializer,
    SiteStatisticsSerializer,
)


# ==============================================================================
# CUSTOM PAGINATION
# ==============================================================================

class StandardResultsPagination(PageNumberPagination):
    """Standard pagination for list endpoints"""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class MapResultsPagination(PageNumberPagination):
    """Larger pagination for map data loading"""
    page_size = 500
    page_size_query_param = 'page_size'
    max_page_size = 2000


# ==============================================================================
# HISTORICAL SITE VIEWSET
# ==============================================================================

class HistoricalSiteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Irish Historical Sites

    Provides GeoJSON-formatted data for map display with spatial query support.
    All endpoints return RFC 7946 compliant GeoJSON FeatureCollections.

    ## Endpoints
    - `GET /api/v1/sites/` - List all approved sites (GeoJSON)
    - `GET /api/v1/sites/{id}/` - Site detail with full information
    - `GET /api/v1/sites/nearby/` - Find sites near coordinates
    - `GET /api/v1/sites/in_bbox/` - Sites within bounding box (viewport)
    - `GET /api/v1/sites/by_era/{era_id}/` - Sites from specific era
    - `GET /api/v1/sites/statistics/` - Aggregate statistics
    """
    queryset = HistoricalSite.objects.filter(
        is_deleted=False,
        approval_status='approved'
    ).select_related('county', 'county__province', 'era').prefetch_related('images')

    serializer_class = HistoricalSiteDetailSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'county': ['exact'],
        'county__province': ['exact'],
        'era': ['exact'],
        'site_type': ['exact', 'in'],
        'significance_level': ['exact', 'gte', 'lte'],
        'national_monument': ['exact'],
        'unesco_site': ['exact'],
        'is_public_access': ['exact'],
    }
    search_fields = ['name_en', 'name_ga', 'description_en', 'description_ga']
    ordering_fields = ['name_en', 'significance_level', 'created_at', 'date_established']
    ordering = ['-significance_level', 'name_en']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return HistoricalSiteListSerializer
        if self.action == 'popup':
            return HistoricalSitePopupSerializer
        return HistoricalSiteDetailSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name='lat', type=float, description='Latitude (51-56)'),
            OpenApiParameter(name='lon', type=float, description='Longitude (-11 to -5)'),
            OpenApiParameter(name='distance', type=float, description='Radius in km (default: 10)'),
            OpenApiParameter(name='limit', type=int, description='Max results (default: 50)'),
        ],
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Find historical sites near a geographic point'
    )
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """
        Find sites near a geographic point

        Query Parameters:
            lat (float): Latitude in WGS84 (required)
            lon (float): Longitude in WGS84 (required)
            distance (float): Search radius in kilometers (default: 10)
            limit (int): Maximum results to return (default: 50)

        Returns:
            GeoJSON FeatureCollection with distance annotations
        """
        serializer = NearbySearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        point = Point(data['lon'], data['lat'], srid=4326)

        sites = self.get_queryset().filter(
            location__distance_lte=(point, D(km=data['distance']))
        ).annotate(
            distance=Distance('location', point)
        ).order_by('distance')[:data['limit']]

        result_serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(result_serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='minx', type=float, description='Min longitude (west)'),
            OpenApiParameter(name='miny', type=float, description='Min latitude (south)'),
            OpenApiParameter(name='maxx', type=float, description='Max longitude (east)'),
            OpenApiParameter(name='maxy', type=float, description='Max latitude (north)'),
        ],
        responses={200: HistoricalSiteListSerializer(many=True)},
        description='Get sites within a bounding box (for map viewport)'
    )
    @action(detail=False, methods=['get'])
    def in_bbox(self, request):
        """
        Get sites within a bounding box (viewport query)

        Query Parameters:
            minx (float): Minimum longitude (west boundary)
            miny (float): Minimum latitude (south boundary)
            maxx (float): Maximum longitude (east boundary)
            maxy (float): Maximum latitude (north boundary)

        Returns:
            GeoJSON FeatureCollection of sites in viewport
        """
        serializer = BboxSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        bbox = Polygon.from_bbox((data['minx'], data['miny'], data['maxx'], data['maxy']))

        sites = self.get_queryset().filter(location__within=bbox)
        result_serializer = HistoricalSiteListSerializer(sites, many=True)
        return Response(result_serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific historical era'
    )
    @action(detail=False, methods=['get'], url_path='by_era/(?P<era_id>[^/.]+)')
    def by_era(self, request, era_id=None):
        """Get sites from a specific historical era"""
        sites = self.get_queryset().filter(era_id=era_id)
        serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific county'
    )
    @action(detail=False, methods=['get'], url_path='by_county/(?P<county_id>[^/.]+)')
    def by_county(self, request, county_id=None):
        """Get sites from a specific county"""
        sites = self.get_queryset().filter(county_id=county_id)
        serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer},
        description='Get popup data for a specific site'
    )
    @action(detail=True, methods=['get'])
    def popup(self, request, pk=None):
        """Get popup-optimized data for a single site"""
        site = self.get_object()
        serializer = HistoricalSitePopupSerializer(site)
        return Response(serializer.data)

    @extend_schema(
        responses={200: SiteStatisticsSerializer},
        description='Get aggregate statistics for historical sites'
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get aggregate statistics for historical sites

        Returns:
            - Total site count
            - National monuments count
            - UNESCO sites count
            - Breakdown by site type
            - Breakdown by era
            - Breakdown by county
            - Breakdown by significance level
        """
        queryset = self.get_queryset()

        stats = {
            'total_sites': queryset.count(),
            'national_monuments': queryset.filter(national_monument=True).count(),
            'unesco_sites': queryset.filter(unesco_site=True).count(),
            'by_site_type': dict(
                queryset.values('site_type')
                .annotate(count=Count('id'))
                .values_list('site_type', 'count')
            ),
            'by_era': list(
                queryset.values('era__name_en', 'era__color_hex')
                .annotate(count=Count('id'))
                .order_by('era__start_year')
            ),
            'by_county': list(
                queryset.values('county__name_en')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            ),
            'by_significance': dict(
                queryset.values('significance_level')
                .annotate(count=Count('id'))
                .values_list('significance_level', 'count')
            ),
        }

        return Response(stats)


# ==============================================================================
# PROVINCE VIEWSET
# ==============================================================================

class ProvinceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Irish Province boundaries

    Returns GeoJSON MultiPolygon features for province overlays.

    ## Endpoints
    - `GET /api/v1/provinces/` - All province boundaries (GeoJSON)
    - `GET /api/v1/provinces/{id}/` - Single province detail
    - `GET /api/v1/provinces/list/` - Simple list (no geometry)
    """
    queryset = Province.objects.filter(is_deleted=False)
    serializer_class = ProvinceBoundarySerializer
    pagination_class = None  # Return all provinces at once
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    @extend_schema(
        responses={200: ProvinceMinimalSerializer(many=True)},
        description='Get simple province list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """Get province list without geometry (for dropdowns)"""
        provinces = self.get_queryset()
        serializer = ProvinceMinimalSerializer(provinces, many=True)
        return Response(serializer.data)


# ==============================================================================
# COUNTY VIEWSET
# ==============================================================================

class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Irish County boundaries

    Returns GeoJSON MultiPolygon features for county overlays.

    ## Endpoints
    - `GET /api/v1/counties/` - All county boundaries (GeoJSON)
    - `GET /api/v1/counties/{id}/` - Single county detail
    - `GET /api/v1/counties/list/` - Simple list (no geometry)
    - `GET /api/v1/counties/by_province/{province_id}/` - Counties in province
    """
    queryset = County.objects.filter(is_deleted=False).select_related('province')
    serializer_class = CountyBoundarySerializer
    pagination_class = None  # Return all counties at once
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['province']
    search_fields = ['name_en', 'name_ga', 'code']

    @extend_schema(
        responses={200: CountyMinimalSerializer(many=True)},
        description='Get simple county list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """Get county list without geometry (for dropdowns/filters)"""
        counties = self.get_queryset()
        serializer = CountyMinimalSerializer(counties, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: CountyBoundarySerializer(many=True)},
        description='Get counties within a specific province'
    )
    @action(detail=False, methods=['get'], url_path='by_province/(?P<province_id>[^/.]+)')
    def by_province(self, request, province_id=None):
        """Get counties in a specific province"""
        counties = self.get_queryset().filter(province_id=province_id)
        serializer = CountyBoundarySerializer(counties, many=True)
        return Response(serializer.data)


# ==============================================================================
# HISTORICAL ERA VIEWSET
# ==============================================================================

class HistoricalEraViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Historical Eras

    Used for timeline filtering and era-based map layers.

    ## Endpoints
    - `GET /api/v1/eras/` - All historical eras (chronological)
    - `GET /api/v1/eras/{id}/` - Single era detail
    - `GET /api/v1/eras/timeline/` - Eras formatted for timeline display
    """
    queryset = HistoricalEra.objects.filter(is_deleted=False).order_by('start_year')
    serializer_class = HistoricalEraSerializer
    pagination_class = None  # Return all eras at once
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    @extend_schema(
        responses={200: HistoricalEraSerializer(many=True)},
        description='Get eras formatted for timeline visualization'
    )
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """
        Get eras formatted for timeline visualization

        Returns eras with site counts for timeline display
        """
        eras = self.get_queryset().annotate(
            site_count=Count(
                'historical_sites',
                filter=Q(
                    historical_sites__is_deleted=False,
                    historical_sites__approval_status='approved'
                )
            )
        )

        timeline_data = []
        for era in eras:
            timeline_data.append({
                'id': era.id,
                'name_en': era.name_en,
                'name_ga': era.name_ga,
                'start_year': era.start_year,
                'end_year': era.end_year,
                'color_hex': era.color_hex,
                'site_count': era.site_count,
                'duration_years': era.duration_years,
            })

        return Response(timeline_data)


# ==============================================================================
# SITE IMAGE VIEWSET
# ==============================================================================

class SiteImageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Site Images

    ## Endpoints
    - `GET /api/v1/images/` - All site images
    - `GET /api/v1/images/{id}/` - Single image detail
    - `GET /api/v1/images/by_site/{site_id}/` - Images for a site
    """
    queryset = SiteImage.objects.filter(is_deleted=False).select_related('site')
    serializer_class = SiteImageSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['site', 'is_primary']

    @extend_schema(
        responses={200: SiteImageSerializer(many=True)},
        description='Get all images for a specific site'
    )
    @action(detail=False, methods=['get'], url_path='by_site/(?P<site_id>[^/.]+)')
    def by_site(self, request, site_id=None):
        """Get all images for a specific site"""
        images = self.get_queryset().filter(site_id=site_id).order_by('display_order')
        serializer = SiteImageSerializer(images, many=True)
        return Response(serializer.data)
