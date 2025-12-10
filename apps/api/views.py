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
from django.contrib.gis.db.models.functions import Transform
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.db import connection
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.utils import timezone
from apps.sites.models import HistoricalSite, SiteImage, SiteSource, BucketListItem
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
    # Bucket list serializers
    HistoricalSiteMinimalSerializer,
    BucketListItemSerializer,
    BucketListCreateSerializer,
    BucketListUpdateSerializer,
    BucketListStatisticsSerializer,
)


# ==============================================================================
# CUSTOM PAGINATION
# ==============================================================================

class StandardResultsPagination(PageNumberPagination):
    """Standard pagination for list endpoints"""
    page_size = 50  # Reduced for B1 Basic tier memory constraints
    page_size_query_param = 'page_size'
    max_page_size = 200  # Reduced from 500 to prevent OOM


class MapResultsPagination(PageNumberPagination):
    """Larger pagination for map data loading"""
    # CRITICAL: Reduced for Render Free tier (512MB RAM)
    # Loading too many sites causes OOM errors
    page_size = 100  # Reduced from 200 for Render Free tier
    page_size_query_param = 'page_size'
    max_page_size = 200  # Reduced from 500 to prevent OOM on 512MB limit


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
    ).select_related('county', 'county__province', 'era')
    
    def get_queryset(self):
        """
        Highly optimized queryset for fast loading of 100+ sites
        - Uses Prefetch with filtered/ordered queryset for images
        - Uses only() to limit fields fetched for list views (reduces data transfer)
        - Optimized for Neon database performance
        """
        from django.db.models import Prefetch
        
        queryset = super().get_queryset()
        
        # CRITICAL: Apply optimizations to ALL list-like actions to prevent memory leaks
        # This includes: list, in_bbox, by_era, by_county, nearby
        # Only detail views (retrieve, popup) need full data
        if self.action in ['list', 'in_bbox', 'by_era', 'by_county', 'nearby']:
            # CRITICAL: Prefetch only ordered images (serializer will use first)
            # Note: Can't slice in Prefetch, but serializer only accesses first image
            queryset = queryset.prefetch_related(
                Prefetch(
                    'images',
                    queryset=SiteImage.objects.filter(
                        is_deleted=False
                    ).order_by('-is_primary', 'display_order'),
                    to_attr='ordered_images'
                )
            )
            # CRITICAL: Use only() to limit fields fetched - reduces memory usage by ~70%
            # This is essential for preventing OOM errors with large datasets
            # Only fetch fields needed for map markers (serializer will handle truncation)
            queryset = queryset.only(
                'id', 'name_en', 'name_ga', 'site_type', 'significance_level',
                'national_monument', 'description_en', 'description_ga', 'location',
                'county_id', 'era_id'  # Foreign keys for select_related
            )
        else:
            # For detail views, prefetch all images normally
            queryset = queryset.prefetch_related('images')
        
        return queryset

    serializer_class = HistoricalSiteDetailSerializer
    pagination_class = MapResultsPagination  # Use MapResultsPagination for map loading (larger page sizes)
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
    ordering = ['-significance_level', 'name_en']  # Uses idx_site_significance index
    
    def list(self, request, *args, **kwargs):
        """
        CRITICAL: Memory-efficient list view using pagination.
        Prevents loading all sites into memory at once, which causes OOM errors.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination - this is critical for memory efficiency
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # Fallback: limit results if pagination not available
            # This should rarely happen as pagination is enabled by default
            queryset = queryset[:100]
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            # Log error and return safe response to prevent 502
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error in HistoricalSiteViewSet.list: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to load sites', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

        # CRITICAL: Apply pagination to prevent loading all sites in bbox into memory
        sites = self.get_queryset().filter(location__within=bbox)
        
        # Apply pagination
        page = self.paginate_queryset(sites)
        if page is not None:
            result_serializer = HistoricalSiteListSerializer(page, many=True)
            return self.get_paginated_response(result_serializer.data)
        
        # Fallback: limit to 200 if pagination not available
        sites = sites[:200]
        result_serializer = HistoricalSiteListSerializer(sites, many=True)
        return Response(result_serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific historical era'
    )
    @action(detail=False, methods=['get'], url_path='by_era/(?P<era_id>[^/.]+)')
    def by_era(self, request, era_id=None):
        """Get sites from a specific historical era"""
        # CRITICAL: Apply pagination to prevent loading all sites into memory
        sites = self.get_queryset().filter(era_id=era_id)
        
        # Apply pagination
        page = self.paginate_queryset(sites)
        if page is not None:
            serializer = HistoricalSitePopupSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback: limit to 200 if pagination not available
        sites = sites[:200]
        serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific county'
    )
    @action(detail=False, methods=['get'], url_path='by_county/(?P<county_id>[^/.]+)')
    def by_county(self, request, county_id=None):
        """Get sites from a specific county"""
        # CRITICAL: Apply pagination to prevent loading all sites into memory
        sites = self.get_queryset().filter(county_id=county_id)
        
        # Apply pagination
        page = self.paginate_queryset(sites)
        if page is not None:
            serializer = HistoricalSitePopupSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback: limit to 200 if pagination not available
        sites = sites[:200]
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
    Uses PostGIS ST_AsGeoJSON to generate GeoJSON directly in database (memory-efficient).

    ## Endpoints
    - `GET /api/v1/provinces/` - All province boundaries (simplified GeoJSON)
    - `GET /api/v1/provinces/{id}/` - Single province detail
    - `GET /api/v1/provinces/list/` - Simple list (no geometry)
    """
    serializer_class = ProvinceBoundarySerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    def list(self, request, *args, **kwargs):
        """
        CRITICAL: Memory-efficient GeoJSON generation using PostGIS ST_AsGeoJSON.
        This avoids loading geometries into Python memory, preventing OOM errors.
        Generates GeoJSON directly in the database and streams the response.
        """
        import json
        import logging
        from django.db import connection
        
        logger = logging.getLogger(__name__)
        
        try:
            # CRITICAL: Generate GeoJSON directly in PostGIS to avoid loading geometries into memory
            # This prevents OOM errors by never loading MultiPolygon objects into Python
            # Note: ORDER BY must be inside json_agg() when using aggregate functions
            sql = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(
                            ST_Multi(ST_SimplifyPreserveTopology(p.geometry, 0.005))
                        )::json,
                        'properties', json_build_object(
                            'id', p.id,
                            'name_en', p.name_en,
                            'name_ga', p.name_ga,
                            'code', p.code,
                            'area_km2', p.area_km2,
                            'population', p.population,
                            'description_en', LEFT(p.description_en, 500),
                            'description_ga', LEFT(p.description_ga, 500),
                            'county_count', (
                                SELECT COUNT(DISTINCT c.id)
                                FROM county c
                                WHERE c.province_id = p.id
                                AND c.is_deleted = false
                            ),
                            'site_count', (
                                SELECT COUNT(*)
                                FROM historical_site hs
                                JOIN county c ON hs.county_id = c.id
                                WHERE c.province_id = p.id
                                AND hs.is_deleted = false
                                AND hs.approval_status = 'approved'
                            )
                        )
                    ) ORDER BY p.name_en
                )
            )
            FROM province p
            WHERE p.is_deleted = false
            """
            
            with connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()[0]
                
                # If no results, return empty FeatureCollection
                if not result or result.get('features') is None:
                    return Response({
                        'type': 'FeatureCollection',
                        'features': []
                    })
                
                return Response(result)
        except Exception as e:
            logger.error(f'Error in ProvinceViewSet.list: {str(e)}', exc_info=True)
            # Return empty FeatureCollection on error to prevent 502
            return Response({
                'type': 'FeatureCollection',
                'features': []
            }, status=status.HTTP_200_OK)  # Return 200 with empty data rather than 500

    def get_queryset(self):
        """
        Return provinces for detail views (single province).
        List view uses raw SQL for memory efficiency.
        """
        return Province.objects.filter(is_deleted=False).order_by('name_en')

    @extend_schema(
        responses={200: ProvinceMinimalSerializer(many=True)},
        description='Get simple province list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """Get province list without geometry (for dropdowns)"""
        # Use iterator() for memory efficiency - no geometry fields, so safe
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
    Uses PostGIS ST_AsGeoJSON to generate GeoJSON directly in database (memory-efficient).

    ## Endpoints
    - `GET /api/v1/counties/` - All county boundaries (simplified GeoJSON)
    - `GET /api/v1/counties/{id}/` - Single county detail
    - `GET /api/v1/counties/list/` - Simple list (no geometry)
    - `GET /api/v1/counties/by_province/{province_id}/` - Counties in province
    """
    serializer_class = CountyBoundarySerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['province']
    search_fields = ['name_en', 'name_ga', 'code']

    def list(self, request, *args, **kwargs):
        """
        CRITICAL: Memory-efficient GeoJSON generation using PostGIS ST_AsGeoJSON.
        This avoids loading geometries into Python memory, preventing OOM errors.
        Generates GeoJSON directly in the database and streams the response.
        """
        import json
        import logging
        from django.db import connection
        
        logger = logging.getLogger(__name__)
        
        try:
            # Build WHERE clause based on filters
            where_clauses = ["c.is_deleted = false"]
            params = []
            
            if 'province' in request.query_params:
                where_clauses.append("c.province_id = %s")
                params.append(request.query_params['province'])
            
            where_sql = " AND ".join(where_clauses)
            
            # CRITICAL: Generate GeoJSON directly in PostGIS to avoid loading geometries into memory
            # This prevents OOM errors by never loading MultiPolygon objects into Python
            # Note: ORDER BY must be inside json_agg() when using aggregate functions
            sql = f"""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(
                            ST_Multi(ST_SimplifyPreserveTopology(c.geometry, 0.003))
                        )::json,
                        'properties', json_build_object(
                            'id', c.id,
                            'name_en', c.name_en,
                            'name_ga', c.name_ga,
                            'code', c.code,
                            'province', c.province_id,
                            'province_name', p.name_en,
                            'province_code', p.code,
                            'area_km2', c.area_km2,
                            'population', c.population,
                            'description_en', LEFT(c.description_en, 500),
                            'description_ga', LEFT(c.description_ga, 500),
                            'site_count', (
                                SELECT COUNT(*) 
                                FROM historical_site hs 
                                WHERE hs.county_id = c.id 
                                AND hs.is_deleted = false 
                                AND hs.approval_status = 'approved'
                            )
                        )
                    ) ORDER BY c.name_en
                )
            )
            FROM county c
            LEFT JOIN province p ON c.province_id = p.id
            WHERE {where_sql}
            """
            
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()[0]
                
                # If no results, return empty FeatureCollection
                if not result or result.get('features') is None:
                    return Response({
                        'type': 'FeatureCollection',
                        'features': []
                    })
                
                return Response(result)
        except Exception as e:
            logger.error(f'Error in CountyViewSet.list: {str(e)}', exc_info=True)
            # Return empty FeatureCollection on error to prevent 502
            return Response({
                'type': 'FeatureCollection',
                'features': []
            }, status=status.HTTP_200_OK)  # Return 200 with empty data rather than 500

    def get_queryset(self):
        """
        Return counties for detail views (single county).
        List view uses raw SQL for memory efficiency.
        """
        return County.objects.filter(is_deleted=False).select_related('province').order_by('name_en')

    @extend_schema(
        responses={200: CountyMinimalSerializer(many=True)},
        description='Get simple county list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """Get county list without geometry (for dropdowns/filters)"""
        # Use iterator() for memory efficiency - no geometry fields, so safe
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


# ==============================================================================
# BUCKET LIST VIEWSET
# ==============================================================================

class BucketListViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Bucket List functionality

    Allows users to track sites they want to visit or have visited.
    Uses session keys for user identification (no authentication required).

    ## Endpoints
    - `GET /api/v1/bucket-list/` - List all bucket list items for current session
    - `POST /api/v1/bucket-list/` - Add new site to bucket list
    - `GET /api/v1/bucket-list/{id}/` - Get specific bucket list item
    - `PATCH /api/v1/bucket-list/{id}/` - Update bucket list item
    - `DELETE /api/v1/bucket-list/{id}/` - Remove from bucket list (soft delete)
    - `POST /api/v1/bucket-list/{id}/mark_visited/` - Mark site as visited
    - `GET /api/v1/bucket-list/statistics/` - Get bucket list statistics
    """
    from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
    from rest_framework.permissions import AllowAny
    
    serializer_class = BucketListItemSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['added_at', 'visited_at', 'status']
    ordering = ['-added_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [AllowAny]

    def get_session_key(self, request):
        """Get or create session key for user tracking"""
        if not request.session.session_key:
            request.session.create()
        return request.session.session_key

    def get_queryset(self):
        """Filter queryset by session key"""
        session_key = self.get_session_key(self.request)
        return BucketListItem.objects.filter(
            session_key=session_key,
            is_deleted=False
        ).select_related('site', 'site__county', 'site__era')

    def get_serializer_context(self):
        """Add request to serializer context for absolute URL generation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return BucketListCreateSerializer
        if self.action in ['update', 'partial_update', 'mark_visited']:
            return BucketListUpdateSerializer
        return BucketListItemSerializer

    @extend_schema(
        request=BucketListCreateSerializer,
        responses={201: BucketListItemSerializer},
        description='Add a new site to bucket list'
    )
    def create(self, request, *args, **kwargs):
        """Add a new site to bucket list"""
        serializer = BucketListCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session_key = self.get_session_key(request)
        site_id = serializer.validated_data['site_id']
        item_status = serializer.validated_data.get('status', 'wishlist')

        # Check if site already in bucket list
        existing = BucketListItem.objects.filter(
            session_key=session_key,
            site_id=site_id,
            is_deleted=False
        ).first()

        if existing:
            return Response(
                {'error': 'Site already in bucket list', 'item_id': existing.id},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the site
        try:
            site = HistoricalSite.objects.get(
                id=site_id,
                is_deleted=False,
                approval_status='approved'
            )
        except HistoricalSite.DoesNotExist:
            return Response(
                {'error': 'Site not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create the bucket list item
        item = BucketListItem.objects.create(
            session_key=session_key,
            site=site,
            status=item_status,
            visited_at=timezone.now() if item_status == 'visited' else None
        )

        result_serializer = BucketListItemSerializer(item, context={'request': request})
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=BucketListUpdateSerializer,
        responses={200: BucketListItemSerializer},
        description='Update bucket list item (photo upload, caption, status)'
    )
    def partial_update(self, request, *args, **kwargs):
        """
        Update a bucket list item
        
        Handles photo uploads and caption updates.
        """
        item = self.get_object()
        
        # Handle photo upload
        if 'photo' in request.FILES:
            item.photo = request.FILES['photo']
        
        # Handle caption update
        if 'photo_caption' in request.data:
            item.photo_caption = request.data['photo_caption']
        
        # Handle status update
        if 'status' in request.data:
            item.status = request.data['status']
            if request.data['status'] == 'visited' and not item.visited_at:
                item.visited_at = timezone.now()
        
        item.save()
        
        serializer = BucketListItemSerializer(item, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        responses={204: None},
        description='Remove item from bucket list (soft delete)'
    )
    def destroy(self, request, *args, **kwargs):
        """Soft delete bucket list item"""
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=BucketListUpdateSerializer,
        responses={200: BucketListItemSerializer},
        description='Mark a site as visited with optional photo upload'
    )
    @action(detail=True, methods=['post'])
    def mark_visited(self, request, pk=None):
        """
        Mark a site as visited

        Can include optional photo and caption.
        Automatically sets visited_at timestamp.
        """
        item = self.get_object()

        # Update status and timestamp
        item.status = 'visited'
        item.visited_at = timezone.now()

        # Optional photo and caption
        if 'photo' in request.FILES:
            item.photo = request.FILES['photo']
        if 'photo_caption' in request.data:
            item.photo_caption = request.data['photo_caption']

        item.save()

        serializer = BucketListItemSerializer(item)
        return Response(serializer.data)

    @extend_schema(
        responses={200: BucketListStatisticsSerializer},
        description='Get bucket list statistics (counts by status, county, site type)'
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get bucket list statistics

        Returns:
            - Total count
            - Count by status (wishlist, visited)
            - Counties explored
            - Count by county
            - Count by site type
        """
        session_key = self.get_session_key(request)
        items = BucketListItem.objects.filter(
            session_key=session_key,
            is_deleted=False
        ).select_related('site', 'site__county')

        # Calculate statistics
        total = items.count()
        wishlist = items.filter(status='wishlist').count()
        visited = items.filter(status='visited').count()

        # Counties explored (unique counties from visited items)
        visited_counties = items.filter(status='visited').values(
            'site__county__name_en'
        ).distinct().count()

        # By county breakdown
        by_county = list(
            items.values('site__county__name_en')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # By site type breakdown
        by_site_type = dict(
            items.values('site__site_type')
            .annotate(count=Count('id'))
            .values_list('site__site_type', 'count')
        )

        stats = {
            'total': total,
            'wishlist': wishlist,
            'visited': visited,
            'counties_explored': visited_counties,
            'by_county': by_county,
            'by_site_type': by_site_type
        }

        return Response(stats)

    @extend_schema(
        responses={200: BucketListItemSerializer},
        description='Toggle item between wishlist and visited status'
    )
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle between wishlist and visited status"""
        item = self.get_object()

        if item.status == 'wishlist':
            item.status = 'visited'
            item.visited_at = timezone.now()
        else:
            item.status = 'wishlist'
            item.visited_at = None

        item.save()
        serializer = BucketListItemSerializer(item)
        return Response(serializer.data)
