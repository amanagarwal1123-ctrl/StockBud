# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Core Inventory Logic
- **Book Stock**: Opening Stock + Purchases - Sales +/- Branch Transfers +/- Polythene
- **Physical Stock Baseline**: When physical stock is approved, it becomes the new starting point for that item. Current Stock = Baseline + Post-Baseline Transactions.
- **Reverse**: Undoing a physical stock session removes the baseline and reverts to book calculation.

## Physical Stock Baseline Feature (Mar 19, 2026)
When a user uploads physical stock and approves items:
1. Approved values are stored in `inventory_baselines` collection
2. `get_current_inventory()` uses baseline as starting point (replaces opening stock)
3. Only transactions AFTER baseline_date are counted for baseline items
4. Non-baseline items retain normal book calculation
5. Polythene adjustments also respect baseline dates
6. Reverse removes baselines -> current stock reverts to book values

### Collection: `inventory_baselines`
Fields: item_key, item_name, baseline_date, gr_wt, net_wt, stamp, updated_at, session_id

## Unified Stock Computation (Mar 20, 2026)
All stock-dependent features now use `get_current_inventory(as_of_date)` as the single source of truth:
- **Current Stock page**: `get_current_inventory()` (no date filter)
- **Upload Preview base**: `get_current_inventory(as_of_date=verification_date)` via `_flat_base_from_inventory()`
- **Compare page**: `_flat_base_from_inventory(verification_date)`
- **Stamp Approvals**: `get_current_inventory(as_of_date=verification_date)` via `by_stamp`
- **Apply Updates snapshot**: `get_effective_physical_base_for_date(verification_date)`

`get_book_closing_stock_as_of_date()` and `get_stamp_closing_stock()` are retained in stock_service.py but no longer called from server.py.

## Session Lifecycle

### 1. One Upload = One Session
- Preview creates a draft session with `preview_session_id`
- Apply updates the SAME session (no new session per click)
- Session tracks full row list: applied, rejected, unmatched, skipped, pending

### 2. Effective Base for Preview
- `get_effective_physical_base_for_date()` checks for ACTIVE sessions before using physical_stock records
- If ALL sessions for a date are reversed, falls back to date-filtered `get_current_inventory()`
- Base uses `get_current_inventory(as_of_date=verification_date)`

### 3. Upload Preview Item Matching
- Comprehensive `name_to_base_key` reverse lookup from ALL groups, mappings, and their chains
- Group members resolve automatically; mapped items resolve via mapping definitions
- Multiple uploaded items resolving to same base key are MERGED before delta computation

### 4. Compare Screen
- Uses `_flat_base_from_inventory(verification_date)` — same identity model as current stock
- Includes both net and gross weight comparison with `gross_difference` fields
- Gross difference used for classification when net is negligible (gross-only files)

### 5. Stamp Approvals Book Values (FIXED Mar 20, 2026)
- Was using `get_stamp_closing_stock()` which ignored baselines
- Now uses `get_current_inventory(as_of_date=verification_date).by_stamp[stamp]`
- After physical stock reconciliation, stamp approval book values reflect updated stock

## Key Endpoints
- `POST /api/physical-stock/upload-preview` -- comprehensive resolver, date-scoped base
- `POST /api/physical-stock/apply-updates` -- creates inventory_baselines
- `POST /api/physical-stock/finalize-session` -- finalize draft
- `POST /api/physical-stock/update-history/{id}/reverse` -- reverse, removes baselines
- `GET /api/inventory/current` -- baseline-aware, full inventory
- `GET /api/physical-stock/compare` -- date-filtered, unified identity, gross+net
- `GET /api/manager/approval-details/{stamp}` -- baseline-aware stamp book values
- `GET /api/manager/pending-approvals` -- pending stock entries
- `GET /api/stamp-verification/history` -- all stamps with verification status

## Files Changed
- `backend/server.py` -- upload-preview resolver; compare uses _flat_base_from_inventory; approval-details uses get_current_inventory(as_of_date).by_stamp
- `backend/services/stock_service.py` -- get_current_inventory(as_of_date), _flat_base_from_inventory(), get_effective_physical_base_for_date
- `frontend/src/pages/Dashboard.jsx` -- Reconciliation History with expand/reverse
- `frontend/src/pages/PhysicalStockComparison.jsx` -- Calendar date picker, DD-MM-YYYY

## Tests
- 18/18 date-filtering and compare tests pass (iteration 25)
- 9/9 upload-preview fix tests pass (iteration 24)
- All regression tests pass: inventory, compare, approvals, health

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P1: User to verify delta and stamp approval values on production
- P2: Fix pre-existing dashboard test file
- P2: Mobile responsiveness
- Investigate: +17g gross weight change on production after file rejection
