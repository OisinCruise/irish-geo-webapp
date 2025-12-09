"""
Geography Models - Irish Administrative Boundaries
Province, County, and Historical Era models for Irish Historical Sites GIS
"""
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


# ==============================================================================
# CUSTOM MANAGERS WITH SPATIAL QUERY METHODS
# ==============================================================================

class ProvinceManager(models.Manager):
    """Custom manager for Province with spatial queries"""
    
    def with_site_counts(self):
        """Annotate provinces with historical site counts"""
        return self.annotate(
            site_count=models.Count('county__historical_sites')
        )
    
    def containing_point(self, longitude, latitude):
        """Find province containing a specific point"""
        point = Point(longitude, latitude, srid=4326)
        return self.filter(geometry__contains=point).first()


class CountyManager(models.Manager):
    """Custom manager for County with spatial and filtering queries"""
    
    def in_province(self, province_name):
        """Get all counties in a province"""
        return self.filter(province__name_en__iexact=province_name)
    
    def with_site_counts(self):
        """Annotate counties with site counts"""
        return self.annotate(
            site_count=models.Count('historical_sites')
        ).order_by('-site_count')
    
    def near_point(self, longitude, latitude, distance_km=50):
        """Find counties within distance of a point"""
        from django.contrib.gis.measure import D
        point = Point(longitude, latitude, srid=4326)
        return self.filter(
            geometry__distance_lte=(point, D(km=distance_km))
        )


class HistoricalEraManager(models.Manager):
    """Custom manager for Historical Eras"""
    
    def active_in_year(self, year):
        """Get eras active in a specific year"""
        return self.filter(
            start_year__lte=year,
            end_year__gte=year
        )
    
    def by_chronology(self):
        """Return eras in chronological order"""
        return self.order_by('start_year')


# ==============================================================================
# PROVINCE MODEL
# ==============================================================================

class Province(models.Model):
    """
    Irish Province (Cúige) - Top-level administrative division
    Ireland has 4 provinces: Connacht, Leinster, Munster, Ulster (ROI portion)
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
    
    # Spatial field - MultiPolygon for complex boundaries
    geometry = models.MultiPolygonField(
        srid=4326,
        geography=False,
        verbose_name=_("Province Boundary"),
        help_text=_("Province boundary geometry (WGS84)")
    )
    
    # Statistical fields
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
    
    # Descriptive fields (bilingual)
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
    
    # Audit fields
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
        """Number of counties in this province"""
        return self.counties.filter(is_deleted=False).count()
    
    @property
    def centroid(self):
        """Geographic center of province"""
        return self.geometry.centroid if self.geometry else None


# ==============================================================================
# COUNTY MODEL
# ==============================================================================

class County(models.Model):
    """
    Irish County (Contae) - Second-level administrative division
    26 counties in Republic of Ireland
    """
    
    # Primary fields
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
    
    # Foreign key to Province
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name='counties',
        verbose_name=_("Province"),
        help_text=_("Province this county belongs to")
    )
    
    # Spatial field
    geometry = models.MultiPolygonField(
        srid=4326,
        geography=False,
        verbose_name=_("County Boundary"),
        help_text=_("County boundary geometry (WGS84)")
    )
    
    # Statistical fields
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
    
    # Descriptive fields (bilingual)
    description_en = models.TextField(
        blank=True,
        verbose_name=_("Description (English)")
    )
    description_ga = models.TextField(
        blank=True,
        verbose_name=_("Description (Irish)")
    )
    
    # Audit fields
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
        """Number of historical sites in this county"""
        return self.historical_sites.filter(is_deleted=False).count()


# ==============================================================================
# HISTORICAL ERA MODEL
# ==============================================================================

class HistoricalEra(models.Model):
    """
    Historical Time Period (Tréimhse Staire)
    Defines major eras in Irish history for site categorization
    """
    
    # Primary fields
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
    
    # Time range
    start_year = models.IntegerField(
        verbose_name=_("Start Year"),
        help_text=_("Era start year (negative for BCE)")
    )
    end_year = models.IntegerField(
        verbose_name=_("End Year"),
        help_text=_("Era end year")
    )
    
    # Display fields
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
    
    # Descriptive fields (bilingual)
    description_en = models.TextField(
        verbose_name=_("Description (English)"),
        help_text=_("Era description in English")
    )
    description_ga = models.TextField(
        verbose_name=_("Description (Irish)"),
        help_text=_("Era description in Irish")
    )
    
    # Audit fields
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
        """Calculate era duration in years"""
        return self.end_year - self.start_year
    
    @property
    def is_ancient(self):
        """Check if era is before Common Era"""
        return self.start_year < 0
    
    def contains_year(self, year):
        """Check if a year falls within this era"""
        return self.start_year <= year <= self.end_year
