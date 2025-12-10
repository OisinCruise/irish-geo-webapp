"""
API views for the Irish Historical Sites web app

This file handles all the API endpoints that the frontend map uses. The frontend
sends requests here and gets back GeoJSON data that Leaflet.js can display on the map.
I'm using Django REST Framework ViewSets because they make it easy to create REST APIs
and handle all the CRUD operations automatically.
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


# Custom pagination classes
# I had to create these because the default pagination was loading too much data
# and causing memory issues on Render's free tier. The map pagination is bigger
# because the map needs more sites at once, but I still had to limit it.

class StandardResultsPagination(PageNumberPagination):
    """Used for most list endpoints - keeps page sizes small to save memory"""
    page_size = 50  # Had to reduce this from the default because Render's free tier only has 512MB RAM
    page_size_query_param = 'page_size'
    max_page_size = 200  # Cap it at 200 so users can't request too much at once


class MapResultsPagination(PageNumberPagination):
    """Bigger pagination for the map view since it needs more sites visible at once"""
    # I learned the hard way that loading too many sites crashes the server
    # This is used by the map endpoints and needs to be bigger than standard
    # but still small enough to not run out of memory
    page_size = 100  # Started at 200 but had to reduce it after crashes
    page_size_query_param = 'page_size'
    max_page_size = 200  # Max limit to prevent someone from requesting everything at once


# Historical Site ViewSet - this is the main one the frontend uses
# The frontend map.js file calls these endpoints to get site data

class HistoricalSiteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Main API endpoint for historical sites
    
    This handles all the site-related API calls. The frontend map uses these
    to load sites, search by location, filter by era/county, etc. Everything
    returns GeoJSON because that's what Leaflet.js expects.
    
    Endpoints:
    - GET /api/v1/sites/ - Gets all approved sites (what the map loads initially)
    - GET /api/v1/sites/{id}/ - Gets full details for one site
    - GET /api/v1/sites/nearby/ - Finds sites near a point (used for location search)
    - GET /api/v1/sites/in_bbox/ - Gets sites in a bounding box (when user pans the map)
    - GET /api/v1/sites/by_era/{era_id}/ - Filters sites by historical era
    - GET /api/v1/sites/statistics/ - Gets counts and breakdowns for the dashboard
    """
    queryset = HistoricalSite.objects.filter(
        is_deleted=False,
        approval_status='approved'
    ).select_related('county', 'county__province', 'era').order_by('-significance_level', 'name_en')
    
    def get_queryset(self):
        """
        Optimizes the database query based on what endpoint is being called
        
        I spent a lot of time optimizing this because the app kept crashing from
        running out of memory. For list views (like when loading the map), I only
        fetch the fields we actually need and prefetch images in a smart way.
        The serializer uses get_county_name() and get_era_name() which need the
        related objects, so I use select_related to avoid N+1 queries.
        """
        from django.db.models import Prefetch
        
        queryset = super().get_queryset()
        
        # For list views, only get what we need to save memory
        # The detail view needs everything, but list views just need basic info for markers
        if self.action in ['list', 'in_bbox', 'by_era', 'by_county', 'nearby']:
            # Prefetch images but order them so primary comes first
            # The serializer will just grab the first one for the marker icon
            queryset = queryset.prefetch_related(
                Prefetch(
                    'images',
                    queryset=SiteImage.objects.filter(
                        is_deleted=False
                    ).order_by('-is_primary', 'display_order'),
                    to_attr='ordered_images'
                )
            )
            # Only fetch the fields we actually use - this cut memory usage way down
            # The serializer needs county and era names, so I include the foreign keys
            # and use select_related to join them in one query instead of many
            queryset = queryset.only(
                'id', 'name_en', 'name_ga', 'site_type', 'significance_level',
                'national_monument', 'description_en', 'description_ga', 'location',
                'county_id', 'era_id'  # Need these for the joins
            )
            # Make sure the joins are there for the serializer methods
            if not queryset.query.select_related:
                queryset = queryset.select_related('county', 'era')
        else:
            # Detail views need all the data, so fetch everything normally
            queryset = queryset.prefetch_related('images')
        
        return queryset

    serializer_class = HistoricalSiteDetailSerializer
    pagination_class = MapResultsPagination  # Bigger pages for map since it needs more sites visible
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # These filters let the frontend filter sites by various criteria
    # The frontend can pass query params like ?county=1 or ?site_type=castle
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
    ordering = ['-significance_level', 'name_en']  # Default sort - most important sites first
    
    def list(self, request, *args, **kwargs):
        """
        Main list endpoint - this is what gets called when the map first loads
        
        I had to add pagination here because loading all sites at once was crashing
        the server. Now it only loads 100 at a time. If something goes wrong, I
        return an empty FeatureCollection instead of crashing so the frontend doesn't
        break completely.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get the optimized queryset (only fetches what we need)
            queryset = self.get_queryset()
            
            # Apply any filters from query params (like ?county=1)
            queryset = self.filter_queryset(queryset)
            
            # Django needs an order_by for pagination to work properly
            # Without it you get warnings about inconsistent pagination
            if not queryset.query.order_by:
                queryset = queryset.order_by('-significance_level', 'name_en')
            
            # Paginate the results - this is what prevents memory issues
            page = self.paginate_queryset(queryset)
            if page is not None:
                # get_serializer() automatically picks HistoricalSiteListSerializer for list action
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # Fallback if pagination somehow isn't working - just limit to 100
            queryset = queryset[:100]
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            # Log the error so I can debug it later
            logger.error(f'Error in HistoricalSiteViewSet.list: {str(e)}', exc_info=True)
            # Return empty data instead of crashing - better than a 500 error
            # The frontend expects GeoJSON format, so I return that even when empty
            return Response({
                'type': 'FeatureCollection',
                'features': []
            }, status=status.HTTP_200_OK)

    def get_serializer_class(self):
        """
        Picks which serializer to use based on what endpoint was called
        
        List view uses a lightweight serializer, popup uses a medium one,
        and detail view uses the full serializer with all fields.
        """
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
        Finds sites near a point - used when user searches by location
        
        Takes lat/lon coordinates and finds all sites within a certain distance.
        The frontend uses this for the "find sites near me" feature. Returns
        sites sorted by distance so closest ones come first.
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
        Gets sites within a bounding box - used when user pans/zooms the map
        
        The frontend sends the map's viewport bounds (min/max lat/lon) and this
        returns all sites visible in that area. I had to add pagination here too
        because some areas have hundreds of sites and would crash otherwise.
        """
        serializer = BboxSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # Create a polygon from the bounding box coordinates
        bbox = Polygon.from_bbox((data['minx'], data['miny'], data['maxx'], data['maxy']))

        # Filter sites that are inside the bounding box
        sites = self.get_queryset().filter(location__within=bbox)
        
        # Paginate to avoid loading too many at once
        page = self.paginate_queryset(sites)
        if page is not None:
            result_serializer = HistoricalSiteListSerializer(page, many=True)
            return self.get_paginated_response(result_serializer.data)
        
        # Fallback if pagination isn't working
        sites = sites[:200]
        result_serializer = HistoricalSiteListSerializer(sites, many=True)
        return Response(result_serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific historical era'
    )
    @action(detail=False, methods=['get'], url_path='by_era/(?P<era_id>[^/.]+)')
    def by_era(self, request, era_id=None):
        """
        Filters sites by historical era - used by the timeline filter on the frontend
        """
        sites = self.get_queryset().filter(era_id=era_id)
        
        # Paginate to avoid memory issues
        page = self.paginate_queryset(sites)
        if page is not None:
            serializer = HistoricalSitePopupSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback
        sites = sites[:200]
        serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer(many=True)},
        description='Get sites from a specific county'
    )
    @action(detail=False, methods=['get'], url_path='by_county/(?P<county_id>[^/.]+)')
    def by_county(self, request, county_id=None):
        """
        Filters sites by county - used when user selects a county from the dropdown
        """
        sites = self.get_queryset().filter(county_id=county_id)
        
        # Paginate
        page = self.paginate_queryset(sites)
        if page is not None:
            serializer = HistoricalSitePopupSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback
        sites = sites[:200]
        serializer = HistoricalSitePopupSerializer(sites, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: HistoricalSitePopupSerializer},
        description='Get popup data for a specific site'
    )
    @action(detail=True, methods=['get'])
    def popup(self, request, pk=None):
        """
        Gets data for a map popup - lighter than full detail but has what the popup needs
        
        When user clicks a marker, the frontend calls this to get the popup content.
        It uses a medium-weight serializer that has descriptions and images but not
        all the extra metadata that the detail page needs.
        """
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
        Gets statistics for the dashboard - counts and breakdowns
        
        The frontend uses this to show things like "X castles, Y monasteries"
        and other stats on the dashboard page. It does a bunch of COUNT queries
        to aggregate the data.
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


# Province ViewSet - handles province boundary data
# The frontend uses this to draw province outlines on the map

class ProvinceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for province boundaries
    
    Returns the province shapes as GeoJSON so the map can draw them as overlays.
    I had to use raw SQL with PostGIS functions because loading all those polygons
    into Python was crashing the server. Now it generates the GeoJSON in the database
    and just sends it straight to the frontend.
    """
    serializer_class = ProvinceBoundarySerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    def list(self, request, *args, **kwargs):
        """
        List all provinces - uses raw SQL to generate GeoJSON in the database
        
        This was a big learning moment for me. I was trying to use Django ORM to
        serialize the province geometries, but they're huge MultiPolygon objects
        and loading them all into Python memory was crashing the server. Now I use
        PostGIS's ST_AsGeoJSON function to generate the GeoJSON right in the database,
        and it also simplifies the geometry to make it smaller. The ORDER BY has to
        be inside json_agg() or PostgreSQL complains about grouping.
        """
        import json
        import logging
        from django.db import connection
        
        logger = logging.getLogger(__name__)
        
        try:
            # Generate GeoJSON in PostGIS - never loads polygons into Python
            # ST_SimplifyPreserveTopology reduces the polygon complexity for smaller file size
            # ORDER BY goes inside json_agg() because of how PostgreSQL grouping works
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
                
                # Handle empty results
                if not result or result.get('features') is None:
                    return Response({
                        'type': 'FeatureCollection',
                        'features': []
                    })
                
                return Response(result)
        except Exception as e:
            logger.error(f'Error in ProvinceViewSet.list: {str(e)}', exc_info=True)
            # Return empty data instead of crashing - better than a 500 error
            return Response({
                'type': 'FeatureCollection',
                'features': []
            }, status=status.HTTP_200_OK)

    def get_queryset(self):
        """
        Used for detail views - list view uses raw SQL instead
        """
        return Province.objects.filter(is_deleted=False).order_by('name_en')

    @extend_schema(
        responses={200: ProvinceMinimalSerializer(many=True)},
        description='Get simple province list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """
        Gets just province names/IDs without the geometry - used for dropdowns
        
        The frontend uses this to populate the province filter dropdown. No need
        to send the huge polygon data for that.
        """
        provinces = self.get_queryset()
        serializer = ProvinceMinimalSerializer(provinces, many=True)
        return Response(serializer.data)


# County ViewSet - same idea as provinces but for counties
# Counties are smaller polygons but there are more of them, so same memory issues

class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for county boundaries
    
    Same approach as provinces - uses raw SQL with PostGIS to generate GeoJSON
    in the database. Counties are smaller but there are 32 of them, so still need
    to be careful about memory. The frontend uses this to draw county boundaries
    on the map when the user toggles that layer.
    """
    serializer_class = CountyBoundarySerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['province']
    search_fields = ['name_en', 'name_ga', 'code']

    def list(self, request, *args, **kwargs):
        """
        List counties - same raw SQL approach as provinces
        
        Can filter by province if the frontend passes ?province=X in the query params.
        Uses the same PostGIS functions to generate GeoJSON without loading polygons
        into Python memory.
        """
        import json
        import logging
        from django.db import connection
        
        logger = logging.getLogger(__name__)
        
        try:
            # Build WHERE clause - check if frontend wants to filter by province
            where_clauses = ["c.is_deleted = false"]
            params = []
            
            if 'province' in request.query_params:
                where_clauses.append("c.province_id = %s")
                params.append(request.query_params['province'])
            
            where_sql = " AND ".join(where_clauses)
            
            # Generate GeoJSON in PostGIS - same approach as provinces
            # 0.003 simplification tolerance (smaller than provinces since counties are smaller)
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
                
                # Handle empty results
                if not result or result.get('features') is None:
                    return Response({
                        'type': 'FeatureCollection',
                        'features': []
                    })
                
                return Response(result)
        except Exception as e:
            logger.error(f'Error in CountyViewSet.list: {str(e)}', exc_info=True)
            # Return empty data instead of crashing
            return Response({
                'type': 'FeatureCollection',
                'features': []
            }, status=status.HTTP_200_OK)

    def get_queryset(self):
        """
        Used for detail views - list view uses raw SQL instead
        """
        return County.objects.filter(is_deleted=False).select_related('province').order_by('name_en')

    @extend_schema(
        responses={200: CountyMinimalSerializer(many=True)},
        description='Get simple county list without geometry'
    )
    @action(detail=False, methods=['get'])
    def list_simple(self, request):
        """
        Gets county names/IDs without geometry - used for dropdowns and filters
        """
        counties = self.get_queryset()
        serializer = CountyMinimalSerializer(counties, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: CountyBoundarySerializer(many=True)},
        description='Get counties within a specific province'
    )
    @action(detail=False, methods=['get'], url_path='by_province/(?P<province_id>[^/.]+)')
    def by_province(self, request, province_id=None):
        """
        Gets all counties in a province - used when user selects a province filter
        """
        counties = self.get_queryset().filter(province_id=province_id)
        serializer = CountyBoundarySerializer(counties, many=True)
        return Response(serializer.data)


# Historical Era ViewSet - handles the timeline/era data
# There aren't many eras so no pagination needed

class HistoricalEraViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for historical eras
    
    Used by the timeline filter on the frontend. There are only like 10 eras
    so no need for pagination - just return them all. The timeline endpoint
    adds site counts to each era so the frontend can show how many sites
    are in each time period.
    """
    queryset = HistoricalEra.objects.filter(is_deleted=False).order_by('start_year')
    serializer_class = HistoricalEraSerializer
    pagination_class = None  # Only ~10 eras, no need to paginate
    filter_backends = [filters.SearchFilter]
    search_fields = ['name_en', 'name_ga']

    @extend_schema(
        responses={200: HistoricalEraSerializer(many=True)},
        description='Get eras formatted for timeline visualization'
    )
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """
        Gets eras with site counts - used by the timeline visualization

        The frontend uses this to show the timeline bar with counts for each era.
        It annotates each era with how many sites belong to it, then formats
        the data in a way that's easy for the frontend to render.
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


# Site Image ViewSet - handles image data
# Not used much by the frontend since images come with sites, but useful for admin

class SiteImageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for site images
    
    Mostly used for admin purposes. The frontend gets images through the site
    serializers, but this endpoint is useful if you need to query images directly
    or get all images for a specific site.
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
        """
        Gets all images for a site - ordered by display_order so primary comes first
        """
        images = self.get_queryset().filter(site_id=site_id).order_by('display_order')
        serializer = SiteImageSerializer(images, many=True)
        return Response(serializer.data)


# Bucket List ViewSet - handles the "My Journey" feature
# Uses sessions instead of authentication so users don't need to sign up

class BucketListViewSet(viewsets.ModelViewSet):
    """
    API for the bucket list / "My Journey" feature
    
    Lets users save sites they want to visit and mark them as visited. I'm using
    Django sessions to track users instead of requiring authentication - that way
    people can use it without creating an account. Each user gets a session key
    that identifies their bucket list items.
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
        """
        Gets the session key for the current user
        
        Creates one if it doesn't exist. This is how we identify which bucket list
        items belong to which user without requiring login.
        """
        if not request.session.session_key:
            request.session.create()
        return request.session.session_key

    def get_queryset(self):
        """
        Only returns bucket list items for the current user's session
        
        Uses select_related to avoid N+1 queries when loading site/county/era data.
        """
        session_key = self.get_session_key(self.request)
        return BucketListItem.objects.filter(
            session_key=session_key,
            is_deleted=False
        ).select_related('site', 'site__county', 'site__era')

    def get_serializer_context(self):
        """
        Passes the request to the serializer so it can build absolute URLs
        
        The serializer needs this to generate full URLs for uploaded photos
        instead of relative paths.
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_serializer_class(self):
        """
        Picks the right serializer based on what action is being performed
        
        Create uses a different serializer than update, and update needs to
        handle file uploads for photos.
        """
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
        """
        Adds a site to the user's bucket list
        
        Checks if the site is already in their list first to avoid duplicates.
        If they mark it as visited right away, sets the visited_at timestamp.
        """
        serializer = BucketListCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session_key = self.get_session_key(request)
        site_id = serializer.validated_data['site_id']
        item_status = serializer.validated_data.get('status', 'wishlist')

        # Don't let them add the same site twice
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

        # Make sure the site exists and is approved
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

        # Create the item
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
        Updates a bucket list item - handles photo uploads and status changes
        
        The frontend can upload a photo when marking a site as visited, and
        can also add a caption. If they change status to visited, automatically
        sets the visited_at timestamp if it wasn't already set.
        """
        item = self.get_object()
        
        # Handle photo upload if one was sent
        if 'photo' in request.FILES:
            item.photo = request.FILES['photo']
        
        # Update caption if provided
        if 'photo_caption' in request.data:
            item.photo_caption = request.data['photo_caption']
        
        # Handle status change
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
        """
        Removes an item from the bucket list - soft delete so we keep the data
        """
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
        Marks a site as visited - can include a photo and caption

        The frontend calls this when user clicks "Mark as visited" on a site.
        They can optionally upload a photo they took at the site.
        """
        item = self.get_object()

        # Mark as visited and set timestamp
        item.status = 'visited'
        item.visited_at = timezone.now()

        # Handle optional photo upload
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
        Gets statistics for the user's bucket list - used on the "My Journey" page
        
        Calculates things like how many sites they've visited, how many counties
        they've explored, breakdown by site type, etc. The frontend uses this to
        show progress and stats.
        """
        session_key = self.get_session_key(request)
        items = BucketListItem.objects.filter(
            session_key=session_key,
            is_deleted=False
        ).select_related('site', 'site__county')

        # Count totals
        total = items.count()
        wishlist = items.filter(status='wishlist').count()
        visited = items.filter(status='visited').count()

        # Count unique counties they've visited sites in
        visited_counties = items.filter(status='visited').values(
            'site__county__name_en'
        ).distinct().count()

        # Breakdown by county
        by_county = list(
            items.values('site__county__name_en')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Breakdown by site type
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
        """
        Toggles a site between wishlist and visited
        
        If it's wishlist, marks it visited and sets timestamp. If it's visited,
        changes it back to wishlist and clears the timestamp.
        """
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
