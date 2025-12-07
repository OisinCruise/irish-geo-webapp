"""
GeoJSON Serializers for Irish Historical Sites GIS API
=======================================================
Production-ready serializers with full GeoJSON support for Leaflet.js frontend.
Supports bilingual content (English/Irish) and comprehensive spatial data.
"""
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from apps.sites.models import HistoricalSite, SiteImage, SiteSource
from apps.geography.models import Province, County, HistoricalEra


# ==============================================================================
# HISTORICAL ERA SERIALIZERS
# ==============================================================================

class HistoricalEraSerializer(serializers.ModelSerializer):
    """
    Serializer for Historical Eras
    Used for timeline filtering and era-based map layers
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
    """Lightweight era serializer for nested use"""
    class Meta:
        model = HistoricalEra
        fields = ['id', 'name_en', 'name_ga', 'color_hex']


# ==============================================================================
# SITE IMAGE SERIALIZERS
# ==============================================================================

class SiteImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Site Images
    Includes bilingual captions and metadata
    """
    class Meta:
        model = SiteImage
        fields = [
            'id', 'image_url', 'thumbnail_url', 'title_en', 'title_ga',
            'caption_en', 'caption_ga', 'photographer', 'photo_date',
            'is_primary', 'display_order', 'width_px', 'height_px'
        ]


class SiteImageMinimalSerializer(serializers.ModelSerializer):
    """Lightweight image serializer for list views"""
    class Meta:
        model = SiteImage
        fields = ['id', 'image_url', 'thumbnail_url', 'is_primary']


# ==============================================================================
# SITE SOURCE SERIALIZERS
# ==============================================================================

class SiteSourceSerializer(serializers.ModelSerializer):
    """
    Serializer for Historical Sources
    Academic references and documentation for sites
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


# ==============================================================================
# PROVINCE SERIALIZERS (GeoJSON)
# ==============================================================================

class ProvinceBoundarySerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for Province boundaries
    Returns MultiPolygon geometry for map overlay
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
        return obj.counties.filter(is_deleted=False).count()

    def get_site_count(self, obj):
        from django.db.models import Count
        return HistoricalSite.objects.filter(
            county__province=obj,
            is_deleted=False,
            approval_status='approved'
        ).count()


class ProvinceMinimalSerializer(serializers.ModelSerializer):
    """Lightweight province serializer for dropdowns"""
    class Meta:
        model = Province
        fields = ['id', 'name_en', 'name_ga', 'code']


# ==============================================================================
# COUNTY SERIALIZERS (GeoJSON)
# ==============================================================================

class CountyBoundarySerializer(GeoFeatureModelSerializer):
    """
    GeoJSON serializer for County boundaries
    Returns MultiPolygon geometry for map overlay with province info
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
        return obj.historical_sites.filter(
            is_deleted=False,
            approval_status='approved'
        ).count()


class CountyMinimalSerializer(serializers.ModelSerializer):
    """Lightweight county serializer for dropdowns and filters"""
    province_name = serializers.CharField(source='province.name_en', read_only=True)

    class Meta:
        model = County
        fields = ['id', 'name_en', 'name_ga', 'code', 'province', 'province_name']


# ==============================================================================
# HISTORICAL SITE SERIALIZERS (GeoJSON)
# ==============================================================================

class HistoricalSiteListSerializer(GeoFeatureModelSerializer):
    """
    Lightweight GeoJSON serializer for map markers
    Optimized for loading many points on the map
    """
    class Meta:
        model = HistoricalSite
        geo_field = 'location'
        fields = [
            'id', 'name_en', 'name_ga', 'site_type',
            'significance_level', 'national_monument'
        ]


class HistoricalSiteDetailSerializer(GeoFeatureModelSerializer):
    """
    Full GeoJSON serializer for site detail view
    Includes all related data, images, and sources
    """
    # Related object names
    county_name = serializers.CharField(source='county.name_en', read_only=True)
    county_name_ga = serializers.CharField(source='county.name_ga', read_only=True)
    province_name = serializers.SerializerMethodField()
    era_name = serializers.CharField(source='era.name_en', read_only=True)
    era_name_ga = serializers.CharField(source='era.name_ga', read_only=True)
    era_color = serializers.CharField(source='era.color_hex', read_only=True)

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
        if obj.county and obj.county.province:
            return obj.county.province.name_en
        return None

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True, is_deleted=False).first()
        if primary:
            return SiteImageMinimalSerializer(primary).data
        # Fall back to first image
        first = obj.images.filter(is_deleted=False).first()
        if first:
            return SiteImageMinimalSerializer(first).data
        return None


class HistoricalSitePopupSerializer(GeoFeatureModelSerializer):
    """
    Medium-weight serializer for map popup display
    Includes essential info without full nested objects
    """
    county_name = serializers.CharField(source='county.name_en', read_only=True)
    era_name = serializers.CharField(source='era.name_en', read_only=True)
    era_color = serializers.CharField(source='era.color_hex', read_only=True)
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

    def get_primary_image_url(self, obj):
        primary = obj.images.filter(is_primary=True, is_deleted=False).first()
        if primary:
            return primary.image_url
        first = obj.images.filter(is_deleted=False).first()
        return first.image_url if first else None


# ==============================================================================
# SPATIAL QUERY SERIALIZERS
# ==============================================================================

class NearbySearchSerializer(serializers.Serializer):
    """Serializer for validating nearby search parameters"""
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
    """Serializer for validating bounding box search parameters"""
    minx = serializers.FloatField(help_text="Minimum longitude (west)")
    miny = serializers.FloatField(help_text="Minimum latitude (south)")
    maxx = serializers.FloatField(help_text="Maximum longitude (east)")
    maxy = serializers.FloatField(help_text="Maximum latitude (north)")

    def validate(self, data):
        if data['minx'] >= data['maxx']:
            raise serializers.ValidationError("minx must be less than maxx")
        if data['miny'] >= data['maxy']:
            raise serializers.ValidationError("miny must be less than maxy")
        return data


# ==============================================================================
# STATISTICS SERIALIZERS
# ==============================================================================

class SiteStatisticsSerializer(serializers.Serializer):
    """Serializer for site statistics endpoint"""
    total_sites = serializers.IntegerField()
    national_monuments = serializers.IntegerField()
    unesco_sites = serializers.IntegerField()
    by_site_type = serializers.DictField()
    by_era = serializers.ListField()
    by_county = serializers.ListField()
    by_significance = serializers.DictField()
