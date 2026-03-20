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

### 5. Effective Base for Preview
- `get_effective_physical_base_for_date()` checks for ACTIVE sessions before using physical_stock records
- If ALL sessions for a date are reversed, falls back to book stock calculation
- Prevents stale physical_stock records from being used as "Old" values

### 6. Upload Preview Item Matching (FIXED Mar 20, 2026)
- Uploaded items are first matched by raw name against the base
- If no direct match, names are resolved through mappings+groups before lookup
- This prevents group members (e.g., SNT-40 PREMIUM → SNT 40-256) from showing as "unmatched"
- Groups apply to physical stock matching for name resolution only

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — parses file, resolves names through mappings+groups, returns preview diff
- `POST /api/physical-stock/apply-updates` — requires preview_session_id, creates inventory_baselines
- `POST /api/physical-stock/finalize-session` — finalize draft
- `POST /api/physical-stock/update-history/{id}/reverse` — reverse latest, removes baselines
- `GET /api/physical-stock/update-history` — filtered, reversible flag
- `GET /api/physical-stock/update-history/{session_id}` — session detail with items
- `GET /api/inventory/current` — uses baselines for physical-stock-overridden items
- `GET /api/stamp-verification/history` — all stamps from all collections with verification status

## Files Changed
- `backend/server.py` — upload-preview resolves names through mappings+groups; apply-updates creates baselines; reverse removes them; stamp-verification/history gets all stamps
- `backend/services/stock_service.py` — get_current_inventory, get_book_closing_stock_as_of_date use baselines; get_effective_physical_base_for_date checks for active sessions
- `frontend/src/pages/Dashboard.jsx` — Reconciliation History with clickable expand, reverse button, all stamps, refetch on focus
- `frontend/src/pages/PhysicalStockComparison.jsx` — Calendar date picker, DD-MM-YYYY format, defaults to today

## Tests
- 13/13 backend tests pass
- 10/10 baseline-specific tests pass
- Verified: SNT-40 PREMIUM, TULSI 70 BELT, MADRASI YASH SHOLDER now resolve correctly in preview

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P2: Fix pre-existing dashboard test file
- P2: Mobile responsiveness
- Investigate: +17g gross weight change on production after file rejection (no code path found that modifies stock during preview+abandon)
