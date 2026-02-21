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
- `GET /api/inventory/current` - Current stock with group expansion support

## Lazy Import Optimization (Feb 12, 2026 - Deployment Crash Fix)
- **Problem:** Backend crashed on startup in deployed environment due to heavy top-level imports
- **Solution:** Converted pandas, numpy, emergentintegrations to lazy imports inside functions
- **Result:** Startup memory reduced from ~152MB to ~17.5MB

## Item Groups (Feb 12, 2026)
- Manual grouping of similar items for combined buffer & order calculations
- Leader item displayed everywhere, shows mapped transaction names per member
- CRUD: POST/GET/DELETE /api/item-groups, GET /api/item-groups/suggestions

## Stamp Detail Page (Feb 12, 2026)
- Clickable stamps → /stamp/{stampName} detail page with items, stock, executive assignment

## Seasonal Item Buffers → Stock Rotation Model (Feb 13, 2026)
- Complete rewrite to 2.73-month rotation cycle model
- Season profiles: Peak (Oct-Jan, Apr-May), Normal (Feb-Mar, Jun), Off-season (Jul-Sep)

## Global Upload Progress (Feb 16, 2026)
- Created UploadContext for persistent upload state across page navigation

## Undo Upload - Full History (Feb 16, 2026)
- Backend returns ALL uploaded files, includes all upload types

## Sales Trend Daily/Monthly Toggle (Feb 16, 2026)
- Backend: `trend_granularity` param (daily/monthly/auto)
- Frontend: Daily/Monthly/Auto toggle buttons on the sales trend chart

## Selective Browser Notifications (Feb 16, 2026)
- Per-category toggles for browser push alerts

## Labour Profit Calculation Fix (Feb 17, 2026)
- Sale returns now treated as PURCHASES (buying back from customer)
- Fixed `labor` field: now stores actual labour value, not the Total column

## Item Group Consolidation (Feb 20, 2026) — LATEST
- **Problem:** Items like TULSI 70 BELT had no purchase ledger, causing wrong Fine/Labour.
  Items sold interchangeably (e.g., SNT 40 PREMIUM / SNT-40) showed negative stock.
- **Solution:** Group-aware purchase ledger (`group_utils.py`)
  - `build_group_ledger()` combines all member ledger entries → weighted-average tunch & labour
  - `resolve_to_leader()` resolves any name through mappings + groups to the leader
- **Stamp-level tracking:** Grouping is for CALCULATION only. For stamp approvals and
  physical vs book, each member's weight counts under its OWN stamp:
  - `by_stamp` distributes group members to their respective stamps
  - `stamp_items` flat list for stamp detail and physical vs book comparison
  - `_member_key()` preserves physical item identity even when mappings redirect names
- **Affected areas updated:**
  - `stock_service.py` → group-aware fine/labour, member breakdowns, per-stamp distribution
  - `customer-profit`, `supplier-profit`, `item-profit`, `historical-profit` → group ledger
  - `visualization` → already had group resolution
  - `stamps/{name}/detail` → uses stamp_items for correct per-stamp weights
  - `physical-stock/compare` → uses stamp_items for correct comparison
  - Frontend CurrentStock.jsx → expandable groups + stamp-specific flat view
- **Result:** 0 negative items, correct Fine/Labour, correct per-stamp weights
- **Item Groups:** TULSI 70 -264 [+BELT], SNT 40-256 [+PREMIUM], KADA-AS 70 [+FANCY], SLG 70 BICCHIYA-255 [+MICRO], BARTAN-040 [+LOTA]

## Date-Based Stock Verification (Feb 20, 2026)
- SEE selects a **verification date** when entering stock (defaults to today)
- System calculates **expected closing stock** as of that date:
  - Opening stock + all purchases/receives up to that date - all sales/issues up to that date
- `get_stamp_closing_stock(stamp, as_of_date)` in stock_service.py handles this calculation
- **Approvals** page shows comparison with color coding:
  - Green = match within 20g (0.020 kg)
  - Blue = stock increased (entered > expected)
  - Red = stock decreased (entered < expected)
- Admin/Manager can **edit verification date** on any entry (pending or approved) via pencil icon
  - PUT `/api/manager/update-verification-date/{stamp}` — updates date and recalculates book values
- When admin deletes transactions, expected stock auto-recalculates (computed on-the-fly)
- Mobile-optimized layout: stacked cards, wrapped badges, compact table with truncation

## Labour Profit Calculation Bug Fix (Feb 20, 2026)
- **Bug 1**: `purchase_labour_per_gram` had `/1000` making purchase rate 1000x too small → inflated/wrong profits
- **Bug 2**: Ledger fallback used `labour_per_kg` (rate) instead of `total_labour` (total Rs amount)
- **Bug 3**: Same two bugs existed in supplier-profit endpoint
- **Fix**: Removed `/1000`, used `total_labour` for ledger fallback in both item-profit and supplier-profit
- **Verified**: Customer-profit and historical-profit have NO bugs
- Result: ₹33.7L total labour profit (was -₹1.05L), 195/205 items with non-zero values

## Branch Transfer Parsing Fix (Feb 20, 2026)
- Last line of branch transfer files (containing just a number like "136") was being parsed as an item
- Fixed: `item_name.isdigit()` now filters ALL purely numeric names (was only filtering ≤2 digits)

## Mobile UI Optimization (Feb 20, 2026)
- Applied responsive mobile-first patterns across ALL 32 pages:
  - Padding: p-3 sm:p-6 md:p-8 (was p-6 md:p-8)
  - Headings: text-2xl sm:text-4xl md:text-5xl
  - Stat values: text-lg sm:text-2xl md:text-3xl
  - Grid: grid-cols-2 md:grid-cols-4 with smaller gaps
  - Tables: hidden columns on mobile, truncated text, compact cells
- ProfitAnalysis.jsx fully rewritten for mobile: compact date range, responsive table
- ManagerApprovals.jsx rewritten: stacked cards, wrapped badges, date editing
- ExecutiveStockEntry.jsx: responsive form layout
- Specific table columns hidden on mobile with `hidden sm:table-cell`

## Labour Profit Calculation Fix v2 (Feb 21, 2026)
- **Root cause**: `labor` field in transactions stored 0 for some uploads (depends on Excel column names)
- **Fix**: All profit endpoints now use `total_amount` as primary source for sale labour
  - In silver trading, the "Total" column IS the labour Rs per line (silver settled by weight, not Rs)
  - `total_amount` or `labor` — whichever is non-zero
- **Purchase labour**: ALWAYS sourced from purchase_ledger's `labour_per_kg / 1000` (per gram)
  - Individual purchase transactions often have labor=0
  - Purchase ledger has cumulative accurate data
- **Endpoints updated**: item-profit, customer-profit, supplier-profit, sales-summary, historical-profit (all views)
- **Result**: Labour Profit now ₹38.84L (was -₹1.05L), 200/205 items with non-zero labour

## Unmapped Items Cleanup (Feb 21, 2026)
- Filtered purely numeric item names (e.g., "136") from unmapped items endpoint
- Filtered test data patterns: TEST_SILVER_ITEM_*, Item X, Batch*
- Branch transfer parsing already prevents new numeric items (isdigit() check)
- Unmapped count reduced from 439 to 233 (test data removed)

## Sortable Table Columns (Feb 21, 2026)
- Created reusable `useSortableData` hook and `SortableHeader` component
- All table columns are now sortable (click to toggle asc/desc) on:
  - Party Analytics: 4 tabs (Customers, Suppliers, Customer Profit, Supplier Profit)
  - Profit Analysis: item name, sold kg, tunch, silver/labour profit
  - Current Stock: item name, stamp, net wt, gross wt, fine, labour
  - Purchase Rates: item name, purchase tunch, labour per kg
- Sort indicators: ArrowUpDown (inactive), ArrowUp/ArrowDown (active)
- Page resets to 1 on sort change

## Party Analytics Mobile Optimization (Feb 21, 2026)
- Compact date range selector (matching Profit Analysis style)
- Top Customer/Supplier cards: compact with truncated names
- Scrollable tabs on mobile (overflow-x-auto)
- Hidden less-important columns on mobile (Fine Wt, Sales Value, Txns)
- Truncated party names with max-w for mobile
- Added pagination to Customer Profit and Supplier Profit tabs

## Backlog
- (P1) Item Mapping: unmapped historical items need mapping
- (P2) Refactor server.py into proper FastAPI structure (routes, services, models)
