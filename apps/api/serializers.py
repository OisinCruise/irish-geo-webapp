"""
Serializers for the API - converts database models to JSON for the frontend

These serializers take Django model objects and turn them into JSON that the
frontend can use. They also handle GeoJSON format which is what Leaflet.js
expects for map data. I have different serializers for different use cases -
lightweight ones for lists, full ones for detail pages, etc.
"""
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.utils import timezone
from apps.sites.models import HistoricalSite, SiteImage, SiteSource, BucketListItem
from apps.geography.models import Province, County, HistoricalEra


# Mixin for common site serializer methods
# I put this in a mixin so I don't have to repeat the same code in every serializer

class SiteRelatedFieldsMixin:
    """
    Mixin with methods that multiple site serializers need
    
    Things like getting county name, era name, and primary image URL are used
    in multiple serializers, so I put them here to avoid code duplication.
    """
    
    def get_county_name(self, obj):
        """Gets the county name - returns None if site has no county"""
        return obj.county.name_en if obj.county else None
    
    def get_era_name(self, obj):
        """Gets the era name - returns None if site has no era"""
        return obj.era.name_en if obj.era else None
    
    def get_era_color(self, obj):
        """Gets the era color for map markers"""
        return obj.era.color_hex if obj.era else None
    
    def get_primary_image_url(self, obj):
        """
        Gets the primary image URL for a site
        
        The viewset prefetches images in a specific order (primary first) and
        stores them in ordered_images. If that exists, I use the first one.
        Otherwise I fall back to querying the images relation, but that should
        be rare since we prefetch in get_queryset.
        """
        # Check if we have the prefetched images from the viewset
        if hasattr(obj, 'ordered_images') and obj.ordered_images:
            # First one is the primary (or first non-deleted)
            return obj.ordered_images[0].image_url
        
        # Fallback if prefetch didn't happen (shouldn't normally happen)
        if hasattr(obj, 'images') and obj.images.exists():
            primary = obj.images.filter(is_primary=True, is_deleted=False).first()
            if primary:
                return primary.image_url
            first = obj.images.filter(is_deleted=False).first()
            return first.image_url if first else None
        
        return None


# Historical Era serializers
# Used by the timeline filter on the frontend

class HistoricalEraSerializer(serializers.ModelSerializer):
    """
    Full era serializer with all fields
    
    Used when the frontend needs full era details. The duration_years is a
    computed property from the model that calculates how long the era lasted.
    """
    duration_years = serializers.ReadOnlyField()

    class Meta:
        model = HistoricalEra
        fields = [
            'id', 'name_en', 'name_ga', 'start_year', 'end_year',
            'description_en', 'description_ga', 'color_hex',
            'display_order', 'duration_years'
        ]


class HistoricalEraMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight era serializer - just the basics
    
    Used when eras are nested inside other serializers and we don't need
    all the details, just name and color for display.
    """
    class Meta:
        model = HistoricalEra
        fields = ['id', 'name_en', 'name_ga', 'color_hex']


# Site Image serializers
# Handles image data with captions in both languages

class SiteImageSerializer(serializers.ModelSerializer):
    """
    Full image serializer with all metadata
    
    Includes captions in English and Irish, photographer info, dates, etc.
    Used when showing image galleries or detail views.
    """
    class Meta:
        model = SiteImage
        fields = [
            'id', 'image_url', 'thumbnail_url', 'title_en', 'title_ga',
            'caption_en', 'caption_ga', 'photographer', 'photo_date',
            'is_primary', 'display_order', 'width_px', 'height_px'
        ]


class SiteImageMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight image serializer - just URLs and primary flag
    
    Used in list views where we just need the image URL, not all the metadata.
    """
    class Meta:
        model = SiteImage
        fields = ['id', 'image_url', 'thumbnail_url', 'is_primary']


# Site Source serializers
# Handles academic references and citations

class SiteSourceSerializer(serializers.ModelSerializer):
    """
    Serializer for sources/citations
    
    These are academic references, books, papers, etc. that document the sites.
    The citation field is a computed property that formats the source properly.
    """
    citation = serializers.ReadOnlyField()
    source_type_display = serializers.CharField(
        source='get_source_type_display', read_only=True
    )

    class Meta:
        model = SiteSource
        fields = [
            'id', 'source_type', 'source_type_display', 'title', 'author',
            'publication_year', 'publisher', 'url', 'isbn', 'pages',
            'notes', 'reliability_score', 'citation'
        ]


# Province serializers
# These return GeoJSON for drawing province boundaries on the map

class ProvinceBoundarySerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for province boundaries
    
    Returns the province shapes as GeoJSON so Leaflet can draw them. The viewset
    uses raw SQL to generate this, but this serializer is used for detail views.
    The county_count and site_count methods try to use annotated values from the
    queryset if available, otherwise they query the database.
    """
    county_count = serializers.SerializerMethodField()
    site_count = serializers.SerializerMethodField()

    class Meta:
        model = Province
        geo_field = 'geometry'
        fields = [
            'id', 'name_en', 'name_ga', 'code', 'area_km2',
            'population', 'description_en', 'description_ga',
            'county_count', 'site_count'
        ]

    def get_county_count(self, obj):
        """
        Gets the number of counties in this province
        
        If the queryset annotated this value, use that (faster). Otherwise
        count them manually.
        """
        if hasattr(obj, 'annotated_county_count'):
            return obj.annotated_county_count
        return obj.counties.filter(is_deleted=False).count()

    def get_site_count(self, obj):
        """
        Gets the total number of sites in this province
        
        Counts all approved sites in all counties within the province.
        """
        return HistoricalSite.objects.filter(
            county__province=obj,
            is_deleted=False,
            approval_status='approved'
        ).count()


class ProvinceMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight province serializer - just names and code
    
    Used for dropdowns and filters where we don't need the geometry or
    other details, just the name to display.
    """
    class Meta:
        model = Province
        fields = ['id', 'name_en', 'name_ga', 'code']


# County serializers
# Same idea as provinces but for counties

class CountyBoundarySerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for county boundaries
    
    Returns county shapes as GeoJSON. Includes province info since counties
    belong to provinces. The site_count method uses annotated values if available
    to avoid extra queries.
    """
    province_name = serializers.CharField(source='province.name_en', read_only=True)
    province_code = serializers.CharField(source='province.code', read_only=True)
    site_count = serializers.SerializerMethodField()

    class Meta:
        model = County
        geo_field = 'geometry'
        fields = [
            'id', 'name_en', 'name_ga', 'code', 'province',
            'province_name', 'province_code', 'area_km2', 'population',
            'description_en', 'description_ga', 'site_count'
        ]

    def get_site_count(self, obj):
        """
        Gets the number of sites in this county
        
        Uses annotated count if the queryset provided it, otherwise queries
        the database to count approved sites.
        """
        if hasattr(obj, 'annotated_site_count'):
            return obj.annotated_site_count
        return obj.historical_sites.filter(
            is_deleted=False,
            approval_status='approved'
        ).count()


class CountyMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight county serializer - just names and province info
    
    Used for dropdowns and filters. Includes province name so the frontend
    can show "County, Province" format.
    """
    province_name = serializers.CharField(source='province.name_en', read_only=True)

    class Meta:
        model = County
        fields = ['id', 'name_en', 'name_ga', 'code', 'province', 'province_name']


# Historical Site serializers
# These are the main ones - different weights for different use cases

class HistoricalSiteListSerializer(SiteRelatedFieldsMixin, GeoFeatureModelSerializer):
    """
    Lightweight serializer for the map list view
    
    This is used when loading sites for the map. I truncate descriptions to
    200 chars to keep the response size down. Only includes fields needed for
    markers and popups - the detail view has everything else.
    """
    county_name = serializers.SerializerMethodField()
    era_name = serializers.SerializerMethodField()
    site_type_display = serializers.CharField(
        source='get_site_type_display', read_only=True
    )
    primary_image_url = serializers.SerializerMethodField()
    # Truncate descriptions for list view to reduce data transfer (popups can load full on demand)
    description_en = serializers.SerializerMethodField()
    description_ga = serializers.SerializerMethodField()
    
    def get_description_en(self, obj):
        """
        Truncates description to 200 chars for list view
        
        Full descriptions can be really long, so I cut them off at 200 chars
        and add "..." to save bandwidth. The popup can load the full description
        if the user wants it.
        """
        if obj.description_en:
            return obj.description_en[:200] + '...' if len(obj.description_en) > 200 else obj.description_en
        return None
    
    def get_description_ga(self, obj):
        """Same as English but for Irish description"""
        if obj.description_ga:
            return obj.description_ga[:200] + '...' if len(obj.description_ga) > 200 else obj.description_ga
        return None
    
    class Meta:
        model = HistoricalSite
        geo_field = 'location'
        # Only include essential fields to keep response size small
        # Descriptions are truncated via the SerializerMethodField above
        fields = [
            'id', 'name_en', 'name_ga', 'site_type', 'site_type_display',
            'significance_level', 'national_monument',
            'county_name', 'era_name',
            'description_en', 'description_ga',  # These are truncated via SerializerMethodField
            'primary_image_url'
        ]


class HistoricalSiteDetailSerializer(SiteRelatedFieldsMixin, GeoFeatureModelSerializer):
    """
    Full serializer for site detail pages
    
    Includes everything - all fields, nested images, sources, etc. This is
    used when the user clicks through to a site's detail page. Much bigger
    than the list serializer but has all the information.
    """
    # Related object names - use SerializerMethodField to handle cases where
    # county or era might be null
    county_name = serializers.SerializerMethodField()
    county_name_ga = serializers.SerializerMethodField()
    province_name = serializers.SerializerMethodField()
    era_name = serializers.SerializerMethodField()
    era_name_ga = serializers.SerializerMethodField()
    era_color = serializers.SerializerMethodField()

    def get_county_name_ga(self, obj):
        return obj.county.name_ga if obj.county else None

    def get_era_name_ga(self, obj):
        return obj.era.name_ga if obj.era else None

    # Nested serializers
    images = SiteImageSerializer(many=True, read_only=True)
    sources = SiteSourceSerializer(many=True, read_only=True)

    # Computed fields
    coordinates = serializers.ReadOnlyField()
    primary_image = serializers.SerializerMethodField()

    # Display values for choice fields
    site_type_display = serializers.CharField(
        source='get_site_type_display', read_only=True
    )
    preservation_status_display = serializers.CharField(
        source='get_preservation_status_display', read_only=True
    )

    class Meta:
        model = HistoricalSite
        geo_field = 'location'
        fields = [
            # Identity
            'id', 'name_en', 'name_ga',
            # Descriptions
            'description_en', 'description_ga',
            # Location
            'coordinates', 'elevation_meters',
            'county', 'county_name', 'county_name_ga', 'province_name',
            # Historical context
            'era', 'era_name', 'era_name_ga', 'era_color',
            'date_established', 'date_abandoned', 'construction_period',
            # Classification
            'site_type', 'site_type_display', 'significance_level',
            'preservation_status', 'preservation_status_display',
            'national_monument', 'unesco_site',
            # Visitor info
            'is_public_access', 'visitor_center', 'admission_required',
            'address', 'eircode', 'website_url', 'phone_number',
            # Media
            'images', 'primary_image',
            # Sources
            'sources',
            # Metadata
            'data_source', 'created_at', 'updated_at'
        ]

    def get_province_name(self, obj):
        """
        Gets province name through the county relationship
        
        Sites don't have a direct province field, they go through county.
        """
        if obj.county and obj.county.province:
            return obj.county.province.name_en
        return None

    def get_primary_image(self, obj):
        """
        Gets the primary image, or first image if no primary is set
        
        Returns it as a minimal serializer since we don't need all the metadata
        in the detail view - just the URL.
        """
        primary = obj.images.filter(is_primary=True, is_deleted=False).first()
        if primary:
            return SiteImageMinimalSerializer(primary).data
        # Fall back to first image if no primary
        first = obj.images.filter(is_deleted=False).first()
        if first:
            return SiteImageMinimalSerializer(first).data
        return None


class HistoricalSitePopupSerializer(SiteRelatedFieldsMixin, GeoFeatureModelSerializer):
    """
    Medium-weight serializer for map popups
    
    When user clicks a marker, this is what gets loaded. Has more info than
    the list view (full descriptions) but less than the detail view (no nested
    images/sources). Just enough for a nice popup.
    """
    county_name = serializers.SerializerMethodField()
    era_name = serializers.SerializerMethodField()
    era_color = serializers.SerializerMethodField()
    site_type_display = serializers.CharField(
        source='get_site_type_display', read_only=True
    )
    primary_image_url = serializers.SerializerMethodField()

    class Meta:
        model = HistoricalSite
        geo_field = 'location'
        fields = [
            'id', 'name_en', 'name_ga',
            'description_en', 'description_ga',
            'site_type', 'site_type_display',
            'significance_level', 'national_monument',
            'county_name', 'era_name', 'era_color',
            'date_established', 'primary_image_url',
            'is_public_access', 'website_url'
        ]


# Query parameter serializers
# These validate the parameters for spatial searches

class NearbySearchSerializer(serializers.Serializer):
    """
    Validates parameters for the nearby search endpoint
    
    Makes sure lat/lon are within Ireland's bounds and distance/limit
    are reasonable values. The viewset uses this to validate query params.
    """
    lat = serializers.FloatField(
        min_value=51.0, max_value=56.0,
        help_text="Latitude (Ireland bounds: 51-56)"
    )
    lon = serializers.FloatField(
        min_value=-11.0, max_value=-5.0,
        help_text="Longitude (Ireland bounds: -11 to -5)"
    )
    distance = serializers.FloatField(
        min_value=0.1, max_value=100, default=10,
        help_text="Search radius in kilometers"
    )
    limit = serializers.IntegerField(
        min_value=1, max_value=100, default=50,
        help_text="Maximum results to return"
    )


class BboxSearchSerializer(serializers.Serializer):
    """
    Validates bounding box parameters for viewport queries
    
    Makes sure the bounding box is valid (min < max for both x and y).
    The frontend sends the map's viewport bounds when panning/zooming.
    """
    minx = serializers.FloatField(help_text="Minimum longitude (west)")
    miny = serializers.FloatField(help_text="Minimum latitude (south)")
    maxx = serializers.FloatField(help_text="Maximum longitude (east)")
    maxy = serializers.FloatField(help_text="Maximum latitude (north)")

    def validate(self, data):
        """Makes sure the bounding box is valid"""
        if data['minx'] >= data['maxx']:
            raise serializers.ValidationError("minx must be less than maxx")
        if data['miny'] >= data['maxy']:
            raise serializers.ValidationError("miny must be less than maxy")
        return data


# Statistics serializers
# These define the structure of statistics responses

class SiteStatisticsSerializer(serializers.Serializer):
    """
    Defines the structure for the statistics endpoint
    
    The viewset calculates all these values and this serializer just defines
    what fields should be in the response. It's a Serializer (not ModelSerializer)
    because the data comes from aggregations, not a single model.
    """
    total_sites = serializers.IntegerField()
    national_monuments = serializers.IntegerField()
    unesco_sites = serializers.IntegerField()
    by_site_type = serializers.DictField()
    by_era = serializers.ListField()
    by_county = serializers.ListField()
    by_significance = serializers.DictField()


# Bucket list serializers
# These handle the "My Journey" feature data

class HistoricalSiteMinimalSerializer(SiteRelatedFieldsMixin, serializers.ModelSerializer):
    """
    Minimal site serializer for bucket list items
    
    When a site is nested inside a bucket list item, we don't need all the
    site details - just enough to display it in the list. This keeps the
    response size reasonable.
    """
    county_name = serializers.SerializerMethodField()
    era_name = serializers.SerializerMethodField()
    site_type_display = serializers.CharField(
        source='get_site_type_display', read_only=True
    )
    coordinates = serializers.ReadOnlyField()

    class Meta:
        model = HistoricalSite
        fields = [
            'id', 'name_en', 'name_ga', 'site_type', 'site_type_display',
            'significance_level', 'national_monument', 'county_name',
            'era_name', 'coordinates', 'description_en'
        ]


class BucketListItemSerializer(serializers.ModelSerializer):
    """
    Full serializer for bucket list items
    
    Includes the nested site data and handles photo URLs. The photo_url field
    builds absolute URLs so the frontend can display uploaded photos correctly
    in production.
    """
    site = HistoricalSiteMinimalSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = BucketListItem
        fields = [
            'id', 'site', 'status', 'status_display', 'added_at',
            'visited_at', 'photo', 'photo_url', 'photo_caption'
        ]
        read_only_fields = ['id', 'added_at']

    def get_photo_url(self, obj):
        """
        Builds an absolute URL for the uploaded photo
        
        In production, relative URLs don't work well, so I build the full URL
        using the request object. If that's not available, falls back to
        constructing it from settings.
        """
        if obj.photo and hasattr(obj.photo, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            # Fallback if request context isn't available
            from django.conf import settings
            return f"{settings.MEDIA_URL}{obj.photo.name}" if obj.photo.name else None
        return None


class BucketListCreateSerializer(serializers.Serializer):
    """
    Serializer for creating bucket list items
    
    Just needs site_id and optionally a status. Validates that the site
    exists and is approved before allowing creation.
    """
    site_id = serializers.IntegerField(required=True)
    status = serializers.CharField(max_length=20, default='wishlist')

    def validate_site_id(self, value):
        """
        Makes sure the site exists and is approved before adding to bucket list
        """
        try:
            site = HistoricalSite.objects.get(
                id=value,
                is_deleted=False,
                approval_status='approved'
            )
        except HistoricalSite.DoesNotExist:
            raise serializers.ValidationError(
                "Site does not exist or is not approved"
            )
        return value

    def validate_status(self, value):
        """Makes sure status is either 'wishlist' or 'visited'"""
        allowed_statuses = ['wishlist', 'visited']
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}"
            )
        return value


class BucketListUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating bucket list items
    
    Lets users update status, upload photos, and add captions. If they change
    status to 'visited', automatically sets the visited_at timestamp.
    """
    status = serializers.CharField(max_length=20, required=False)
    photo = serializers.ImageField(required=False, allow_null=True)
    photo_caption = serializers.CharField(allow_blank=True, required=False)
    visited_at = serializers.DateTimeField(allow_null=True, required=False)

    def validate_status(self, value):
        """Makes sure status is valid"""
        allowed_statuses = ['wishlist', 'visited']
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}"
            )
        return value

    def validate(self, data):
        """
        Auto-sets visited_at timestamp when status changes to 'visited'
        
        If they mark it as visited and didn't provide a timestamp, I set it
        to now automatically.
        """
        if data.get('status') == 'visited' and not data.get('visited_at'):
            data['visited_at'] = timezone.now()
        return data


class BucketListStatisticsSerializer(serializers.Serializer):
    """
    Defines the structure for bucket list statistics
    
    The viewset calculates these values and this just defines what fields
    should be in the response.
    """
    total = serializers.IntegerField()
    wishlist = serializers.IntegerField()
    visited = serializers.IntegerField()
    counties_explored = serializers.IntegerField()
    by_county = serializers.ListField()
    by_site_type = serializers.DictField()
