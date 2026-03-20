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

## Session Lifecycle (Mar 19, 2026)

### 1. One Upload = One Session
- Preview creates a draft session with `preview_session_id`
- Apply updates the SAME session (no new session per click)
- Session tracks full row list: applied, rejected, unmatched, skipped, pending

### 2. Draft Initialization
- Pending rows start with final_gr_wt = old_gr_wt, gr_delta = 0 (not proposed values)

### 3. Session Finalization
- Modal close triggers finalize: remaining pending rows -> rejected
- Rejected rows reset: final_* = old_*, deltas = 0
- Zero-applied sessions -> abandoned (hidden from history)

### 4. Reverse/Undo
- `POST /api/physical-stock/update-history/{session_id}/reverse`
- Only latest unreversed session per date can be reversed
- Restores old weights for applied rows in physical_stock
- Removes inventory_baselines for reversed items
- Marks session as reversed

### 5. Effective Base for Preview
- `get_effective_physical_base_for_date()` checks for ACTIVE sessions before using physical_stock records
- If ALL sessions for a date are reversed, falls back to date-filtered `get_current_inventory()`
- Prevents stale physical_stock records from being used as "Old" values
- Base uses `get_current_inventory(as_of_date=verification_date)` ensuring both date-scoping AND consistency with Current Stock page identity model

### 6. Upload Preview Item Matching (FIXED Mar 20, 2026)
- **Comprehensive resolver**: Builds a `name_to_base_key` reverse lookup from ALL groups, mappings, and their chains
- Group members (e.g., TULSI 70 BELT -> TULSI 70 -264) resolve automatically via group definitions
- Mapped items (e.g., MADRASI YASH SHOLDER -186 -> MADRASI YASH -186) resolve via mapping definitions
- Multiple uploaded items resolving to the same base key are MERGED before delta computation
- Fallback chain resolution still runs if the comprehensive lookup misses

### 7. Identity Model Unification (FIXED Mar 20, 2026)
- `get_current_inventory(as_of_date)` now accepts optional date parameter
- When `as_of_date` is set: filters transactions (date <= as_of_date), baselines (baseline_date <= as_of_date), polythene (date <= as_of_date)
- `_flat_base_from_inventory(as_of_date)` helper extracts flat base dict from inventory result
- Both `get_effective_physical_base_for_date()` and compare endpoint use `_flat_base_from_inventory()`
- This ensures upload-preview, apply-updates, AND compare all use the same identity model as the Current Stock page
- `get_book_closing_stock_as_of_date()` no longer used in server.py (only retained in stock_service.py for potential future use)

### 8. Compare Screen Gross Weight (FIXED Mar 20, 2026)
- Compare endpoint now includes `gross_difference`, `gross_difference_kg`, `book_gross_wt`, `physical_gross_wt` fields
- For gross-only physical files where net difference is negligible, gross difference is used for match/discrepancy classification

## Key Endpoints
- `POST /api/physical-stock/upload-preview` -- parses file, resolves names through comprehensive lookup, date-scoped base
- `POST /api/physical-stock/apply-updates` -- requires preview_session_id, creates inventory_baselines
- `POST /api/physical-stock/finalize-session` -- finalize draft
- `POST /api/physical-stock/update-history/{id}/reverse` -- reverse latest, removes baselines
- `GET /api/physical-stock/update-history` -- filtered, reversible flag
- `GET /api/physical-stock/update-history/{session_id}` -- session detail with items
- `GET /api/inventory/current` -- uses baselines for physical-stock-overridden items (no date filter)
- `GET /api/physical-stock/compare` -- date-filtered, same identity model, gross+net comparison
- `GET /api/stamp-verification/history` -- all stamps from all collections with verification status

## Files Changed
- `backend/server.py` -- upload-preview with comprehensive resolver; compare uses _flat_base_from_inventory; apply-updates uses consistent base
- `backend/services/stock_service.py` -- get_current_inventory(as_of_date), _flat_base_from_inventory(), get_effective_physical_base_for_date passes date
- `frontend/src/pages/Dashboard.jsx` -- Reconciliation History with clickable expand, reverse button, all stamps, refetch on focus
- `frontend/src/pages/PhysicalStockComparison.jsx` -- Calendar date picker, DD-MM-YYYY format, defaults to today

## Tests
- 18/18 date-filtering and compare tests pass (iteration 25)
- 9/9 upload-preview fix tests pass (iteration 24)
- Frontend verification: login, dashboard, physical vs book, current stock all pass
- Date filtering verified: CHAIN MS-70 shows different base values for different verification dates

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P1: User to verify -3.050 delta on production after deploying this fix
- P2: Fix pre-existing dashboard test file
- P2: Mobile responsiveness
- Investigate: +17g gross weight change on production after file rejection
