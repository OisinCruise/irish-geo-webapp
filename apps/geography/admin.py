"""Django admin configuration for Geography models"""
from django.contrib.gis import admin
from .models import Province, County, HistoricalEra


@admin.register(Province)
class ProvinceAdmin(admin.GISModelAdmin):
    """Admin interface for Province model"""
    list_display = ['name_en', 'name_ga', 'code', 'area_km2', 'population', 'county_count']
    search_fields = ['name_en', 'name_ga', 'code']
    list_filter = ['is_deleted']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_en', 'name_ga', 'code')
        }),
        ('Geographic Data', {
            'fields': ('geometry', 'area_km2')
        }),
        ('Statistics', {
            'fields': ('population',)
        }),
        ('Descriptions', {
            'fields': ('description_en', 'description_ga'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 6,
            'default_lon': -8.0,
            'default_lat': 53.4,
        },
    }


@admin.register(County)
class CountyAdmin(admin.GISModelAdmin):
    """Admin interface for County model"""
    list_display = ['name_en', 'name_ga', 'code', 'province', 'area_km2', 'population', 'site_count']
    search_fields = ['name_en', 'name_ga', 'code']
    list_filter = ['province', 'is_deleted']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_en', 'name_ga', 'code', 'province')
        }),
        ('Geographic Data', {
            'fields': ('geometry', 'area_km2')
        }),
        ('Statistics', {
            'fields': ('population',)
        }),
        ('Descriptions', {
            'fields': ('description_en', 'description_ga'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(HistoricalEra)
class HistoricalEraAdmin(admin.ModelAdmin):
    """Admin interface for HistoricalEra model"""
    list_display = ['name_en', 'name_ga', 'start_year', 'end_year', 'duration_years', 'color_hex', 'display_order']
    search_fields = ['name_en', 'name_ga']
    list_filter = ['is_deleted']
    ordering = ['display_order', 'start_year']
    readonly_fields = ['created_at', 'updated_at', 'duration_years']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_en', 'name_ga')
        }),
        ('Time Period', {
            'fields': ('start_year', 'end_year', 'duration_years')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'color_hex')
        }),
        ('Descriptions', {
            'fields': ('description_en', 'description_ga')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
