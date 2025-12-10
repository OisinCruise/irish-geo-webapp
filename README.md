# Irish Historical Sites GIS

A full-stack geospatial web application for exploring Ireland's rich historical heritage through interactive mapping, journey tracking, and Progressive Web App (PWA) capabilities.

![Irish Historical Sites GIS](https://img.shields.io/badge/Django-4.2-green) ![PostGIS](https://img.shields.io/badge/PostGIS-3.6-blue) ![Leaflet](https://img.shields.io/badge/Leaflet.js-1.9-green) ![PWA](https://img.shields.io/badge/PWA-Enabled-orange)

**Live Demo:** [https://irish-geo-webapp.onrender.com](https://irish-geo-webapp.onrender.com)

---

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Features](#features)
- [Page-by-Page Features](#page-by-page-features)
- [Installation](#installation)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

Irish Historical Sites GIS is a location-based services (LBS) application that provides an interactive platform for exploring Ireland's historical monuments, castles, monasteries, and archaeological sites. The application combines accurate geographic data from official sources (National Monuments Service, Ordnance Survey Ireland) with detailed historical information, presented through a modern, bilingual web interface.

### Key Highlights

- **100+ Historical Sites** across 26 counties and 4 provinces
- **Interactive Mapping** with 13+ specialized tools
- **Journey Tracking** with session-based bucket list functionality
- **Bilingual Support** (English/Irish - Gaeilge)
- **Progressive Web App** with offline capabilities
- **RESTful API** with GeoJSON spatial data

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Database** | PostgreSQL 16 + PostGIS | Spatial data storage and queries |
| **Backend** | Django 4.2 LTS + GeoDjango | MVC framework with geospatial extensions |
| **API** | Django REST Framework | RESTful API with GeoJSON serialization |
| **Frontend** | HTML5, CSS3, ES6 | Modern web standards |
| **Mapping** | Leaflet.js + OpenStreetMap | Interactive map visualization |
| **PWA** | Service Worker API | Offline support and app-like experience |
| **Deployment** | Render.com + Docker | Cloud hosting with containerization |
| **Database Hosting** | Render PostgreSQL | Managed PostgreSQL with PostGIS |

---

## Features

### Core Functionality

- **Interactive Map Explorer** with multiple basemap options (Street, Satellite, Terrain)
- **Spatial Queries** - Find sites by proximity, bounding box, county, or historical era
- **Journey Tracking** - Personal bucket list with wishlist and visited status
- **Photo Uploads** - Upload and caption photos for visited sites (5MB limit)
- **Rich Site Information** - Detailed bilingual descriptions, dates, and metadata
- **Advanced Filtering** - Filter by site type, county, era, and designation
- **Measurement Tools** - Distance measurement and elevation profiling
- **Coordinate System** - Real-time coordinate display and search

### User Experience

- **Responsive Design** - Works seamlessly on desktop, tablet, and mobile
- **Dark/Light Themes** - User preference with CSS variable system
- **Bilingual Interface** - Full English/Irish language support
- **Offline Support** - Service worker caches map tiles and static assets
- **Cross-tab Synchronization** - Real-time updates across browser tabs

---

## Page-by-Page Features

### Home Page (`/`)

**Purpose:** Dashboard and entry point showcasing journey statistics and key features.

#### Features & Implementation

1. **Hero Section with Animated Gradient**
   - Animated gradient background using CSS keyframes
   - Floating decorative elements with rotation animations
   - Call-to-action buttons linking to map and about pages
   - **Implementation:** CSS animations with `@keyframes`, flexbox layout

2. **Journey Dashboard (Fitness-Style Stats)**
   - **Wishlist Count** - Sites added to bucket list
   - **Visited Count** - Sites marked as visited
   - **Counties Explored** - Unique counties with visited sites
   - **Progress Rings** - Circular progress indicators (SVG-based)
   - **Progress Bars** - Linear progress visualization
   - **Implementation:** 
     - Real-time API integration (`/api/v1/bucket-list/statistics/`)
     - Animated number counting with JavaScript
     - SVG progress rings with `stroke-dashoffset` animation
     - Custom events for cross-page updates

3. **Recent Activity Preview**
   - Grid display of 4 most recent bucket list items
   - Photo thumbnails with fallback icons
   - Status badges (Wishlist/Visited)
   - **Implementation:** 
     - Paginated API calls (`/api/v1/bucket-list/?page_size=4`)
     - Dynamic DOM manipulation
     - Image lazy loading

4. **Feature Cards (Glassmorphism Design)**
   - 6 feature highlights with glassmorphism effects
   - Icon-based visual hierarchy
   - Hover animations
   - **Implementation:** 
     - CSS `backdrop-filter: blur()` for glass effect
     - CSS Grid responsive layout
     - Staggered fade-in animations

5. **Quick Stats Section**
   - Animated counters (26 Counties, 4 Provinces, 13+ Categories, 2 Languages)
   - Scroll-triggered animations using Intersection Observer
   - **Implementation:** 
     - Intersection Observer API for performance
     - Number animation with easing functions

#### Integration Applications

- **API Integration:** Fetches real-time statistics from Django REST Framework
- **Event System:** Custom `journeyUpdated` events for real-time updates
- **Storage API:** Cross-tab synchronization using `localStorage` events
- **Responsive Design:** Mobile-first approach with CSS Grid and Flexbox

---

### Explore Page (`/explore/`)

**Purpose:** Interactive map interface for exploring historical sites with comprehensive toolset.

#### Features & Implementation

1. **Interactive Leaflet Map**
   - Full-screen map with OpenStreetMap integration
   - Multiple basemap layers (Street, Satellite, Terrain)
   - Custom marker clustering for performance
   - **Implementation:** 
     - Leaflet.js library with custom plugins
     - GeoJSON data from Django REST Framework
     - Marker clustering with `Leaflet.markercluster`

2. **Basemap Gallery**
   - Toggle between Street, Satellite, and Terrain views
   - Era-specific basemap filtering
   - **Implementation:** Leaflet layer control with custom tile providers

3. **Boundary Visualization**
   - **County Borders** - 26 ROI counties as GeoJSON polygons
   - **Province Borders** - 4 Irish provinces
   - Toggle on/off with styled borders
   - **Implementation:** 
     - GeoJSON layers from `/api/v1/counties/` and `/api/v1/provinces/`
     - Custom styling with Leaflet path options

4. **Legend Panel**
   - Dynamic legend showing active map elements
   - Color-coded site types
   - National Monument indicators
   - Collapsible design
   - **Implementation:** 
     - Real-time legend updates based on visible layers
     - CSS transitions for smooth collapse/expand

5. **Measurement Tool**
   - Distance measurement between points
   - Click to place points, double-click to finish
   - Real-time distance display
   - **Implementation:** 
     - Leaflet.draw plugin
     - Haversine formula for accurate distance calculation

6. **Coordinate Finder**
   - Real-time coordinate display on mouse hover
   - Click to copy coordinates
   - **Implementation:** 
     - Leaflet `mousemove` event listeners
     - Coordinate formatting (decimal degrees)

7. **Elevation Profile Tool**
   - Click to place start point, double-click to finish
   - Elevation data from Open Elevation API
   - Visual profile graph
   - **Implementation:** 
     - External API integration (`api.open-elevation.com`)
     - Chart.js for elevation visualization

8. **Device Location**
   - Browser geolocation API
   - Center map on user location
   - Find nearby sites
   - **Implementation:** 
     - HTML5 Geolocation API
     - Spatial query to `/api/v1/sites/nearby/`

9. **Custom Markers**
   - Add/remove user-defined points
   - Persistent markers with localStorage
   - **Implementation:** 
     - Leaflet marker management
     - Browser storage API

10. **Site Popups**
    - Rich popups with site images, descriptions, dates
    - Bilingual content display
    - Add to wishlist/visited buttons
    - Link to detailed site information
    - **Implementation:** 
      - Custom Leaflet popup templates
      - API calls to `/api/v1/bucket-list/` for status updates
      - Image lazy loading

11. **Filter Sidebar**
    - Filter by site type (13 categories)
    - Filter by county (26 counties)
    - Filter by historical era
    - National Monument designation filter
    - **Implementation:** 
      - Dynamic filter options from API
      - Real-time map marker filtering
      - URL parameter persistence

12. **Site Count Badge**
    - Real-time count of visible sites
    - Updates on filter changes
    - **Implementation:** 
      - Event-driven counter updates
      - Debounced API calls

13. **Search Functionality**
    - Search sites by name
    - Autocomplete suggestions
    - **Implementation:** 
      - Django REST Framework filtering
      - Debounced search input

#### Integration Applications

- **GeoJSON API:** All spatial data returned as RFC 7946 compliant GeoJSON
- **Spatial Queries:** PostGIS functions (`ST_DWithin`, `ST_Within`, `ST_Contains`)
- **Bounding Box Loading:** Efficient viewport-based data loading
- **Marker Clustering:** Performance optimization for 100+ sites
- **Real-time Updates:** Custom events for bucket list changes

---

### My Journey Page (`/my-journey/`)

**Purpose:** Visual cork board display of visited sites with photo uploads and memories.

#### Features & Implementation

1. **Cork Board Design**
   - Realistic cork texture background
   - Wooden frame border
   - Push pin effects on polaroid cards
   - **Implementation:** 
     - CSS gradients and patterns
     - Multiple background layers
     - Box shadows for depth

2. **Polaroid-Style Cards**
   - Photo display with white borders
   - Random rotation for natural look
   - Hover effects with scale and shadow
   - **Implementation:** 
     - CSS transforms (`rotate()`, `scale()`)
     - CSS Grid layout
     - Transition animations

3. **Photo Upload System**
   - Upload photos for visited sites (5MB limit)
   - Optional captions
   - Image preview
   - **Implementation:** 
     - HTML5 File API
     - FormData for multipart uploads
     - PATCH requests to `/api/v1/bucket-list/{id}/`
     - Django file handling

4. **Statistics Summary**
   - Total photos uploaded
   - Counties visited
   - Sites explored
   - **Implementation:** 
     - Aggregate statistics from API
     - Real-time counter updates

5. **County Filtering**
   - Filter polaroids by county
   - Dynamic filter button generation
   - Active state management
   - **Implementation:** 
     - Client-side filtering
     - Dynamic DOM manipulation

6. **Photo Modal**
   - Full-screen photo viewer
   - Site details and metadata
   - Caption display
   - **Implementation:** 
     - CSS modal overlay
     - Image lazy loading
     - Keyboard navigation (ESC to close)

7. **Empty State**
   - Encouraging message for new users
   - Call-to-action to explore map
   - **Implementation:** 
     - Conditional rendering
     - API response handling

#### Integration Applications

- **File Upload API:** Multipart form data handling
- **Image Storage:** Django media file management
- **Session Management:** Session-based bucket list items
- **Real-time Updates:** Page refresh after upload

---

### About Page (`/about/`)

**Purpose:** Project information, technology stack, and API documentation links.

#### Features & Implementation

1. **Mission Statement**
   - Project goals and purpose
   - Bilingual content
   - **Implementation:** 
     - Semantic HTML structure
     - Data attributes for i18n

2. **Feature List**
   - Comprehensive feature overview
   - Bullet-point format
   - **Implementation:** 
     - HTML lists with semantic markup

3. **Technology Stack Display**
   - Visual tech stack breakdown
   - Grid layout
   - **Implementation:** 
     - CSS Grid
     - Responsive design

4. **Data Sources**
   - Attribution to official sources
   - Academic references
   - **Implementation:** 
     - Text content with proper citations

5. **API Documentation Links**
   - Links to Swagger UI and ReDoc
   - **Implementation:** 
     - DRF Spectacular integration
     - External link handling

#### Integration Applications

- **API Documentation:** DRF Spectacular for OpenAPI schema
- **Content Management:** Django template system
- **Internationalization:** Bilingual content system

---

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 17+ with PostGIS 3.6
- GDAL library (for GeoDjango)
- Node.js (optional, for frontend tooling)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd irish-geo-webapp
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb irish_geo_db
   
   # Enable PostGIS extension
   psql -d irish_geo_db -c "CREATE EXTENSION postgis;"
   ```

5. **Configure environment variables**
   Create a `.env` file:
   ```env
   DJANGO_SECRET_KEY=your-secret-key-here
   DJANGO_DEBUG=True
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   DB_NAME=irish_geo_db
   DB_USER=your-db-user
   DB_PASSWORD=your-db-password
   DB_HOST=localhost
   DB_PORT=5432
   ```

6. **Run migrations**
   ```bash
   python manage.py migrate
   ```

7. **Import data**
   ```bash
   python scripts/import_monuments.py
   python scripts/import_counties.py
   python scripts/import_osi_boundaries.py
   python scripts/import_image_urls.py
   ```

8. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

9. **Run development server**
   ```bash
   python manage.py runserver
   ```

10. **Access the application**
    - Web app: http://localhost:8000
    - Admin panel: http://localhost:8000/admin
    - API docs: http://localhost:8000/api/docs/

### Docker Setup

```bash
# Development (PGAdmin only)
docker-compose -f docker/docker-compose.dev.yml up -d

# Full stack
docker-compose up -d
```

---

## API Documentation

### Base URL
```
/api/v1/
```

### Key Endpoints

#### Sites
- `GET /api/v1/sites/` - List all sites (GeoJSON)
- `GET /api/v1/sites/{id}/` - Site detail
- `GET /api/v1/sites/nearby/?lat={lat}&lon={lon}&radius={km}` - Find nearby sites
- `GET /api/v1/sites/in_bbox/?min_lat={lat}&min_lon={lon}&max_lat={lat}&max_lon={lon}` - Sites in bounding box
- `GET /api/v1/sites/by_era/{era_id}/` - Sites by historical era
- `GET /api/v1/sites/by_county/{county_id}/` - Sites by county
- `GET /api/v1/sites/statistics/` - Aggregate statistics

#### Geography
- `GET /api/v1/provinces/` - List provinces (GeoJSON)
- `GET /api/v1/counties/` - List counties (GeoJSON)
- `GET /api/v1/counties/by_province/{province_id}/` - Counties by province

#### Historical Eras
- `GET /api/v1/eras/` - List historical eras
- `GET /api/v1/eras/timeline/` - Era timeline data

#### Journey Tracking
- `GET /api/v1/bucket-list/` - List bucket list items
- `POST /api/v1/bucket-list/` - Add site to bucket list
- `GET /api/v1/bucket-list/{id}/` - Bucket list item detail
- `PATCH /api/v1/bucket-list/{id}/` - Update item (upload photo, mark visited)
- `POST /api/v1/bucket-list/{id}/mark_visited/` - Mark as visited
- `GET /api/v1/bucket-list/statistics/` - Journey statistics

### Response Format

All spatial endpoints return **GeoJSON** (RFC 7946) format:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-8.2439, 53.4129]
      },
      "properties": {
        "id": 1,
        "name_en": "Newgrange",
        "name_ga": "Sí an Bhrú",
        ...
      }
    }
  ]
}
```

### Interactive API Documentation

- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`
- **OpenAPI Schema:** `/api/schema/`

---

## Project Structure

```
irish-geo-webapp/
├── apps/
│   ├── api/              # Django REST Framework API
│   │   ├── views.py      # ViewSets and API endpoints (739 lines)
│   │   ├── serializers.py # GeoJSON serializers (515 lines)
│   │   └── urls.py       # API routing
│   ├── geography/        # Province, County, Era models
│   │   └── models.py     # Geographic models (384 lines)
│   └── sites/            # Historical sites and journey tracking
│       └── models.py     # Site, Image, BucketList models (872 lines)
├── config/
│   ├── settings/         # Django settings
│   │   ├── base.py       # Base configuration
│   │   ├── development.py
│   │   └── production.py # Render/Neon deployment config
│   └── urls.py           # Main URL routing
├── static/
│   ├── css/
│   │   ├── theme.css     # Theme variables (407 lines)
│   │   └── components.css # UI components (1,752 lines)
│   ├── js/
│   │   ├── map.js        # Leaflet map logic (2,063 lines)
│   │   ├── sw.js         # Service worker (421 lines)
│   │   ├── theme.js      # Theme toggle
│   │   └── i18n.js       # Internationalization
│   └── images/           # PWA icons, screenshots
├── templates/
│   ├── base.html         # Base template
│   ├── home.html         # Home page (1,195 lines)
│   ├── explore.html      # Map page
│   ├── collage.html      # Journey page (987 lines)
│   └── about.html        # About page
├── data/                 # CSV and GeoJSON data files
├── scripts/              # Data import scripts
├── docker/               # Docker configurations
├── Dockerfile            # Production Docker build
├── docker-compose.yml    # Full stack orchestration
└── render.yaml          # Render.com blueprint
```

---

## Deployment

### Render.com Deployment

The application is deployed on Render.com using Docker:

**Live URL:** https://irish-geo-webapp.onrender.com

#### Deployment Configuration

1. **Service Type:** Web Service + PostgreSQL Database
2. **Runtime:** Docker
3. **Region:** Frankfurt (EU)
4. **Database:** Render PostgreSQL + PostGIS

#### Environment Variables

```env
DJANGO_SECRET_KEY=<auto-generated>
DJANGO_ALLOWED_HOSTS=.onrender.com
# DATABASE_URL is automatically provided by Render when database is linked
# No manual database configuration needed
```

#### Deployment Files

- `render.yaml` - Infrastructure as Code blueprint (includes database service)
- `Dockerfile` - Multi-stage production build
- `build.sh` - Build script (alternative deployment)
- `scripts/migrate_neon_to_render.py` - Database migration script

### Database Hosting

**Render PostgreSQL**
- Managed PostgreSQL 16 with PostGIS extension
- Automatic backups
- SSL required
- Connection pooling via `CONN_MAX_AGE`
- `DATABASE_URL` automatically provided when database is linked to web service

### Migrating from Neon to Render PostgreSQL

If you're migrating from Neon, use the migration script:

```bash
# Set your connection strings
export NEON_DATABASE_URL='postgresql://neondb_owner:password@ep-gentle-cake-a8ekv7j8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require'
export RENDER_DATABASE_URL='postgresql://user:password@dpg-xxxxx-a.oregon-postgres.render.com/irish_geo_db?sslmode=require'

# Run migration
python scripts/migrate_neon_to_render.py
```

The script will:
1. Enable PostGIS extension on Render PostgreSQL
2. Export all data from Neon
3. Import data to Render PostgreSQL
4. Verify the migration

---

## Design System

### Color Palette

- **Primary:** Pine Green `#1a5f4a`
- **Accent:** Orange `#ff8c00`
- **Background:** Light/Dark theme support
- **Text:** High contrast for accessibility

### Typography

- **Headings:** System font stack
- **Body:** Sans-serif with fallbacks
- **Code:** Monospace for technical content

### Responsive Breakpoints

- **Mobile:** < 768px
- **Tablet:** 768px - 1024px
- **Desktop:** > 1024px

---

## Development

### Running Tests

```bash
python manage.py test
```

### Code Style

- **Python:** PEP 8 compliant
- **JavaScript:** ES6+ with modern syntax
- **CSS:** BEM-inspired naming convention

### Key Dependencies

**Backend:**
- Django 4.2 LTS
- Django REST Framework
- GeoDjango
- PostGIS
- DRF Spectacular (API docs)

**Frontend:**
- Leaflet.js 1.9
- OpenStreetMap tiles
- Service Worker API
- Modern CSS (Grid, Flexbox, Custom Properties)

---

## License

This project was developed as part of the Advanced Web Mapping module at TU Dublin.

---

## Author

**Oisin Cruise**  
TU Dublin | Advanced Web Mapping Module  
Due: December 9th, 2025

---

## Acknowledgments

- **Data Sources:**
  - National Monuments Service (NMS)
  - Ordnance Survey Ireland (OSi)
  - Academic research and historical records

- **Technologies:**
  - Leaflet.js community
  - OpenStreetMap contributors
  - Django and GeoDjango teams

---

## Contact

For questions or feedback about this project, please contact the development team.

---

**Last Updated:** December 2025
