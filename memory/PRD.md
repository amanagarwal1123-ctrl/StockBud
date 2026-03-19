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
6. Reverse removes baselines → current stock reverts to book values

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
- Modal close triggers finalize: remaining pending rows → rejected
- Rejected rows reset: final_* = old_*, deltas = 0
- Zero-applied sessions → abandoned (hidden from history)

### 4. Reverse/Undo
- `POST /api/physical-stock/update-history/{session_id}/reverse`
- Only latest unreversed session per date can be reversed
- Restores old weights for applied rows in physical_stock
- Removes inventory_baselines for reversed items
- Marks session as reversed

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — returns preview_session_id
- `POST /api/physical-stock/apply-updates` — requires preview_session_id, creates inventory_baselines
- `POST /api/physical-stock/finalize-session` — finalize draft
- `POST /api/physical-stock/update-history/{id}/reverse` — reverse latest, removes baselines
- `GET /api/physical-stock/update-history` — filtered, reversible flag
- `GET /api/inventory/current` — uses baselines for physical-stock-overridden items

## Files Changed
- `backend/server.py` — apply-updates creates baselines, reverse removes them
- `backend/services/stock_service.py` — get_current_inventory AND get_book_closing_stock_as_of_date use baselines
- `frontend/src/pages/Dashboard.jsx` — Stock Reconciliation History table with filter
- `frontend/src/components/PhysicalStockPreview.jsx` — session lifecycle, info banner
- `frontend/src/pages/PhysicalStockComparison.jsx` — Session section removed, calendar date picker, DD-MM-YYYY format

## UI Changes (Mar 19, 2026)
- Physical vs Book page: Removed session history section (moved to Dashboard)
- Physical vs Book page: Replaced discrete date dropdown with continuous calendar date picker
- Physical vs Book page: All dates now display as DD-MM-YYYY format

## Tests
- 13/13 backend tests pass (test_rejected_row_weights.py + test_codex_fixes.py)
- 10/10 baseline-specific tests pass (test_physical_stock_baseline.py)
- Full e2e flow verified: preview→approve→current stock updated→reverse→current stock reverted

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P2: Fix pre-existing dashboard test file
- P2: Mobile responsiveness
