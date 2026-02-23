# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI, Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios, SheetJS (xlsx)
- **Database:** MongoDB (test_database)

## Key Credentials
- Admin: admin / admin123  
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123

## Data Architecture
- `transactions` collection: Current operational data (daily sales, purchases, branch transfers)
- `historical_transactions` collection: Historical data for analytics
- Upload Files page → `transactions` (current operations)
- Historical Upload page → `historical_transactions` (analytics only)

## Key Endpoints
- `POST /api/upload/client-batch` - Client-parsed batch upload (OOM-safe)
- `POST /api/upload/init` - Chunked upload init
- `GET /api/manager/approval-details/{stamp}` - Book vs physical comparison
- `GET /api/debug/item-closing/{item_name}?as_of_date=YYYY-MM-DD` - Item calculation debug
- `POST /api/system/fix-dates` - Fix swapped month/day dates (admin only)
- `POST /api/system/reset` - Selective system reset
- `POST /api/master-stock/upload` - Upload master stock (replaces opening stock)

## Completed Features

### Date Parsing Bug Fix (Feb 23, 2026)
- **Bug**: `normalize_date()` used `pd.to_datetime(date_str, dayfirst=True)` which swapped month/day for ISO-format dates (YYYY-MM-DD). Feb 3 stored as Mar 2, etc.
- **Fix**: Detect ISO format strings (regex `^\d{4}-\d{1,2}-\d{1,2}$`) and parse with `dayfirst=False`; native datetime objects formatted directly via `strftime`
- **Migration**: 2,037 transactions fixed across 5 dates (2026-03-02→02-03, 04-02→02-04, 05-02→02-05, 06-02→02-06, 07-02→02-07)
- **UI**: Added "Fix Swapped Dates" admin button in sidebar
- **Debug**: Added `/api/debug/item-closing/{item_name}` endpoint for calculation transparency

### Stamp Closing Stock Double-Count Fix (Feb 21, 2026)
- Fixed `get_stamp_closing_stock()` double-counting items mapped to group leaders in other stamps
- Polythene adjustments now date-filtered (up to verification_date)

### Labour Profit Calculation Fix v2 (Feb 21, 2026)
- All profit endpoints use `total_amount` as primary source for sale labour
- Purchase labour from purchase_ledger's `labour_per_kg / 1000`

### Sortable Table Columns (Feb 21, 2026)
- Reusable `useSortableData` hook and `SortableHeader` component
- All major tables sortable

### Mobile UI Horizontal Scroll (Feb 21, 2026)
- Tables wrapped in `overflow-x-auto` instead of hiding columns

### Item Group Consolidation (Feb 20, 2026)
- Group-aware purchase ledger, member breakdowns, per-stamp distribution

### Date-Based Stock Verification (Feb 20, 2026)
- SEE selects verification date; system calculates expected closing stock as of that date

### Client-Side Excel Parsing (Feb 11, 2026)
- SheetJS parsing in browser → JSON batches → server insert (OOM-safe)

## Master Stock Reset + Re-upload Behavior
1. **Reset "Master Stock"**: Zeros quantities only. Items, stamps, mappings, groups preserved.
2. **Upload new master stock**: DELETES all opening_stock and master_items, inserts new. New stamps used. Old items removed.
3. **Impact**: Mappings/groups NOT auto-updated — manual review needed if item names change.

## Code Architecture
```
/app/backend/
  server.py              # Monolithic (3800+ lines) - ALL routes, parsing, endpoints
  services/
    stock_service.py     # Book stock calculation (cross-stamp fix, date filtering)
    group_utils.py       # Item group resolution utilities
    helpers.py           # normalize_date (FIXED), normalize_stamp, save_action
  database.py, models.py, auth.py
/app/frontend/src/
  components/
    Layout.jsx           # Sidebar, reset dialog, fix-dates button
    SortableHeader.jsx   # Reusable sort header
    hooks/useSortableData.js
  pages/                 # All app pages
```

## Backlog
- (P1) Refactor server.py into proper FastAPI structure (routes, services, models)
- (P1) Item mapping cleanup tooling after master stock re-uploads
- (P2) Additional profit analysis improvements
- (P2) Enhanced mobile UI refinements
