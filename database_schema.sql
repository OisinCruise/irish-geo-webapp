-- ==============================================================================
-- Irish Historical Sites GIS Database Schema - FINAL VERSION
-- PostgreSQL 17+ with PostGIS 3.6
-- SRID: 4326 (WGS84) for web mapping compatibility
-- NOTE: Extensions must be created by superuser BEFORE running this script
-- ==============================================================================

-- ==============================================================================
-- TABLE 1: Province
-- ==============================================================================

CREATE TABLE IF NOT EXISTS province (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL UNIQUE,
    name_ga VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(10) NOT NULL UNIQUE,
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    area_km2 NUMERIC(10, 2),
    population INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    description_en TEXT,
    description_ga TEXT,
    CONSTRAINT province_area_positive CHECK (area_km2 > 0),
    CONSTRAINT province_population_positive CHECK (population >= 0)
);

CREATE INDEX IF NOT EXISTS idx_province_geometry ON province USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_province_name_en ON province (name_en);
CREATE INDEX IF NOT EXISTS idx_province_code ON province (code);
CREATE INDEX IF NOT EXISTS idx_province_deleted ON province (is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_province_description_en_fts ON province USING GIN (to_tsvector('english', description_en));

COMMENT ON TABLE province IS 'Irish provinces with polygon boundaries - 4 historic provinces';
COMMENT ON COLUMN province.geometry IS 'MultiPolygon geometry in WGS84 (SRID 4326) for web mapping';

-- ==============================================================================
-- TABLE 2: County
-- ==============================================================================

CREATE TABLE IF NOT EXISTS county (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL UNIQUE,
    name_ga VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(10) NOT NULL UNIQUE,
    province_id INTEGER NOT NULL REFERENCES province(id) ON DELETE RESTRICT,
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    area_km2 NUMERIC(10, 2),
    population INTEGER,
    county_town VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    description_en TEXT,
    description_ga TEXT,
    CONSTRAINT county_area_positive CHECK (area_km2 > 0),
    CONSTRAINT county_population_positive CHECK (population >= 0)
);

CREATE INDEX IF NOT EXISTS idx_county_geometry ON county USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_county_province_id ON county (province_id);
CREATE INDEX IF NOT EXISTS idx_county_name_en ON county (name_en);
CREATE INDEX IF NOT EXISTS idx_county_code ON county (code);
CREATE INDEX IF NOT EXISTS idx_county_deleted ON county (is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_county_description_en_fts ON county USING GIN (to_tsvector('english', description_en));

COMMENT ON TABLE county IS 'Irish counties (32) with polygon boundaries';

-- ==============================================================================
-- TABLE 3: HistoricalEra
-- ==============================================================================

CREATE TABLE IF NOT EXISTS historical_era (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL UNIQUE,
    name_ga VARCHAR(100) NOT NULL UNIQUE,
    start_year INTEGER NOT NULL,
    end_year INTEGER NOT NULL,
    description_en TEXT NOT NULL,
    description_ga TEXT NOT NULL,
    color_hex VARCHAR(7) DEFAULT '#1a5f4a',
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT era_years_valid CHECK (end_year > start_year),
    CONSTRAINT era_color_format CHECK (color_hex ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE INDEX IF NOT EXISTS idx_era_years ON historical_era (start_year, end_year);
CREATE INDEX IF NOT EXISTS idx_era_name_en ON historical_era (name_en);
CREATE INDEX IF NOT EXISTS idx_era_display_order ON historical_era (display_order);
CREATE INDEX IF NOT EXISTS idx_era_deleted ON historical_era (is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_era_description_en_fts ON historical_era USING GIN (to_tsvector('english', description_en));

COMMENT ON TABLE historical_era IS 'Historical time periods for categorizing Irish historical sites';

-- ==============================================================================
-- TABLE 4: HistoricalSite
-- ==============================================================================

CREATE TABLE IF NOT EXISTS historical_site (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(255) NOT NULL,
    name_ga VARCHAR(255),
    description_en TEXT NOT NULL,
    description_ga TEXT,
    location GEOMETRY(PointZ, 4326) NOT NULL,
    elevation_meters NUMERIC(8, 2),
    county_id INTEGER REFERENCES county(id) ON DELETE SET NULL,
    era_id INTEGER REFERENCES historical_era(id) ON DELETE SET NULL,
    site_type VARCHAR(50) NOT NULL,
    significance_level INTEGER NOT NULL DEFAULT 2,
    date_established DATE,
    date_abandoned DATE,
    construction_period VARCHAR(100),
    preservation_status VARCHAR(50),
    unesco_site BOOLEAN DEFAULT FALSE,
    national_monument BOOLEAN DEFAULT FALSE,
    is_public_access BOOLEAN DEFAULT TRUE,
    visitor_center BOOLEAN DEFAULT FALSE,
    admission_required BOOLEAN DEFAULT FALSE,
    address TEXT,
    eircode VARCHAR(10),
    website_url VARCHAR(500),
    phone_number VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    modified_by VARCHAR(100),
    approval_status VARCHAR(20) DEFAULT 'pending',
    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    data_source VARCHAR(255),
    data_quality INTEGER DEFAULT 3,
    view_count INTEGER DEFAULT 0,
    CONSTRAINT site_significance_range CHECK (significance_level BETWEEN 1 AND 4),
    CONSTRAINT site_dates_valid CHECK (date_abandoned IS NULL OR date_established IS NULL OR date_abandoned >= date_established),
    CONSTRAINT site_elevation_range CHECK (elevation_meters BETWEEN -100 AND 2000),
    CONSTRAINT site_approval_status_valid CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT site_data_quality_range CHECK (data_quality BETWEEN 1 AND 5)
);

-- Critical spatial index
CREATE INDEX IF NOT EXISTS idx_site_location ON historical_site USING GIST (location);

-- Other indexes
CREATE INDEX IF NOT EXISTS idx_site_created_brin ON historical_site USING BRIN (created_at);
CREATE INDEX IF NOT EXISTS idx_site_county_id ON historical_site (county_id);
CREATE INDEX IF NOT EXISTS idx_site_era_id ON historical_site (era_id);
CREATE INDEX IF NOT EXISTS idx_site_type ON historical_site (site_type);
CREATE INDEX IF NOT EXISTS idx_site_significance ON historical_site (significance_level DESC);
CREATE INDEX IF NOT EXISTS idx_site_approval_status ON historical_site (approval_status);
CREATE INDEX IF NOT EXISTS idx_site_deleted ON historical_site (is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_site_county_era ON historical_site (county_id, era_id);
CREATE INDEX IF NOT EXISTS idx_site_type_significance ON historical_site (site_type, significance_level DESC);
CREATE INDEX IF NOT EXISTS idx_site_name_en_fts ON historical_site USING GIN (to_tsvector('english', name_en));
CREATE INDEX IF NOT EXISTS idx_site_description_en_fts ON historical_site USING GIN (to_tsvector('english', description_en));
CREATE INDEX IF NOT EXISTS idx_site_name_en_trgm ON historical_site USING GIN (name_en gin_trgm_ops);

COMMENT ON TABLE historical_site IS 'Irish historical sites with point geometry and comprehensive metadata';

-- ==============================================================================
-- TABLE 5: SiteImage
-- ==============================================================================

CREATE TABLE IF NOT EXISTS site_image (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES historical_site(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    image_path VARCHAR(500),
    thumbnail_url VARCHAR(500),
    title_en VARCHAR(255),
    title_ga VARCHAR(255),
    caption_en TEXT,
    caption_ga TEXT,
    alt_text VARCHAR(255),
    photographer VARCHAR(100),
    photo_date DATE,
    copyright_info VARCHAR(255),
    license_type VARCHAR(50) DEFAULT 'All Rights Reserved',
    is_primary BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    is_public BOOLEAN DEFAULT TRUE,
    file_size_kb INTEGER,
    width_px INTEGER,
    height_px INTEGER,
    mime_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    uploaded_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT image_dimensions_positive CHECK (width_px > 0 AND height_px > 0),
    CONSTRAINT image_file_size_positive CHECK (file_size_kb > 0)
);

CREATE INDEX IF NOT EXISTS idx_image_site_id ON site_image (site_id);
CREATE INDEX IF NOT EXISTS idx_image_primary ON site_image (site_id, is_primary) WHERE is_primary = TRUE;
CREATE INDEX IF NOT EXISTS idx_image_display_order ON site_image (site_id, display_order);
CREATE INDEX IF NOT EXISTS idx_image_deleted ON site_image (is_deleted) WHERE is_deleted = FALSE;

COMMENT ON TABLE site_image IS 'Images associated with historical sites';

-- ==============================================================================
-- TABLE 6: SiteSource
-- ==============================================================================

CREATE TABLE IF NOT EXISTS site_source (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES historical_site(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    author VARCHAR(255),
    publication_year INTEGER,
    publisher VARCHAR(255),
    isbn VARCHAR(20),
    doi VARCHAR(100),
    url VARCHAR(500),
    pages VARCHAR(50),
    language VARCHAR(10) DEFAULT 'en',
    reliability_score INTEGER DEFAULT 3,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    added_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    CONSTRAINT source_type_valid CHECK (source_type IN ('book', 'journal', 'website', 'archive', 'oral_history', 'government_record')),
    CONSTRAINT source_reliability_range CHECK (reliability_score BETWEEN 1 AND 5),
    CONSTRAINT source_year_valid CHECK (publication_year > 0 AND publication_year <= EXTRACT(YEAR FROM CURRENT_DATE))
);

CREATE INDEX IF NOT EXISTS idx_source_site_id ON site_source (site_id);
CREATE INDEX IF NOT EXISTS idx_source_type ON site_source (source_type);
CREATE INDEX IF NOT EXISTS idx_source_year ON site_source (publication_year DESC);
CREATE INDEX IF NOT EXISTS idx_source_deleted ON site_source (is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_source_title_fts ON site_source USING GIN (to_tsvector('english', title));

COMMENT ON TABLE site_source IS 'Historical and academic sources documenting each site';

-- ==============================================================================
-- MATERIALIZED VIEW
-- ==============================================================================

DROP MATERIALIZED VIEW IF EXISTS mv_site_county_summary CASCADE;

CREATE MATERIALIZED VIEW mv_site_county_summary AS
SELECT 
    c.id AS county_id,
    c.name_en AS county_name,
    c.geometry AS county_geometry,
    COUNT(hs.id) AS site_count,
    COUNT(CASE WHEN hs.significance_level = 4 THEN 1 END) AS critical_sites,
    COUNT(CASE WHEN hs.national_monument = TRUE THEN 1 END) AS national_monuments,
    ARRAY_AGG(DISTINCT hs.site_type) FILTER (WHERE hs.site_type IS NOT NULL) AS site_types_present
FROM county c
LEFT JOIN historical_site hs ON c.id = hs.county_id 
    AND hs.is_deleted = FALSE 
    AND hs.approval_status = 'approved'
GROUP BY c.id, c.name_en, c.geometry;

CREATE INDEX IF NOT EXISTS idx_mv_site_county_geometry ON mv_site_county_summary USING GIST (county_geometry);
CREATE INDEX IF NOT EXISTS idx_mv_site_count ON mv_site_county_summary (site_count DESC);

-- ==============================================================================
-- TRIGGER FUNCTIONS
-- ==============================================================================

-- Function to update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS update_province_updated_at ON province;
CREATE TRIGGER update_province_updated_at BEFORE UPDATE ON province
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_county_updated_at ON county;
CREATE TRIGGER update_county_updated_at BEFORE UPDATE ON county
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_era_updated_at ON historical_era;
CREATE TRIGGER update_era_updated_at BEFORE UPDATE ON historical_era
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_site_updated_at ON historical_site;
CREATE TRIGGER update_site_updated_at BEFORE UPDATE ON historical_site
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to validate Ireland bounds
CREATE OR REPLACE FUNCTION validate_ireland_bounds()
RETURNS TRIGGER AS $$
BEGIN
    IF ST_XMin(NEW.geometry) < -11 OR ST_XMax(NEW.geometry) > -5 OR
       ST_YMin(NEW.geometry) < 51 OR ST_YMax(NEW.geometry) > 56 THEN
        RAISE EXCEPTION 'Geometry extends beyond Ireland boundaries';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_province_bounds ON province;
CREATE TRIGGER validate_province_bounds BEFORE INSERT OR UPDATE ON province
    FOR EACH ROW EXECUTE FUNCTION validate_ireland_bounds();

DROP TRIGGER IF EXISTS validate_county_bounds ON county;
CREATE TRIGGER validate_county_bounds BEFORE INSERT OR UPDATE ON county
    FOR EACH ROW EXECUTE FUNCTION validate_ireland_bounds();

-- Function to ensure only one primary image per site
CREATE OR REPLACE FUNCTION enforce_single_primary_image()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_primary = TRUE THEN
        UPDATE site_image 
        SET is_primary = FALSE 
        WHERE site_id = NEW.site_id AND id != COALESCE(NEW.id, 0);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_primary_image ON site_image;
CREATE TRIGGER enforce_primary_image BEFORE INSERT OR UPDATE ON site_image
    FOR EACH ROW EXECUTE FUNCTION enforce_single_primary_image();

-- ==============================================================================
-- UTILITY FUNCTIONS
-- ==============================================================================

-- Refresh materialized view
CREATE OR REPLACE FUNCTION refresh_site_statistics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_site_county_summary;
END;
$$ LANGUAGE plpgsql;

-- Find sites near a point
CREATE OR REPLACE FUNCTION find_sites_near_point(
    p_longitude NUMERIC,
    p_latitude NUMERIC,
    p_radius_km NUMERIC DEFAULT 10
)
RETURNS TABLE (
    site_id INTEGER,
    site_name VARCHAR,
    distance_km NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        hs.id,
        hs.name_en,
        ROUND((ST_Distance(
            hs.location::geography,
            ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography
        ) / 1000)::numeric, 2) AS distance_km
    FROM historical_site hs
    WHERE hs.is_deleted = FALSE
        AND hs.approval_status = 'approved'
        AND ST_DWithin(
            hs.location::geography,
            ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography,
            p_radius_km * 1000
        )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

-- Find sites in bounding box
CREATE OR REPLACE FUNCTION find_sites_in_bbox(
    p_min_lng NUMERIC,
    p_min_lat NUMERIC,
    p_max_lng NUMERIC,
    p_max_lat NUMERIC
)
RETURNS TABLE (
    site_id INTEGER,
    site_name VARCHAR,
    longitude NUMERIC,
    latitude NUMERIC,
    site_type VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        hs.id,
        hs.name_en,
        ST_X(hs.location::geometry)::numeric AS longitude,
        ST_Y(hs.location::geometry)::numeric AS latitude,
        hs.site_type
    FROM historical_site hs
    WHERE hs.is_deleted = FALSE
        AND hs.approval_status = 'approved'
        AND ST_Intersects(
            hs.location,
            ST_MakeEnvelope(p_min_lng, p_min_lat, p_max_lng, p_max_lat, 4326)
        );
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- GRANTS
-- ==============================================================================

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO geo_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO geo_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO geo_user;
GRANT SELECT ON mv_site_county_summary TO geo_user;

-- ==============================================================================
-- VERIFICATION
-- ==============================================================================

SELECT PostGIS_Version();

SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT 
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
    AND indexdef LIKE '%GIST%'
ORDER BY tablename, indexname;

SELECT 
    'province' AS table_name, COUNT(*) AS record_count FROM province
UNION ALL
SELECT 'county', COUNT(*) FROM county
UNION ALL
SELECT 'historical_era', COUNT(*) FROM historical_era
UNION ALL
SELECT 'historical_site', COUNT(*) FROM historical_site;

-- ==============================================================================
-- END OF SCHEMA
-- ==============================================================================
