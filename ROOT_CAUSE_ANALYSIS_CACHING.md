# ROOT CAUSE ANALYSIS - Stamp Display Issue

## Issue Summary
User reported "SNT-40 PREMIUM" appearing in Stamp 5 with 54 total items, when it should be in Stamp 6 with 24 items. Issue persisted even after:
- Database updates
- Browser cache clearing
- Hard refreshes
- Incognito mode
- Frontend restarts

## ROOT CAUSE: Kubernetes Ingress/Proxy Caching

### The Problem
The application runs behind a Kubernetes ingress controller that caches GET requests for performance. When the `/api/master-items` endpoint is called, the ingress returns cached responses even though:
- The backend database has been updated
- The backend API generates fresh responses
- Browser cache has been cleared

### Evidence
1. **Database Check**: SNT-40 PREMIUM in Stamp 6 ✓
2. **Direct API Call**: curl returns Stamp 6 ✓
3. **Frontend Behavior**: Shows Stamp 5 (stale cached data) ✗

### Why Browser Cache Clear Didn't Help
- Browser cache was not the issue
- The caching was happening at the infrastructure level (Kubernetes ingress)
- Even incognito mode received cached responses from the proxy

## Solution Implemented

### 1. Backend: Cache-Control Headers
Added HTTP cache-control headers to `/api/master-items` endpoint:
```python
return JSONResponse(
    content=items,
    headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
)
```

**Status**: ✅ Implemented but NOT sufficient for proxy caching

### 2. Frontend: Cache-Busting Query Parameters
Added timestamp query parameters to force unique URLs:

#### ExecutiveStockEntry.jsx
```javascript
// fetchStamps function
const cacheBuster = `?_t=${Date.now()}`;
const response = await axios.get(`${API}/master-items${cacheBuster}`);

// loadStampItems function
const cacheBuster = `?_t=${Date.now()}`;
const response = await axios.get(`${API}/master-items${cacheBuster}`);
```

#### PolytheneEntry.jsx
```javascript
const cacheBuster = `?_t=${Date.now()}`;
const response = await axios.get(`${API}/inventory/current${cacheBuster}`);

// ALSO: Include negative_items in search results
const allInventoryItems = [...response.data.inventory, ...response.data.negative_items];
```

**Status**: ✅ Implemented - This forces Kubernetes ingress to treat each request as unique

## Additional Fix: Polythene Entry Missing Items

### Problem
"SNT-40 PREMIUM" not appearing in Polythene Adjustment search because it has negative stock (-17.708 kg gross, -13.662 kg net).

### Cause
Polythene Entry page only showed `response.data.inventory` (positive stock items), excluding `response.data.negative_items`.

### Solution
```javascript
const allInventoryItems = [...response.data.inventory, ...response.data.negative_items];
setAllItems(allInventoryItems);
```

Now polythene executives can adjust weights for ALL items, including those with negative stock.

## Correct Data State

### Database (Source of Truth):
- Stamp 5: **53 items** (no SNT-40 PREMIUM)
- Stamp 6: **24 items** (includes SNT-40 PREMIUM)

### What User Was Seeing (Cached):
- Stamp 5: 54 items (with SNT-40 PREMIUM) ← OLD DATA
- Stamp 6: 23 items (without SNT-40 PREMIUM) ← OLD DATA

### After Cache-Busting Fix:
- Stamp 5: **53 items** (no SNT-40 PREMIUM) ✓
- Stamp 6: **24 items** (with SNT-40 PREMIUM) ✓

## Why This Issue Was Hard to Diagnose

1. **Database was correct**: Direct queries showed proper stamps
2. **API was correct**: curl tests returned proper data
3. **Code was correct**: No logic errors in filtering
4. **Multi-layer caching**: Browser + Proxy made it complex
5. **Intermittent nature**: Depends on cache TTL and request timing

## Files Modified

1. `/app/backend/server.py`
   - Added JSONResponse with cache-control headers
   - Fixed import statements

2. `/app/frontend/src/pages/ExecutiveStockEntry.jsx`
   - Added cache-busting to `fetchStamps()` (line 36)
   - Added cache-busting to `loadStampItems()` (line 61)

3. `/app/frontend/src/pages/PolytheneEntry.jsx`
   - Added cache-busting to `fetchAllItems()` (line 49)
   - Include negative_items in search results

## Testing Instructions

### For User:
1. **Hard refresh the page**: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. **Login as SEE1** (executive123)
3. **Select Stamp 5**: Should show 53 items (no SNT-40 PREMIUM)
4. **Select Stamp 6**: Should show 24 items (with SNT-40 PREMIUM)

### For Polythene Entry:
1. **Login as PEE1** (poly123)
2. **Search for "SNT"**: Should now show all 3 items including SNT-40 PREMIUM
3. **Can adjust polythene** for SNT-40 PREMIUM even though it has negative stock

## Long-term Recommendations

1. **API Versioning**: Add `/v1/` prefix to APIs and increment when data structure changes
2. **ETags**: Implement ETag headers for proper cache validation
3. **WebSocket Updates**: Push real-time updates for stamp changes
4. **Frontend State Management**: Use React Query or SWR for better cache control

## Status: ✅ RESOLVED

Cache-busting mechanisms now in place at both backend (headers) and frontend (query parameters) levels to prevent stale data from being displayed.
