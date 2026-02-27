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

## Key Endpoints
- `POST /api/upload/client-batch` - Client-parsed batch upload (OOM-safe)
- `POST /api/upload/init` - Chunked upload init
- `GET /api/manager/approval-details/{stamp}` - Book vs physical comparison
- `GET /api/debug/item-closing/{item_name}?as_of_date=YYYY-MM-DD` - Item calculation debug
- `GET /api/stats/transaction-summary` - Weight totals per type for reconciliation
- `POST /api/system/fix-dates` - Fix swapped month/day dates (admin only)
- `POST /api/system/reset` - Selective system reset
- `POST /api/master-stock/upload` - Upload master stock (replaces opening stock)
- `GET /api/analytics/sales-summary` - Total sales with net/fine/labour
- `GET /api/analytics/profit` - Silver & labour profit calculation

## Critical Bugs Fixed (Feb 27, 2026)

### to_list(10000) Truncation Bug
- **Bug**: MongoDB `to_list(10000)` silently capped queries at 10,000 records. With 10,500+ sale records, ~500 were dropped → ~80 kg missing from Total Sales
- **Fix**: All transaction queries now use `to_list(100000)`
- **Impact**: Affected sales-summary, profit, customer-profit, supplier-profit, unmapped-items, and current stock endpoints
- **Verified**: Total Sales now 1552.016 kg (matches Excel 1552.044 kg, diff = SILVER ORNAMENTS exclusion)

### Branch Transfer Re-upload Bug
- **Bug**: Delete query used `type: "branch_transfer"` but stored types are `issue`/`receive`. Old records were never deleted on re-upload.
- **Fix**: Delete now correctly targets `['issue', 'receive']` for branch_transfer file type

### _safe_float Comma Handling
- **Bug**: Numbers formatted as "1,705.433" (Indian thousands separator) returned 0.0
- **Fix**: Added comma-stripping fallback in _safe_float

### Pandas Memory Fix  
- **Bug**: `helpers.py` had `import pandas as pd` at top level → ~150MB on startup → OOM crashes
- **Fix**: Replaced `pd.isna()` with lightweight `_is_na()`, lazy-import pandas only in `normalize_date`
- **Result**: Startup RSS 26MB (down from 150MB+)

### Date Parsing Fix
- **Bug**: `pd.to_datetime('2026-02-03', dayfirst=True)` → 2026-03-02 (month/day swapped for ISO dates)
- **Fix**: Detect ISO format and skip dayfirst; migrated 2,037 existing records
- **Admin tool**: "Fix Swapped Dates" button in sidebar

## Master Stock Reset + Re-upload Behavior
1. **Reset "Master Stock"**: Zeros quantities only. Items, stamps, mappings, groups preserved.
2. **Upload new master stock**: DELETES all opening_stock and master_items, inserts new. New stamps used.
3. **Impact**: Mappings/groups NOT auto-updated — manual review needed if item names change.

## Upload Type-Safety Confirmed
- Re-uploading purchases: ONLY deletes `purchase` + `purchase_return` (sales unaffected)
- Re-uploading sales: ONLY deletes `sale` + `sale_return` (purchases unaffected)
- Re-uploading branch transfers: ONLY deletes `issue` + `receive` (FIXED)
- Issue transactions don't disturb sale calculations

## Code Architecture
```
/app/backend/
  server.py              # Monolithic (5400+ lines) - ALL routes, parsing, endpoints
  services/
    stock_service.py     # Book stock calculation (cross-stamp fix, date filtering)
    group_utils.py       # Item group resolution utilities
    helpers.py           # normalize_date (FIXED), normalize_stamp, _is_na (no pandas)
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
- (P1) Add upload validation showing record count + weight totals before confirming
- (P2) Item mapping cleanup tooling after master stock re-uploads
- (P2) Additional profit analysis improvements
