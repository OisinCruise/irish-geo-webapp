"""
Geography models - provinces, counties, and historical eras

These models store the geographic boundaries and time periods. Provinces and
counties have MultiPolygon geometries for drawing boundaries on the map.
Historical eras are used for filtering sites by time period.
"""
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


# Custom managers for geography models
# These add helper methods for spatial queries and filtering

class ProvinceManager(models.Manager):
    """
    Manager with methods for querying provinces
    
    Can find provinces by location, add site counts, etc.
    """
    
    def with_site_counts(self):
        """
        Adds site count to each province
        
        Counts sites through the county relationship. Useful for showing
        how many sites are in each province.
        """
        return self.annotate(
            site_count=models.Count('county__historical_sites')
        )
    
    def containing_point(self, longitude, latitude):
        """
        Finds which province contains a point
        
        Uses PostGIS contains to check if a point is inside the province
        boundary. Returns the first match (should only be one).
        """
        point = Point(longitude, latitude, srid=4326)
        return self.filter(geometry__contains=point).first()


class CountyManager(models.Manager):
    """
    Manager with methods for querying counties
    
    Can filter by province, find counties near points, add site counts.
    """
    
    def in_province(self, province_name):
        """Gets all counties in a specific province"""
        return self.filter(province__name_en__iexact=province_name)
    
    def with_site_counts(self):
        """
        Adds site count to each county, sorted by count
        
        Useful for showing which counties have the most sites.
        """
        return self.annotate(
            site_count=models.Count('historical_sites')
        ).order_by('-site_count')
    
    def near_point(self, longitude, latitude, distance_km=50):
        """
        Finds counties near a point
        
        Uses distance calculation to find counties within a radius.
        Default is 50km which is pretty big, but useful for finding
        nearby counties.
        """
        from django.contrib.gis.measure import D
        point = Point(longitude, latitude, srid=4326)
        return self.filter(
            geometry__distance_lte=(point, D(km=distance_km))
        )


class HistoricalEraManager(models.Manager):
    """
    Manager for historical eras
    
    Can find eras active in a specific year, get them in chronological order.
    """
    
    def active_in_year(self, year):
        """
        Gets eras that were active in a specific year
        
        Checks if the year falls between start_year and end_year.
        """
        return self.filter(
            start_year__lte=year,
            end_year__gte=year
        )
    
    def by_chronology(self):
        """Gets eras sorted by start year - earliest first"""
        return self.order_by('start_year')


# Province model
# Ireland has 4 provinces - these are the top-level administrative divisions

class Province(models.Model):
    """
    Model for Irish provinces
    
    Each province has a MultiPolygon geometry for its boundary, which gets
    drawn on the map. Provinces contain counties, and counties contain sites.
    I'm using managed=False because the table already exists in the database.
    """
    
    # Primary fields
    id = models.BigAutoField(primary_key=True)
    name_en = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name (English)"),
        help_text=_("Province name in English")
    )
    name_ga = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name (Irish)"),
        help_text=_("Province name in Irish (Gaeilge)")
    )
    code = models.CharField(
        max_length=2,
        unique=True,
        verbose_name=_("Province Code"),
        help_text=_("Two-letter province code (C, L, M, U)")
    )
    
    # Province boundary - MultiPolygon because some provinces have multiple
    # separate areas (like islands)
    geometry = models.MultiPolygonField(
        srid=4326,
        geography=False,
        verbose_name=_("Province Boundary"),
        help_text=_("Province boundary geometry (WGS84)")
    )
    
    # Area and population stats
    area_km2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Area (km²)"),
        help_text=_("Province area in square kilometers")
    )
    population = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Population"),
        help_text=_("Province population")
    )
    
    # Descriptions in both languages
    description_en = models.TextField(
        blank=True,
        verbose_name=_("Description (English)"),
        help_text=_("Province description in English")
    )
    description_ga = models.TextField(
        blank=True,
        verbose_name=_("Description (Irish)"),
        help_text=_("Province description in Irish")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Custom manager
    objects = ProvinceManager()
    
    class Meta:
        managed = False  # Existing table - don't create migrations
        db_table = 'province'
        ordering = ['name_en']
        verbose_name = _("Province")
        verbose_name_plural = _("Provinces")
        indexes = [
            models.Index(fields=['name_en']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.name_en} ({self.name_ga})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('province-detail', kwargs={'pk': self.pk})
    
    @property
    def county_count(self):
        """Counts how many counties are in this province"""
        return self.counties.filter(is_deleted=False).count()
    
    @property
    def centroid(self):
        """
        Gets the geographic center point of the province
        
        Useful for centering the map on a province or calculating distances.
        """
        return self.geometry.centroid if self.geometry else None


# County model
# There are 26 counties in Ireland - these are the second-level divisions

class County(models.Model):
    """
    Model for Irish counties
    
    Counties belong to provinces and contain historical sites. Each county
    has a MultiPolygon boundary that can be drawn on the map. Same as
    provinces, using managed=False because the table exists already.
    """
    
    # Basic info - name in both languages and a 3-letter code
    id = models.BigAutoField(primary_key=True)
    name_en = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name (English)"),
        help_text=_("County name in English")
    )
    name_ga = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name (Irish)"),
        help_text=_("County name in Irish (Gaeilge)")
    )
    code = models.CharField(
        max_length=3,
        unique=True,
        verbose_name=_("County Code"),
        help_text=_("Three-letter county code")
    )
    
    # Which province this county belongs to
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name='counties',
        verbose_name=_("Province"),
        help_text=_("Province this county belongs to")
    )
    
    # County boundary - also MultiPolygon for the same reason as provinces
    geometry = models.MultiPolygonField(
        srid=4326,
        geography=False,
        verbose_name=_("County Boundary"),
        help_text=_("County boundary geometry (WGS84)")
    )
    
    # Area and population stats
    area_km2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Area (km²)")
    )
    population = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Population")
    )
    
    # Descriptions in both languages
    description_en = models.TextField(
        blank=True,
        verbose_name=_("Description (English)")
    )
    description_ga = models.TextField(
        blank=True,
        verbose_name=_("Description (Irish)")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Custom manager
    objects = CountyManager()
    
    class Meta:
        managed = False
        db_table = 'county'
        ordering = ['name_en']
        verbose_name = _("County")
        verbose_name_plural = _("Counties")
        indexes = [
            models.Index(fields=['name_en']),
            models.Index(fields=['code']),
            models.Index(fields=['province']),
        ]
    
    def __str__(self):
        return f"County {self.name_en}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('county-detail', kwargs={'pk': self.pk})
    
    @property
    def site_count(self):
        """Counts how many approved sites are in this county"""
        return self.historical_sites.filter(is_deleted=False).count()


# Historical Era model
# These define time periods for categorizing sites

class HistoricalEra(models.Model):
    """
    Model for historical time periods
    
    Each era has a start and end year, a color for map visualization, and
    descriptions. Sites are linked to eras so users can filter by time period.
    The color_hex field is used to color-code sites on the map by era.
    """
    
    # Name in both languages
    id = models.BigAutoField(primary_key=True)
    name_en = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Era Name (English)"),
        help_text=_("Historical era name in English")
    )
    name_ga = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Era Name (Irish)"),
        help_text=_("Historical era name in Irish")
    )
    
    # When this era started and ended
    start_year = models.IntegerField(
        verbose_name=_("Start Year"),
        help_text=_("Era start year (negative for BCE)")
    )
    end_year = models.IntegerField(
        verbose_name=_("End Year"),
        help_text=_("Era end year")
    )
    
    # How to display it - order in timeline and color for map
    display_order = models.IntegerField(
        default=0,
        verbose_name=_("Display Order"),
        help_text=_("Order for display in timelines")
    )
    color_hex = models.CharField(
        max_length=7,
        default='#1a5f4a',
        verbose_name=_("Color Code"),
        help_text=_("Hex color for map visualization (#RRGGBB)")
    )
    
    # Descriptions in both languages
    description_en = models.TextField(
        verbose_name=_("Description (English)"),
        help_text=_("Era description in English")
    )
    description_ga = models.TextField(
        verbose_name=_("Description (Irish)"),
        help_text=_("Era description in Irish")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Custom manager
    objects = HistoricalEraManager()
    
    class Meta:
        managed = False
        db_table = 'historical_era'
        ordering = ['start_year', 'display_order']
        verbose_name = _("Historical Era")
        verbose_name_plural = _("Historical Eras")
        indexes = [
            models.Index(fields=['start_year', 'end_year']),
            models.Index(fields=['display_order']),
        ]
    
    def __str__(self):
        return f"{self.name_en} ({self.start_year}-{self.end_year})"
    
    @property
    def duration_years(self):
        """Calculates how many years the era lasted"""
        return self.end_year - self.start_year
    
    @property
    def is_ancient(self):
        """Checks if the era is BCE (before year 0)"""
        return self.start_year < 0
    
    def contains_year(self, year):
        """
        Checks if a specific year falls within this era
        
        Useful for filtering sites by year - if a site was established in
        a certain year, you can check which era it belongs to.
        """
        return self.start_year <= year <= self.end_year
