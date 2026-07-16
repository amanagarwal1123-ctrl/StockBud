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



## Auth Hardening — Production Login Fix (Jun 1, 2026)
- **Problem reported**: User could NOT log in to the PRODUCTION (deployed) app; preview worked fine.
- **Root cause (primary)**: `auth.py` read `SECRET_KEY = os.environ.get('JWT_SECRET_KEY')` and, when missing, generated a **random** `secrets.token_hex(32)` PER PROCESS. In a multi-worker deployment (or any restart) each worker signed/validated JWTs with a different key → login succeeds but the very next authenticated request returns 401 "Invalid token" → appears as "cannot log in". Preview has the env var set + single worker, so it never surfaced there.
- **Root cause (secondary)**: Admin user was only created via the manual `/users/initialize-admin` endpoint (works only when 0 users exist). A fresh / migrated production DB could have no `admin` → login 401.
- **Fix #1 — Stable JWT secret** (`auth.py`): removed the per-process random fallback. Added `async def ensure_secret_key(db)` resolving a STABLE key in order: env `JWT_SECRET_KEY` → key persisted in `db.app_config` (`_id="jwt_secret"`) → generate once & persist. Called on startup so all workers share one secret. `create_access_token`/`get_current_user` read the module global at call time, so the resolved value is used.
- **Fix #2 — Idempotent admin seed** (`server.py` `seed_admin()`, called on startup): guarantees an active `admin` account exists in whatever DB the deployment connects to. Does NOT overwrite an existing admin's password (custom passwords preserved); reactivates an inactive admin.
- **Tests**: `tests/test_auth_secret_key.py` (3 tests): stable key shared across simulated workers + cross-worker JWT validation, env-var precedence (not persisted), idempotent admin seed. All pass.
- **Verified on preview**: login (curl + UI) → token 144 chars in sessionStorage → dashboard loads; authed endpoint returns 200; wrong password → 401; no duplicate admin.
- **ACTION REQUIRED BY USER**: REDEPLOY to apply these code fixes to production. They only take effect on the next deployment.
- **NOTE (kept, not changed)**: Auth uses Bearer JWT in sessionStorage (no refactor to httpOnly cookies, per user). Deployment agent also flagged an OOM-risk unbounded backup query (`.to_list(None)`) in the upload-delete path — left untouched because that area is fragile (a prior agent broke uploads editing it) and it is not the login cause.

## Code Review — Safe Fixes Applied (Jun 1, 2026)
- **Mutable default arg** (`server.py` `/analytics/recompute-summaries`): `request: Dict = {}` → `Optional[Dict] = None` with safe init.
- **Empty catch blocks** (3): `OrderManagement.jsx` overdue check, `Notifications.jsx` prefs read + markRead now log errors instead of silently swallowing.
- **Investigated → false positives (intentionally NOT changed)**: (a) "9 undefined vars" — ruff F821/F823 + pylint E0606/E0601/E0602 report ZERO. (b) "84 incorrect is/==" — all are `is None`/`is True/False` (correct PEP8 idiom; `==` would add E711 errors). (c) "25 sensitive storage" — all `sessionStorage.getItem('token')` (app-wide JWT convention) + non-sensitive notif UI prefs; cookie migration = full auth rewrite, declined. (d) "74 missing hook deps" — project ESLint passes clean; mass useCallback changes risk infinite loops.


## Daily Profit Additivity — "Sum of daywise profit != total profit" Fix (Jun 1, 2026)
- **Problem reported (production)**: On Profit Analysis (Jun 2026), the sum of the daily Silver Profit rows did NOT equal the header Silver Profit total (daily summed ~17.97 kg vs header 10.998 kg). Labour matched. "Was correct till ~2 days ago."
- **Root cause (code, not data)**: Two different cost bases for the same metric.
  - Header total (`/analytics/monthly-profit`) reads pre-computed `monthly_summaries` built by `_compute_item_profits`, which uses a per-item **month-level** `avg_purchase_tunch` (constant across the month).
  - `/analytics/daily-profit` recomputed `avg_purchase_tunch` from **each day's** purchases (and fell back to the ledger only on no-purchase days). Silver profit = `(avg_sale_tunch − avg_purchase_tunch) × wt`; a per-day purchase tunch is **non-additive**, so daily values can't sum to the monthly total. Labour matched because its `labour_per_kg` comes from the ledger (constant per item → additive). The gap widened after the recent upload added sale days with no same-day purchase (which used the ledger tunch, diverging from the month avg).
- **Fix (`services/profit_helpers.py`)**: New shared, additive helpers:
  - `_build_month_context()` — builds one per-item month-level cost basis (avg purchase tunch + purchase labour/kg) + resolve/include closures.
  - `compute_daily_profits()` — per-day silver/labour using the CONSTANT per-item cost basis → sum of daily == monthly total by construction.
  - `compute_date_profit_detail()` — per-date drilldown (top items/customers) using the SAME cost basis, so drilldown item silver sums to the day's total.
  - `/analytics/daily-profit` and `/analytics/daily-profit-detail` endpoints rewired to these helpers (old inline per-day math deleted).
- **Tests** (`tests/test_daily_profit_additivity.py`, 5): daily silver sums to `_compute_item_profits` total (no returns, exact); documents the OLD per-day method diverges; with returns within tolerance; excluded items skipped; drilldown items sum to the daily row.
- **Verified live (preview, isolated injected item + recompute, cleaned up)**: header item silver/labour (3.27/13600) == daily-sum (3.27/13600); drilldown 06-03 silver (1.233) == daily row 06-03 (1.233). MATCH on all three views.
- **Not the deploy's fault**: the Jun 1 auth deploy only touched login code; this averaging bug pre-existed and surfaced as data grew.
- **ACTION REQUIRED BY USER**: REDEPLOY to apply to production.
- **Scope note**: Other profit endpoints (`/analytics/profit`, `customer-profit`, `supplier-profit`, `historical-profit`) are single-period aggregates (no daily sub-rows to reconcile) → no additivity bug, left unchanged.


## Profit Cost-Basis Correction — Long-run Cumulative Ledger + Per-Entry (Jun 1, 2026)
- **User principle (first-principles / "Elon test")**: Goods sold today were purchased weeks/months ago, so using *today's* or *this month's* purchase tunch/labour as the cost basis is wrong. The COST side must be a long-run average; only the SALE side is period-specific. The atomic unit of profit is a single sale entry.
- **Decision (confirmed by user)**: 1a cost basis = cumulative PURCHASE_CUMUL ledger (long-run weighted-avg purchase tunch & labour/kg, ≥3 months by nature, same for every period); 2 = compute profit PER SALE ENTRY (each entry's actual sale tunch/labour vs the ledger cost), then sum; 3a = skip items with no ledger entry (effectively unassigned); 4a = proceed (headline numbers will change; correctness matters).
- **Why per-entry beats monthly-average-then-distribute**: (1) accuracy — each sale's real rate, no blending; (2) immutability — a past day's profit never shifts when later sales arrive; (3) perfect additivity — day→month→year always reconcile since every total sums the same atoms.
- **Canonical helpers (`services/profit_helpers.py`)**: `ledger_cost_basis(grp_ledger, leader)` (cumulative cost basis or None→skip) and `aggregate_sale_profit(sales, cost_tunch, cost_lpg)` (per-entry silver kg + labour INR, signed for returns; matches the proven `/analytics/customer-profit` logic).
- **Applied everywhere (single model)**: `compute_item_margins` (/analytics/profit + seasonal PMS), `_compute_item_profits` (monthly_summaries → Dashboard + Profit Analysis header/monthly), `compute_daily_profits` + `compute_date_profit_detail` (daily + drilldown), and `/analytics/profit` inline. `customer-profit` already used this model. `supplier-profit` intentionally keeps per-supplier purchase rates (different question — "which supplier is most profitable").
- **Auto-recompute after deploy**: added `PROFIT_LOGIC_VERSION = 2` to the `monthly_summaries` `_meta` fingerprint; `is_year_summary_stale` returns True when the stored version differs, so deploying the new logic auto-recomputes stale summaries on the next read (no manual step).
- **Tests**: 68 unit tests pass (additivity now EXACT incl. returns; sale-return + signed-sum + corrective-patch tests updated to supply a ledger cost basis). Live e2e (injected item + ledger + recompute, cleaned up): header == daily-sum == /analytics/profit ALL = silver 3.35 / labour 13680. RECONCILE ✅.
- **ACTION REQUIRED BY USER**: REDEPLOY. After deploy, summaries auto-recompute with the corrected logic; profit numbers will change (now correct). Net-sales weight/Tally parity is unaffected (cost basis only changes margin, not sale weights).

## Hardcoded DB Query Limit Removal — Data Truncation Fix (Jun 8, 2026)
- **Problem**: Silent data truncation from bounded PyMongo queries corrupting calculations at production scale (51K+ txns): `/api/item/{name}` capped txn history at 1000, `/api/analytics/visualization` capped at 50,000, `item_groups` capped at 1000 in ~20 places in `server.py` + `stock_service.py` (3), `monthly_summary_service.py`, `seasonal_ml_service.py`, plus caps on `master_items` (1000), `opening_stock` (1000/10), per-item `item_mappings` (100), `polythene_adjustments` (100/1000), `stamp_assignments` (100), pending `stock_entries` (100), overdue orders (100), stock alerts (100), historical yearly aggregate (100).
- **Fix**: All calculation-affecting queries → `.to_list(None)` (unbounded). Display-only lists intentionally keep limits (activity log 200, recent actions 50, notifications 500, orders list 1000, verification history 500).
- **Verified (testing agent, iteration_31.json)**: 7/7 backend tests PASS — login, /api/stats (full 11,767 txn count), item detail, visualization, profit additivity, physical-stock compare; all <1s, no 500s. Regression suite: `/app/backend/tests/test_unbounded_limits.py`.
- **Pre-existing (NOT regressions)**: 124 data-dependent integration test failures (expect production items absent from local DB — verified failing identically before this fix via git stash). Local-DB profit values are 0 (local purchase_ledger doesn't align with imported sale item names) — production ledger is complete, logic verified in prior session.
- **CHAIN MS-70 divergence**: still open — diagnosed as item alias/variant mismatch (`CHAIN MS-70 CASTING`, `CHAIN KJN-70` split book stock); needs the Alias/Suffix mapping feature. "999 customer" issue dropped per user.
- **ACTION REQUIRED BY USER**: REDEPLOY to apply to production, then re-check CHAIN MS-70 physical vs book stock.

## Large File Upload Timeout + False Green Tick Fix (Jun 8, 2026)
- **Problem (production)**: 23MB sale xlsx chunked into 116 parts timed out at the frontend's hard 15-min poll cap ("Processing timed out after 15 minutes"), while the file card kept a green tick (it was set at click-time, never reverted).
- **Root cause**: openpyxl parsing is pure-Python/single-threaded — a ~300K-row file on a constrained production pod exceeds 15 min. Green tick was set in `confirmUpload` before any result.
- **Fixes**:
  - `python-calamine` (Rust) parser in `parse_excel_streaming` with openpyxl fallback — verified 0 field diffs on 60K rows, ~6-20x faster (60K rows upload end-to-end in 9s).
  - Heartbeat: `upload_sessions` gets `heartbeat` on every meta save + every 5s during parse; `/api/upload/status` returns error if heartbeat >180s stale (detects OOM/pod-restart instead of hanging forever).
  - Frontend poll window 15→60 min with elapsed display; server error details now propagate correctly (previously swallowed unless containing 'Processing failed'); 5 consecutive 404s → "session lost" error.
  - UploadManager cards: spinner+progress while active, RED XCircle + message + "Click to try again" on failure (`upload-error-state-{type}`), green tick ONLY on actual success (`upload-success-state-{type}`). Error entries persist until retry/dismiss.
  - `replaced_records` undo backup chunked into 5000-record parts (Mongo 16MB doc limit would have crashed year-wide replacements); undo endpoint reads all parts.
  - Stuck-upload auto-clear 10→30 min (10 min could kill slow 23MB chunk uploads mid-flight).
- **Verified (iteration_32.json)**: 8/8 PASS — happy path, 60K double-upload + 12-part backup + undo restore, stale heartbeat → error, FE green-on-success, FE red-on-failure. Regression: /api/stats unchanged (11,767).
- **ACTION REQUIRED BY USER**: REDEPLOY, then re-upload the 23MB sale file on production.

## Upload OOM/Restart Self-Healing — "Server restarted during processing" Fix (Jun 8, 2026)
- **Problem (production)**: after redeploy, the 23MB sale file upload died with "Server restarted during processing. Please re-upload." — the background task was killed mid-processing (most likely pod OOM from calamine materializing ~300K rows in memory).
- **Fixes ("one go" hardening, backend only)**:
  1. **Adaptive Excel reader** (`_choose_excel_reader`): reads cgroup memory headroom; calamine (fast) when headroom > ~30× file size + 150MB, else true-streaming openpyxl (bounded memory, slower but safe on small pods).
  2. **Streaming insert pipeline** (`_process_upload`): txn/historical uploads insert in 5,000-doc batches DURING parsing (`run_coroutine_threadsafe`), raw rows freed as consumed → memory bounded. New records inserted first under batch_id, then old records for uploaded dates backed up (chunked parts) + deleted excluding the new batch.
  3. **Auto-resume after crash**: chunks stay in Mongo until final success/error; sessions carry `attempts` (max 3); stale heartbeat (>90s) → `_try_resume_upload` atomically claims, rolls back partial inserts (delete batch + restore backups), reprocesses from stored chunks. Triggered from startup recovery, a delayed 120s sweep, and the status-poll path. Exhausted attempts → rollback + error + chunk cleanup. Supersession guard prevents zombie attempts clobbering retries.
  4. **branch_transfer streaming mapper added** — chunked branch uploads previously parsed 0 records (latent bug, now fixed + tested).
  5. Sale/purchase mappers skip numeric-only item names (Tally grand-total rows).
- **Verified (iteration_33.json, 7/7 PASS)**: 26MB/300K-row upload SIGKILLed mid-pipeline → 47K partial rolled back → 'Resuming after server restart...' at ~90s → complete with EXACTLY 300,000 records, no dupes, chunks cleaned. Plus happy path, replace+undo, branch_transfer, attempts exhaustion, 404, stats regression (11,767 baseline intact). Local pytest 18/18 + iter33 suite.
- **Regression suites**: `tests/test_chunked_upload_e2e.py`, `tests/test_streaming_pipeline_iter33.py`, `tests/test_unbounded_limits.py`.
- **ACTION REQUIRED BY USER**: REDEPLOY, then re-upload the 23MB sale file. Even if the pod restarts mid-processing, the upload now retries itself (up to 2 retries) and the card shows "Resuming after server restart...".

## Stock Fudging on Re-upload — Ghost Continuation-Line Fix (Jun 8, 2026)
- **User report**: re-uploading the same purchase/sale files changed Current Stock (gross 9399→7300kg). Reported as "what did you do wrong" — root cause was a PRE-EXISTING flaw, newly exposed because large re-uploads finally work.
- **Root cause (reproduced locally)**: Tally exports contain voucher continuation lines (item+weights, EMPTY date/refno/party/type). They were stored with date=''. Replace-on-reupload only deletes old records whose date is in the new file → no-date "ghost" rows never replaced → duplicated on EVERY re-upload, inflating sales, dragging stock down. Repro: 5,189-row Tally-style file → 2nd upload grew DB to 7,378 rows / +5,491kg sales.
- **Fixes** (`server.py`):
  1. Forward-fill: continuation lines inherit date/refno/party/type from the previous dated row — in streaming mappers (purchase/sale; branch date-only) AND pandas `parse_excel_file` path.
  2. Replace scope widened: `date $in new_dates + ['', None]` in both chunked (~1445) and direct (~1850) paths → legacy ghosts are self-repaired on the next upload of that type.
  3. Direct path backup switched to chunked `_backup_replaced_records`.
- **Verified (iteration_34.json, 8/8 PASS)**: re-upload now perfectly idempotent (identical counts + net_wt, 0 ghosts, grand-total rows excluded, sale_return inheritance correct); 150 seeded legacy ghosts purged by one upload; undo works; baseline 11,767 intact. Regression suite: `tests/test_upload_idempotency.py`. All prior suites 24/24.
- **RECOVERY FOR PRODUCTION**: REDEPLOY, then re-upload the purchase file once and the sale file once. Each upload purges its type's doubled ghosts and re-inserts clean dated records → stock returns to correct values automatically. Note: continuation lines now carry real dates, so daily/monthly analytics will include them (more accurate than before).
- **Testing-agent suggestion (future)**: extract shared _voucher_ffill helper (ffill logic duplicated in 4 places); consider tightening the ghost purge once production is clean.
