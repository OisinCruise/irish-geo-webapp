#!/usr/bin/env python3
"""Import NMS Archaeological Survey Data - FINAL VERSION"""
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
    try:
        if not itm_e or not itm_n:
            return None, None
        lon, lat = transformer.transform(float(itm_e), float(itm_n))
        return lon, lat
    except:
        return None, None

def map_site_type(class_desc):
    if not class_desc:
        return 'archaeological_site'
    desc = str(class_desc).lower()
    if 'castle' in desc: return 'castle'
    elif any(x in desc for x in ['church', 'abbey', 'monastery']): return 'monastery'
    elif any(x in desc for x in ['fort', 'ringfort', 'rath']): return 'fort'
    elif any(x in desc for x in ['tomb', 'burial', 'grave']): return 'burial_site'
    elif any(x in desc for x in ['stone circle', 'standing stone']): return 'stone_monument'
    elif 'well' in desc: return 'holy_well'
    elif 'battle' in desc: return 'battlefield'
    elif 'house' in desc: return 'historic_house'
    else: return 'archaeological_site'

def estimate_era(class_desc):
    if not class_desc: return 1
    desc = str(class_desc).lower()
    if any(x in desc for x in ['megalithic', 'neolithic', 'stone circle']): return 1
    elif 'early christian' in desc: return 2
    elif 'viking' in desc: return 3
    elif any(x in desc for x in ['norman', 'medieval', 'castle']): return 4
    else: return 1

def get_county_id(conn, county_name):
    if not county_name: return None
    cur = conn.cursor()
    try:
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
        execute_batch(cur, query, batch_data, page_size=500)
        return True, None
    except Exception as e:
        return False, str(e)

def import_nms_data(conn, csv_file):
    print(f"\n{'='*60}")
    print(f"NMS Archaeological Survey Data Import - FINAL")
    print(f"{'='*60}\n")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    cur = conn.cursor()
    total_rows = 0
    imported_rows = 0
    skipped_rows = 0
    batch_data = []
    BATCH_SIZE = 500
    error_count = 0
    seen_sites = set()  # Track SMR numbers to prevent duplicates
    
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            print(f"Processing monuments...\n")
            
            for row in reader:
                total_rows += 1
                
                if total_rows % 5000 == 0:
                    print(f"  Processed {total_rows:,} (Imported: {imported_rows:,}, Skipped: {skipped_rows:,}, Errors: {error_count})")
                
                try:
                    smr_no = row.get('SMRS', '').strip()  # Use SMRS as unique ID
                    if not smr_no:
                        smr_no = row.get('SMR_NO', '').strip()
                    
                    # Skip duplicates
                    if smr_no in seen_sites:
                        skipped_rows += 1
                        continue
                    
                    townland = row.get('TOWNLAND', '').strip()
                    county_name = row.get('COUNTY', '').strip()
                    class_desc = row.get('CLASSDESC', '').strip()
                    itm_e = row.get('ITM_E', '').strip()
                    itm_n = row.get('ITM_N', '').strip()
                    
                    if not itm_e or not itm_n:
                        skipped_rows += 1
                        continue
                    
                    lon, lat = transform_coordinates(itm_e, itm_n)
                    if lon is None or not (-11 < lon < -5 and 51 < lat < 56):
                        skipped_rows += 1
                        continue
                    
                    county_id = get_county_id(conn, county_name)
                    site_type = map_site_type(class_desc)
                    era_id = estimate_era(class_desc)
                    
                    # Create site name and TRUNCATE to 255 chars
                    if townland:
                        site_name = f"{townland} - {class_desc[:80]}"
                    else:
                        site_name = class_desc[:100]
                    site_name = site_name[:255]  # CRITICAL FIX
                    
                    # Truncate Irish name too
                    name_ga = (townland if townland else class_desc[:100])[:255]
                    
                    batch_data.append({
                        'name_en': site_name,
                        'name_ga': name_ga,
                        'description_en': f"SMR: {smr_no}. {class_desc}. Source: NMS.",
                        'description_ga': f"SMR: {smr_no}. {class_desc}.",
                        'longitude': lon,
                        'latitude': lat,
                        'county_id': county_id,
                        'era_id': era_id,
                        'site_type': site_type,
                        'significance_level': 2,
                        'preservation_status': 'archaeological',
                        'national_monument': False,
                        'approval_status': 'approved',
                        'data_source': 'National Monuments Service (2023)',
                        'data_quality': 5
                    })
                    
                    seen_sites.add(smr_no)  # Mark as processed
                    
                    # Insert batch
                    if len(batch_data) >= BATCH_SIZE:
                        success, error = insert_batch(cur, batch_data)
                        if success:
                            imported_rows += len(batch_data)
                            conn.commit()
                        else:
                            error_count += 1
                            print(f"\n  ✗ Batch error: {error}\n")
                            conn.rollback()
                        batch_data = []
                
                except Exception as e:
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
        
        print(f"\n{'='*60}")
        print(f"Import Complete!")
        print(f"{'='*60}")
        print(f"Total rows: {total_rows:,}")
        print(f"Imported: {imported_rows:,}")
        print(f"Skipped: {skipped_rows:,}")
        print(f"Batch errors: {error_count}")
        print(f"Success rate: {(imported_rows/total_rows*100):.1f}%")
        print(f"{'='*60}\n")
        
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
    csv_file = 'data/NMS_OpenData_20230823.csv'
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    conn = connect_db()
    try:
        create_historical_eras(conn)
        import_nms_data(conn, csv_file)
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
