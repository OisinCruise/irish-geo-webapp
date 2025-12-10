#!/usr/bin/env python3
"""
Import Site Image URLs (Option A - External URLs)
==================================================
Reads a CSV file with external image URLs (e.g., Wikimedia Commons)
and creates site_image records.

CSV Format:
    site_id,image_url,title_en,caption_en
    439137,https://upload.wikimedia.org/.../300px-Corcomroe_Abbey.jpg,Corcomroe Abbey,View of the abbey

Usage:
    python scripts/import_image_urls.py                    # Import from default CSV
    python scripts/import_image_urls.py data/images.csv   # Import from specific CSV
    python scripts/import_image_urls.py --template        # Generate CSV template
    python scripts/import_image_urls.py --list            # List sites without images

Wikimedia Commons URL Format:
    https://upload.wikimedia.org/wikipedia/commons/thumb/{hash}/{filename}/{width}px-{filename}
    
    Example (300px wide):
    https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Donegal_Castle.jpg/300px-Donegal_Castle.jpg
"""

import os
import sys
import csv
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sites.models import HistoricalSite, SiteImage


def import_image_urls(csv_file):
    """Import site image URLs from CSV"""
    print("=" * 70)
    print("SITE IMAGE URL IMPORT (Option A - External URLs)")
    print("=" * 70)
    print(f"\nCSV File: {csv_file}\n")

    imported = 0
    skipped = 0
    errors = 0

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                site_id = row.get('site_id', '').strip()
                image_url = row.get('image_url', '').strip()
                title_en = row.get('title_en', '').strip()
                caption_en = row.get('caption_en', '').strip()

                if not image_url:
                    skipped += 1
                    continue

                # Skip empty URLs or placeholder text
                if image_url.lower() in ['', 'url', 'todo', 'tbd', 'none']:
                    skipped += 1
                    continue

                # Try to find site by name (title_en) first, then by ID
                site = None
                if title_en:
                    # Try exact match first
                    site = HistoricalSite.objects.filter(name_en=title_en).first()
                    # If no exact match, try case-insensitive contains
                    if not site:
                        site = HistoricalSite.objects.filter(name_en__icontains=title_en.split(',')[0]).first()
                
                # Fallback to ID if provided
                if not site and site_id:
                    try:
                        site = HistoricalSite.objects.get(id=int(site_id))
                    except (HistoricalSite.DoesNotExist, ValueError):
                        pass
                
                if not site:
                    print(f"  ✗ Site not found: {title_en[:50] if title_en else site_id}")
                    errors += 1
                    continue

                # Check if image already exists for this site
                existing = SiteImage.objects.filter(site=site, image_url=image_url).first()
                if existing:
                    print(f"  - Skipping (exists): {site.name_en[:40]}")
                    skipped += 1
                    continue

                # Create the SiteImage record
                try:
                    # Mark any existing images as not primary
                    SiteImage.objects.filter(site=site, is_primary=True).update(is_primary=False)
                    
                    site_image = SiteImage.objects.create(
                        site=site,
                        image_url=image_url,
                        title_en=title_en or site.name_en[:255],
                        caption_en=caption_en[:500] if caption_en else '',
                        is_primary=True,
                        width_px=300,  # Standard width for Wikimedia thumbs
                        height_px=200,  # Approximate
                        is_public=True
                    )
                    imported += 1
                    print(f"  ✓ {site.name_en[:45]}")
                    
                except Exception as e:
                    print(f"  ✗ Error for site {site_id}: {e}")
                    errors += 1
                    continue

    except FileNotFoundError:
        print(f"ERROR: CSV file not found: {csv_file}")
        print("\nRun with --template to generate a CSV template first.")
        sys.exit(1)

    print()
    print("=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")
    print()


def list_sites():
    """List all sites with their current image status"""
    print("\n" + "=" * 70)
    print("ALL SITES - IMAGE STATUS")
    print("=" * 70 + "\n")
    
    sites = HistoricalSite.objects.filter(is_deleted=False).order_by('id')
    
    with_images = 0
    without_images = 0
    
    print(f"{'ID':<8} {'Has Image':<10} {'Name':<45} {'County':<15}")
    print("-" * 80)
    
    for site in sites:
        has_image = site.images.filter(is_primary=True).exists()
        county = site.county.name_en if site.county else 'Unknown'
        status = "✓" if has_image else "✗"
        print(f"{site.id:<8} {status:<10} {site.name_en[:43]:<45} {county:<15}")
        
        if has_image:
            with_images += 1
        else:
            without_images += 1
    
    print()
    print(f"With images:    {with_images}")
    print(f"Without images: {without_images}")
    print(f"Total:          {sites.count()}")
    print()


def generate_csv_template():
    """Generate a CSV template with all sites"""
    output_file = 'data/site_image_urls.csv'
    
    print(f"\nGenerating CSV template: {output_file}")
    
    sites = HistoricalSite.objects.filter(is_deleted=False).order_by('id')
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['site_id', 'image_url', 'title_en', 'caption_en'])
        
        for site in sites:
            # Check if already has an image
            existing_image = site.images.filter(is_primary=True).first()
            existing_url = existing_image.image_url if existing_image else ''
            
            writer.writerow([
                site.id,
                existing_url,  # Empty or existing URL
                site.name_en[:100],
                ''  # Empty caption for user to fill
            ])
    
    print(f"✓ Template created: {output_file}")
    print(f"  Contains {sites.count()} sites")
    print()
    print("INSTRUCTIONS:")
    print("=" * 70)
    print("1. Open the CSV file in a spreadsheet editor")
    print("2. For each site, find an image on Wikimedia Commons:")
    print("   https://commons.wikimedia.org/")
    print()
    print("3. Get the thumbnail URL (right-click image → Copy image address)")
    print("   Format: https://upload.wikimedia.org/.../300px-{filename}")
    print()
    print("4. Paste the URL in the 'image_url' column")
    print("5. Optionally add a caption")
    print("6. Save and run: python scripts/import_image_urls.py")
    print("=" * 70)
    print()


def show_help():
    """Show help information"""
    print("""
SITE IMAGE URL IMPORT SCRIPT
============================

This script imports external image URLs (e.g., Wikimedia Commons) into the database.

COMMANDS:
    python scripts/import_image_urls.py                  Import from data/site_image_urls.csv
    python scripts/import_image_urls.py path/to/file.csv Import from specific CSV
    python scripts/import_image_urls.py --template       Generate CSV template
    python scripts/import_image_urls.py --list           List all sites and image status
    python scripts/import_image_urls.py --help           Show this help

CSV FORMAT:
    site_id,image_url,title_en,caption_en
    439137,https://upload.wikimedia.org/.../300px-Example.jpg,Site Name,Optional caption

FINDING WIKIMEDIA IMAGES:
    1. Go to https://commons.wikimedia.org/
    2. Search for the site name (e.g., "Donegal Castle")
    3. Click on an image
    4. Right-click the image and select "Copy image address"
    5. Paste into your CSV

    Tip: Use 300px thumbnails for consistency:
    https://upload.wikimedia.org/wikipedia/commons/thumb/.../300px-Filename.jpg
""")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--list':
            list_sites()
        elif arg == '--template':
            generate_csv_template()
        elif arg == '--help':
            show_help()
        elif arg.startswith('-'):
            print(f"Unknown option: {arg}")
            show_help()
        else:
            import_image_urls(arg)
    else:
        # Default: import from standard location
        default_csv = 'data/site_image_urls.csv'
        if os.path.exists(default_csv):
            import_image_urls(default_csv)
        else:
            print("No CSV file found at data/site_image_urls.csv")
            print("Generating template...\n")
            generate_csv_template()

