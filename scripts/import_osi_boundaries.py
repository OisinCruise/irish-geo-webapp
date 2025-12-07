#!/usr/bin/env python
"""
Import OSi Counties - FIXED VERSION
Handles council name format (e.g., "DUBLIN CITY COUNCIL" -> "Dublin")
"""

import os
import sys
import django
import json
import re

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from apps.geography.models import Province, County
from django.db import transaction

COUNTY_MAPPING = {
    'CARLOW': {'name_en': 'Carlow', 'name_ga': 'Ceatharlach', 'code': 'CW'},
    'CAVAN': {'name_en': 'Cavan', 'name_ga': 'An Cabhán', 'code': 'CN'},
    'CLARE': {'name_en': 'Clare', 'name_ga': 'An Clár', 'code': 'CE'},
    'CORK': {'name_en': 'Cork', 'name_ga': 'Corcaigh', 'code': 'C'},
    'DONEGAL': {'name_en': 'Donegal', 'name_ga': 'Dún na nGall', 'code': 'DL'},
    'DUBLIN': {'name_en': 'Dublin', 'name_ga': 'Baile Átha Cliath', 'code': 'D'},
    'GALWAY': {'name_en': 'Galway', 'name_ga': 'Gaillimh', 'code': 'G'},
    'KERRY': {'name_en': 'Kerry', 'name_ga': 'Ciarraí', 'code': 'KY'},
    'KILDARE': {'name_en': 'Kildare', 'name_ga': 'Cill Dara', 'code': 'KE'},
    'KILKENNY': {'name_en': 'Kilkenny', 'name_ga': 'Cill Chainnigh', 'code': 'KK'},
    'LAOIS': {'name_en': 'Laois', 'name_ga': 'Laois', 'code': 'LS'},
    'LEITRIM': {'name_en': 'Leitrim', 'name_ga': 'Liatroim', 'code': 'LM'},
    'LIMERICK': {'name_en': 'Limerick', 'name_ga': 'Luimneach', 'code': 'LK'},
    'LONGFORD': {'name_en': 'Longford', 'name_ga': 'An Longfort', 'code': 'LD'},
    'LOUTH': {'name_en': 'Louth', 'name_ga': 'Lú', 'code': 'LH'},
    'MAYO': {'name_en': 'Mayo', 'name_ga': 'Maigh Eo', 'code': 'MO'},
    'MEATH': {'name_en': 'Meath', 'name_ga': 'An Mhí', 'code': 'MH'},
    'MONAGHAN': {'name_en': 'Monaghan', 'name_ga': 'Muineachán', 'code': 'MN'},
    'OFFALY': {'name_en': 'Offaly', 'name_ga': 'Uíbh Fhailí', 'code': 'OY'},
    'ROSCOMMON': {'name_en': 'Roscommon', 'name_ga': 'Ros Comáin', 'code': 'RN'},
    'SLIGO': {'name_en': 'Sligo', 'name_ga': 'Sligeach', 'code': 'SO'},
    'TIPPERARY': {'name_en': 'Tipperary', 'name_ga': 'Tiobraid Árann', 'code': 'TA'},
    'WATERFORD': {'name_en': 'Waterford', 'name_ga': 'Port Láirge', 'code': 'WD'},
    'WESTMEATH': {'name_en': 'Westmeath', 'name_ga': 'An Iarmhí', 'code': 'WH'},
    'WEXFORD': {'name_en': 'Wexford', 'name_ga': 'Loch Garman', 'code': 'WX'},
    'WICKLOW': {'name_en': 'Wicklow', 'name_ga': 'Cill Mhantáin', 'code': 'WW'},
    # Handle Dublin sub-counties
    'SOUTH DUBLIN': {'name_en': 'Dublin', 'name_ga': 'Baile Átha Cliath', 'code': 'D', 'merge': True},
    'FINGAL': {'name_en': 'Dublin', 'name_ga': 'Baile Átha Cliath', 'code': 'D', 'merge': True},
    'DUN LAOGHAIRE-RATHDOWN': {'name_en': 'Dublin', 'name_ga': 'Baile Átha Cliath', 'code': 'D', 'merge': True},
}

def extract_county_name(council_name):
    """
    Extract county name from council name.
    Examples:
      "DUBLIN CITY COUNCIL" -> "DUBLIN"
      "CORK COUNTY COUNCIL" -> "CORK"
      "LIMERICK CITY AND COUNTY COUNCIL" -> "LIMERICK"
    """
    if not council_name:
        return None

    # Remove common suffixes (order matters - check longer patterns first)
    name = council_name.upper().strip()
    name = re.sub(r'\s+CITY\s+AND\s+COUNTY\s+COUNCIL$', '', name)
    name = re.sub(r'\s+(CITY|COUNTY)\s+COUNCIL$', '', name)
    name = re.sub(r'\s+COUNCIL$', '', name)

    return name.strip()

def import_counties():
    """Import ROI counties with detailed boundaries"""
    print("=" * 80)
    print("IMPORTING COUNTIES (Republic of Ireland)")
    print("=" * 80)

    filepath = 'data/Counties___OSi_National_Statutory_Boundaries_7976842105364698409.geojson'

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    print(f"\n✓ Found {len(features)} administrative units in GeoJSON")

    # Get province mappings
    province_map = {}
    for prov in Province.objects.all():
        province_map[prov.name_en] = prov

    print(f"✓ Loaded {len(province_map)} provinces from database\n")

    updated = 0
    created = 0
    skipped = 0
    merged = 0

    # Track which counties we've already processed (for Dublin merge)
    processed_counties = set()

    with transaction.atomic():
        for feature in features:
            props = feature['properties']

            # Get the council name
            council_name = (props.get('ENGLISH') or 
                          props.get('COUNTY') or 
                          props.get('COUNTYNAME') or
                          props.get('NAME_TAG'))

            province_name = props.get('PROVINCE')

            if not council_name:
                print(f"  ⚠ Skipping: No name found in properties")
                skipped += 1
                continue

            # Extract county name from council name
            county_key = extract_county_name(council_name)

            if not county_key or county_key not in COUNTY_MAPPING:
                print(f"  ⚠ Skipping: {council_name} (no mapping for '{county_key}')")
                skipped += 1
                continue

            mapping = COUNTY_MAPPING[county_key]
            county_name = mapping['name_en']

            # Handle Dublin sub-counties (merge into Dublin)
            if mapping.get('merge') and county_name in processed_counties:
                print(f"  ⊕ Merging: {council_name} -> {county_name} (already processed)")
                merged += 1
                continue

            # Get province
            province = province_map.get(province_name)
            if not province:
                print(f"  ⚠ Warning: Province '{province_name}' not found for {council_name}")
                skipped += 1
                continue

            # Convert geometry
            geom_json = json.dumps(feature['geometry'])
            geometry = GEOSGeometry(geom_json, srid=4326)

            if geometry.geom_type == 'Polygon':
                geometry = MultiPolygon(geometry)

            # Update or create county
            county, created_flag = County.objects.update_or_create(
                name_en=county_name,
                defaults={
                    'name_ga': mapping['name_ga'],
                    'code': mapping['code'],
                    'province': province,
                    'geometry': geometry,
                }
            )

            processed_counties.add(county_name)

            if created_flag:
                created += 1
                print(f"  ✓ Created: {county.name_en} ({council_name}) -> {province.name_en}")
            else:
                updated += 1
                print(f"  ✓ Updated: {county.name_en} ({council_name}) -> {province.name_en}")

    print("\n" + "=" * 80)
    print("IMPORT COMPLETE")
    print("=" * 80)
    print(f"  ✓ Created: {created}")
    print(f"  ✓ Updated: {updated}")
    print(f"  ⊕ Merged (Dublin sub-counties): {merged}")
    print(f"  ⚠ Skipped: {skipped}")
    print(f"  📊 Total counties in database: {created + updated}")

    # Verify
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    total_counties = County.objects.count()
    print(f"  Total counties: {total_counties}")

    for prov in Province.objects.all():
        count = prov.counties.count()
        counties = prov.counties.values_list('name_en', flat=True)
        print(f"  • {prov.name_en}: {count} counties - {', '.join(sorted(counties))}")

    # Check geometry detail
    print("\n" + "=" * 80)
    print("GEOMETRY DETAIL CHECK")
    print("=" * 80)
    from django.db.models import Count

    for county in County.objects.all()[:5]:  # Show first 5
        point_count = county.geometry.num_points if county.geometry else 0
        print(f"  {county.name_en}: {point_count:,} points")

if __name__ == '__main__':
    import_counties()
