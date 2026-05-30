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

## Seasonal ML Corrective Patch (Apr 7, 2026)
- **Fix 1**: Removed AI tab and smart-insights from Visualization page and backend
- **Fix 2**: PMS now uses shared `profit_helpers.compute_item_margins()` — same group-aware logic as `/analytics/profit`
- **Fix 3**: Silver price service kept as free non-blocking exogenous provider
- **Fix 4**: Historical purchases now loaded alongside historical sales
- **Fix 5**: Coverage-aware demand — uncovered dates are NaN (not zero), confidence adjusted by coverage ratio
- **Fix 6**: Segmentation based on covered active history
- **Fix 7-8**: PMS tabs and balancing formula preserved
- Tests: 36 total (23 unit + 13 business-logic integration), all passing

## Stamp Management: Group Member Visibility + Stamp Assignment Fix (Apr 16, 2026)
- **Bug 1**: Grouped items (e.g., JB-70 Kada II in JB-70 Ring group) were invisible in Stamp Management because the inventory response consolidates groups into a single leader entry. Frontend only read top-level `item_name`, missing members.
- **Fix 1**: StampManagement.jsx now extracts individual members from `item.members[]` for grouped items, showing each member as a separate row.
- **Bug 2**: Assigning a stamp from the item detail page for a group member failed silently because `master_items.update_many()` matched 0 documents (no master_items entry existed). Also missing `_inv_cache.invalidate()`.
- **Fix 2**: `assign-stamp` endpoint now uses `update_one` with `upsert=True` to create a master_items entry if missing, and invalidates inventory cache after assignment.

## Monthly Analytics & Pre-computed Summaries (Apr 16, 2026)
- **Architecture**: Pre-computed monthly summaries stored in `monthly_summaries` collection for instant retrieval at any data scale (100K+ transactions)
- **Backend Service**: `/app/backend/services/monthly_summary_service.py` — computes item profit + party sales/purchases per month
- **Auto-trigger**: Summaries recompute automatically after any data upload (background task)
- **Manual trigger**: `POST /api/analytics/recompute-summaries` for admin
- **New endpoints**:
  - `GET /api/analytics/monthly-profit?year=2026&month=4` (item profits for month, 0=ALL year)
  - `GET /api/analytics/monthly-party?year=2026&month=4` (party data for month)
  - `GET /api/analytics/item-monthly-breakdown/{item_name}?year=2026` (12-month bar chart data)
  - `GET /api/analytics/party-monthly-breakdown/{party_name}?year=2026` (12-month bar chart data)
  - `GET /api/analytics/dashboard-year-summary?year=2026` (dashboard year cards)
- **Frontend**: Both ProfitAnalysis.jsx and PartyAnalytics.jsx now feature:
  - Year selector dropdown + 12 month buttons (Jan-Dec) + "ALL" button
  - Default: current month auto-selected on page load
  - Auto-fetch on month click (no Apply button needed)
  - Expandable rows with bar charts showing monthly comparison (toggle: silver profit / labour / net wt)
- **Dashboard**: Year-wise comparison section with:
  - Year selector (dropdown)
  - Totals row (net wt sold, sales value, transactions)
  - Month-wise sales bar chart (12 months)
  - Top 5 Customers by weight
  - Top 5 Items by sold weight
- **Performance**: Reads from pre-computed collection = instant response regardless of transaction volume
- **Backward compat**: Old `/analytics/profit` and `/analytics/party-analysis` endpoints untouched

## Stamp Approval Bug Fix: verification_date targeting (Apr 16, 2026)
- **Bug**: When a stamp had multiple entries (e.g., an old approved + a new pending), clicking "Approve" on the pending entry silently approved the wrong (already-approved) entry. The pending entry stayed stuck.
- **Root cause**: Frontend `handleApproval()` received `verificationDate` but did not send it to the backend. Backend `approve_stamp` queried only by stamp name + status, sorted by `entry_date DESC` — picking the most recent entry regardless of which one the user clicked.
- **Fix**: Frontend now sends `verification_date` in the POST payload. Backend uses it as an additional filter to target the correct entry. Includes fallback logic: if no entry found with verification_date, tries pending-only, then any pending/approved.

## Sales Report Page (Apr 30, 2026)
- **New page**: `/sales-report` under "Analytics & ML" sidebar group (FileText icon)
- **Period selection**: Year + Month tabs (Jan-Dec + ALL) OR Custom Date Range tabs (default: current month)
- **Two views** (toggle tabs): "By Stamp" and "By Item"
- **Columns** (per row): Gross Wt, Net Wt, Avg Tunch, Avg Labour ₹/kg, Total Fine, Total Labour, Sale (green), Return (red), Txns, Items count (stamp view), Customers count
- **Per-stamp inclusion checkbox**: each stamp row has a checkbox to include/exclude from header totals; totals recompute live in-browser. Items inherit from their stamp.
- **Filter parity with Profit Analysis**: same `EXCLUDED_ITEMS` set (SILVER ORNAMENTS, COURIER, EMERALD MURTI, FRAME NEW, NAJARIA) dropped automatically; Unassigned-stamp items shown under "Unassigned" stamp group with a "no stamp assigned" badge
- **CSV Export**: per-view export (by_stamp or by_item) with all visible columns + Included column for stamp view
- **Backend**: new `GET /api/analytics/sales-report?year=&month=` OR `?start_date=&end_date=` (admin only). Uses canonical `signed_sale_value` formula so SR rows always subtract regardless of DB sign storage.
- **Tests**: `tests/test_sales_report_endpoint.py` (6 endpoint tests covering year+month mode, custom range, columns, missing params, auth, canonical signed math). 60 total backend tests passing.

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P1: PySpark/Databricks technical handoff document
- P2: "P" Suffix Item Mapping — auto-detect/resolve branch transfer items
- P2: Transaction archiving / materialized views for 200K+ scale

## Monthly Summary Freshness + Sales Reconciliation (May 30, 2026)
- **Problem reported**: User on production saw Dashboard "Net Wt Sold = 5503.77 kg" and Profit Analysis figures NOT updating despite recent uploads. Tally Excel (27/01 → 29/05) showed correct 5621.126 kg. Live Sales Report was close to correct (5638 kg) but Dashboard / Profit Analysis kept serving the older pre-computed totals.
- **Root cause**: Both pages read from `monthly_summaries` collection populated by `asyncio.create_task(recompute_monthly_summaries(db))` after every upload. The detached task had no error handler — any failure (DB exception, worker restart, timeout) was silently swallowed, leaving summaries stale.
- **Fix #1 — Freshness fingerprint**: `services/monthly_summary_service.py` now writes a per-year `_meta` doc capturing `txn_count` + `max(created_at)`. New helpers `get_year_meta`, `is_year_summary_stale`, `ensure_year_summary_fresh` detect drift on every read and recompute synchronously when needed.
- **Fix #2 — Safe background recompute**: `_safe_recompute_summaries()` wraps the task in try/except with structured logging so any failure shows up in supervisor logs instead of disappearing.
- **Fix #3 — Endpoint freshness fields**: `/analytics/dashboard-year-summary`, `/monthly-profit`, `/monthly-party`, `/recompute-summaries` all now return `last_computed_at` + `was_recomputed` so the UI can show "Updated X ago" and a one-click "Refresh" button.
- **Fix #4 — UI Refresh control**: new `components/SummaryFreshness.jsx` rendered on Dashboard (next to Year Comparison) and Profit Analysis (header). One-click manual refresh + relative-time indicator.
- **Fix #5 — Sales Reconciliation**: new `GET /api/analytics/sales-reconciliation?start_date=&end_date=` returns per-raw-item rows with leader/stamp/excluded/unassigned flags + sale/return/net weights, fine, amounts. Headline totals separate "grand", "excluded", "unassigned", and "visible" buckets so the user can pinpoint which items are silently dropped by the EXCLUDED_ITEMS or Unassigned-stamp filters. New `/sales-reconciliation` page with date pickers, totals cards, filter tabs (All / Included / Unassigned / Excluded), search, and CSV export. Sidebar entry added under Analytics & ML.
- **New endpoint**: `GET /api/analytics/summary-status?year=Y` returns the stored fingerprint vs. live fingerprint so UI can show data-current/stale state.
- **Tests**: `tests/test_summary_freshness.py` (6 unit tests for meta/stale detection/ensure_fresh) + `tests/test_freshness_and_reconciliation_endpoints.py` (7 endpoint tests). Combined 27/27 backend tests pass. Recompute completes in 0.23s for 11.7K transactions on preview; expected ~1s on production's 39K+ txns.
- **Action required by user**: redeploy preview build to production to apply the fix on the production database.

## Sales Report — Hidden Labour Disclosure (May 30, 2026, follow-up)
- **Why**: User pushed back on the "Unassigned items are hidden" framing — Sales Report ALREADY shows Unassigned items under an "Unassigned" stamp group (see PRD line 119). The real cause of the ~₹49L labour gap vs Tally is items in `EXCLUDED_ITEMS` (SILVER ORNAMENTS, COURIER, EMERALD MURTI, FRAME NEW, NAJARIA). These items carry small weight but **large labour** — and the previous response only exposed their weight (`excluded_items_kg`), not their labour amount.
- **Backend fix** (`/api/analytics/sales-report`): now also returns:
  - `excluded_items_amount_inr` (total labour Rs hidden by the filter)
  - `excluded_items_fine_kg` (total fine kg hidden)
  - `excluded_items_breakdown[]` — per-item rows {item_name, net_kg, fine_kg, amount_inr, rows} sorted by amount desc.
- **Frontend (Sales Report page)**: replaced the small badge with a collapsible amber panel that prominently shows "Hidden from totals: N rows · X kg · ₹Y labour" + click-to-expand per-item breakdown table. Users can now see at a glance EXACTLY which excluded items account for the gap, and decide whether to (a) accept the filter (Tally has them, App doesn't), or (b) request to remove an item from EXCLUDED_ITEMS if it shouldn't be hidden.
- **Preview verification**: EMERALD MURTI ₹12.3L + FRAME NEW ₹3L + NAJARIA ₹2L + COURIER ₹1.2L = ₹18.5L hidden in preview's smaller dataset. Production has ~3x volume → projects to ~₹50L hidden, almost exactly the ₹49L gap user reported.
- **Test**: `tests/test_sales_report_excluded_labour.py` — guards the breakdown shape + sum invariant. 28 backend tests now pass.

## Net Sales = Sale − Sale_Return Fix (Apr 30, 2026) + **Canonical Signed-Sum Correction (Apr 30, 2026, later)**
- **Initial bug**: Previous agent applied `mult = 1 if sale else -1` to SR rows. Since the parser preserves Excel signs, SR rows are stored with NEGATIVE net_wt already. Applying `-1` to an already-negative value flipped it back to positive → returns were being ADDED instead of subtracted. April showed 1494.188 kg instead of correct 1445.294 kg.
- **Root cause**: `1469.741 + (-(-24.447)) = 1494.188` (double negation). The user's Tally shows 1445.294 kg = `1469.741 - 24.447`.
- **Canonical fix**: Introduced `signed_sale_value(t, f) = abs(v) * (-1 if SR else 1)` pattern across every aggregation. This is SIGN-AGNOSTIC — it works whether DB stored SR as signed (-24.447) OR unsigned (+24.447). Both cases now yield 1445.294 kg.
- **Files patched**: `services/profit_helpers.py`, `services/monthly_summary_service.py` (item + party), `server.py` `/analytics/profit` + `/analytics/sales-summary` + `/analytics/monthly-profit` + `/analytics/monthly-profit-daily` + `/analytics/daily-profit-detail`.
- **New debug endpoint**: `GET /api/analytics/sale-debug-breakdown?year=Y&month=M` shows `sale_raw_sum_kg`, `sale_return_raw_sum_kg`, `sale_return_abs_sum_kg`, `signed_net_total_all_items_kg`, `displayed_net_total_kg`, `double_negation_would_produce_kg`, and a human-readable `sr_storage` diagnostic.
- **Tests**: `tests/test_sale_return_signed_sums.py` (8 new tests — specifically Tests 1 & 2: signed-negative SR and signed-positive SR both yield 1445.294 kg). Combined 54 profit/sales tests passing.

## Upload Date Deletion Reverted (Apr 30, 2026)
- **Issue**: Previous agent had widened upload deletion from `date $in [new_dates]` to `date $gte min_date $lte max_date` to clean "ghost data". User reported this broke reliable uploads.
- **Fix**: Reverted to original `{"type": {"$in": delete_types}, "date": {"$in": new_dates}}` in both `_process_upload` (chunked) and the legacy upload handler. Only dates present in the file are replaced.
- **Verified**: end-to-end chunked upload (init → chunk → finalize → status=complete) works. 2 records uploaded successfully in test.

## PMS Group Resolution Fix (Apr 13, 2026)
- **Bug**: `_compute_margins_shared()` returned margins keyed only by leader name; forecasts use raw item names from sales → 74 items got zero margins
- **Fix**: Extended margins dict to register ALL group members + transaction-name aliases pointing to the same leader margins
- **Result**: Margin coverage improved from 67% (230/343) → 87.5% (300/343). Remaining 43 are legitimately excluded items.
- Tests: 38 total (2 new group resolution tests), all passing

## Polythene Duplicate Entry Prevention (Apr 13, 2026)
- **Problem**: Polythene executives could double/triple-submit entries by clicking Save multiple times on slow connections
- **Frontend Fix**: Save button disables during API call (spinner + "Saving..." text); duplicate detection blocks same item+weight+operation in pending list
- **Backend Fix**: 20-second dedup window on both `/polythene/adjust` and `/polythene/adjust-batch` — identical (item, weight, operation, user) within window is silently skipped
- Response now returns `{saved: N, skipped: M}` for transparency

## Standard DD/MM/YYYY Date Format (Apr 13, 2026)
- Created shared `utils/dateFormat.js` with `formatDate`, `formatDateTime`, `formatDateTimeFull`, `formatTime`
- Applied DD/MM/YYYY consistently across all pages: PolytheneEntry, PolytheneManagement, ExecutiveStockEntry, Dashboard, History, ActivityLog, Layout (Undo Upload), UserManagement, StampVerificationHistory, ManagerApprovals, PhysicalStockComparison

## Profit Calculation Fix: Sale Return Tunch Corruption (Apr 15, 2026)
- **Bug**: `sale_return` was treated as a pseudo-purchase, injecting SALE tunch into the purchase cost basis. BS-053 showed Buy T%=46% (from a sale_return) instead of the real purchase cost of 51%. **23 items** had >5% tunch distortion in date-filtered views.
- **Root cause**: `server.py` line 4227 and `profit_helpers.py` line 71 both routed `sale_return` → purchases bucket
- **Fix**: `sale_return` now goes into the **sales bucket as a negative sale** — correctly reduces sold weight and labour income without corrupting the purchase cost basis
- **Labour fix**: Returns (negative net_wt) now reduce total sale labour income instead of adding to it
- **Header alignment**: Profit Analysis table now uses `table-fixed` with explicit column widths for consistent alignment
- Tests: 41 total (18 corrective + 23 ML), all passing. 3 new sale_return tests added.
