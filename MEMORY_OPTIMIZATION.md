# Memory Optimization Summary

## Critical Memory Issues Fixed

### 1. **Double Marker Storage (CRITICAL)**
**Problem:** Markers were being added to both `sitesLayer` AND `markersCluster`, causing each marker to be stored twice in memory.

**Fix:** Modified `displaySites()` to add markers directly to the cluster group only, eliminating duplicate storage.

**Impact:** ~50% reduction in marker memory usage

### 2. **Event Listener Memory Leaks**
**Problem:** Event listeners were added but never removed, causing memory accumulation over time.

**Fix:** 
- Added cleanup function `cleanupEventListeners()`
- Store listener references for proper removal
- Clean up on page unload (`beforeunload` event)
- Remove DOMContentLoaded listener after initialization

**Impact:** Prevents memory leaks from accumulating event listeners

### 3. **Excessive Data Loading**
**Problem:** Loading 200 sites at once with full descriptions was too much for 512MB RAM.

**Fixes:**
- Reduced page size from 200 to 100 sites per request
- Reduced max page size from 500 to 200
- Descriptions are truncated to 200 characters in list view
- Only essential fields are fetched from database

**Impact:** ~50% reduction in data transfer and memory usage

### 4. **Gunicorn Configuration**
**Problem:** Worker configuration wasn't optimized for 512MB memory limit.

**Fixes:**
- Reduced `max-requests` from 500 to 250 (prevents memory accumulation)
- Added `--preload` flag (shared memory, reduces per-worker overhead)
- Reduced `max-requests-jitter` from 50 to 25

**Impact:** More frequent worker recycling prevents memory leaks

### 5. **Database Query Optimization**
**Problem:** Queries were fetching unnecessary fields.

**Fix:** 
- Using `only()` to limit fields fetched
- Prefetching images efficiently with ordering
- Using `select_related` for foreign keys

**Impact:** Reduced database memory footprint

## Memory Usage Estimates

### Before Optimization:
- Markers: ~2MB (double storage)
- Event listeners: Accumulating (leak)
- Data per request: ~5-10MB (200 sites with full data)
- **Total per page load: ~15-20MB+**

### After Optimization:
- Markers: ~1MB (single storage)
- Event listeners: Cleaned up (no leak)
- Data per request: ~2-3MB (100 sites with truncated data)
- **Total per page load: ~5-7MB**

## Recommendations

1. **Monitor Memory Usage:**
   - Check Render logs for memory warnings
   - Monitor `/api/health/` endpoint
   - Watch for OOM errors

2. **Further Optimizations (if needed):**
   - Implement viewport-based loading (only load sites in visible area)
   - Add pagination to map markers
   - Lazy-load site details on popup open
   - Use image CDN for site photos

3. **Upgrade Path:**
   - If memory issues persist, consider upgrading to Render Starter plan ($7/month, 512MB → 1GB RAM)
   - Or implement viewport-based loading to reduce initial load

## Testing

After deployment, verify:
1. ✅ Explore page loads without OOM errors
2. ✅ Map markers display correctly
3. ✅ No memory leaks (check browser DevTools Memory profiler)
4. ✅ Page can be reloaded multiple times without issues

## Files Modified

1. `static/js/map.js` - Fixed double marker storage, added cleanup
2. `apps/api/views.py` - Reduced pagination, optimized queries
3. `Dockerfile` - Optimized Gunicorn configuration
4. `apps/api/serializers.py` - Already optimized (truncated descriptions)

---

**Last Updated:** December 2025

