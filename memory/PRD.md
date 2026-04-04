# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Core Inventory Logic
- **Book Stock**: Opening Stock + Purchases - Sales +/- Branch Transfers +/- Polythene
- **Physical Stock Baseline**: When physical stock is approved, it becomes the new starting point. Current Stock = Baseline + Post-Baseline Transactions.
- **Reverse**: Undoing a session removes the baseline and reverts to book calculation.

## Critical Rule: Individual Item Computation (FIXED Mar 24, 2026)
Groups are used ONLY for display (expandable rows in Current Stock) and profit calculations.
Stock must be computed at the INDIVIDUAL ITEM level. Each item retains its own stamp assignment.

## Performance Improvements (Mar 24, 2026)
- 25+ database indexes for transactions, baselines, stock_entries, polythene, notifications
- Inventory caching (30s TTL) for `get_current_inventory()`
- Non-blocking badge loading in Stamp Approvals

## Item Detail Fixes (Apr 2, 2026)
- Item Detail now uses `get_current_inventory()` for accurate stock (matches Current Stock page)
- Added Labour Margin card alongside Tunch Margin
- Added Purchase Rate input (tunch % + labour/kg) for items without purchase ledger entries
- Items without purchase rates marked with "NOT SET" badge and orange alert
- `POST /api/item/{item_name}/set-purchase-rate` endpoint for manual rate input

## Item Buffers Fix (Apr 2, 2026)
- Item Buffers now refreshes current stock from `get_current_inventory()` using individual-level `by_stamp` data
- Previously showed stale pre-computed values

## Key Endpoints
- `GET /api/item/{item_name}` — uses get_current_inventory() for accurate stock, includes labour margin
- `POST /api/item/{item_name}/set-purchase-rate` — set purchase tunch/labour for items without purchase data
- `GET /api/item-buffers` — refreshes current stock from live inventory
- `POST /api/physical-stock/fix-group-baselines` — idempotent, splits group baselines
- `POST /api/physical-stock/restore-group-baselines` — one-time fix for corrupted baselines

## Polythene Management for Executives (Apr 4, 2026)
- Executive (SEE) role can now access /polythene-management as read-only (no edit/delete)
- Added filters: Item Name, Stamp Name, Date From, Date To (combinable)
- Summary totals (Total Add, Total Subtract, Net Polythene) always visible at top, update with filters
- Admin retains full access (delete buttons, user filter dropdown)
- Sidebar: Polythene Mgmt visible under Inventory group for executive role
- Backend: GET /api/polythene/all now accepts admin + executive roles
- Item Name and Stamp Name filters are searchable dropdowns showing only values present in polythene entries
- 30-Day Polythene Trend bar chart (admin only) showing daily add/subtract activity via recharts

## Seasonal ML Analysis Module (Apr 4, 2026)
- **Replaced** old LLM-based `/ai/seasonal-analysis` with deterministic ML-based module
- **Sidebar**: Renamed "Analytics & AI" to "Analytics & ML"
- **New page**: `/seasonal-analysis` with 8 sub-tabs:
  - PMS Final (balanced profit-margin score penalising one-sided distortion)
  - PMS Silver (silver-margin weighted demand)
  - PMS Labour (labour-margin weighted demand)
  - Demand Forecast (14d/30d segmented forecasting via LightGBM)
  - Seasonality (month-over-month patterns from historical data)
  - Procurement Planner (buy/hold recommendations with reason codes)
  - Supplier View (supplier-wise PMS and recency)
  - Dead Stock (dead stock + slow mover detection)
- **Segmentation**: dense_daily, medium_daily, weekly_sparse, cold_start
- **PMS formula**: balanced_score = 0.5*(s+l) + 0.5*min(s,l) — penalises imbalance
- **Silver MCX**: Free API (metals.live), demand-side features only, non-blocking
- **Profit Analysis**: Completely untouched (tunch-spread + labour margin)
- Backend: 8 new endpoints under `/api/seasonal/*`
- Tests: 23 unit tests + 32 integration tests, all passing

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P2: Transaction archiving / materialized views for 200K+ scale
