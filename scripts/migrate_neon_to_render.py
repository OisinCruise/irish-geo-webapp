#!/usr/bin/env python3
"""
Database Migration Script: Neon PostgreSQL to Render PostgreSQL

This script migrates your database from Neon to Render PostgreSQL.
It exports all data from Neon and imports it into Render PostgreSQL.

Usage:
    python scripts/migrate_neon_to_render.py

Prerequisites:
    1. Install pg_dump and psql (PostgreSQL client tools)
    2. Set environment variables:
       - NEON_DATABASE_URL: Your Neon connection string
       - RENDER_DATABASE_URL: Your Render PostgreSQL connection string
    3. Ensure both databases are accessible

Example:
    export NEON_DATABASE_URL='postgresql://neondb_owner:password@ep-gentle-cake-a8ekv7j8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require'
    export RENDER_DATABASE_URL='postgresql://user:password@dpg-xxxxx-a.oregon-postgres.render.com/irish_geo_db?sslmode=require'
    python scripts/migrate_neon_to_render.py
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_step(message):
    """Print a step message."""
    print(f"{BLUE}→ {message}{RESET}")


def print_success(message):
    """Print a success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_warning(message):
    """Print a warning message."""
    print(f"{YELLOW}⚠ {message}{RESET}")


def print_error(message):
    """Print an error message."""
    print(f"{RED}✗ {message}{RESET}")


def check_command(command):
    """Check if a command is available."""
    try:
        subprocess.run(
            [command, '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_command(command, description, check=True):
    """Run a shell command and handle errors."""
    print_step(description)
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {e}")
        if e.stderr:
            print(e.stderr)
        return False


def validate_render_connection_string(connection_string):
    """Validate Render PostgreSQL connection string format."""
    import urllib.parse
    url = urllib.parse.urlparse(connection_string)
    
    # Check if hostname looks incomplete (missing .render.com domain)
    if url.hostname and not '.' in url.hostname:
        return False, "Hostname appears incomplete. Render PostgreSQL hostnames should include the full domain (e.g., dpg-xxxxx-a.frankfurt-postgres.render.com)"
    
    # Check for common Render PostgreSQL hostname patterns
    if url.hostname and 'render.com' not in url.hostname:
        return False, "Hostname doesn't appear to be a Render PostgreSQL hostname. Should contain 'render.com'"
    
    return True, None


def enable_postgis(connection_string):
    """Enable PostGIS extension on the target database."""
    print_step("Enabling PostGIS extension on Render PostgreSQL...")
    
    # Validate connection string first
    is_valid, error_msg = validate_render_connection_string(connection_string)
    if not is_valid:
        print_error(error_msg)
        print_warning("\nTo find your correct Render PostgreSQL connection string:")
        print("1. Go to Render Dashboard → Your PostgreSQL Database")
        print("2. Click on the 'Info' tab")
        print("3. Look for 'External Connection String' (for local access)")
        print("   OR 'Internal Database URL' (for use within Render)")
        print("4. The hostname should look like: dpg-xxxxx-a.frankfurt-postgres.render.com")
        print("   (or similar with your region)")
        return False
    
    # Extract connection details for psql
    # Format: postgresql://user:password@host:port/database?sslmode=require
    import urllib.parse
    url = urllib.parse.urlparse(connection_string)
    
    # Preserve query parameters from original URL
    query_params = urllib.parse.parse_qs(url.query)
    query_params['sslmode'] = ['require']  # Ensure SSL is required
    
    # Rebuild query string
    query_string = urllib.parse.urlencode(query_params, doseq=True)
    
    # Build psql connection string with proper port
    port = url.port or 5432
    psql_conn = f"postgresql://{url.username}:{url.password}@{url.hostname}:{port}/{url.path[1:]}?{query_string}"
    
    # Enable PostGIS extension
    enable_postgis_cmd = f'psql "{psql_conn}" -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS postgis_topology;"'
    
    if run_command(enable_postgis_cmd, "Creating PostGIS extension"):
        print_success("PostGIS extension enabled")
        return True
    else:
        print_error("Failed to enable PostGIS extension")
        print_warning("\nTroubleshooting tips:")
        print("1. Verify your connection string is correct")
        print("2. Check that you're using the 'External Connection String' from Render Dashboard")
        print("3. Ensure your IP is allowed (if database has IP restrictions)")
        print("4. Try connecting manually: psql \"YOUR_CONNECTION_STRING\"")
        return False


def export_from_neon(neon_url, output_file):
    """Export database from Neon using pg_dump."""
    print_step("Exporting database from Neon...")
    
    # Use pg_dump with custom format for better compatibility
    # --no-owner: Don't output commands to set ownership
    # --no-acl: Don't output access privileges
    # --clean: Include commands to drop objects before creating
    # --if-exists: Use IF EXISTS when dropping objects
    dump_cmd = (
        f'pg_dump "{neon_url}" '
        f'--format=custom '
        f'--no-owner '
        f'--no-acl '
        f'--clean '
        f'--if-exists '
        f'--file="{output_file}"'
    )
    
    if run_command(dump_cmd, "Running pg_dump on Neon database"):
        # Check file size to verify export succeeded
        file_size = os.path.getsize(output_file)
        print_success(f"Database exported to {output_file} ({file_size / 1024 / 1024:.2f} MB)")
        return True
    else:
        print_error("Failed to export database from Neon")
        return False


def import_to_render(render_url, dump_file):
    """Import database to Render PostgreSQL using pg_restore."""
    print_step("Importing database to Render PostgreSQL...")
    
    # Validate connection string
    is_valid, error_msg = validate_render_connection_string(render_url)
    if not is_valid:
        print_error(error_msg)
        return False
    
    # Extract connection details and preserve query parameters
    import urllib.parse
    url = urllib.parse.urlparse(render_url)
    query_params = urllib.parse.parse_qs(url.query)
    query_params['sslmode'] = ['require']
    query_string = urllib.parse.urlencode(query_params, doseq=True)
    port = url.port or 5432
    psql_conn = f"postgresql://{url.username}:{url.password}@{url.hostname}:{port}/{url.path[1:]}?{query_string}"
    
    # Use pg_restore with custom format
    # -d or --dbname: Connection string (required flag, not positional)
    # --no-owner: Don't output commands to set ownership
    # --no-acl: Don't output access privileges
    # --clean: Clean (drop) database objects before recreating
    # --if-exists: Use IF EXISTS when dropping objects
    # --exit-on-error: Exit immediately on error (we'll handle warnings separately)
    restore_cmd = (
        f'pg_restore '
        f'--dbname="{psql_conn}" '
        f'--format=custom '
        f'--no-owner '
        f'--no-acl '
        f'--clean '
        f'--if-exists '
        f'--verbose '
        f'"{dump_file}" 2>&1'
    )
    
    print_step("Running pg_restore on Render database")
    result = subprocess.run(
        restore_cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    
    # Check output for known non-critical errors
    output = result.stdout + result.stderr
    critical_errors = []
    warnings = []
    
    # Known non-critical errors (Neon-specific settings that don't exist in standard PostgreSQL)
    non_critical_patterns = [
        'unrecognized configuration parameter "transaction_timeout"',
        'cannot drop extension postgis because other objects depend on it',
        'errors ignored on restore',
    ]
    
    # Check for critical errors (anything not matching non-critical patterns)
    if result.returncode != 0:
        lines = output.split('\n')
        for line in lines:
            line_lower = line.lower()
            if 'error:' in line_lower:
                is_non_critical = any(pattern in line_lower for pattern in non_critical_patterns)
                if is_non_critical:
                    warnings.append(line.strip())
                else:
                    critical_errors.append(line.strip())
    
    # Print warnings
    if warnings:
        print_warning(f"Non-critical warnings encountered ({len(warnings)}):")
        for warning in warnings[:5]:  # Show first 5
            print(f"  ⚠ {warning}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more warnings")
        print("  (These are expected when migrating from Neon to standard PostgreSQL)")
    
    # Check if we have critical errors
    if critical_errors:
        print_error("Critical errors encountered:")
        for error in critical_errors[:10]:  # Show first 10
            print(f"  ✗ {error}")
        return False
    
    # If we got here, either success or only non-critical warnings
    if result.returncode == 0:
        print_success("Database imported to Render PostgreSQL")
        return True
    elif warnings and not critical_errors:
        # Exit code 1 but only non-critical warnings - likely successful
        print_warning("Import completed with warnings (this is normal when migrating from Neon)")
        print_success("Database imported to Render PostgreSQL")
        return True
    else:
        print_error("Failed to import database to Render")
        if output:
            print("Last 20 lines of output:")
            for line in output.split('\n')[-20:]:
                print(f"  {line}")
        return False


def verify_migration(render_url):
    """Verify the migration by checking table counts."""
    print_step("Verifying migration...")
    
    import urllib.parse
    url = urllib.parse.urlparse(render_url)
    psql_conn = f"postgresql://{url.username}:{url.password}@{url.hostname}:{url.port or 5432}/{url.path[1:]}?sslmode=require"
    
    # Check key tables
    tables_to_check = [
        'historical_site',
        'county',
        'province',
        'historical_era',
        'site_image',
        'bucket_list_item'
    ]
    
    all_good = True
    for table in tables_to_check:
        check_cmd = f'psql "{psql_conn}" -t -c "SELECT COUNT(*) FROM {table};"'
        result = subprocess.run(
            check_cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            count = result.stdout.strip()
            print_success(f"Table '{table}': {count} rows")
        else:
            print_warning(f"Could not verify table '{table}'")
            all_good = False
    
    return all_good


def main():
    """Main migration function."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Database Migration: Neon → Render PostgreSQL{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Check prerequisites
    print_step("Checking prerequisites...")
    if not check_command('pg_dump'):
        print_error("pg_dump not found. Please install PostgreSQL client tools.")
        sys.exit(1)
    if not check_command('pg_restore'):
        print_error("pg_restore not found. Please install PostgreSQL client tools.")
        sys.exit(1)
    if not check_command('psql'):
        print_error("psql not found. Please install PostgreSQL client tools.")
        sys.exit(1)
    print_success("All required tools are available")
    
    # Get connection strings
    neon_url = os.environ.get('NEON_DATABASE_URL', '')
    render_url = os.environ.get('RENDER_DATABASE_URL', '')
    
    if not neon_url:
        print_error("NEON_DATABASE_URL environment variable not set")
        print("Example: export NEON_DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'")
        sys.exit(1)
    
    if not render_url:
        print_error("RENDER_DATABASE_URL environment variable not set")
        print("Example: export RENDER_DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'")
        print("\nYou can find your Render connection string in:")
        print("  Render Dashboard → Your Database → Info → External Connection String")
        print("\n  ⚠️  IMPORTANT: Use 'External Connection String' (not Internal)")
        print("     The External Connection String has the full hostname like:")
        print("     dpg-xxxxx-a.frankfurt-postgres.render.com")
        print("     (Internal URL only works from within Render's network)")
        sys.exit(1)
    
    print_success("Connection strings found")
    
    # Create temporary file for dump
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dump') as tmp_file:
        dump_file = tmp_file.name
    
    try:
        # Step 1: Enable PostGIS on Render
        if not enable_postgis(render_url):
            print_error("Failed to enable PostGIS. Migration aborted.")
            sys.exit(1)
        
        # Step 2: Export from Neon
        if not export_from_neon(neon_url, dump_file):
            print_error("Failed to export from Neon. Migration aborted.")
            sys.exit(1)
        
        # Step 3: Import to Render
        if not import_to_render(render_url, dump_file):
            print_error("Failed to import to Render. Migration aborted.")
            sys.exit(1)
        
        # Step 4: Verify migration
        if not verify_migration(render_url):
            print_warning("Migration completed but verification had issues")
        else:
            print_success("Migration verified successfully")
        
        print(f"\n{GREEN}{'='*60}{RESET}")
        print(f"{GREEN}  Migration completed successfully!{RESET}")
        print(f"{GREEN}{'='*60}{RESET}\n")
        
        print("Next steps:")
        print("1. Update your Render web service to use the new database")
        print("2. Test your application thoroughly")
        print("3. Once verified, you can decommission your Neon database")
        
    except KeyboardInterrupt:
        print_error("\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary file
        if os.path.exists(dump_file):
            os.remove(dump_file)
            print_step(f"Cleaned up temporary file: {dump_file}")


if __name__ == '__main__':
    main()

