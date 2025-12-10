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
        
        # CRITICAL: Apply optimizations to ALL list-like actions, not just 'list'
        # This includes: list, in_bbox, by_era, by_county, nearby
        # Only detail views (retrieve, popup) need full data
        if self.action in ['list', 'in_bbox', 'by_era', 'by_county', 'nearby']:
            # Prefetch images ordered by primary first - serializer will use first item
            # This reduces memory vs loading all images, and ensures primary is first
            # Prefetch images ordered by primary first
            # Note: We can't slice in Prefetch, but serializer only uses first image
            queryset = queryset.prefetch_related(
                Prefetch(
                    'images',
                    queryset=SiteImage.objects.filter(
                        is_deleted=False
                    ).order_by('-is_primary', 'display_order'),
                    to_attr='ordered_images'
                )
            )
            # CRITICAL: Use only() to limit fields fetched - reduces memory usage
            # This is essential for Render Free tier (512MB RAM) with 100+ sites
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
        Optimized list view for fast loading of sites
        Uses optimized queryset with field limiting and efficient image prefetching
        """
        return super().list(request, *args, **kwargs)

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

        # CRITICAL: Use optimized queryset and limit results
        # The [:data['limit']] slice is applied, but we should still use optimized queryset
        sites = self.get_queryset().filter(
            location__distance_lte=(point, D(km=data['distance']))
        ).annotate(
            distance=Distance('location', point)
        ).order_by('distance')[:min(data['limit'], 100)]  # Cap at 100 to prevent OOM

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

        # CRITICAL: Apply pagination to prevent loading all sites into memory
        # Use the optimized queryset (get_queryset applies optimizations for 'in_bbox' action)
        sites = self.get_queryset().filter(location__within=bbox)
        
        # Apply pagination
        page = self.paginate_queryset(sites)
        if page is not None:
            result_serializer = HistoricalSiteListSerializer(page, many=True)
            return self.get_paginated_response(result_serializer.data)
        
        # Fallback: limit to 200 if pagination not available (shouldn't happen)
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
    Geometries are simplified for efficient transfer (~90% size reduction).

    ## Endpoints
    - `GET /api/v1/provinces/` - All province boundaries (simplified GeoJSON)
    - `GET /api/v1/provinces/{id}/` - Single province detail
    - `GET /api/v1/provinces/list/` - Simple list (no geometry)
    """
    serializer_class = ProvinceBoundarySerializer
    # CRITICAL: Enable pagination for provinces to prevent loading all geometries at once
    # Even with simplification, 4 provinces with MultiPolygon geometry can be large
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    def get_queryset(self):
        """
        Return provinces with simplified geometries.
        Uses ST_SimplifyPreserveTopology to reduce coordinate count while maintaining shape.
        Tolerance of 0.005 degrees (~500m) works well for display purposes.
        """
        from django.contrib.gis.db.models.functions import GeoFunc
        from django.db.models import Value
        from django.db.models.functions import Cast
        from django.contrib.gis.db.models import MultiPolygonField

        # Use raw SQL annotation for geometry simplification (PostGIS)
        # This reduces 13MB of province geometries to ~1-2MB
        # Also annotate county_count and site_count to avoid N+1 queries
        # Table name qualified to avoid ambiguous column reference when joins are present
        return Province.objects.filter(is_deleted=False).extra(
            select={'geometry': 'ST_SimplifyPreserveTopology(province.geometry, 0.005)'}
        ).annotate(
            annotated_county_count=Count(
                'counties',
                filter=Q(counties__is_deleted=False),
                distinct=True
            )
        )

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
    Geometries are simplified for efficient transfer (~90% size reduction).

    ## Endpoints
    - `GET /api/v1/counties/` - All county boundaries (simplified GeoJSON)
    - `GET /api/v1/counties/{id}/` - Single county detail
    - `GET /api/v1/counties/list/` - Simple list (no geometry)
    - `GET /api/v1/counties/by_province/{province_id}/` - Counties in province
    """
    serializer_class = CountyBoundarySerializer
    # CRITICAL: Enable pagination for counties to prevent loading all geometries at once
    # Even with simplification, 26 counties with MultiPolygon geometry can be large
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['province']
    search_fields = ['name_en', 'name_ga', 'code']

    def get_queryset(self):
        """
        Return counties with simplified geometries and pre-calculated site counts.
        Uses ST_SimplifyPreserveTopology to reduce coordinate count while maintaining shape.
        Tolerance of 0.003 degrees (~300m) provides good detail for counties.
        Annotates site_count to avoid N+1 queries.
        """
        # Use raw SQL annotation for geometry simplification (PostGIS)
        # This reduces 28MB of county geometries to ~2-3MB
        # Table name qualified to avoid ambiguous column reference when province is joined via select_related
        return County.objects.filter(is_deleted=False).select_related('province').extra(
            select={'geometry': 'ST_SimplifyPreserveTopology(county.geometry, 0.003)'}
        ).annotate(
            annotated_site_count=Count(
                'historical_sites',
                filter=Q(
                    historical_sites__is_deleted=False,
                    historical_sites__approval_status='approved'
                )
            )
        )

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

        result_serializer = BucketListItemSerializer(item)
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
        
        serializer = BucketListItemSerializer(item)
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
