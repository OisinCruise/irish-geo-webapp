/**
 * Irish Historical Sites GIS - Map Application
 * =============================================
 * Leaflet.js map with full feature set for exploring Irish historical sites
 *
 * Features:
 * 1. Basemap Gallery (Street, Satellite, Terrain)
 * 2. County Borders Toggle
 * 3. Province Borders Toggle
 * 4. Dynamic Legend
 * 5. Measurement Tool
 * 6. Add/Remove User Points
 * 7. Coordinate Finder (real-time)
 * 8. Elevation Profile
 * 9. Device Location
 * 10. Zoom Controls
 * 11. Data Point Popups
 * 12. Search/Filter
 * 13. Draw Tools
 */

(function() {
    'use strict';

    // ===========================================================================
    // CONFIGURATION
    // ===========================================================================

    const CONFIG = {
        // Ireland center coordinates
        defaultCenter: [53.4129, -8.2439],
        defaultZoom: 7,
        minZoom: 5,
        maxZoom: 18,

        // Ireland bounds for constraining the map
        maxBounds: [
            [51.0, -11.5],  // Southwest
            [56.0, -4.5]    // Northeast
        ],

        // API endpoints
        api: {
            sites: '/api/v1/sites/',
            sitesNearby: '/api/v1/sites/nearby/',
            sitesBbox: '/api/v1/sites/in_bbox/',
            counties: '/api/v1/counties/',
            provinces: '/api/v1/provinces/',
            eras: '/api/v1/eras/',
        },

        // Open Elevation API (free service)
        elevationApi: 'https://api.open-elevation.com/api/v1/lookup',

        // Marker colors by site type
        siteTypeColors: {
            'castle': '#8B4513',
            'monastery': '#4B0082',
            'fort': '#556B2F',
            'burial_site': '#2F4F4F',
            'stone_monument': '#708090',
            'holy_well': '#4169E1',
            'battlefield': '#8B0000',
            'historic_house': '#CD853F',
            'archaeological_site': '#D2691E',
            'church': '#6A5ACD',
            'tower': '#A0522D',
            'bridge': '#696969',
            'other': '#808080'
        },

        // Province colors
        provinceColors: {
            'Leinster': '#1a5f4a',
            'Munster': '#8B0000',
            'Connacht': '#4169E1',
            'Ulster': '#ff8c00'
        },

        // Default colors
        defaultColor: '#ff8c00',
        primaryColor: '#1a5f4a'
    };

    // ===========================================================================
    // STATE
    // ===========================================================================

    let map = null;
    let sitesLayer = null;
    let markersCluster = null;
    let countiesLayer = null;
    let provincesLayer = null;
    let drawnItems = null;
    let userMarkersLayer = null;
    let userLocationMarker = null;
    let userLocationCircle = null;
    let elevationPoints = [];
    let elevationLine = null;

    // Tool states
    let coordsDisplayEnabled = false;
    let coordsControl = null;
    let measurementActive = false;
    let elevationActive = false;
    let addPointActive = false;
    let nearbySearchActive = false;

    // Layer visibility states
    let countiesVisible = false;
    let provincesVisible = false;
    let legendVisible = true;

    // Current filters
    let currentFilters = {
        era: null,
        county: null,
        siteType: null,
        nationalMonument: null
    };

    // ===========================================================================
    // MAP INITIALIZATION
    // ===========================================================================

    /**
     * Initialize the Leaflet map
     */
    function initMap() {
        // Create map instance
        map = L.map('map', {
            center: CONFIG.defaultCenter,
            zoom: CONFIG.defaultZoom,
            minZoom: CONFIG.minZoom,
            maxZoom: CONFIG.maxZoom,
            maxBounds: CONFIG.maxBounds,
            maxBoundsViscosity: 0.8,
            zoomControl: false
        });

        // Initialize all components
        initBasemaps();
        initOverlays();
        initDrawTools();
        initControls();

        // Load initial data
        loadSites();
        loadCounties();
        loadProvinces();

        // Set up event listeners
        setupEventListeners();
        setupToolbarButtons();
        setupPopupListeners();

        console.log('Irish Historical Sites Map initialized');
    }

    /**
     * Initialize basemap layers
     */
    function initBasemaps() {
        // OpenStreetMap
        const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        });

        // ESRI Satellite
        const satelliteLayer = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {
                attribution: '&copy; Esri, DigitalGlobe, GeoEye, Earthstar Geographics',
                maxZoom: 18
            }
        );

        // OpenTopoMap (Terrain)
        const terrainLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            attribution: 'Map data: &copy; OpenStreetMap, SRTM | Map style: &copy; OpenTopoMap',
            maxZoom: 17
        });

        // Add default layer
        osmLayer.addTo(map);

        // Store basemaps for layer control
        window.baseMaps = {
            '<span class="layer-icon">🗺️</span> Street Map': osmLayer,
            '<span class="layer-icon">🛰️</span> Satellite': satelliteLayer,
            '<span class="layer-icon">⛰️</span> Terrain': terrainLayer
        };
    }

    /**
     * Initialize overlay layers
     */
    function initOverlays() {
        // Create marker cluster group
        markersCluster = L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 40, // Reduced from 50 to make clustering less aggressive
            spiderfyOnMaxZoom: true,
            disableClusteringAtZoom: 12, // Lower zoom level to show individual markers sooner
            zoomToBoundsOnClick: true,
            iconCreateFunction: function(cluster) {
                const count = cluster.getChildCount();
                let size = 'small';
                let dimension = 40;
                if (count > 100) {
                    size = 'large';
                    dimension = 50;
                } else if (count > 30) {
                    size = 'medium';
                    dimension = 45;
                }

                return L.divIcon({
                    html: `<div><span>${count}</span></div>`,
                    className: 'marker-cluster marker-cluster-' + size,
                    iconSize: L.point(dimension, dimension)
                });
            }
        });
        map.addLayer(markersCluster);

        // GeoJSON layer for sites
        sitesLayer = L.geoJSON(null, {
            pointToLayer: createSiteMarker,
            onEachFeature: onEachSiteFeature
        });

        // Counties layer (initially hidden)
        countiesLayer = L.geoJSON(null, {
            style: function(feature) {
                return {
                    color: CONFIG.primaryColor,
                    weight: 2,
                    opacity: 0.8,
                    fillColor: CONFIG.primaryColor,
                    fillOpacity: 0.1
                };
            },
            onEachFeature: function(feature, layer) {
                const props = feature.properties;
                layer.bindTooltip(props.name_en || props.name, {
                    permanent: false,
                    direction: 'center',
                    className: 'county-tooltip'
                });
            }
        });

        // Provinces layer (initially hidden)
        provincesLayer = L.geoJSON(null, {
            style: function(feature) {
                const provinceName = feature.properties.name_en || feature.properties.name;
                const color = CONFIG.provinceColors[provinceName] || CONFIG.defaultColor;
                return {
                    color: color,
                    weight: 3,
                    opacity: 0.9,
                    fillColor: color,
                    fillOpacity: 0.15,
                    dashArray: '8, 4'
                };
            },
            onEachFeature: function(feature, layer) {
                const props = feature.properties;
                layer.bindTooltip(props.name_en || props.name, {
                    permanent: false,
                    direction: 'center',
                    className: 'province-tooltip'
                });
            }
        });

        // User markers layer for custom points
        userMarkersLayer = L.featureGroup();
        map.addLayer(userMarkersLayer);

        // Create drawn items layer for measurements
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
    }

    /**
     * Initialize drawing tools for measurement
     */
    function initDrawTools() {
        // Draw control will be added when measurement tool is activated
        map.on(L.Draw.Event.CREATED, function(e) {
            const layer = e.layer;
            drawnItems.addLayer(layer);

            // Show measurement based on shape type
            if (e.layerType === 'polyline') {
                const distance = calculatePolylineDistance(layer);
                layer.bindPopup(`<strong>Distance:</strong> ${formatDistance(distance)}`).openPopup();
                showToast(`Distance: ${formatDistance(distance)}`, 'info');
            } else if (e.layerType === 'polygon' || e.layerType === 'rectangle') {
                const area = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
                layer.bindPopup(`<strong>Area:</strong> ${formatArea(area)}`).openPopup();
                showToast(`Area: ${formatArea(area)}`, 'info');
            } else if (e.layerType === 'circle') {
                const radius = layer.getRadius();
                const area = Math.PI * radius * radius;
                layer.bindPopup(`<strong>Radius:</strong> ${formatDistance(radius)}<br><strong>Area:</strong> ${formatArea(area)}`).openPopup();
                showToast(`Radius: ${formatDistance(radius)}`, 'info');
            }
        });

        map.on(L.Draw.Event.DELETED, function(e) {
            showToast('Shapes deleted', 'info');
        });
    }

    /**
     * Initialize map controls
     */
    function initControls() {
        // Zoom control (top-right)
        L.control.zoom({
            position: 'topright'
        }).addTo(map);

        // Scale control (bottom-left)
        L.control.scale({
            metric: true,
            imperial: false,
            position: 'bottomleft'
        }).addTo(map);

        // Layer control
        const overlayMaps = {
            '<span class="layer-icon">📍</span> Historical Sites': markersCluster,
            '<span class="layer-icon">🗺️</span> County Boundaries': countiesLayer,
            '<span class="layer-icon">🏛️</span> Province Boundaries': provincesLayer,
            '<span class="layer-icon">✏️</span> Your Markers': userMarkersLayer
        };

        L.control.layers(window.baseMaps, overlayMaps, {
            collapsed: true,
            position: 'topright'
        }).addTo(map);
    }

    // ===========================================================================
    // DATA LOADING
    // ===========================================================================

    /**
     * Load sites from API
     */
    async function loadSites() {
        showLoading(true);
        try {
            let url = CONFIG.api.sites;
            const params = new URLSearchParams();

            // Request a large page size to get all sites (or at least many)
            params.append('page_size', '2000');

            // Apply filters
            if (currentFilters.era) params.append('era', currentFilters.era);
            if (currentFilters.county) params.append('county', currentFilters.county);
            if (currentFilters.siteType) params.append('site_type', currentFilters.siteType);
            if (currentFilters.nationalMonument) {
                params.append('national_monument', 'true');
            }

            const queryString = params.toString();
            if (queryString) url += '?' + queryString;

            console.log('Loading sites from:', url);
            const response = await fetch(url);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error:', response.status, errorText);
                throw new Error(`Failed to load sites: ${response.status}`);
            }

            const data = await response.json();
            console.log('API Response received:', {
                hasResults: !!data.results,
                hasFeatures: !!data.features,
                type: data.type,
                count: data.count,
                keys: Object.keys(data)
            });
            
            // Handle paginated response (DRF wraps GeoJSON in pagination)
            let geojsonData;
            if (data.results && data.results.type === 'FeatureCollection') {
                // Paginated response: data.results contains the GeoJSON
                geojsonData = data.results;
                console.log('Using paginated response, features count:', geojsonData.features?.length);
            } else if (data.type === 'FeatureCollection') {
                // Direct GeoJSON response
                geojsonData = data;
                console.log('Using direct GeoJSON response, features count:', geojsonData.features?.length);
            } else {
                console.error('Unexpected API response format:', data);
                throw new Error('Unexpected response format from API');
            }

            displaySites(geojsonData);

            const count = geojsonData.features ? geojsonData.features.length : 0;
            updateSiteCount(count);

            if (count > 0) {
                showToast(`Loaded ${count.toLocaleString()} historical sites`, 'success');
            } else {
                console.warn('No sites found in response');
            }
        } catch (error) {
            console.error('Error loading sites:', error);
            showToast('Failed to load historical sites', 'error');
        } finally {
            showLoading(false);
        }
    }

    /**
     * Display sites on the map
     */
    function displaySites(geojsonData) {
        console.log('displaySites called with:', {
            hasFeatures: !!geojsonData.features,
            featureCount: geojsonData.features?.length,
            type: geojsonData.type
        });

        // Clear existing markers
        if (markersCluster) {
            markersCluster.clearLayers();
        }
        if (sitesLayer) {
            sitesLayer.clearLayers();
        }

        // Add new data
        if (geojsonData && geojsonData.features && geojsonData.features.length > 0) {
            console.log(`Adding ${geojsonData.features.length} features to map`);
            
            // Add data to GeoJSON layer (this creates individual markers)
            sitesLayer.addData(geojsonData);
            
            // Collect all layers created by addData and add them to cluster
            const layers = [];
            sitesLayer.eachLayer(function(layer) {
                layers.push(layer);
            });
            
            if (layers.length > 0) {
                markersCluster.addLayers(layers);
                console.log(`Successfully added ${layers.length} markers to cluster group`);
            } else {
                console.warn('No layers created from GeoJSON data - check pointToLayer function');
            }
        } else {
            console.warn('No features to display in GeoJSON data', geojsonData);
        }
    }

    /**
     * Load county boundaries
     */
    async function loadCounties() {
        try {
            const response = await fetch(CONFIG.api.counties);
            if (!response.ok) throw new Error('Failed to load counties');

            const data = await response.json();
            countiesLayer.clearLayers();
            countiesLayer.addData(data);
        } catch (error) {
            console.error('Error loading counties:', error);
        }
    }

    /**
     * Load province boundaries
     */
    async function loadProvinces() {
        try {
            const response = await fetch(CONFIG.api.provinces);
            if (!response.ok) throw new Error('Failed to load provinces');

            const data = await response.json();
            provincesLayer.clearLayers();
            provincesLayer.addData(data);
        } catch (error) {
            console.error('Error loading provinces:', error);
        }
    }

    // ===========================================================================
    // MARKER CREATION
    // ===========================================================================

    /**
     * Create a marker for a site
     */
    function createSiteMarker(feature, latlng) {
        const props = feature.properties;
        const siteType = props.site_type || 'other';
        const color = CONFIG.siteTypeColors[siteType] || CONFIG.defaultColor;
        const isNationalMonument = props.is_national_monument || props.national_monument;

        // Verify coordinates are valid
        if (!latlng || isNaN(latlng.lat) || isNaN(latlng.lng)) {
            console.warn('Invalid coordinates for feature:', props.id || props.name_en, latlng);
            return null;
        }

        // Verify coordinates are within Ireland bounds
        if (latlng.lat < 51.0 || latlng.lat > 56.0 || latlng.lng < -11.5 || latlng.lng > -4.5) {
            console.warn('Coordinates outside Ireland bounds for feature:', props.id || props.name_en, latlng);
        }

        const markerOptions = {
            radius: isNationalMonument ? 10 : 7,
            fillColor: color,
            color: isNationalMonument ? CONFIG.defaultColor : '#ffffff',
            weight: isNationalMonument ? 3 : 2,
            opacity: 1,
            fillOpacity: 0.85
        };

        return L.circleMarker(latlng, markerOptions);
    }

    /**
     * Handle feature binding for sites
     */
    function onEachSiteFeature(feature, layer) {
        const props = feature.properties;
        const lang = getCurrentLang();

        // GeoJSON puts 'id' at the feature level, not in properties
        // Copy it to props so createPopupContent can access it
        if (feature.id && !props.id) {
            props.id = feature.id;
        }

        // Extract coordinates from geometry if available
        if (feature.geometry && feature.geometry.coordinates) {
            props.geometry = feature.geometry;
            // Also set lat/lon from geometry for consistency
            if (!props.latitude && feature.geometry.coordinates[1]) {
                props.latitude = feature.geometry.coordinates[1];
            }
            if (!props.longitude && feature.geometry.coordinates[0]) {
                props.longitude = feature.geometry.coordinates[0];
            }
        }

        // Create popup content
        const name = lang === 'ga' && props.name_ga ? props.name_ga : (props.name_en || props.name);
        const popupContent = createPopupContent(props, lang);

        layer.bindPopup(popupContent, {
            maxWidth: 350,
            minWidth: 280
        });

        // Bind tooltip for hover
        layer.bindTooltip(name, {
            permanent: false,
            direction: 'top',
            offset: [0, -10],
            className: 'site-tooltip'
        });
    }

    /**
     * Create popup HTML content
     */
    function createPopupContent(props, lang) {
        const name = lang === 'ga' && props.name_ga ? props.name_ga : (props.name_en || props.name);
        const description = lang === 'ga' && props.description_ga
            ? props.description_ga
            : (props.description_en || props.description || '');

        const siteTypeDisplay = props.site_type_display || formatSiteType(props.site_type);
        const isNationalMonument = props.is_national_monument || props.national_monument;

        // Get coordinates from geometry if available, otherwise from properties
        let lat = null, lon = null;
        if (props.geometry && props.geometry.coordinates) {
            lon = props.geometry.coordinates[0];
            lat = props.geometry.coordinates[1];
        } else if (props.latitude && props.longitude) {
            lat = parseFloat(props.latitude);
            lon = parseFloat(props.longitude);
        }

        let html = `
            <div class="site-popup">
                <div class="popup-header">
                    <div class="popup-titles">
                        <h3 class="popup-title">${escapeHtml(name)}</h3>
                        ${props.name_ga && lang === 'en' ? `<p class="popup-subtitle">${escapeHtml(props.name_ga)}</p>` : ''}
                        ${props.id ? `<p class="popup-id">Site ID: ${props.id}</p>` : ''}
                    </div>
                    <span class="popup-type-badge" title="${escapeHtml(siteTypeDisplay)}">${escapeHtml(siteTypeDisplay)}</span>
                </div>
        `;

        // Site image (from Wikimedia or local storage)
        if (props.primary_image_url) {
            html += `
                <div class="popup-image-container">
                    <img 
                        src="${escapeHtml(props.primary_image_url)}" 
                        alt="${escapeHtml(name)}"
                        class="popup-site-image"
                        loading="lazy"
                        onerror="this.parentElement.style.display='none'"
                    />
                </div>
            `;
        }

        if (description) {
            const needsTruncation = description.length > 200;
            const truncatedDesc = needsTruncation
                ? description.substring(0, 200)
                : description;
            
            if (needsTruncation) {
                const uniqueId = `desc-${props.id || Date.now()}`;
                html += `
                    <div class="popup-description-container">
                        <p class="popup-description" id="${uniqueId}-short">${escapeHtml(truncatedDesc)}<span class="description-ellipsis">...</span></p>
                        <p class="popup-description popup-description-full" id="${uniqueId}-full" style="display: none;">${escapeHtml(description)}</p>
                        <button class="btn-expand-desc" onclick="window.toggleDescription('${uniqueId}')" data-expanded="false">
                            <span class="expand-text">Read more</span>
                        </button>
                    </div>
                `;
            } else {
                html += `<p class="popup-description">${escapeHtml(description)}</p>`;
            }
        }

        html += `<div class="popup-meta">`;

        if (props.county_name) {
            html += `<span class="popup-meta-item"><span class="meta-icon">📍</span>${escapeHtml(props.county_name)}</span>`;
        }

        if (props.era_name) {
            html += `<span class="popup-meta-item"><span class="meta-icon">🏛️</span>${escapeHtml(props.era_name)}</span>`;
        }

        if (props.significance_level) {
            html += `<span class="popup-meta-item"><span class="meta-icon">⭐</span>Significance: ${escapeHtml(String(props.significance_level))}</span>`;
        }

        if (isNationalMonument) {
            html += `<span class="popup-meta-item national-monument"><span class="meta-icon">🏆</span>National Monument</span>`;
        }

        html += `</div>`;

        // Coordinates with better formatting
        if (lat !== null && lon !== null) {
            html += `
                <div class="popup-coords">
                    <span class="meta-icon">🧭</span>
                    <span class="coord-label">Coordinates:</span>
                    <span class="coord-value">${lat.toFixed(6)}, ${lon.toFixed(6)}</span>
                </div>
            `;
        }

        // Journey buttons (Add to Journey / Remove from Journey)
        if (props.id) {
            html += `
                <div class="popup-journey-actions">
                    <button
                        class="btn-journey-add"
                        data-site-id="${props.id}"
                        onclick="window.addToJourney(${props.id}, '${escapeHtml(name)}', 'wishlist')"
                    >
                        <span class="btn-icon">⭐</span>
                        <span class="btn-text">Add to Wishlist</span>
                    </button>
                    <button
                        class="btn-journey-visited"
                        data-site-id="${props.id}"
                        onclick="window.addToJourney(${props.id}, '${escapeHtml(name)}', 'visited')"
                    >
                        <span class="btn-icon">✓</span>
                        <span class="btn-text">Mark as Visited</span>
                    </button>
                    <button
                        class="btn-journey-remove"
                        data-site-id="${props.id}"
                        onclick="window.removeFromJourney(${props.id}, '${escapeHtml(name)}')"
                        style="display: none;"
                    >
                        <span class="btn-icon">✕</span>
                        <span class="btn-text">Remove from Journey</span>
                    </button>
                    <div class="journey-loading" data-site-id="${props.id}" style="display: none;">
                        <span class="loading-spinner-small"></span>
                    </div>
                </div>
            `;
        }

        html += `</div>`;

        return html;
    }

    // ===========================================================================
    // TOOLBAR ACTIONS
    // ===========================================================================

    /**
     * Setup toolbar button handlers
     */
    function setupToolbarButtons() {
        // Device location button
        const locateBtn = document.getElementById('locateBtn');
        if (locateBtn) {
            locateBtn.addEventListener('click', handleGeolocation);
        }

        // Coordinates display button
        const coordBtn = document.getElementById('coordBtn');
        if (coordBtn) {
            coordBtn.addEventListener('click', toggleCoordinatesDisplay);
        }

        // Filter button
        const filterBtn = document.getElementById('filterBtn');
        if (filterBtn) {
            filterBtn.addEventListener('click', toggleFilterPanel);
        }

        // Nearby search button
        const nearbyBtn = document.getElementById('nearbyBtn');
        if (nearbyBtn) {
            nearbyBtn.addEventListener('click', handleNearbySearch);
        }

        // County borders toggle
        const countyBtn = document.getElementById('countyBtn');
        if (countyBtn) {
            countyBtn.addEventListener('click', toggleCountyBorders);
        }

        // Province borders toggle
        const provinceBtn = document.getElementById('provinceBtn');
        if (provinceBtn) {
            provinceBtn.addEventListener('click', toggleProvinceBorders);
        }

        // Measurement tool button
        const measureBtn = document.getElementById('measureBtn');
        if (measureBtn) {
            measureBtn.addEventListener('click', toggleMeasurementTool);
        }

        // Add point button
        const addPointBtn = document.getElementById('addPointBtn');
        if (addPointBtn) {
            addPointBtn.addEventListener('click', toggleAddPointMode);
        }

        // Elevation profile button
        const elevationBtn = document.getElementById('elevationBtn');
        if (elevationBtn) {
            elevationBtn.addEventListener('click', toggleElevationTool);
        }

        // Legend toggle button
        const legendBtn = document.getElementById('legendBtn');
        if (legendBtn) {
            legendBtn.addEventListener('click', toggleLegend);
        }

        // Clear drawings button
        const clearBtn = document.getElementById('clearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', clearAllDrawings);
        }
    }

    /**
     * Handle geolocation request
     */
    function handleGeolocation() {
        const btn = document.getElementById('locateBtn');

        if (!navigator.geolocation) {
            showToast('Geolocation is not supported by your browser', 'error');
            return;
        }

        btn?.classList.add('loading');
        showToast('Finding your location...', 'info');

        navigator.geolocation.getCurrentPosition(
            function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const accuracy = position.coords.accuracy;

                // Remove existing location markers
                if (userLocationMarker) map.removeLayer(userLocationMarker);
                if (userLocationCircle) map.removeLayer(userLocationCircle);

                // Check if within Ireland bounds
                if (lat < 51 || lat > 56 || lng < -11 || lng > -5) {
                    showToast('Your location is outside Ireland - showing on map anyway', 'warning');
                }

                // Add accuracy circle
                userLocationCircle = L.circle([lat, lng], {
                    radius: accuracy,
                    color: '#4285f4',
                    fillColor: '#4285f4',
                    fillOpacity: 0.15,
                    weight: 2
                }).addTo(map);

                // Add location marker
                userLocationMarker = L.marker([lat, lng], {
                    icon: L.divIcon({
                        className: 'user-location-marker',
                        html: `
                            <div class="location-dot">
                                <div class="location-pulse"></div>
                            </div>
                        `,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    })
                }).addTo(map)
                    .bindPopup(`
                        <strong>Your Location</strong><br>
                        Lat: ${lat.toFixed(6)}<br>
                        Lng: ${lng.toFixed(6)}<br>
                        Accuracy: ${Math.round(accuracy)}m
                    `)
                    .openPopup();

                // Fly to location
                map.flyTo([lat, lng], 13, { duration: 1.5 });

                btn?.classList.remove('loading');
                btn?.classList.add('active');
                showToast('Location found!', 'success');
            },
            function(error) {
                btn?.classList.remove('loading');
                let message = 'Unable to retrieve your location';
                if (error.code === error.PERMISSION_DENIED) {
                    message = 'Location access denied. Please enable location services.';
                } else if (error.code === error.TIMEOUT) {
                    message = 'Location request timed out. Please try again.';
                }
                showToast(message, 'error');
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            }
        );
    }

    /**
     * Toggle coordinate display on mouse move
     */
    function toggleCoordinatesDisplay() {
        coordsDisplayEnabled = !coordsDisplayEnabled;
        const btn = document.getElementById('coordBtn');

        if (coordsDisplayEnabled) {
            btn?.classList.add('active');

            // Create coordinates display panel
            coordsControl = L.control({ position: 'bottomleft' });
            coordsControl.onAdd = function() {
                const div = L.DomUtil.create('div', 'coords-panel');
                div.innerHTML = `
                    <div class="coords-title">📍 Coordinates</div>
                    <div class="coords-values">
                        <div class="coord-row">
                            <span class="coord-label">Lat:</span>
                            <span class="coord-value" id="coordLat">--</span>
                        </div>
                        <div class="coord-row">
                            <span class="coord-label">Lng:</span>
                            <span class="coord-value" id="coordLng">--</span>
                        </div>
                    </div>
                `;
                return div;
            };
            coordsControl.addTo(map);

            map.on('mousemove', updateCoordinatesDisplay);
            map.getContainer().style.cursor = 'crosshair';
            showToast('Coordinate finder enabled - move mouse over map', 'info');
        } else {
            btn?.classList.remove('active');
            if (coordsControl) {
                map.removeControl(coordsControl);
                coordsControl = null;
            }
            map.off('mousemove', updateCoordinatesDisplay);
            map.getContainer().style.cursor = '';
            showToast('Coordinate finder disabled', 'info');
        }
    }

    function updateCoordinatesDisplay(e) {
        const latEl = document.getElementById('coordLat');
        const lngEl = document.getElementById('coordLng');
        if (latEl) latEl.textContent = e.latlng.lat.toFixed(6);
        if (lngEl) lngEl.textContent = e.latlng.lng.toFixed(6);
    }

    /**
     * Toggle filter panel
     */
    function toggleFilterPanel() {
        const sidebar = document.getElementById('filterSidebar');
        const btn = document.getElementById('filterBtn');

        if (sidebar) {
            sidebar.classList.toggle('open');
            btn?.classList.toggle('active');
        }
    }

    /**
     * Toggle county borders visibility
     */
    function toggleCountyBorders() {
        const btn = document.getElementById('countyBtn');
        countiesVisible = !countiesVisible;

        if (countiesVisible) {
            map.addLayer(countiesLayer);
            btn?.classList.add('active');
            showToast('County boundaries shown', 'info');
        } else {
            map.removeLayer(countiesLayer);
            btn?.classList.remove('active');
            showToast('County boundaries hidden', 'info');
        }

        updateLegend();
    }

    /**
     * Toggle province borders visibility
     */
    function toggleProvinceBorders() {
        const btn = document.getElementById('provinceBtn');
        provincesVisible = !provincesVisible;

        if (provincesVisible) {
            map.addLayer(provincesLayer);
            btn?.classList.add('active');
            showToast('Province boundaries shown', 'info');
        } else {
            map.removeLayer(provincesLayer);
            btn?.classList.remove('active');
            showToast('Province boundaries hidden', 'info');
        }

        updateLegend();
    }

    /**
     * Toggle measurement tool
     */
    let drawControl = null;

    function toggleMeasurementTool() {
        measurementActive = !measurementActive;
        const btn = document.getElementById('measureBtn');

        // Deactivate other tools
        if (measurementActive) {
            deactivateOtherTools('measure');
        }

        if (measurementActive) {
            btn?.classList.add('active');

            // Add draw control
            drawControl = new L.Control.Draw({
                position: 'topright',
                draw: {
                    polyline: {
                        shapeOptions: {
                            color: CONFIG.defaultColor,
                            weight: 4
                        },
                        metric: true,
                        feet: false
                    },
                    polygon: {
                        allowIntersection: false,
                        shapeOptions: {
                            color: CONFIG.primaryColor,
                            fillColor: CONFIG.primaryColor,
                            fillOpacity: 0.2
                        },
                        metric: true
                    },
                    circle: {
                        shapeOptions: {
                            color: CONFIG.defaultColor,
                            fillOpacity: 0.2
                        },
                        metric: true
                    },
                    rectangle: {
                        shapeOptions: {
                            color: CONFIG.primaryColor,
                            fillOpacity: 0.2
                        }
                    },
                    marker: false,
                    circlemarker: false
                },
                edit: {
                    featureGroup: drawnItems,
                    remove: true
                }
            });
            map.addControl(drawControl);

            showToast('Measurement tool enabled - draw shapes on map', 'info');
        } else {
            btn?.classList.remove('active');

            if (drawControl) {
                map.removeControl(drawControl);
                drawControl = null;
            }

            showToast('Measurement tool disabled', 'info');
        }
    }

    /**
     * Toggle add point mode
     */
    function toggleAddPointMode() {
        addPointActive = !addPointActive;
        const btn = document.getElementById('addPointBtn');

        // Deactivate other tools
        if (addPointActive) {
            deactivateOtherTools('addPoint');
        }

        if (addPointActive) {
            btn?.classList.add('active');
            map.getContainer().style.cursor = 'crosshair';
            map.on('click', handleAddPoint);
            showToast('Click on the map to add a marker', 'info');
        } else {
            btn?.classList.remove('active');
            map.getContainer().style.cursor = '';
            map.off('click', handleAddPoint);
            showToast('Add marker mode disabled', 'info');
        }
    }

    function handleAddPoint(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;

        // Create custom marker
        const marker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'user-marker',
                html: `<div class="user-marker-icon">📌</div>`,
                iconSize: [30, 30],
                iconAnchor: [15, 30]
            }),
            draggable: true
        });

        // Create popup with delete option
        const popupContent = `
            <div class="user-marker-popup">
                <strong>Custom Marker</strong><br>
                Lat: ${lat.toFixed(6)}<br>
                Lng: ${lng.toFixed(6)}<br>
                <button class="btn btn-small btn-delete" onclick="window.IrishGIS.map.removeMarker(this)">
                    🗑️ Remove
                </button>
            </div>
        `;

        marker.bindPopup(popupContent);
        marker.on('dragend', function(e) {
            const newPos = e.target.getLatLng();
            marker.setPopupContent(`
                <div class="user-marker-popup">
                    <strong>Custom Marker</strong><br>
                    Lat: ${newPos.lat.toFixed(6)}<br>
                    Lng: ${newPos.lng.toFixed(6)}<br>
                    <button class="btn btn-small btn-delete" onclick="window.IrishGIS.map.removeMarker(this)">
                        🗑️ Remove
                    </button>
                </div>
            `);
        });

        userMarkersLayer.addLayer(marker);
        marker.openPopup();

        showToast('Marker added! Drag to reposition.', 'success');
    }

    /**
     * Remove a user marker
     */
    function removeMarker(buttonElement) {
        // Find the marker that owns this popup
        userMarkersLayer.eachLayer(function(layer) {
            if (layer.getPopup() && layer.getPopup().isOpen()) {
                userMarkersLayer.removeLayer(layer);
                showToast('Marker removed', 'info');
            }
        });
    }

    /**
     * Toggle elevation profile tool
     */
    function toggleElevationTool() {
        elevationActive = !elevationActive;
        const btn = document.getElementById('elevationBtn');

        // Deactivate other tools
        if (elevationActive) {
            deactivateOtherTools('elevation');
        }

        if (elevationActive) {
            btn?.classList.add('active');
            elevationPoints = [];
            if (elevationLine) {
                map.removeLayer(elevationLine);
                elevationLine = null;
            }
            map.getContainer().style.cursor = 'crosshair';
            map.on('click', handleElevationClick);
            map.on('dblclick', finishElevationProfile);
            showToast('Click to add points, double-click to finish elevation profile', 'info');
        } else {
            btn?.classList.remove('active');
            map.getContainer().style.cursor = '';
            map.off('click', handleElevationClick);
            map.off('dblclick', finishElevationProfile);
            elevationPoints = [];
            showToast('Elevation tool disabled', 'info');
        }
    }

    function handleElevationClick(e) {
        if (!elevationActive) return;

        elevationPoints.push([e.latlng.lat, e.latlng.lng]);

        // Add marker for point
        L.circleMarker([e.latlng.lat, e.latlng.lng], {
            radius: 6,
            fillColor: CONFIG.defaultColor,
            color: '#fff',
            weight: 2,
            fillOpacity: 1
        }).addTo(drawnItems);

        // Update line
        if (elevationPoints.length > 1) {
            if (elevationLine) map.removeLayer(elevationLine);
            elevationLine = L.polyline(elevationPoints, {
                color: CONFIG.defaultColor,
                weight: 3,
                dashArray: '5, 10'
            }).addTo(map);
        }

        showToast(`Point ${elevationPoints.length} added. Double-click to finish.`, 'info');
    }

    async function finishElevationProfile(e) {
        if (!elevationActive || elevationPoints.length < 2) {
            showToast('Add at least 2 points for elevation profile', 'warning');
            return;
        }

        // Disable double-click zoom temporarily
        e.originalEvent.preventDefault();

        showLoading(true);
        showToast('Fetching elevation data...', 'info');

        try {
            // Prepare locations for API
            const locations = elevationPoints.map(p => ({
                latitude: p[0],
                longitude: p[1]
            }));

            const response = await fetch(CONFIG.elevationApi, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ locations })
            });

            if (!response.ok) throw new Error('Failed to fetch elevation data');

            const data = await response.json();
            displayElevationProfile(data.results);

        } catch (error) {
            console.error('Elevation error:', error);
            showToast('Failed to get elevation data. Service may be unavailable.', 'error');
        } finally {
            showLoading(false);

            // Reset tool
            const btn = document.getElementById('elevationBtn');
            btn?.classList.remove('active');
            elevationActive = false;
            map.getContainer().style.cursor = '';
            map.off('click', handleElevationClick);
            map.off('dblclick', finishElevationProfile);
        }
    }

    function displayElevationProfile(results) {
        if (!results || results.length === 0) {
            showToast('No elevation data received', 'warning');
            return;
        }

        // Create elevation chart popup
        const elevations = results.map(r => r.elevation);
        const minElev = Math.min(...elevations);
        const maxElev = Math.max(...elevations);
        const avgElev = elevations.reduce((a, b) => a + b, 0) / elevations.length;

        // Calculate total distance
        let totalDistance = 0;
        for (let i = 1; i < elevationPoints.length; i++) {
            const p1 = L.latLng(elevationPoints[i - 1][0], elevationPoints[i - 1][1]);
            const p2 = L.latLng(elevationPoints[i][0], elevationPoints[i][1]);
            totalDistance += p1.distanceTo(p2);
        }

        // Build simple SVG chart
        const chartWidth = 280;
        const chartHeight = 100;
        const padding = 10;

        let pathData = '';
        const elevRange = maxElev - minElev || 1;

        results.forEach((r, i) => {
            const x = padding + (i / (results.length - 1)) * (chartWidth - 2 * padding);
            const y = chartHeight - padding - ((r.elevation - minElev) / elevRange) * (chartHeight - 2 * padding);
            pathData += (i === 0 ? 'M' : 'L') + `${x},${y} `;
        });

        const chartSvg = `
            <svg width="${chartWidth}" height="${chartHeight}" class="elevation-chart">
                <rect width="100%" height="100%" fill="var(--bg-secondary)" rx="4"/>
                <path d="${pathData}" fill="none" stroke="${CONFIG.defaultColor}" stroke-width="2"/>
            </svg>
        `;

        const content = `
            <div class="elevation-popup">
                <h4>Elevation Profile</h4>
                ${chartSvg}
                <div class="elevation-stats">
                    <div><strong>Min:</strong> ${minElev.toFixed(0)}m</div>
                    <div><strong>Max:</strong> ${maxElev.toFixed(0)}m</div>
                    <div><strong>Avg:</strong> ${avgElev.toFixed(0)}m</div>
                    <div><strong>Distance:</strong> ${formatDistance(totalDistance)}</div>
                </div>
            </div>
        `;

        // Show popup at midpoint
        const midIndex = Math.floor(elevationPoints.length / 2);
        L.popup()
            .setLatLng(elevationPoints[midIndex])
            .setContent(content)
            .openOn(map);

        showToast('Elevation profile generated!', 'success');
    }

    /**
     * Toggle legend visibility
     */
    function toggleLegend() {
        const legend = document.getElementById('mapLegend');
        const btn = document.getElementById('legendBtn');

        legendVisible = !legendVisible;

        if (legend) {
            legend.style.display = legendVisible ? 'block' : 'none';
        }

        if (btn) {
            btn.classList.toggle('active', legendVisible);
        }
    }

    /**
     * Handle nearby search
     */
    function handleNearbySearch() {
        nearbySearchActive = !nearbySearchActive;
        const btn = document.getElementById('nearbyBtn');

        // Deactivate other tools
        if (nearbySearchActive) {
            deactivateOtherTools('nearby');
        }

        if (nearbySearchActive) {
            btn?.classList.add('active');
            map.getContainer().style.cursor = 'crosshair';
            map.once('click', performNearbySearch);
            showToast('Click on the map to find nearby historical sites', 'info');
        } else {
            btn?.classList.remove('active');
            map.getContainer().style.cursor = '';
        }
    }

    async function performNearbySearch(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        const distance = 15; // km

        map.getContainer().style.cursor = '';
        document.getElementById('nearbyBtn')?.classList.remove('active');
        nearbySearchActive = false;

        showLoading(true);
        try {
            const url = `${CONFIG.api.sitesNearby}?lat=${lat}&lon=${lng}&distance=${distance}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Search failed');

            const data = await response.json();

            if (data.features && data.features.length > 0) {
                // Show results on map
                displaySites(data);

                // Add search origin marker
                L.circleMarker([lat, lng], {
                    radius: 10,
                    fillColor: '#4285f4',
                    color: 'white',
                    weight: 3,
                    fillOpacity: 1
                }).addTo(drawnItems)
                    .bindPopup(`<strong>Search Center</strong><br>${data.features.length} sites within ${distance}km`)
                    .openPopup();

                // Draw search radius
                L.circle([lat, lng], {
                    radius: distance * 1000,
                    color: '#4285f4',
                    fillColor: '#4285f4',
                    fillOpacity: 0.1,
                    weight: 2,
                    dashArray: '5, 5'
                }).addTo(drawnItems);

                showToast(`Found ${data.features.length} sites within ${distance}km`, 'success');
            } else {
                showToast(`No sites found within ${distance}km`, 'info');
            }
        } catch (error) {
            console.error('Nearby search error:', error);
            showToast('Search failed. Please try again.', 'error');
        } finally {
            showLoading(false);
        }
    }

    /**
     * Clear all drawings
     */
    function clearAllDrawings() {
        drawnItems.clearLayers();
        if (elevationLine) {
            map.removeLayer(elevationLine);
            elevationLine = null;
        }
        elevationPoints = [];
        showToast('All drawings cleared', 'info');
    }

    /**
     * Deactivate other tools
     */
    function deactivateOtherTools(currentTool) {
        if (currentTool !== 'coords' && coordsDisplayEnabled) {
            toggleCoordinatesDisplay();
        }
        if (currentTool !== 'measure' && measurementActive) {
            measurementActive = false;
            document.getElementById('measureBtn')?.classList.remove('active');
            if (drawControl) {
                map.removeControl(drawControl);
                drawControl = null;
            }
        }
        if (currentTool !== 'addPoint' && addPointActive) {
            addPointActive = false;
            document.getElementById('addPointBtn')?.classList.remove('active');
            map.off('click', handleAddPoint);
        }
        if (currentTool !== 'elevation' && elevationActive) {
            elevationActive = false;
            document.getElementById('elevationBtn')?.classList.remove('active');
            map.off('click', handleElevationClick);
            map.off('dblclick', finishElevationProfile);
        }
        if (currentTool !== 'nearby' && nearbySearchActive) {
            nearbySearchActive = false;
            document.getElementById('nearbyBtn')?.classList.remove('active');
        }

        map.getContainer().style.cursor = '';
    }

    // ===========================================================================
    // EVENT LISTENERS
    // ===========================================================================

    function setupEventListeners() {
        // Listen for language changes
        document.addEventListener('languageChanged', function(e) {
            loadSites();
        });

        // Handle keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                deactivateOtherTools('none');

                // Close filter panel
                const sidebar = document.getElementById('filterSidebar');
                if (sidebar?.classList.contains('open')) {
                    sidebar.classList.remove('open');
                    document.getElementById('filterBtn')?.classList.remove('active');
                }
            }
        });
    }

    // ===========================================================================
    // UPDATE LEGEND
    // ===========================================================================

    function updateLegend() {
        const legendContent = document.getElementById('legendContent');
        if (!legendContent) return;

        let html = `
            <div class="legend-section">
                <h5>Site Types</h5>
        `;

        // Add site type colors
        Object.entries(CONFIG.siteTypeColors).forEach(([type, color]) => {
            html += `
                <div class="legend-item">
                    <span class="legend-color" style="background-color: ${color};"></span>
                    <span>${formatSiteType(type)}</span>
                </div>
            `;
        });

        html += `
                <div class="legend-item">
                    <span class="legend-color national-monument-indicator" style="background-color: ${CONFIG.defaultColor}; border: 2px solid ${CONFIG.primaryColor};"></span>
                    <span>National Monument</span>
                </div>
            </div>
        `;

        // Add province colors if visible
        if (provincesVisible) {
            html += `
                <div class="legend-section">
                    <h5>Provinces</h5>
            `;
            Object.entries(CONFIG.provinceColors).forEach(([name, color]) => {
                html += `
                    <div class="legend-item">
                        <span class="legend-line" style="background-color: ${color};"></span>
                        <span>${name}</span>
                    </div>
                `;
            });
            html += `</div>`;
        }

        // Add county indicator if visible
        if (countiesVisible) {
            html += `
                <div class="legend-section">
                    <h5>Boundaries</h5>
                    <div class="legend-item">
                        <span class="legend-line" style="background-color: ${CONFIG.primaryColor};"></span>
                        <span>County Borders</span>
                    </div>
                </div>
            `;
        }

        legendContent.innerHTML = html;
    }

    // ===========================================================================
    // UTILITY FUNCTIONS
    // ===========================================================================

    function showLoading(show) {
        let overlay = document.querySelector('.loading-overlay');
        if (show) {
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'loading-overlay';
                overlay.innerHTML = `
                    <div class="loading-content">
                        <div class="loading-spinner"></div>
                        <span>Loading...</span>
                    </div>
                `;
                document.querySelector('.map-container')?.appendChild(overlay);
            }
            overlay.style.display = 'flex';
        } else if (overlay) {
            overlay.style.display = 'none';
        }
    }

    function showToast(message, type = 'info') {
        // Remove existing toast
        const existingToast = document.querySelector('.toast');
        if (existingToast) existingToast.remove();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ'}</span>
            <span class="toast-message">${message}</span>
        `;

        document.body.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Auto-remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function updateSiteCount(count) {
        const countEl = document.getElementById('siteCount');
        if (countEl) {
            countEl.textContent = count.toLocaleString();
        }
    }

    function calculatePolylineDistance(layer) {
        const latlngs = layer.getLatLngs();
        let total = 0;
        for (let i = 0; i < latlngs.length - 1; i++) {
            total += latlngs[i].distanceTo(latlngs[i + 1]);
        }
        return total;
    }

    function formatDistance(meters) {
        if (meters >= 1000) {
            return (meters / 1000).toFixed(2) + ' km';
        }
        return Math.round(meters) + ' m';
    }

    function formatArea(sqMeters) {
        if (sqMeters >= 1000000) {
            return (sqMeters / 1000000).toFixed(2) + ' km²';
        }
        if (sqMeters >= 10000) {
            return (sqMeters / 10000).toFixed(2) + ' ha';
        }
        return Math.round(sqMeters) + ' m²';
    }

    function formatSiteType(type) {
        if (!type) return 'Unknown';
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function getCurrentLang() {
        return document.documentElement.getAttribute('data-lang') || 'en';
    }

    // ===========================================================================
    // FILTER FUNCTIONS
    // ===========================================================================

    function applyFilters() {
        const siteType = document.getElementById('filterSiteType')?.value;
        const county = document.getElementById('filterCounty')?.value;
        const era = document.getElementById('filterEra')?.value;
        const nationalMonument = document.getElementById('filterNationalMonument')?.checked;

        currentFilters.siteType = siteType || null;
        currentFilters.county = county || null;
        currentFilters.era = era || null;
        currentFilters.nationalMonument = nationalMonument || null;

        loadSites();

        // Close sidebar
        document.getElementById('filterSidebar')?.classList.remove('open');
        document.getElementById('filterBtn')?.classList.remove('active');

        showToast('Filters applied', 'success');
    }

    function clearFilters() {
        document.getElementById('filterSiteType').value = '';
        document.getElementById('filterCounty').value = '';
        document.getElementById('filterEra').value = '';
        document.getElementById('filterNationalMonument').checked = false;

        currentFilters = { era: null, county: null, siteType: null, nationalMonument: null };
        loadSites();

        showToast('Filters cleared', 'info');
    }

    // ===========================================================================
    // JOURNEY MANAGEMENT (Bucket List)
    // ===========================================================================

    /**
     * Check journey status for a site and update popup buttons
     */
    async function checkJourneyStatus(siteId) {
        try {
            const response = await fetch('/api/v1/bucket-list/');
            if (!response.ok) return null;

            const data = await response.json();
            const items = data.results || data || [];
            const item = items.find(i => i.site && i.site.id == siteId);

            return item || null;
        } catch (error) {
            console.error('Error checking journey status:', error);
            return null;
        }
    }

    /**
     * Update popup button visibility based on journey status
     */
    function updatePopupButtons(siteId, journeyItem) {
        const addBtn = document.querySelector(`.btn-journey-add[data-site-id="${siteId}"]`);
        const visitedBtn = document.querySelector(`.btn-journey-visited[data-site-id="${siteId}"]`);
        const removeBtn = document.querySelector(`.btn-journey-remove[data-site-id="${siteId}"]`);
        const loading = document.querySelector(`.journey-loading[data-site-id="${siteId}"]`);

        // Always hide loading spinner when updating buttons
        if (loading) loading.style.display = 'none';

        if (!addBtn || !visitedBtn || !removeBtn) return;

        if (!journeyItem) {
            // Not in journey - show add buttons
            addBtn.style.display = 'flex';
            visitedBtn.style.display = 'flex';
            removeBtn.style.display = 'none';
        } else {
            // Already in journey - show remove button
            addBtn.style.display = 'none';
            visitedBtn.style.display = 'none';
            removeBtn.style.display = 'flex';

            // Update remove button text based on status
            const btnText = removeBtn.querySelector('.btn-text');
            if (btnText) {
                btnText.textContent = journeyItem.status === 'visited'
                    ? 'Remove from Visited'
                    : 'Remove from Wishlist';
            }
        }
    }

    /**
     * Add site to journey (wishlist or visited)
     */
    window.addToJourney = async function(siteId, siteName, status = 'wishlist') {
        const loading = document.querySelector(`.journey-loading[data-site-id="${siteId}"]`);
        const addBtn = document.querySelector(`.btn-journey-add[data-site-id="${siteId}"]`);
        const visitedBtn = document.querySelector(`.btn-journey-visited[data-site-id="${siteId}"]`);

        // Show loading spinner
        if (loading) loading.style.display = 'flex';
        if (addBtn) addBtn.style.display = 'none';
        if (visitedBtn) visitedBtn.style.display = 'none';

        try {
            const response = await fetch('/api/v1/bucket-list/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    site_id: siteId,
                    status: status
                })
            });

            if (!response.ok) {
                const error = await response.json();
                if (error.error && error.error.includes('already in bucket list')) {
                    showToast('Site already in your journey', 'info');
                } else {
                    throw new Error('Failed to add to journey');
                }
            } else {
                const statusText = status === 'visited' ? 'Visited' : 'Wishlist';
                showToast(`Added to ${statusText}!`, 'success');

                // Trigger stats update event (for same page)
                window.dispatchEvent(new CustomEvent('journeyUpdated'));

                // Trigger storage event (for other tabs)
                localStorage.setItem('journeyUpdated', Date.now().toString());
            }

            // Refresh button state
            const item = await checkJourneyStatus(siteId);
            updatePopupButtons(siteId, item);

        } catch (error) {
            console.error('Error adding to journey:', error);
            showToast('Failed to add to journey', 'error');

            // Reset buttons
            if (loading) loading.style.display = 'none';
            if (addBtn) addBtn.style.display = 'flex';
            if (visitedBtn) visitedBtn.style.display = 'flex';
        }
    };

    /**
     * Remove site from journey
     */
    window.removeFromJourney = async function(siteId, siteName) {
        const loading = document.querySelector(`.journey-loading[data-site-id="${siteId}"]`);
        const removeBtn = document.querySelector(`.btn-journey-remove[data-site-id="${siteId}"]`);

        // Show loading spinner
        if (loading) loading.style.display = 'flex';
        if (removeBtn) removeBtn.style.display = 'none';

        try {
            // First get the bucket list item ID
            const journeyItem = await checkJourneyStatus(siteId);
            if (!journeyItem) {
                showToast('Site not found in journey', 'error');
                // Hide loading and show button again
                if (loading) loading.style.display = 'none';
                if (removeBtn) removeBtn.style.display = 'flex';
                return;
            }

            const response = await fetch(`/api/v1/bucket-list/${journeyItem.id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error('Failed to remove from journey');
            }

            showToast('Removed from journey', 'success');

            // Trigger stats update event (for same page)
            window.dispatchEvent(new CustomEvent('journeyUpdated'));

            // Trigger storage event (for other tabs)
            localStorage.setItem('journeyUpdated', Date.now().toString());

            // Refresh button state (this will also hide loading)
            updatePopupButtons(siteId, null);

        } catch (error) {
            console.error('Error removing from journey:', error);
            showToast('Failed to remove from journey', 'error');

            // Reset buttons
            if (loading) loading.style.display = 'none';
            if (removeBtn) removeBtn.style.display = 'flex';
        }
    };

    /**
     * Toggle description expand/collapse
     */
    window.toggleDescription = function(uniqueId) {
        const shortDesc = document.getElementById(`${uniqueId}-short`);
        const fullDesc = document.getElementById(`${uniqueId}-full`);
        const btn = shortDesc?.parentElement?.querySelector('.btn-expand-desc');
        
        if (!shortDesc || !fullDesc || !btn) return;
        
        const isExpanded = btn.getAttribute('data-expanded') === 'true';
        
        if (isExpanded) {
            // Collapse
            shortDesc.style.display = 'block';
            fullDesc.style.display = 'none';
            btn.setAttribute('data-expanded', 'false');
            btn.querySelector('.expand-text').textContent = 'Read more';
        } else {
            // Expand
            shortDesc.style.display = 'none';
            fullDesc.style.display = 'block';
            btn.setAttribute('data-expanded', 'true');
            btn.querySelector('.expand-text').textContent = 'Show less';
        }
    };

    /**
     * Get CSRF token from cookie or meta tag
     */
    function getCsrfToken() {
        // First try to get from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag && metaTag.content) {
            return metaTag.content;
        }

        // Fallback to cookie
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Listen for popup open events to check journey status
     */
    function setupPopupListeners() {
        if (map) {
            map.on('popupopen', async function(e) {
                const popup = e.popup;
                const content = popup.getContent();

                // Extract site ID from popup content
                const match = content.match(/data-site-id="(\d+)"/);
                if (match && match[1]) {
                    const siteId = match[1];
                    const journeyItem = await checkJourneyStatus(siteId);
                    updatePopupButtons(siteId, journeyItem);
                }
            });
        }
    }

    // ===========================================================================
    // PUBLIC API
    // ===========================================================================

    window.IrishGIS = window.IrishGIS || {};
    window.IrishGIS.map = {
        init: initMap,
        loadSites: loadSites,
        loadCounties: loadCounties,
        loadProvinces: loadProvinces,
        setFilter: function(filterName, value) {
            currentFilters[filterName] = value;
            loadSites();
        },
        clearFilters: clearFilters,
        applyFilters: applyFilters,
        getMap: function() { return map; },
        removeMarker: removeMarker,
        toggleCounties: toggleCountyBorders,
        toggleProvinces: toggleProvinceBorders,
        clearDrawings: clearAllDrawings
    };

    // Auto-initialize if map container exists
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (document.getElementById('map')) {
                initMap();
            }
        });
    } else {
        if (document.getElementById('map')) {
            initMap();
        }
    }

})();
