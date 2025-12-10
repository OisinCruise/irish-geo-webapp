# Database Migration Guide: Neon → Render PostgreSQL

This guide will help you migrate your database from Neon PostgreSQL to Render PostgreSQL.

## Prerequisites

1. **PostgreSQL Client Tools** - You need `pg_dump`, `pg_restore`, and `psql` installed
   - macOS: `brew install postgresql`
   - Linux: `sudo apt-get install postgresql-client` (Ubuntu/Debian)
   - Windows: Download from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)

2. **Access to Both Databases**
   - Your Neon database connection string
   - Your Render PostgreSQL connection string (from Render Dashboard)

## Step-by-Step Migration Process

### Step 1: Create Render PostgreSQL Database

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name:** `irish-geo-db`
   - **Region:** `Frankfurt` (or your preferred region)
   - **PostgreSQL Version:** `16`
   - **Plan:** `Starter` (or upgrade as needed)
4. Click **"Create Database"**
5. Wait for the database to be provisioned (2-3 minutes)

### Step 2: Get Connection Strings

#### Neon Connection String
You already have this:
```
postgresql://neondb_owner:npg_tlhL12ZErOkS@ep-gentle-cake-a8ekv7j8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require
```

#### Render Connection String
1. In Render Dashboard, go to your PostgreSQL database
2. Click on **"Info"** tab
3. **For local migration (running from your computer):**
   - Use **"External Connection String"** 
   - This has the full hostname like: `dpg-xxxxx-a.frankfurt-postgres.render.com`
   - Example: `postgresql://irish_geo_user:password@dpg-xxxxx-a.frankfurt-postgres.render.com/irish_geo_db?sslmode=require`
4. **For Render web service (automatic):**
   - Use **"Internal Database URL"** (automatically provided via `DATABASE_URL` env var)
   - This is shorter and only works within Render's network
   - Example: `postgresql://irish_geo_user:password@dpg-xxxxx-a/irish_geo_db?sslmode=require`

**Important:** For the migration script running from your local machine, you MUST use the **External Connection String** with the full hostname (including `.frankfurt-postgres.render.com` or similar region domain).

### Step 3: Enable PostGIS on Render PostgreSQL

Before importing data, PostGIS must be enabled:

```bash
# Replace with your Render connection string
psql "postgresql://user:password@host:port/database?sslmode=require" \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS postgis_topology;"
```

Or use the migration script (see Step 4) which does this automatically.

### Step 4: Run Migration Script

The easiest way is to use the provided migration script:

```bash
# Set environment variables
export NEON_DATABASE_URL='postgresql://neondb_owner:npg_tlhL12ZErOkS@ep-gentle-cake-a8ekv7j8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require'
export RENDER_DATABASE_URL='postgresql://user:password@dpg-xxxxx-a.frankfurt-postgres.render.com/irish_geo_db?sslmode=require'

# Run migration
cd irish-geo-webapp
python scripts/migrate_neon_to_render.py
```

The script will:
- ✅ Check prerequisites
- ✅ Enable PostGIS extension
- ✅ Export data from Neon
- ✅ Import data to Render PostgreSQL
- ✅ Verify the migration

### Step 5: Manual Migration (Alternative)

If you prefer to do it manually:

```bash
# 1. Export from Neon
pg_dump "postgresql://neondb_owner:npg_tlhL12ZErOkS@ep-gentle-cake-a8ekv7j8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require" \
  --format=custom \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  --file=neon_backup.dump

# 2. Enable PostGIS on Render
psql "postgresql://user:password@host:port/database?sslmode=require" \
  -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 3. Import to Render
pg_restore "postgresql://user:password@host:port/database?sslmode=require" \
  --format=custom \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  --verbose \
  neon_backup.dump
```

### Step 6: Update Render Blueprint

The `render.yaml` file has been updated to include the PostgreSQL database service. When you deploy:

1. **If using Blueprint deployment:**
   - Push your changes to GitHub
   - Render will automatically detect the updated `render.yaml`
   - It will create both the database and web service
   - The web service will automatically be linked to the database

2. **If using manual deployment:**
   - Create the PostgreSQL database (if not already done)
   - Update your web service to link to the database
   - The `DATABASE_URL` environment variable will be automatically provided

### Step 7: Verify Migration

After migration, verify your data:

```bash
# Connect to Render database
psql "postgresql://user:password@host:port/database?sslmode=require"

# Check table counts
SELECT 'historical_site' as table_name, COUNT(*) FROM historical_site
UNION ALL
SELECT 'county', COUNT(*) FROM county
UNION ALL
SELECT 'province', COUNT(*) FROM province
UNION ALL
SELECT 'historical_era', COUNT(*) FROM historical_era;
```

Or use the Django shell:

```bash
python manage.py shell
```

```python
from apps.sites.models import HistoricalSite
from apps.geography.models import County, Province

print(f"Sites: {HistoricalSite.objects.count()}")
print(f"Counties: {County.objects.count()}")
print(f"Provinces: {Province.objects.count()}")
```

### Step 8: Test Your Application

1. **Deploy to Render** (if not already done)
2. **Test key functionality:**
   - Map loads and shows sites
   - API endpoints return data
   - Bucket list functionality works
   - Admin panel accessible

### Step 9: Clean Up

Once you've verified everything works:

1. ✅ Keep Neon database for a few days as backup
2. ✅ Monitor Render application for any issues
3. ✅ After 1-2 weeks of stable operation, you can delete the Neon database

## Troubleshooting

### Issue: "PostGIS extension not found"

**Solution:** Enable PostGIS manually:
```bash
psql "YOUR_RENDER_CONNECTION_STRING" -c "CREATE EXTENSION postgis;"
```

### Issue: "Permission denied" errors

**Solution:** The migration script uses `--no-owner` and `--no-acl` flags to avoid permission issues. If you still have problems, check that your Render database user has proper permissions.

### Issue: "Connection timeout"

**Solution:** 
- Check your connection string is correct
- Ensure you're using the correct host (internal vs external)
- Verify SSL mode is set to `require`

### Issue: "Table already exists" errors

**Solution:** The `--clean --if-exists` flags should handle this. If issues persist, you may need to drop and recreate the database on Render.

## Important Notes

1. **Backup First:** Always backup your Neon database before migration
2. **Downtime:** Plan for brief downtime during migration
3. **Data Size:** Large databases may take time to migrate
4. **PostGIS:** Must be enabled before importing spatial data
5. **Connection Strings:** Keep your connection strings secure - never commit them to git

## Support

If you encounter issues:
1. Check Render logs in the Dashboard
2. Review the migration script output
3. Verify both databases are accessible
4. Check PostgreSQL client tools are installed correctly

---

**Last Updated:** December 2025

