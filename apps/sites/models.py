"""
Historical Sites Models - Main Content Models
HistoricalSite, SiteImage, and SiteSource models
"""
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q, Count, Avg
import os


# ==============================================================================
# CUSTOM MANAGERS WITH SPATIAL QUERIES
# ==============================================================================

class HistoricalSiteManager(gis_models.Manager):
    """Custom manager for HistoricalSite with spatial and filtering queries"""
    
    def active(self):
        """Return only non-deleted, approved sites"""
        return self.filter(is_deleted=False, approval_status='approved')
    
    def by_county(self, county_name):
        """Filter sites by county name"""
        return self.filter(county__name_en__iexact=county_name, is_deleted=False)
    
    def by_era(self, era_name):
        """Filter sites by historical era"""
        return self.filter(era__name_en__iexact=era_name, is_deleted=False)
    
    def by_type(self, site_type):
        """Filter sites by type"""
        return self.filter(site_type=site_type, is_deleted=False)
    
    def near_point(self, longitude, latitude, distance_km=10):
        """
        Find sites within distance of a point
        Args:
            longitude: Longitude in WGS84
            latitude: Latitude in WGS84
            distance_km: Search radius in kilometers
        """
        from django.contrib.gis.db.models.functions import Distance
        point = Point(longitude, latitude, srid=4326)
        return self.filter(
            location__distance_lte=(point, D(km=distance_km)),
            is_deleted=False
        ).annotate(distance=Distance('location', point)).order_by('distance')
    
    def in_bounding_box(self, min_lon, min_lat, max_lon, max_lat):
        """
        Find sites within a bounding box
        Args:
            min_lon, min_lat: Southwest corner
            max_lon, max_lat: Northeast corner
        """
        from django.contrib.gis.geos import Polygon
        bbox = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
        return self.filter(location__within=bbox, is_deleted=False)
    
    def with_high_significance(self):
        """Return sites with significance level 4 or 5"""
        return self.filter(significance_level__gte=4, is_deleted=False)
    
    def national_monuments(self):
        """Return only national monuments"""
        return self.filter(national_monument=True, is_deleted=False)
    
    def with_ratings(self):
        """Annotate sites with average rating"""
        return self.annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        )


# ==============================================================================
# HISTORICAL SITE MODEL (Main Model)
# ==============================================================================

class HistoricalSite(gis_models.Model):
    """
    Historical Site (Suíomh Stairiúil) - Main model for archaeological sites
    Represents castles, monasteries, battlefields, and other historical locations
    """
    
    # Site Type Choices
    SITE_TYPE_CHOICES = [
        ('castle', _('Castle')),
        ('monastery', _('Monastery/Abbey')),
        ('fort', _('Fort/Ringfort')),
        ('burial_site', _('Burial Site/Tomb')),
        ('stone_monument', _('Stone Monument')),
        ('holy_well', _('Holy Well')),
        ('battlefield', _('Battlefield')),
        ('historic_house', _('Historic House')),
        ('archaeological_site', _('Archaeological Site')),
        ('church', _('Church/Chapel')),
        ('tower', _('Tower/Round Tower')),
        ('bridge', _('Historic Bridge')),
        ('other', _('Other')),
    ]
    
    # Approval Status Choices
    APPROVAL_STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]
    
    # Preservation Status Choices
    PRESERVATION_STATUS_CHOICES = [
        ('excellent', _('Excellent')),
        ('good', _('Good')),
        ('fair', _('Fair')),
        ('poor', _('Poor')),
        ('ruins', _('Ruins')),
        ('archaeological', _('Archaeological Only')),
    ]
    
    # Primary fields
    id = models.AutoField(primary_key=True)
    name_en = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Site Name (English)"),
        help_text=_("Historical site name in English")
    )
    name_ga = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Site Name (Irish)"),
        help_text=_("Historical site name in Irish (Gaeilge)")
    )
    
    # Descriptive fields (bilingual)
    description_en = models.TextField(
        verbose_name=_("Description (English)"),
        help_text=_("Detailed description in English")
    )
    description_ga = models.TextField(
        blank=True,
        verbose_name=_("Description (Irish)"),
        help_text=_("Detailed description in Irish")
    )
    
    # Spatial field - 3D Point location (PointZ)
    location = gis_models.PointField(
        srid=4326,
        dim=3,  # Your database uses PointZ (3D coordinates)
        geography=False,
        verbose_name=_("Location"),
        help_text=_("Site coordinates (WGS84) with elevation")
    )
    
    # Physical attributes
    elevation_meters = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(2000)],
        verbose_name=_("Elevation (m)"),
        help_text=_("Elevation above sea level in meters")
    )
    
    # Foreign Keys
    county = models.ForeignKey(
        'geography.County',
        on_delete=models.SET_NULL,
        related_name='historical_sites',
        null=True,
        blank=True,
        db_column='county_id',
        verbose_name=_("County"),
        help_text=_("County where site is located")
    )
    
    era = models.ForeignKey(
        'geography.HistoricalEra',
        on_delete=models.SET_NULL,
        related_name='historical_sites',
        null=True,
        blank=True,
        db_column='era_id',
        verbose_name=_("Historical Era"),
        help_text=_("Primary historical era")
    )
    
    # Site categorization
    site_type = models.CharField(
        max_length=50,
        choices=SITE_TYPE_CHOICES,
        db_index=True,
        verbose_name=_("Site Type"),
        help_text=_("Type of historical site")
    )
    
    significance_level = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name=_("Significance Level"),
        help_text=_("1=Local, 2=Regional, 3=National, 4=International")
    )
    
    # Temporal data (as DATE fields - matching database)
    date_established = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date Established"),
        help_text=_("Date site was established")
    )
    date_abandoned = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date Abandoned"),
        help_text=_("Date site was abandoned/destroyed")
    )
    
    construction_period = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Construction Period"),
        help_text=_("Historical period description (e.g., 'Early Medieval')")
    )
    
    # Preservation and status
    preservation_status = models.CharField(
        max_length=50,
        choices=PRESERVATION_STATUS_CHOICES,
        blank=True,
        verbose_name=_("Preservation Status"),
        help_text=_("Current preservation state")
    )
    
    unesco_site = models.BooleanField(
        default=False,
        verbose_name=_("UNESCO World Heritage Site"),
        help_text=_("Designated as UNESCO World Heritage Site")
    )
    
    national_monument = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("National Monument"),
        help_text=_("Designated as National Monument")
    )
    
    # Visitor access information
    is_public_access = models.BooleanField(
        default=True,
        verbose_name=_("Public Access"),
        help_text=_("Site is accessible to public")
    )
    
    visitor_center = models.BooleanField(
        default=False,
        verbose_name=_("Visitor Center"),
        help_text=_("Has visitor center or information point")
    )
    
    admission_required = models.BooleanField(
        default=False,
        verbose_name=_("Admission Required"),
        help_text=_("Admission fee required")
    )
    
    # Contact and location details
    address = models.TextField(
        blank=True,
        verbose_name=_("Address"),
        help_text=_("Physical address or location description")
    )
    
    eircode = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_("Eircode"),
        help_text=_("Irish postal code")
    )
    
    website_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_("Website URL"),
        help_text=_("Official website URL")
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Phone Number"),
        help_text=_("Contact phone number")
    )
    
    # Audit fields (matching database exactly)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Created By"),
        help_text=_("Username who created this record")
    )
    
    modified_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Modified By"),
        help_text=_("Username who last modified this record")
    )
    
    # Approval workflow
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name=_("Approval Status"),
        help_text=_("Content moderation status")
    )
    
    approved_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Approved By"),
        help_text=_("Username who approved this site")
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Approval Date")
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Data quality
    data_source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Data Source"),
        help_text=_("Source of site information")
    )
    
    data_quality = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Data Quality"),
        help_text=_("Quality rating: 1=Poor, 5=Excellent")
    )
    
    # Analytics
    view_count = models.IntegerField(
        default=0,
        verbose_name=_("View Count"),
        help_text=_("Number of times site has been viewed")
    )
    
    # Custom manager
    objects = HistoricalSiteManager()
    
    class Meta:
        managed = False
        db_table = 'historical_site'
        ordering = ['-significance_level', 'name_en']
        verbose_name = _("Historical Site")
        verbose_name_plural = _("Historical Sites")
    
    def __str__(self):
        return f"{self.name_en} ({self.get_site_type_display()})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('site-detail', kwargs={'pk': self.pk})
    
    @property
    def coordinates(self):
        """Return (longitude, latitude) tuple"""
        if self.location:
            return (self.location.x, self.location.y)
        return None
    
    @property
    def latitude(self):
        """Return latitude"""
        return self.location.y if self.location else None
    
    @property
    def longitude(self):
        """Return longitude"""
        return self.location.x if self.location else None
    
    @property
    def elevation_from_geometry(self):
        """Return elevation from Z coordinate if available"""
        if self.location and self.location.z:
            return self.location.z
        return self.elevation_meters
    
    def distance_from(self, longitude, latitude):
        """
        Calculate distance from a point in kilometers
        """
        from django.contrib.gis.geos import Point
        point = Point(longitude, latitude, srid=4326)
        # Convert degrees to approximate km (rough conversion)
        return self.location.distance(point) * 111
    
    def nearby_sites(self, radius_km=10, limit=10):
        """Find nearby historical sites"""
        return HistoricalSite.objects.near_point(
            self.longitude,
            self.latitude,
            distance_km=radius_km
        ).exclude(pk=self.pk)[:limit]

# ==============================================================================
# SITE IMAGE MODEL
# ==============================================================================

class SiteImage(models.Model):
    """
    Site Image (Íomhá Suímh) - Images associated with historical sites
    """
    
    # Primary fields
    id = models.BigAutoField(primary_key=True)
    
    # Foreign Key to Site
    site = models.ForeignKey(
        HistoricalSite,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_("Historical Site"),
        help_text=_("Site this image belongs to")
    )
    
    # Image file
    image_url = models.URLField(
        max_length=500,
        verbose_name=_("Image URL"),
        help_text=_("URL to image file")
    )
    
    # Captions (bilingual)
    title_en = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Title (English)")
    )
    title_ga = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Title (Irish)")
    )
    
    caption_en = models.TextField(
        blank=True,
        verbose_name=_("Caption (English)")
    )
    caption_ga = models.TextField(
        blank=True,
        verbose_name=_("Caption (Irish)")
    )
    
    # Metadata
    photographer = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Photographer"),
        help_text=_("Name of photographer/creator")
    )

    photo_date = models.DateField(  
        db_column='photo_date',  # Explicitly specify column name
        null=True,
        blank=True,
        verbose_name=_("Date Taken"),
        help_text=_("Date photograph was taken")
    )
    
    copyright_info = models.CharField(
        db_column='copyright_info',
        max_length=255,
        blank=True,
        verbose_name=_("Copyright Info"),
        help_text=_("Copyright information")
    )

    mime_type = models.CharField(
        db_column='mime_type',
        max_length=50,
        blank=True,
        verbose_name=_("MIME Type"),
        help_text=_("Image MIME type (e.g., image/jpeg)")
    )

    alt_text = models.CharField(
        db_column='alt_text',
        max_length=255,
        blank=True,
        verbose_name=_("Alt Text"),
        help_text=_("Accessibility alt text")
    )

    image_path = models.CharField(
        db_column='image_path',
        max_length=500,
        blank=True,
        verbose_name=_("Image Path"),
        help_text=_("Local file path for image")
    )

    thumbnail_url = models.URLField(
        db_column='thumbnail_url',
        max_length=500,
        blank=True,
        verbose_name=_("Thumbnail URL"),
        help_text=_("URL to thumbnail image")
    )

    is_public = models.BooleanField(
        db_column='is_public',
        default=True,
        verbose_name=_("Public"),
        help_text=_("Image is public")
    )
    
    # Technical fields
    width_px = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Width (pixels)")
    )
    height_px = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Height (pixels)")
    )
    file_size_kb = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("File Size (KB)")
    )
    
    # Display fields
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Image"),
        help_text=_("Use as main site image")
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_("Display Order")
    )
    
    # Rights and permissions
    license_type = models.CharField(
        db_column='license_type',  # Add db_column for consistency
        max_length=50,  # Match database: max_length=50
        blank=True,
        default='All Rights Reserved',  # Match database default
        verbose_name=_("License Type"),
        help_text=_("Copyright/license information")
    )
    
    # User contribution
    uploaded_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Uploaded By"),
        help_text=_("Username who uploaded this image")
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        managed = False
        db_table = 'site_image'
        ordering = ['display_order', '-is_primary', '-created_at']
        verbose_name = _("Site Image")
        verbose_name_plural = _("Site Images")
        indexes = [
            models.Index(fields=['site']),
            models.Index(fields=['is_primary']),
            models.Index(fields=['display_order']),
        ]
    
    def __str__(self):
        return f"Image for {self.site.name_en}"


# ==============================================================================
# SITE SOURCE MODEL
# ==============================================================================

class SiteSource(models.Model):
    """
    Historical Source (Foinse Stairiúil) - Academic/historical references for sites
    """
    
    SOURCE_TYPE_CHOICES = [
        ('book', _('Book')),
        ('journal', _('Journal Article')),
        ('website', _('Website')),
        ('archive', _('Archive Document')),
        ('oral_history', _('Oral History')),
        ('government_record', _('Government Record')),
    ]
    
    # Primary fields
    id = models.BigAutoField(primary_key=True)
    
    # Foreign Key to Site
    site = models.ForeignKey(
        HistoricalSite,
        on_delete=models.CASCADE,
        related_name='sources',
        verbose_name=_("Historical Site")
    )
    
    # Source details
    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        verbose_name=_("Source Type")
    )
    
    title = models.CharField(
        max_length=500,
        verbose_name=_("Title"),
        help_text=_("Full title of source")
    )
    
    author = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Author(s)")
    )
    
    publication_year = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Publication Year")
    )
    
    publisher = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Publisher")
    )
    
    url = models.URLField(
        max_length=500,
        blank=True,
        validators=[URLValidator()],
        verbose_name=_("URL"),
        help_text=_("Link to online source")
    )
    
    isbn = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("ISBN"),
        help_text=_("ISBN for books")
    )

    pages = models.CharField( 
        db_column='pages',  # Explicitly specify column name
        max_length=50,
        blank=True,
        verbose_name=_("Page Numbers"),
        help_text=_("Relevant page numbers")
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes about source")
    )
    
    # Quality rating
    reliability_score = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Reliability Score"),
        help_text=_("1=Questionable, 5=Highly reliable")
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    added_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Added By"),
        help_text=_("Username who added this source")
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        managed = False
        db_table = 'site_source'
        ordering = ['-reliability_score', '-publication_year']
        verbose_name = _("Historical Source")
        verbose_name_plural = _("Historical Sources")
        indexes = [
            models.Index(fields=['site']),
            models.Index(fields=['source_type']),
            models.Index(fields=['reliability_score']),
        ]
    
    def __str__(self):
        if self.author:
            return f"{self.author} - {self.title}"
        return self.title
    
    @property
    def citation(self):
        """Generate a basic citation string"""
        parts = []
        if self.author:
            parts.append(self.author)
        if self.publication_year:
            parts.append(f"({self.publication_year})")
        parts.append(self.title)
        if self.publisher:
            parts.append(self.publisher)
        return ". ".join(parts)
