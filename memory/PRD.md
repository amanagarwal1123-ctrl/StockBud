# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI, Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios, SheetJS (xlsx)
- **Database:** MongoDB (test_database)

## Data Architecture
- `transactions` collection: Current operational data (daily sales, purchases, branch transfers)
- `historical_transactions` collection: Historical data for analytics — does NOT affect dashboard
- Upload Files page → `transactions` (current operations)
- Historical Upload page → `historical_transactions` (analytics only)

## Client-Side Excel Parsing Architecture (Feb 11, 2026 - OOM fix)
- **Problem:** 24MB XLSX files caused OOM crashes in deployed pods (256-512MB memory limit)
- **Solution:** Excel parsed in the BROWSER using SheetJS, rows sent as JSON batches
- **Flow:** File → SheetJS parse in browser → detect headers → send 2000-row JSON batches → server applies column mapping → MongoDB insert
- **Endpoint:** `POST /api/upload/client-batch` — accepts headers + row arrays, returns batch_records + total_so_far
- **Zero server-side Excel parsing** — no pandas, no openpyxl, no OOM
- **Progress bar** shows real-time batch progress with percentage

## Legacy Chunked Upload (still available for non-historical files)
- Files >200KB auto-chunked into 200KB binary chunks
- 3-step API: init → chunk(s) → finalize → background processing
- MongoDB-backed chunk storage for multi-pod deployments
- Used by UploadManager for regular transaction files

## Historical Profit Analysis (Feb 11, 2026)
- Endpoint: `GET /api/analytics/historical-profit?year=2025&view={yearly|customer|supplier|item|month}`
- Frontend: "Profit" tab in Data Visualization page

## Key Credentials
- Admin: admin / admin123  
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123

## Key Endpoints
- `POST /api/upload/client-batch` - Client-parsed batch upload (NEW - OOM-safe)
- `POST /api/upload/init` - Chunked upload init
- `POST /api/upload/chunk/{upload_id}` - Chunk upload
- `POST /api/upload/finalize/{upload_id}` - Finalize chunked upload
- `GET /api/upload/status/{upload_id}` - Poll upload status
- `GET /api/historical/summary` - Historical data summary
- `GET /api/analytics/historical-profit` - Profit analysis

## Lazy Import Optimization (Feb 12, 2026 - Deployment Crash Fix)
- **Problem:** Backend crashed on startup in deployed environment (connection refused on port 8001) due to heavy top-level imports consuming ~135MB at startup
- **Solution:** Converted pandas (~32MB), numpy (~7MB), and emergentintegrations (~96MB) from top-level imports to lazy imports inside the functions that use them
- **Result:** Startup memory reduced from ~152MB to ~17.5MB, preventing OOM kills in memory-constrained pods
- **Functions modified:** `_read_excel_once`, `_read_excel_from_path`, `upload_master_stock`, `upload_purchase_ledger`, smart-insights endpoint, seasonal-analysis endpoint
- **Also replaced:** `pd.isna()` → `math.isnan()`, `np.percentile()` → pure Python sorted percentile

## Item Groups (Feb 12, 2026)
- Manual grouping of similar items for combined buffer & order calculations
- Leader item displayed everywhere, shows mapped transaction names per member
- CRUD: POST/GET/DELETE /api/item-groups, GET /api/item-groups/suggestions

## Stamp Detail Page (Feb 12, 2026)
- Clickable stamps → /stamp/{stampName} detail page with items, stock, executive assignment
- One stamp → one executive, one executive can have multiple stamps

## Seasonal Item Buffers (Feb 12, 2026)
- Categorization uses historical data + Hindu calendar seasons for velocity
- Item groups merged during categorization, season boost applied

## Backlog
- (P1) Item Mapping: 219 unmapped historical items need mapping
- (P2) Refactor server.py into proper FastAPI structure
