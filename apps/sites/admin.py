"""
Django admin configuration for sites models

This sets up the admin interface so I can manage sites, images, and sources
through Django's admin panel. I've organized the fields into fieldsets to
make it easier to edit.
"""
from django.contrib.gis import admin
from django.utils.html import format_html
from .models import HistoricalSite, SiteImage, SiteSource


class SiteImageInline(admin.TabularInline):
    """
    Inline editor for images
    
    Lets me add/edit images directly on the site edit page instead of
    having to go to a separate page. Shows one empty row by default.
    """
    model = SiteImage
    extra = 1
    fields = ['image_url', 'title_en', 'is_primary', 'display_order']
    readonly_fields = ['created_at']


class SiteSourceInline(admin.TabularInline):
    """
    Inline editor for sources
    
    Same idea - can add sources right on the site page.
    """
    model = SiteSource
    extra = 1
    fields = ['source_type', 'title', 'author', 'reliability_score']


@admin.register(HistoricalSite)
class HistoricalSiteAdmin(admin.GISModelAdmin):
    """
    Admin interface for sites
    
    Uses GISModelAdmin so I can edit the location on a map widget. I've
    organized fields into fieldsets to make editing easier. The actions
    let me bulk-approve or reject sites.
    """
    list_display = [
        'name_en', 'site_type', 'county', 'era', 
        'significance_level', 'national_monument', 
        'approval_status', 'created_at'
    ]
    search_fields = ['name_en', 'name_ga', 'description_en']
    list_filter = [
        'site_type', 'county', 'era', 'significance_level',
        'national_monument', 'unesco_site', 'approval_status', 'is_deleted'
    ]
    readonly_fields = ['created_at', 'updated_at', 'coordinates', 'elevation_from_geometry']
    inlines = [SiteImageInline, SiteSourceInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_en', 'name_ga', 'site_type')
        }),
        ('Location', {
            'fields': ('location', 'coordinates', 'elevation_meters', 'elevation_from_geometry', 'county')
        }),
        ('Historical Context', {
            'fields': ('era', 'date_established', 'date_abandoned', 'construction_period')
        }),
        ('Classification', {
            'fields': ('significance_level', 'preservation_status', 'national_monument', 'unesco_site')
        }),
        ('Descriptions', {
            'fields': ('description_en', 'description_ga')
        }),
        ('Visitor Information', {
            'fields': (
                'is_public_access', 'visitor_center', 'admission_required',
                'address', 'eircode', 'website_url', 'phone_number'
            ),
            'classes': ('collapse',)
        }),
        ('Data Quality', {
            'fields': ('data_source', 'data_quality', 'view_count'),
            'classes': ('collapse',)
        }),
        ('Moderation', {
            'fields': (
                'approval_status', 'created_by', 'modified_by',
                'approved_by', 'approved_at'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at', 'updated_at', 
                'is_deleted', 'deleted_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_sites', 'reject_sites', 'mark_as_national_monuments']
    
    def approve_sites(self, request, queryset):
        """
        Bulk approves selected sites
        
        Updates approval status and records who approved them and when.
        Useful when reviewing a bunch of pending sites at once.
        """
        from django.utils import timezone
        count = queryset.update(
            approval_status='approved',
            approved_by=request.user.username,
            approved_at=timezone.now()
        )
        self.message_user(request, f"{count} sites approved")
    approve_sites.short_description = "Approve selected sites"
    
    def reject_sites(self, request, queryset):
        """Bulk rejects selected sites"""
        count = queryset.update(approval_status='rejected')
        self.message_user(request, f"{count} sites rejected")
    reject_sites.short_description = "Reject selected sites"
    
    def mark_as_national_monuments(self, request, queryset):
        """
        Marks selected sites as national monuments
        
        Useful for bulk updating when I get a list of newly designated
        monuments.
        """
        count = queryset.update(national_monument=True)
        self.message_user(request, f"{count} sites marked as national monuments")
    mark_as_national_monuments.short_description = "Mark as National Monuments"


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    """
    Admin interface for images
    
    Lets me manage images separately if needed. Most of the time I use
    the inline editor on the site page, but this is useful for bulk edits.
    """
    list_display = ['site', 'title_en', 'is_primary', 'display_order', 'photographer', 'created_at']
    search_fields = ['title_en', 'title_ga', 'photographer', 'site__name_en']
    list_filter = ['is_primary', 'is_deleted', 'created_at']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Site Association', {
            'fields': ('site',)
        }),
        ('Image', {
            'fields': ('image_url', 'thumbnail_url', 'width_px', 'height_px', 'file_size_kb')
        }),
        ('Metadata', {
            'fields': (
                'title_en', 'title_ga', 'caption_en', 'caption_ga',
                'photographer', 'photo_date', 'alt_text'
            )
        }),
        ('Display Settings', {
            'fields': ('is_primary', 'display_order', 'is_public')
        }),
        ('Rights', {
            'fields': ('license_type', 'copyright_info'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('uploaded_by', 'created_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SiteSource)
class SiteSourceAdmin(admin.ModelAdmin):
    """
    Admin interface for sources
    
    Same idea - can manage sources separately or use the inline editor.
    The citation field is read-only since it's computed from other fields.
    """
    list_display = ['title', 'author', 'source_type', 'publication_year', 'reliability_score', 'site']
    search_fields = ['title', 'author', 'site__name_en']
    list_filter = ['source_type', 'reliability_score', 'is_deleted']
    readonly_fields = ['created_at', 'citation']
    
    fieldsets = (
        ('Site Association', {
            'fields': ('site',)
        }),
        ('Source Details', {
            'fields': (
                'source_type', 'title', 'author', 
                'publication_year', 'publisher'
            )
        }),
        ('Additional Information', {
            'fields': ('url', 'isbn', 'pages', 'notes')
        }),
        ('Quality', {
            'fields': ('reliability_score', 'citation')
        }),
        ('Audit', {
            'fields': ('added_by', 'created_at', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
