"""
Models for historical sites - the main data models

These are the core models that store all the site information. HistoricalSite
is the main one, and SiteImage and SiteSource are related models. I'm using
GeoDjango models because sites have location data that needs spatial queries.
"""
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q, Count, Avg
import os


# Custom manager for sites
# I added these methods to make it easier to query sites in different ways
# Instead of writing the same filters over and over, I can just call site_manager.near_point()

class HistoricalSiteManager(gis_models.Manager):
    """
    Custom manager with helper methods for querying sites
    
    These methods make it easier to find sites by location, type, era, etc.
    The spatial queries use PostGIS functions to find sites near points or
    in bounding boxes.
    """
    
    def active(self):
        """Gets only approved sites that aren't deleted"""
        return self.filter(is_deleted=False, approval_status='approved')
    
    def by_county(self, county_name):
        """Finds sites in a specific county"""
        return self.filter(county__name_en__iexact=county_name, is_deleted=False)
    
    def by_era(self, era_name):
        """Finds sites from a specific historical era"""
        return self.filter(era__name_en__iexact=era_name, is_deleted=False)
    
    def by_type(self, site_type):
        """Finds sites of a specific type (castle, monastery, etc.)"""
        return self.filter(site_type=site_type, is_deleted=False)
    
    def near_point(self, longitude, latitude, distance_km=10):
        """
        Finds sites near a point - used for location-based search
        
        Uses PostGIS distance calculations to find all sites within a certain
        radius. Returns them sorted by distance so closest ones come first.
        """
        from django.contrib.gis.db.models.functions import Distance
        point = Point(longitude, latitude, srid=4326)
        return self.filter(
            location__distance_lte=(point, D(km=distance_km)),
            is_deleted=False
        ).annotate(distance=Distance('location', point)).order_by('distance')
    
    def in_bounding_box(self, min_lon, min_lat, max_lon, max_lat):
        """
        Finds sites within a bounding box - used when the map viewport changes
        
        Takes the corners of a rectangle and finds all sites inside it. This
        is what gets called when the user pans or zooms the map.
        """
        from django.contrib.gis.geos import Polygon
        bbox = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
        return self.filter(location__within=bbox, is_deleted=False)
    
    def with_high_significance(self):
        """Gets only the most important sites (significance 4 or 5)"""
        return self.filter(significance_level__gte=4, is_deleted=False)
    
    def national_monuments(self):
        """Gets only sites that are designated national monuments"""
        return self.filter(national_monument=True, is_deleted=False)
    
    def with_ratings(self):
        """
        Adds rating info to sites - not really used yet but might be useful later
        
        Annotates each site with average rating and count of ratings.
        """
        return self.annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        )


# Historical Site model - this is the main one
# Stores all the information about each historical site

class HistoricalSite(gis_models.Model):
    """
    Main model for historical sites
    
    This stores everything about a site - name, location, description, type,
    significance level, etc. The location field is a PointZ (3D point) so
    it includes elevation. I'm using managed=False because the table already
    exists in the database and I don't want Django to try to create it.
    """
    
    # Site type options - these are the categories sites can be
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
    
    # Approval workflow - sites need to be approved before showing on the map
    APPROVAL_STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]
    
    # How well preserved the site is
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
    
    # Descriptions in both languages
    description_en = models.TextField(
        verbose_name=_("Description (English)"),
        help_text=_("Detailed description in English")
    )
    description_ga = models.TextField(
        blank=True,
        verbose_name=_("Description (Irish)"),
        help_text=_("Detailed description in Irish")
    )
    
    # Location - PointZ means it has X, Y, and Z (elevation)
    # The database already has this as 3D, so I need to match it
    location = gis_models.PointField(
        srid=4326,
        dim=3,  # 3D coordinates (longitude, latitude, elevation)
        geography=False,
        verbose_name=_("Location"),
        help_text=_("Site coordinates (WGS84) with elevation")
    )
    
    # Elevation - can also get this from the Z coordinate in location
    elevation_meters = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(2000)],
        verbose_name=_("Elevation (m)"),
        help_text=_("Elevation above sea level in meters")
    )
    
    # Relationships - site belongs to a county and an era
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
    
    # What kind of site it is
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
    
    # When the site was built/used
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
    
    # How well preserved it is and special designations
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
    
    # Info for visitors - can they access it, is there a visitor center, etc.
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
    
    # Contact info and address
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
    
    # Tracking who created/modified records
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
    
    # Approval system - sites need to be approved before going live
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
    
    # Soft delete - don't actually delete, just mark as deleted
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Where the data came from and how good it is
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
    
    # Track how many times the site has been viewed
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
        """Gets lat/lon as a tuple - useful for the frontend"""
        if self.location:
            return (self.location.x, self.location.y)
        return None
    
    @property
    def latitude(self):
        """Gets just the latitude"""
        return self.location.y if self.location else None
    
    @property
    def longitude(self):
        """Gets just the longitude"""
        return self.location.x if self.location else None
    
    @property
    def elevation_from_geometry(self):
        """
        Gets elevation from the Z coordinate in the location field
        
        The location is a PointZ, so it has elevation built in. This checks
        if that's available, otherwise falls back to the elevation_meters field.
        """
        if self.location and self.location.z:
            return self.location.z
        return self.elevation_meters
    
    def distance_from(self, longitude, latitude):
        """
        Calculates distance to a point in kilometers
        
        Uses a rough conversion (1 degree ≈ 111 km) since we're dealing with
        lat/lon coordinates. For more accuracy, you'd use proper geodesic
        calculations, but this is good enough for most purposes.
        """
        from django.contrib.gis.geos import Point
        point = Point(longitude, latitude, srid=4326)
        # Rough conversion - 1 degree ≈ 111 km
        return self.location.distance(point) * 111
    
    def nearby_sites(self, radius_km=10, limit=10):
        """
        Finds other sites near this one
        
        Uses the manager's near_point method to find sites within a radius.
        Excludes itself from the results.
        """
        return HistoricalSite.objects.near_point(
            self.longitude,
            self.latitude,
            distance_km=radius_km
        ).exclude(pk=self.pk)[:limit]

# Site Image model
# Stores images that belong to sites

class SiteImage(models.Model):
    """
    Model for images associated with sites
    
    Sites can have multiple images. Each image has captions in both languages,
    metadata about the photographer, and display settings like whether it's
    the primary image or what order to show it in.
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
    
    # Image URL - images are stored externally, not in the database
    image_url = models.URLField(
        max_length=500,
        verbose_name=_("Image URL"),
        help_text=_("URL to image file")
    )
    
    # Titles and captions in both languages
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
    
    # Who took the photo and when
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
    
    # Image dimensions and file size
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
    
    # Display settings - which image shows first, what order they're in
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Image"),
        help_text=_("Use as main site image")
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_("Display Order")
    )
    
    # Copyright/license info
    license_type = models.CharField(
        db_column='license_type',  # Add db_column for consistency
        max_length=50,  # Match database: max_length=50
        blank=True,
        default='All Rights Reserved',  # Match database default
        verbose_name=_("License Type"),
        help_text=_("Copyright/license information")
    )
    
    # Who uploaded this image
    uploaded_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Uploaded By"),
        help_text=_("Username who uploaded this image")
    )
    
    # When it was added
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


# Site Source model
# Stores academic references and citations for sites

class SiteSource(models.Model):
    """
    Model for sources/citations
    
    These are academic references, books, papers, websites, etc. that document
    information about the site. Each source has a reliability score to indicate
    how trustworthy it is.
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
    
    # What kind of source it is and all the details
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
    
    # How reliable/trustworthy this source is
    reliability_score = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Reliability Score"),
        help_text=_("1=Questionable, 5=Highly reliable")
    )
    
    # When it was added and by whom
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
        """
        Generates a formatted citation string
        
        Combines author, year, title, and publisher into a basic citation
        format. Used when displaying sources on the site detail page.
        """
        parts = []
        if self.author:
            parts.append(self.author)
        if self.publication_year:
            parts.append(f"({self.publication_year})")
        parts.append(self.title)
        if self.publisher:
            parts.append(self.publisher)
        return ". ".join(parts)


# Bucket List model
# This is for the "My Journey" feature where users can save sites

class BucketListItem(models.Model):
    """
    Model for bucket list items - user's saved sites
    
    Users can add sites to their bucket list and mark them as visited. I'm
    using session keys instead of requiring login, so people can use it
    without creating an account. Each item can have a photo and caption
    that the user uploads when they visit.
    """

    STATUS_CHOICES = [
        ('wishlist', _('Wishlist - Want to Visit')),
        ('visited', _('Visited - Completed')),
    ]

    # Which site this bucket list item is for
    id = models.AutoField(primary_key=True)

    site = models.ForeignKey(
        HistoricalSite,
        on_delete=models.CASCADE,
        related_name='bucket_list_items',
        db_column='site_id',
        verbose_name=_("Historical Site"),
        help_text=_("Site on bucket list")
    )

    # Session key identifies which user this belongs to
    # No login required - just uses Django sessions
    session_key = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name=_("Session Key"),
        help_text=_("Django session key for anonymous user tracking")
    )

    # Whether it's on their wishlist or they've visited it
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='wishlist',
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of bucket list item")
    )

    # When they added it and when they visited
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Added At"),
        help_text=_("When item was added to bucket list")
    )

    visited_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Visited At"),
        help_text=_("When user marked site as visited")
    )

    # User can upload a photo and add a caption when they visit
    photo = models.ImageField(
        upload_to='bucket_photos/',
        null=True,
        blank=True,
        verbose_name=_("Photo"),
        help_text=_("User's photo from visit")
    )

    photo_caption = models.TextField(
        blank=True,
        verbose_name=_("Photo Caption"),
        help_text=_("User's notes or caption about their visit")
    )

    # Soft delete
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Deleted"),
        help_text=_("Soft delete flag")
    )

    class Meta:
        managed = True  # Django manages this table (new feature)
        db_table = 'bucket_list_item'
        ordering = ['-added_at']
        verbose_name = _("Bucket List Item")
        verbose_name_plural = _("Bucket List Items")
        indexes = [
            models.Index(fields=['session_key', 'status']),
            models.Index(fields=['site', 'session_key']),
            models.Index(fields=['status']),
        ]
        # Prevent duplicate entries - one user can't add the same site twice
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'session_key'],
                condition=models.Q(is_deleted=False),
                name='unique_active_bucket_item'
            )
        ]

    def __str__(self):
        return f"{self.session_key[:8]}... - {self.site.name_en} ({self.status})"

    def mark_as_visited(self):
        """
        Marks the item as visited and sets the timestamp
        
        Helper method to update status and timestamp in one go.
        """
        from django.utils import timezone
        self.status = 'visited'
        self.visited_at = timezone.now()
        self.save()

    def mark_as_wishlist(self):
        """
        Changes it back to wishlist status
        
        If they marked it visited by mistake, they can change it back.
        """
        self.status = 'wishlist'
        self.visited_at = None
        self.save()
