# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Core Inventory Logic
- **Book Stock**: Opening Stock + Purchases - Sales +/- Branch Transfers +/- Polythene
- **Physical Stock Baseline**: When physical stock is approved, it becomes the new starting point. Current Stock = Baseline + Post-Baseline Transactions.
- **Reverse**: Undoing a session removes the baseline and reverts to book calculation.

## Critical Rule: Individual Item Computation (FIXED Mar 24, 2026)
### The Rule
Groups are used ONLY for display (expandable rows in Current Stock) and profit calculations.
Stock must be computed at the INDIVIDUAL ITEM level. Each item retains its own stamp assignment.

### Previous Bug
`_resolve()` function merged group members into group leaders during stock computation.
Example: TULSI 70 BELT (STAMP 6, ~91kg) was merged into TULSI 70 -264 (STAMP 3), causing:
- STAMP 3 book stock showed 182kg instead of 91kg (included both items)
- STAMP 6 showed -5kg for TULSI 70 BELT (negative stock)
- ~93kg discrepancy in STAMP 3 approval workflow

### The Fix
1. `_resolve()` now returns only `master_name` (NO leader merging)
2. `inventory_map` keyed by individual item, not group leader
3. `baseline_by_key` matched at individual item level
4. `by_stamp` built from individual items → each item goes to its OWN stamp
5. Group display built in second pass AFTER individual computation (for Current Stock UI only)
6. `get_book_closing_stock_as_of_date()` also fixed with same individual-level computation

## Unified Stock Computation (Mar 20, 2026)
All stock-dependent features use `get_current_inventory(as_of_date)` as the single source of truth.

## Member-Level Baselines (FIXED Mar 24, 2026)
### The Bug
Merged group members into one baseline at the leader level, causing negative stock for members (TULSI 70 BELT: -4.644 kg).
### The Fix
1. `_flat_base_from_inventory()` decomposes groups into member-level entries
2. Upload-preview shows members as separate rows (no merging)
3. Each approved member gets its own baseline
4. Admin fix endpoint: `POST /api/physical-stock/fix-group-baselines` splits existing leader-level baselines

## Performance Improvements (Mar 24, 2026)
- 25+ database indexes added for transactions, baselines, stock_entries, polythene, notifications
- Inventory caching (30s TTL) for `get_current_inventory()`
- Non-blocking badge loading in Stamp Approvals (parallel fetch after page renders)
- Loading skeletons for Current Stock and Stamp Approvals pages

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — member-level comparison
- `POST /api/physical-stock/apply-updates` — member-level baselines
- `POST /api/physical-stock/fix-group-baselines` — splits existing group baselines (admin only)
- `GET /api/physical-stock/compare` — member-level comparison
- `GET /api/inventory/current` — individual-level computation, grouped display, cached
- `GET /api/manager/approval-details/{stamp}` — individual item book values per stamp

## Backlog
- P0: Deploy latest code to production (CRITICAL - fixes 93kg STAMP 3 discrepancy)
- P0: Run `POST /api/physical-stock/fix-group-baselines` on production after deploy
- P1: Investigate +17g gross weight anomaly on production
- P1: Refactor server.py into proper FastAPI structure
- P2: Mobile responsiveness
- P2: Fix test suite
- P2: Transaction archiving / materialized views for 200K+ scale
