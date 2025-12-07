#!/usr/bin/env python3

"""Import NMS Monuments To Visit Data - MODIFIED FOR NEW CSV"""

import csv
import psycopg2
from psycopg2.extras import execute_batch
from pyproj import Transformer
import sys
from datetime import datetime

DB_CONFIG = {
    'dbname': 'irish_geo_db',
    'user': 'geo_user',
    'password': 'Genius1',
    'host': 'localhost',
    'port': '5432'
}

transformer = Transformer.from_crs("EPSG:2157", "EPSG:4326", always_xy=True)

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        print("✓ Database connection established")
        return conn
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)

def create_historical_eras(conn):
    cur = conn.cursor()
    eras = [
        ('Prehistoric Ireland', 'Éire Réamhstairiúil', -8000, 400, 1, '#8B4513',
         'Period before written records.', 'Tréimhse roimh thaifid scríofa.'),
        ('Early Christian Ireland', 'Luath-Chríostaí', 400, 800, 2, '#2E8B57',
         'Golden age of monasticism.', 'Ré órga mhainistireachta.'),
        ('Viking Age', 'Ré na Lochlanach', 795, 1014, 3, '#B22222',
         'Norse raids and settlements.', 'Ruathar Lochlannach.'),
        ('Norman Ireland', 'Éire Normannach', 1169, 1541, 4, '#4B0082',
         'Anglo-Norman invasion.', 'Ionradh Angla-Normannach.'),
        ('Tudor Period', 'Ré na dTiúdarach', 1541, 1603, 5, '#DC143C',
         'English conquest.', 'Concas Sasanach.'),
        ('17th Century', 'An 17ú hAois', 1600, 1700, 6, '#8B008B',
         'Century of war.', 'Aois chogaidh.'),
        ('18th Century', 'An 18ú hAois', 1700, 1800, 7, '#FF8C00',
         'Penal Laws.', 'Dlíthe Péindlithe.'),
        ('19th Century', 'An 19ú hAois', 1800, 1900, 8, '#1E90FF',
         'Famine and emigration.', 'Gorta agus eisimirce.'),
        ('20th Century', 'An 20ú hAois', 1900, 2000, 9, '#32CD32',
         'Independence.', 'Neamhspleáchas.')
    ]

    print("\nCreating historical eras...")
    for era in eras:
        try:
            cur.execute("""
                INSERT INTO historical_era (
                    name_en, name_ga, start_year, end_year, display_order,
                    color_hex, description_en, description_ga
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name_en) DO NOTHING
            """, era)
        except Exception as e:
            print(f"  Warning: {e}")
    conn.commit()
    print("✓ Historical eras ready")
    cur.close()

def transform_coordinates(itm_e, itm_n):
    """Transform ITM coordinates to WGS84 lat/lon"""
    try:
        if not itm_e or not itm_n:
            return None, None
        lon, lat = transformer.transform(float(itm_e), float(itm_n))
        return lon, lat
    except:
        return None, None

def map_site_type(class_desc):
    """Map monument class to site type"""
    if not class_desc:
        return 'archaeological_site'
    desc = str(class_desc).lower()
    if 'castle' in desc: return 'castle'
    elif any(x in desc for x in ['church', 'abbey', 'monastery', 'religious house']): return 'monastery'
    elif any(x in desc for x in ['fort', 'ringfort', 'rath']): return 'fort'
    elif any(x in desc for x in ['tomb', 'burial', 'grave']): return 'burial_site'
    elif any(x in desc for x in ['stone circle', 'standing stone', 'megalithic']): return 'stone_monument'
    elif 'well' in desc: return 'holy_well'
    elif 'battle' in desc: return 'battlefield'
    elif 'house' in desc: return 'historic_house'
    else: return 'archaeological_site'

def estimate_era(class_desc):
    """Estimate historical era from monument class"""
    if not class_desc: return 1
    desc = str(class_desc).lower()
    if any(x in desc for x in ['megalithic', 'neolithic', 'stone circle', 'passage tomb', 'portal tomb']): return 1
    elif 'early christian' in desc or 'round tower' in desc: return 2
    elif 'viking' in desc: return 3
    elif any(x in desc for x in ['norman', 'medieval', 'castle', 'cistercian', 'franciscan', 'dominican', 'augustinian']): return 4
    else: return 1

def get_county_id(conn, county_name):
    """Get county ID from name"""
    if not county_name: return None
    cur = conn.cursor()
    try:
        # Handle TIPPERARY NORTH/SOUTH → TIPPERARY
        if 'TIPPERARY' in county_name.upper():
            county_name = 'TIPPERARY'

        cur.execute("SELECT id FROM county WHERE LOWER(name_en) = LOWER(%s)", (county_name.strip(),))
        result = cur.fetchone()
        return result[0] if result else None
    except:
        return None
    finally:
        cur.close()

def insert_batch(cur, batch_data):
    """Batch insert with proper error handling"""
    query = """
        INSERT INTO historical_site (
            name_en, name_ga, description_en, description_ga,
            location, county_id, era_id, site_type,
            significance_level, preservation_status, national_monument,
            approval_status, data_source, data_quality
        ) VALUES (
            %(name_en)s, %(name_ga)s, %(description_en)s, %(description_ga)s,
            ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s, 0), 4326),
            %(county_id)s, %(era_id)s, %(site_type)s,
            %(significance_level)s, %(preservation_status)s, %(national_monument)s,
            %(approval_status)s, %(data_source)s, %(data_quality)s
        )
    """
    try:
        execute_batch(cur, query, batch_data, page_size=100)
        return True, None
    except Exception as e:
        return False, str(e)

def import_monuments_to_visit(conn, csv_file):
    """Import curated Monuments To Visit dataset"""
    print(f"\n{'='*70}")
    print(f"NMS MONUMENTS TO VISIT - Import (Featured Sites)")
    print(f"{'='*70}\n")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    cur = conn.cursor()
    total_rows = 0
    imported_rows = 0
    skipped_rows = 0
    batch_data = []
    BATCH_SIZE = 50
    error_count = 0
    seen_sites = set()

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            print(f"Processing featured monuments...\n")

            for row in reader:
                total_rows += 1

                try:
                    # CRITICAL: Use SMRS as unique identifier
                    smr_no = row.get('SMRS', '').strip()
                    if not smr_no:
                        skipped_rows += 1
                        continue

                    # Skip duplicates
                    if smr_no in seen_sites:
                        skipped_rows += 1
                        continue

                    # MODIFIED: LOCALITY instead of TOWNLAND
                    locality = row.get('LOCALITY', '').strip()

                    # IDENTICAL: COUNTY
                    county_name = row.get('COUNTY', '').strip()

                    # MODIFIED: MONUMENT_CLASS instead of CLASSDESC
                    monument_class = row.get('MONUMENT_CLASS', '').strip()

                    # NEW: Use direct NAME field
                    direct_name = row.get('NAME', '').strip()

                    # NEW: Rich description from MonumentsToVisit_INFO
                    rich_description = row.get('MonumentsToVisit_INFO', '').strip()

                    # NEW: External link for future use
                    external_link = row.get('external_link', '').strip()

                    # COORDINATES: Use direct lat/lon (already in WGS84)
                    try:
                        lat = float(row.get('LATITUDE', '').strip())
                        lon = float(row.get('LONGITUDE', '').strip())
                    except (ValueError, AttributeError):
                        # Fallback to ITM transformation
                        itm_e = row.get('ITM_E', '').strip()
                        itm_n = row.get('ITM_N', '').strip()
                        if not itm_e or not itm_n:
                            skipped_rows += 1
                            continue
                        lon, lat = transform_coordinates(itm_e, itm_n)
                        if lon is None:
                            skipped_rows += 1
                            continue

                    # Validate Ireland bounds
                    if not (-11 < lon < -5 and 51 < lat < 56):
                        skipped_rows += 1
                        continue

                    # Get county ID
                    county_id = get_county_id(conn, county_name)

                    # Map site type from MONUMENT_CLASS
                    site_type = map_site_type(monument_class)

                    # Estimate era from MONUMENT_CLASS
                    era_id = estimate_era(monument_class)

                    # Create site name (use direct NAME or construct from locality)
                    if direct_name:
                        site_name = direct_name[:255]
                    elif locality:
                        site_name = f"{locality} - {monument_class[:80]}"[:255]
                    else:
                        site_name = monument_class[:255]

                    # Irish name (use locality as fallback)
                    name_ga = (locality if locality else monument_class[:100])[:255]

                    # Enhanced description with rich info
                    if rich_description:
                        description_en = f"{rich_description[:800]}\n\nSMR: {smr_no}. Classification: {monument_class}."
                    else:
                        description_en = f"SMR: {smr_no}. {monument_class}. Featured monument to visit."

                    batch_data.append({
                        'name_en': site_name,
                        'name_ga': name_ga,
                        'description_en': description_en[:1000],
                        'description_ga': f"SMR: {smr_no}. {monument_class}.",
                        'longitude': lon,
                        'latitude': lat,
                        'county_id': county_id,
                        'era_id': era_id,
                        'site_type': site_type,
                        'significance_level': 4,
                        'preservation_status': 'good',
                        'national_monument': True,
                        'approval_status': 'approved',
                        'data_source': 'NMS Monuments To Visit (2023)',
                        'data_quality': 5
                    })

                    seen_sites.add(smr_no)

                    # Insert batch
                    if len(batch_data) >= BATCH_SIZE:
                        success, error = insert_batch(cur, batch_data)
                        if success:
                            imported_rows += len(batch_data)
                            conn.commit()
                            print(f"  ✓ Imported {imported_rows} monuments...")
                        else:
                            error_count += 1
                            print(f"\n  ✗ Batch error: {error}\n")
                            conn.rollback()
                        batch_data = []

                except Exception as e:
                    print(f"  ⚠ Row {total_rows} error: {e}")
                    skipped_rows += 1
                    continue

            # Insert remaining batch
            if batch_data:
                success, error = insert_batch(cur, batch_data)
                if success:
                    imported_rows += len(batch_data)
                    conn.commit()
                else:
                    error_count += 1
                    print(f"\n  ✗ Final batch error: {error}\n")
                    conn.rollback()

            print(f"\n{'='*70}")
            print(f"Import Complete!")
            print(f"{'='*70}")
            print(f"Total rows processed: {total_rows:,}")
            print(f"Successfully imported: {imported_rows:,}")
            print(f"Skipped: {skipped_rows:,}")
            print(f"Batch errors: {error_count}")
            print(f"Success rate: {(imported_rows/total_rows*100):.1f}%" if total_rows > 0 else "N/A")
            print(f"{'='*70}\n")

    except FileNotFoundError:
        print(f"\n✗ File not found: {csv_file}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Import failed: {e}\n")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()

def main():
    csv_file = 'data/NMSMonumentsToVisit.csv'  # MODIFIED: New CSV file

    if len(sys.argv) > 1:
        csv_file = sys.argv[1]

    conn = connect_db()
    try:
        create_historical_eras(conn)
        import_monuments_to_visit(conn, csv_file)
        print("✓ Import completed successfully!\n")
    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
