/**
 * Irish Historical Sites GIS - Service Worker
 * ============================================
 * Professional PWA implementation with offline support
 * 
 * Caching Strategies:
 * - Static assets: Cache First (CSS, JS, images)
 * - API responses: Network First with cache fallback
 * - Pages: Stale While Revalidate
 * - Map tiles: Cache First with network fallback
 */

const CACHE_VERSION = 'v1.0.0';
const STATIC_CACHE = `irish-gis-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `irish-gis-dynamic-${CACHE_VERSION}`;
const API_CACHE = `irish-gis-api-${CACHE_VERSION}`;
const TILE_CACHE = `irish-gis-tiles-${CACHE_VERSION}`;

// Assets to cache immediately on install
const STATIC_ASSETS = [
    '/',
    '/explore/',
    '/my-journey/',
    '/about/',
    '/offline/',
    '/static/css/theme.css',
    '/static/css/components.css',
    '/static/js/theme.js',
    '/static/js/i18n.js',
    '/static/js/map.js',
    '/static/images/favicon.svg',
    '/static/images/icon-192.png',
    '/static/images/icon-512.png',
    '/static/manifest.json'
];

// External CDN assets to cache
const CDN_ASSETS = [
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css',
    'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js',
    'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
    'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
    'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js'
];

// ============================================================================
// INSTALL EVENT - Cache static assets
// ============================================================================
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker...');
    
    event.waitUntil(
        Promise.all([
            // Cache static assets
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS).catch((err) => {
                    console.warn('[SW] Some static assets failed to cache:', err);
                });
            }),
            // Cache CDN assets
            caches.open(DYNAMIC_CACHE).then((cache) => {
                console.log('[SW] Caching CDN assets');
                return Promise.all(
                    CDN_ASSETS.map((url) => 
                        cache.add(url).catch((err) => {
                            console.warn(`[SW] Failed to cache CDN asset: ${url}`, err);
                        })
                    )
                );
            })
        ]).then(() => {
            console.log('[SW] Installation complete');
            // Skip waiting to activate immediately
            return self.skipWaiting();
        })
    );
});

// ============================================================================
// ACTIVATE EVENT - Clean up old caches
// ============================================================================
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cacheName) => {
                        // Delete old version caches
                        return cacheName.startsWith('irish-gis-') && 
                               !cacheName.includes(CACHE_VERSION);
                    })
                    .map((cacheName) => {
                        console.log(`[SW] Deleting old cache: ${cacheName}`);
                        return caches.delete(cacheName);
                    })
            );
        }).then(() => {
            console.log('[SW] Activation complete');
            // Take control of all pages immediately
            return self.clients.claim();
        })
    );
});

// ============================================================================
// FETCH EVENT - Handle requests with appropriate strategies
// ============================================================================
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Skip Chrome extensions and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }
    
    // Route to appropriate strategy
    if (isApiRequest(url)) {
        event.respondWith(networkFirstStrategy(request, API_CACHE));
    } else if (isMapTile(url)) {
        event.respondWith(cacheFirstStrategy(request, TILE_CACHE));
    } else if (isStaticAsset(url)) {
        event.respondWith(cacheFirstStrategy(request, STATIC_CACHE));
    } else if (isCdnAsset(url)) {
        event.respondWith(cacheFirstStrategy(request, DYNAMIC_CACHE));
    } else if (isNavigationRequest(request)) {
        event.respondWith(staleWhileRevalidate(request, DYNAMIC_CACHE));
    } else {
        event.respondWith(networkFirstStrategy(request, DYNAMIC_CACHE));
    }
});

// ============================================================================
// REQUEST CLASSIFICATION HELPERS
// ============================================================================

function isApiRequest(url) {
    return url.pathname.startsWith('/api/');
}

function isMapTile(url) {
    return url.hostname.includes('tile.openstreetmap.org') ||
           url.hostname.includes('tile.opentopomap.org') ||
           url.hostname.includes('arcgisonline.com') ||
           url.pathname.includes('/tile/');
}

function isStaticAsset(url) {
    return url.pathname.startsWith('/static/') ||
           url.pathname.match(/\.(css|js|svg|png|jpg|jpeg|gif|webp|woff|woff2|ttf|eot)$/i);
}

function isCdnAsset(url) {
    return url.hostname.includes('unpkg.com') ||
           url.hostname.includes('cdnjs.cloudflare.com') ||
           url.hostname.includes('cdn.jsdelivr.net');
}

function isNavigationRequest(request) {
    return request.mode === 'navigate' ||
           request.headers.get('accept')?.includes('text/html');
}

// ============================================================================
// CACHING STRATEGIES
// ============================================================================

/**
 * Cache First Strategy
 * Best for: Static assets, CDN resources, map tiles
 * Serves from cache, falls back to network
 */
async function cacheFirstStrategy(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        // Optionally refresh cache in background for tiles
        if (cacheName === TILE_CACHE) {
            refreshCache(request, cache);
        }
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            // Clone and cache the response
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.warn('[SW] Cache first failed:', request.url);
        return createOfflineResponse(request);
    }
}

/**
 * Network First Strategy
 * Best for: API requests, dynamic content
 * Tries network first, falls back to cache
 */
async function networkFirstStrategy(request, cacheName) {
    const cache = await caches.open(cacheName);
    
    try {
        const networkResponse = await fetch(request);
        
        // Cache successful API responses
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return offline JSON for API requests
        if (isApiRequest(new URL(request.url))) {
            return new Response(
                JSON.stringify({ 
                    error: 'offline', 
                    message: 'You are currently offline. This data was not cached.' 
                }),
                { 
                    status: 503, 
                    headers: { 'Content-Type': 'application/json' } 
                }
            );
        }
        
        return createOfflineResponse(request);
    }
}

/**
 * Stale While Revalidate Strategy
 * Best for: HTML pages, frequently updated content
 * Returns cached version immediately, updates cache in background
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);
    
    // Fetch fresh version in background
    const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    }).catch(() => null);
    
    // Return cached version if available, otherwise wait for network
    if (cachedResponse) {
        return cachedResponse;
    }
    
    const networkResponse = await fetchPromise;
    if (networkResponse) {
        return networkResponse;
    }
    
    return createOfflineResponse(request);
}

/**
 * Background cache refresh (for map tiles)
 */
function refreshCache(request, cache) {
    fetch(request).then((response) => {
        if (response.ok) {
            cache.put(request, response);
        }
    }).catch(() => {});
}

/**
 * Create offline response
 */
function createOfflineResponse(request) {
    const url = new URL(request.url);
    
    // Return offline page for navigation requests
    if (isNavigationRequest(request)) {
        return caches.match('/offline/').then((response) => {
            return response || new Response(
                `<!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Offline - Irish Historical Sites</title>
                    <style>
                        body { font-family: system-ui, sans-serif; display: flex; 
                               justify-content: center; align-items: center; 
                               min-height: 100vh; margin: 0; background: #1a5f4a; color: white; }
                        .container { text-align: center; padding: 2rem; }
                        h1 { font-size: 2rem; margin-bottom: 1rem; }
                        p { opacity: 0.9; margin-bottom: 2rem; }
                        button { background: #ff8c00; color: white; border: none; 
                                padding: 1rem 2rem; font-size: 1rem; border-radius: 8px; 
                                cursor: pointer; }
                        button:hover { background: #e67e00; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>📍 You're Offline</h1>
                        <p>Please check your internet connection to explore Irish historical sites.</p>
                        <button onclick="location.reload()">Try Again</button>
                    </div>
                </body>
                </html>`,
                { 
                    status: 503, 
                    headers: { 'Content-Type': 'text/html' } 
                }
            );
        });
    }
    
    // Return empty response for other requests
    return new Response('', { status: 503, statusText: 'Service Unavailable' });
}

// ============================================================================
// BACKGROUND SYNC (for offline journey actions)
// ============================================================================
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);
    
    if (event.tag === 'sync-journey') {
        event.waitUntil(syncJourneyData());
    }
});

async function syncJourneyData() {
    // Get pending journey actions from IndexedDB
    // This would sync any offline journey additions when back online
    console.log('[SW] Syncing journey data...');
}

// ============================================================================
// PUSH NOTIFICATIONS (optional, for future use)
// ============================================================================
self.addEventListener('push', (event) => {
    if (!event.data) return;
    
    const data = event.data.json();
    const options = {
        body: data.body || 'New update from Irish Historical Sites',
        icon: '/static/images/icon-192.png',
        badge: '/static/images/icon-72.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/'
        },
        actions: [
            { action: 'explore', title: 'Explore' },
            { action: 'close', title: 'Close' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(
            data.title || 'Irish Historical Sites',
            options
        )
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    if (event.action === 'explore' || !event.action) {
        event.waitUntil(
            clients.openWindow(event.notification.data.url || '/explore/')
        );
    }
});

// ============================================================================
// MESSAGE HANDLING (for communication with main app)
// ============================================================================
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_VERSION });
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((names) => 
                Promise.all(names.map((name) => caches.delete(name)))
            ).then(() => {
                event.ports[0].postMessage({ cleared: true });
            })
        );
    }
});

console.log(`[SW] Service Worker loaded - Version ${CACHE_VERSION}`);

