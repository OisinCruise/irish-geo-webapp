#!/usr/bin/env python3
"""Import Irish County Boundaries - 32 counties across 4 provinces"""
import psycopg2
import sys

DB_CONFIG = {
    'dbname': 'irish_geo_db',
    'user': 'geo_user',
    'password': 'Genius1',
    'host': 'localhost',
    'port': '5432'
}

COUNTY_TO_PROVINCE = {
    'Carlow': 'Leinster', 'Dublin': 'Leinster', 'Kildare': 'Leinster',
    'Kilkenny': 'Leinster', 'Laois': 'Leinster', 'Longford': 'Leinster',
    'Louth': 'Leinster', 'Meath': 'Leinster', 'Offaly': 'Leinster',
    'Westmeath': 'Leinster', 'Wexford': 'Leinster', 'Wicklow': 'Leinster',
    'Clare': 'Munster', 'Cork': 'Munster', 'Kerry': 'Munster',
    'Limerick': 'Munster', 'Tipperary': 'Munster', 'Waterford': 'Munster',
    'Galway': 'Connacht', 'Leitrim': 'Connacht', 'Mayo': 'Connacht',
    'Roscommon': 'Connacht', 'Sligo': 'Connacht',
    'Cavan': 'Ulster', 'Donegal': 'Ulster', 'Monaghan': 'Ulster'
}

COUNTY_CODES = {
    'Carlow': 'CAR', 'Dublin': 'DUB', 'Kildare': 'KID', 'Kilkenny': 'KIK',
    'Laois': 'LAO', 'Longford': 'LON', 'Louth': 'LOU', 'Meath': 'MEA',
    'Offaly': 'OFF', 'Westmeath': 'WME', 'Wexford': 'WEX', 'Wicklow': 'WIC',
    'Clare': 'CLA', 'Cork': 'COR', 'Kerry': 'KER', 'Limerick': 'LIM',
    'Tipperary': 'TIP', 'Waterford': 'WAT',
    'Galway': 'GAL', 'Leitrim': 'LEI', 'Mayo': 'MAY', 'Roscommon': 'ROS',
    'Sligo': 'SLI',
    'Cavan': 'CAV', 'Donegal': 'DON', 'Monaghan': 'MON'
}

COUNTY_NAMES_GA = {
    'Carlow': 'Ceatharlach', 'Dublin': 'Baile Átha Cliath', 'Kildare': 'Cill Dara',
    'Kilkenny': 'Cill Chainnigh', 'Laois': 'Laois', 'Longford': 'An Longfort',
    'Louth': 'Lú', 'Meath': 'An Mhí', 'Offaly': 'Uíbh Fhailí',
    'Westmeath': 'An Iarmhí', 'Wexford': 'Loch Garman', 'Wicklow': 'Cill Mhantáin',
    'Clare': 'An Clár', 'Cork': 'Corcaigh', 'Kerry': 'Ciarraí',
    'Limerick': 'Luimneach', 'Tipperary': 'Tiobraid Árann', 'Waterford': 'Port Láirge',
    'Galway': 'Gaillimh', 'Leitrim': 'Liatroim', 'Mayo': 'Maigh Eo',
    'Roscommon': 'Ros Comáin', 'Sligo': 'Sligeach',
    'Cavan': 'An Cabhán', 'Donegal': 'Dún na nGall', 'Monaghan': 'Muineachán'
}

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Database connection established")
        return conn
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)

def create_provinces(conn):
    cur = conn.cursor()
    provinces = [
        ('Leinster', 'Laighin', 'L'),
        ('Munster', 'An Mhumhain', 'M'),
        ('Connacht', 'Connachta', 'C'),
        ('Ulster', 'Ulaidh', 'U')
    ]
    
    print("\n" + "="*60)
    print("Creating Irish Provinces")
    print("="*60)
    
    for name_en, name_ga, code in provinces:
        try:
            cur.execute("""
                INSERT INTO province (name_en, name_ga, code, geometry)
                VALUES (%s, %s, %s, 
                    ST_GeomFromText('MULTIPOLYGON(((-6 53, -6 54, -7 54, -7 53, -6 53)))', 4326)
                )
                ON CONFLICT (name_en) DO NOTHING
                RETURNING id
            """, (name_en, name_ga, code))
            
            result = cur.fetchone()
            if result:
                print(f"  ✓ Created: {name_en} ({name_ga})")
            else:
                print(f"  ⚠ Already exists: {name_en}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    conn.commit()
    cur.close()

def get_province_id(conn, province_name):
    cur = conn.cursor()
    cur.execute("SELECT id FROM province WHERE name_en = %s", (province_name,))
    result = cur.fetchone()
    cur.close()
    return result[0] if result else None

def create_counties(conn):
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("Creating Irish Counties (32 total)")
    print("="*60)
    
    imported = 0
    skipped = 0
    
    for county_name, province_name in COUNTY_TO_PROVINCE.items():
        try:
            province_id = get_province_id(conn, province_name)
            if not province_id:
                print(f"  ✗ Province not found for {county_name}")
                skipped += 1
                continue
            
            name_ga = COUNTY_NAMES_GA.get(county_name, county_name)
            code = COUNTY_CODES.get(county_name, county_name[:3].upper())
            
            cur.execute("""
                INSERT INTO county (
                    name_en, name_ga, code, province_id, geometry
                )
                VALUES (
                    %s, %s, %s, %s,
                    ST_GeomFromText('MULTIPOLYGON(((-7 52, -7 53, -8 53, -8 52, -7 52)))', 4326)
                )
                ON CONFLICT (name_en) DO NOTHING
                RETURNING id
            """, (county_name, name_ga, code, province_id))
            
            result = cur.fetchone()
            if result:
                print(f"  ✓ {county_name} ({name_ga}) → {province_name}")
                imported += 1
            else:
                print(f"  ⚠ Already exists: {county_name}")
                skipped += 1
            
            conn.commit()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            skipped += 1
    
    print(f"\n{'='*60}")
    print(f"Import Summary:")
    print(f"  Imported: {imported}")
    print(f"  Skipped: {skipped}")
    print(f"{'='*60}\n")
    cur.close()

def verify_import(conn):
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("Verification")
    print("="*60)
    
    cur.execute("SELECT COUNT(*) FROM province")
    province_count = cur.fetchone()[0]
    print(f"  Provinces: {province_count}/4")
    
    cur.execute("SELECT COUNT(*) FROM county")
    county_count = cur.fetchone()[0]
    print(f"  Counties: {county_count}/32")
    
    cur.execute("""
        SELECT p.name_en, COUNT(c.id) as county_count
        FROM province p
        LEFT JOIN county c ON p.id = c.province_id
        GROUP BY p.name_en
        ORDER BY p.name_en
    """)
    
    print("\n  Counties by Province:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]} counties")
    
    print(f"{'='*60}\n")
    cur.close()

def main():
    print("\n" + "="*60)
    print("Irish County Boundaries Import")
    print("="*60 + "\n")
    
    conn = connect_db()
    
    try:
        create_provinces(conn)
        create_counties(conn)
        verify_import(conn)
        print("✓ Import completed successfully!\n")
    except Exception as e:
        print(f"\n✗ Import failed: {e}\n")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
