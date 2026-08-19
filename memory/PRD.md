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

## Estimated Cost-Basis Fallback for No-Ledger Items (Jul 21, 2026 — session 6)
- **User request**: items sold in 2024 (discontinued) missing from PURCHASE_CUMUL ledger were SKIPPED from profit (prev fix) — user asked to instead derive their cost from the item's OWN purchase transactions ("take 2024's purchase of that item and include it in profits"). Also: fill missing purchase rates in Current Stock from any purchase found (user confirmed 1a: long-run all-years average; 2a: mark estimated items in UI).
- **Implementation** (`services/profit_helpers.py`): `fetch_fallback_purchase_stats(db)` — Mongo aggregation over `transactions` + `historical_transactions` (purchase/purchase_return, signed, abs-value canonical; fine falls back to net_wt*tunch/100; labour prefers `labor` then `total_amount`; skips numeric-only names; 60s module cache + `invalidate_fallback_cache()`); `merge_fallback_entries()` — synthesizes ledger-shaped entries (`fallback: True`) ONLY for group leaders with NO real ledger coverage (real ledger always wins, never blends); `fetch_ledger_with_fallback(db, groups, mappings, use_cache)` — drop-in replacement for the raw purchase_ledger fetch. `group_utils.build_group_ledger` preserves the `fallback` flag when all contributing entries are fallback.
- **Wired into**: `/analytics/profit` (+ `cost_basis_source` per row), `/analytics/customer-profit`, `/analytics/daily-profit`, `/analytics/daily-profit-detail`, `monthly_summary_service._compute_year` (use_cache=False; item_profit docs get `cost_source`; PROFIT_LOGIC_VERSION 5→6 → auto-recompute on first read), seasonal `_compute_margins_shared`, `stock_service.get_current_inventory` (estimated items get fine/labour filled + `rate_source` field), `/api/item/{name}` (group-aware + fallback lookup, returns `purchase_rate_source`). Year Comparison & Party monthly profits inherit via summaries.
- **UI**: CurrentStock.jsx amber `EST` badge (`est-rate-badge-{idx}`); ItemDetail.jsx `ESTIMATED` badge + amber info alert (`estimated-rate-alert`, `est-rate-badge`); ProfitAnalysis.jsx `EST` tag on rows with `cost_source==='estimated'`. Supplier-profit intentionally unchanged (per-supplier rates).
- **Verified (self-test, exact math)**: injected no-ledger item (P: 10kg@60%/₹2000kg → S: 5kg@65%/₹15000) → silver 0.25kg, labour ₹5000, source=estimated on /analytics/profit, /customer-profit AND monthly summaries; regression 42/42 profit pytest suites pass; Current Stock totals unchanged (15.163kg/105 items), 11 items gained estimated rates, 19 items with zero purchase history stay NOT SET; Item Detail returns estimated tunch/labour.
- **ACTION REQUIRED BY USER**: REDEPLOY — production summaries auto-recompute (version bump); 2024 profits will now include discontinued items at their real historical purchase cost.

## Doubled Items/Profits in 2025 — Summary Recompute Race FIXED (Jul 21, 2026 — session 6b)
- **User report (production)**: every item listed TWICE with identical values in Mar 2025 Item Profits; 2025 totals doubled.
- **Root cause**: `ensure_year_summary_fresh` had NO locking and `_compute_year` did `delete_many(year)` → `insert_many`. After the PROFIT_LOGIC_VERSION bump deploy, every summary endpoint on page load (×2 production replicas) saw "stale version" simultaneously → concurrent recomputes of the same year interleaved delete/insert → doubled docs across ALL summary types (item_profit, party profits, item_sales, even `_meta`). Preview (1 replica) escaped; production hit it. Latent since the freshness feature; every prior version bump was a roll of the dice.
- **Fix (`monthly_summary_service.py`)**:
  1. **Deterministic `_id`** per summary doc (`{year}|{month:02d}|{summary_type}|{name}`) + `insert_many(ordered=False)` tolerating BulkWriteError → duplicate rows structurally impossible even across replicas.
  2. `_meta` written via `replace_one({"_id": f"{year}|_meta"}, ..., upsert=True)` → exactly one meta per year.
  3. Per-year `asyncio.Lock` in `ensure_year_summary_fresh` + stale double-check after acquiring → parallel same-pod requests no longer duplicate work. `recompute_monthly_summaries` uses the same lock.
  4. **PROFIT_LOGIC_VERSION 6→7** → on first read after redeploy every year auto-rebuilds cleanly, purging production's existing doubled docs (no manual step).
- **Checked elsewhere**: other delete+insert patterns (opening_stock, purchase_ledger, master_items) are single-admin-action paths, not read-triggered — not exposed to this race. All doubled VIEWS (Dashboard, Profit Analysis, Party Analytics, Year Comparison, monthly breakdowns) read monthly_summaries → all heal with the v7 rebuild.
- **Verified (preview)**: 8 concurrent `ensure_year_summary_fresh` → 0 dupes, 1 meta; simulated cross-replica race (2 raw concurrent `_compute_year`, no lock) → 0 dupes, no lost docs (1205 == clean-run 1205); full-collection dupe scan clean; freshness pytest suites 11 pass; endpoints return unique items.
- **ACTION REQUIRED BY USER**: REDEPLOY — 2025 (and all years) auto-heal on first page load.

## Year Comparison Party List 1000-Cap Removed (Jul 21, 2026 — session 6c)
- **User report (production)**: Year Comparison → Customer/Supplier Drill-Down search list not showing all customers/suppliers.
- **Root cause**: `/api/analytics/year-comparison/parties` sliced sorted names to `[:1000]` — production has 6000+ customers, so all names after the 1000th alphabetical entry were silently missing.
- **Fix**: backend cap removed (full distinct list returned); frontend `YearComparison.jsx` datalist now renders a case-insensitive substring-filtered subset (max 100 DOM options for perf) while keeping the full list in memory for exact-match selection; added party count label (`party-count-label`).
- **Verified (iteration_41.json, 100% backend + frontend)**: 3220 customers / 1186 suppliers returned (>1000), late-alphabet names reachable via search, party-detail loads, monthly-profit regression clean. Test seeds (YCTEST, year 2018) cleaned up after run.
- **Follow-up (same session)**: user couldn't scroll past the first 100 names (datalist DOM cap). Replaced native datalist with a custom scrollable dropdown (`party-options-list` / `party-option` testids): renders ALL names (scroll to bottom works — verified 2020/2020 options, last = ZIL SILVER...), case-insensitive filter as you type, click to select (onMouseDown before blur), opens on focus. Verified via playwright: full scroll, ZIL filter→select→customer detail, supplier toggle→ZEENAT→supplier detail.
- **ACTION REQUIRED BY USER**: REDEPLOY.

## Sales Report — Stock vs Sale Drill-Down Charts (Jul 27, 2026 — session 6d)
- **User request**: expandable graph per item AND stamp in Sales Report — day-opening net stock as tight bars, day sale as line, whole period fits on screen, stock-to-sale ratio badge (low=green, high=red), mobile friendly + colorful.
- **Backend**: `GET /api/analytics/sales-report-drill?entity_type=item|stamp&name=&start_date=&end_date=` (server.py, after sales-report). Opening stock seeded from `get_current_inventory_cached(as_of=day-before-start)` (baseline/anchor aware), rolled forward with engine sign rules (purchase/PR/receive ADD raw, sale/SR/issue SUBTRACT raw); sales = canonical signed; range capped at today (IST). Returns days[{date, stock_kg (day-opening), sold_kg}], avg_stock_kg, total_sold_kg, stock_to_sale_ratio (= avg stock ÷ period sale; null when no sales). Item mode matches by group leader; stamp mode by leader's stamp (same resolution as sales-report rows); EXCLUDED_ITEMS skipped. 400 on bad entity_type.
- **Frontend**: `components/StockSaleChart.jsx` — ComposedChart: indigo bars (barCategoryGap 12%, whole range fits, no h-scroll) + rose sale line, dual colored y-axes, badges (Avg Stock / Sale / ratio: ≤2 green Healthy, ≤4 amber Watch, >4 red Overstocked, <0 red Negative stock, null red No sales) + plain-language legend. SalesReport.jsx: BarChart2 toggle on stamp rows (`chart-toggle-stamp-*`), item rows (`chart-toggle-item-*`), and item sub-rows under stamps (`chart-toggle-subitem-*`); one chart open at a time, cached per period, cache cleared on period change; chart row uses sticky-left width trick so it fits the viewport inside the h-scrollable table (mobile verified at 390px).
- **Tested (self)**: curl item + stamp + 400 case (27 days, ratio math verified); desktop screenshots (item chart red 'Negative stock' badge — preview data artifact; stamp chart green 'Healthy 0.03×'); mobile 390px screenshot — chart 326px wide, fits fully.
- **ACTION REQUIRED BY USER**: REDEPLOY to get this on production.

## Sales Report — Monthly-Average Ratio + Ratio Column + Merged Names (Jul 28, 2026 — session 6e)
- **User bug**: multi-month ranges diluted the Stock:Sale ratio (divided by TOTAL period sale). FIX: ratio = avg day-opening stock ÷ AVG MONTHLY sale (months_equiv = elapsed_days/30.44, range capped at today IST). Applied in BOTH `/analytics/sales-report` (new per-row computation) and `/analytics/sales-report-drill` (also returns `avg_monthly_sale_kg`, chart shows 'Sale/Mo' badge).
- **New ratio column**: `stock_sale_ratio` + `avg_stock_kg` on every by_item/by_stamp row (single-pass: opening inventory as-of prev day + streamed txn deltas per leader; stamp = sum of leader avg stocks). Sortable 'Stock:Sale' column right after 'Avg Labour ₹/kg' in both tables + stamp sub-rows, rendered as colored `RatioPill` (exported from StockSaleChart.jsx): ≤2 green, ≤4 amber, >4/negative/null red. ChartRow colSpans now 14 (stamp) / 13 (item).
- **Merged names**: by_item rows include `merged_names` (variant raw names folded into the leader, seen in period, max 10); shown in small indigo text 'incl. …' under the item name on MAIN rows (`merged-names-{item}`) and stamp sub-rows — no expansion needed. (Leader-level combining of mapped items already existed.)
- **Tested (iteration_42.json — 100% backend + frontend)**: full-year math verified ≠ old formula, drill == table ratio, merged names correct with no duplicate row, 14/13 column alignment verified, sorting works, regression totals clean. Pytest: tests/test_iteration_42_sales_ratio.py (6/6).
- **ACTION REQUIRED BY USER**: REDEPLOY.

## Stock vs Sale Chart — Cursor Tracking Fix + Negative Ratio Green (Jul 28, 2026 — session 7)
- **User bug**: red active dot on drill chart didn't move horizontally with cursor; also asked to verify ratio math and make negative ratios green.
- **Root cause (dot)**: XAxis `dataKey="day"` used day-of-month only — duplicated across multi-month ranges, so Recharts snapped the active dot/tooltip to the FIRST matching category. FIX (`StockSaleChart.jsx`): XAxis now uses full unique `date` with `tickFormatter` showing day only; tooltip label = full date.
- **Ratio math verified** (no change needed): both `/analytics/sales-report` (`_ratio`) and `/analytics/sales-report-drill` compute `avg day-opening stock ÷ (total sale ÷ months_equiv)`, negative sign preserved.
- **Negative = green**: `ratioMeta` (ratio < 0 → green 'Neg. stock, selling') was already in code from session 6e — user's red screenshot was PRODUCTION (not yet redeployed).
- **Verified (preview screenshot)**: 6-month range tooltip @30% = 2026-02-21, @70% = 2026-05-10 (tracks); 3 negative pills confirmed `text-green-700`.
- **ACTION REQUIRED BY USER**: REDEPLOY.

## Sales Manager Role + Restricted Sales View (Aug 5, 2026 — session 8)
- **User request**: new `sales_manager` role — sees item-wise & stamp-wise sales (gross+net weight ONLY), limited to last 2 months and to stamps assigned via Stamp Assign; sortable by name/weight; also has all stock-entry-executive powers but NO approval rights; Stamp Assign dropdown shows only managers/sales managers (one manager → multiple stamps).
- **Backend (`server.py`)**: `sales_manager` added to role validation (create ~1120, update ~1196), `/executive/stock-entry` gate, `/polythene/all` gate. New `GET /api/analytics/sales-manager-report?start_date=&end_date=` (before sales-report-drill): roles sales_manager/admin; window earliest = min(today−60d, first day of prev month) IST, 400 outside; filters to `stamp_assignments` where assigned_user==caller (admin unrestricted); streams sale/sale_return txns (canonical signed abs×sign), group-leader + stamp resolution identical to sales-report, EXCLUDED_ITEMS skipped; returns by_item/by_stamp rows {name, stamp, gross_wt_kg, net_wt_kg}, totals, assigned_stamps, window, no_stamps_assigned flag.
- **Frontend**: new `pages/ManagerSalesView.jsx` (/manager-sales): This Month / Last Month / custom range (client+server capped to window), By Item / By Stamp tabs, sortable Name/Gross/Net headers, totals cards, assigned-stamp chips, no-stamps amber alert. App.js redirect sales_manager→/manager-sales; Layout nav (Stock Entry, Sales View, Notifications, Inventory>Polythene Mgmt); AuthContext isSalesManager; PolytheneManagement canAccess + sales_manager; UserManagement role option + purple badge; StampAssignments dropdown filtered to manager/sales_manager, description updated.
- **Approval rights explicitly NOT granted**: /manager/* endpoints stay manager/admin (verified 403 for TEST_SM).
- **Tested (iteration_43.json — 100% backend 15/15 + 100% frontend)**: filtering, window enforcement, role gates, math parity with admin sales-report (July: 1096.830 gross / 937.167 net), sorting, custom-range toast block, stamp-assign dropdown only shows SMANAGER + TEST_SM, admin sales-report regression clean. Regression suite: `tests/test_sales_manager_feature.py`.
- **Credentials**: TEST_SM / sm123 (preview). **ACTION REQUIRED BY USER**: REDEPLOY, then create real sales manager users + assign stamps on production.
- **Follow-up (Aug 6, 2026)**: Total Gross/Net cards REMOVED from Sales View per user — `totals` stripped from the API response and the UI (per-row weights only). Verified sale − sale_return math is applied (sale_return rows signed −1). Regression suite updated, 15/15 pass; UI screenshot confirms no totals, 253 rows.

## Purchase List + Goods to Arrive (Aug 19, 2026 — session 9)
- **User request**: admin-only Purchase List tab (below Dashboard) + Goods to Arrive tab. Confirmed choices: only rows with order_qty>0; profit sale-side = last 2 months; variable baseline = peak closing stock since baseline start (default Jan 1, admin-editable, resets yearly); purview = single orderer label (not app users); unchecking green also removes the pending Goods-to-Arrive entry.
- **Backend**: new `services/purchase_list_service.py` `compute_purchase_snapshot` — opening inventory as-of baseline_start−1 (get_current_inventory_cached), streams txns once (ADD purchase/purchase_return/receive, SUB sale/sale_return/issue), rolls daily closing per leader, order_qty=baseline−closing; fine=qty×ledger tunch/100, labour=qty×ledger ₹/kg; profit Ag g/kg & labour ₹/kg from last-60d sales vs ledger cost basis. Endpoints in server.py (block 'PURCHASE LIST & GOODS TO ARRIVE'): GET /purchase-list?date (lazy compute+cache in `purchase_list_snapshots`, fingerprint=txn count in window; recomputes on data change → past-modification safe), POST /purchase-list/item-state (temp_removed/green/season_months/purview/baseline_mode/fixed_baseline_kg; green→creates goods_orders capturing that day's row, with latest-snapshot fallback; uncheck→deletes pending; baseline changes purge snapshots), POST /purchase-list/refresh (clears temp removals only), POST /purchase-list/orderers, PUT /purchase-list/config (baseline_start), GET /goods-to-arrive, PUT /goods-to-arrive/{id} (qty edit recomputes fine/labour; arrive/undo). Collections: purchase_list_snapshots, purchase_item_state, purchase_orderers, purchase_list_config, goods_orders.
- **Frontend**: `pages/PurchaseList.jsx` (sortable table default Profit Ag desc, left-swipe via pointer events = temp remove, green checkbox = green fill+outline row, orderer filter checkboxes All/Admin/salesmen default Admin, date picker max today, Refresh, settings popover for baseline start) + `components/PurchaseItemSheet.jsx` (baseline variable/fixed, 12-month season toggles, purview chips + add-orderer with +) + `pages/GoodsToArrive.jsx` (To Arrive: inline qty edit/Mark Arrived; Arrived: Undo). Nav: Purchase List + Goods to Arrive under Dashboard (admin).
- **Tested (iteration_44.json)**: 100% backend (14/14, suite `tests/test_purchase_list_feature.py`) + 100% frontend. Post-test polish: pointercancel handler on swipe rows, negative fixed_baseline_kg rejected (400). QA orderers cleaned; 'RAJESH' demo orderer remains in preview.
- **REDEPLOY required** to get this on production.

- **Bugfix (production empty list, Aug 17-19 2026 — iteration_45.json)**: production showed 'No items to order for this view'. Two contributors fixed: (1) GET /purchase-list no longer serves a cached snapshot with empty rows (`or not snap.get('rows')` in cache-bypass) — protects against snapshots computed mid-upload; response now includes `window_txn_count`; (2) frontend empty state differentiates: hidden-by-filters (count + breakdown + 'Show all orderers' pl-show-all-btn + 'Restore swiped items' pl-restore-swiped-btn), no-transactions-in-window (pl-empty-nodata), or genuinely-at-peak. New suite `tests/test_purchase_list_bugfix_45.py`. NOTE: likely production cause is rows hidden under other orderers' purview or swiped away — the new banner reveals it; user must REDEPLOY.

## Seasonal Switch + Seasonal Items List (Aug 19, 2026 — session 9 cont.)
- Per-item 'Seasonal selling' Switch (pl-seasonal-toggle), OFF by default; ON reveals month grid with selection cleared; OFF clears months. Filtering applies only when enabled AND months chosen. Legacy items with months auto-treated as enabled (read-time fallback `seasonal_enabled` = bool(season_months)).
- Header 'Seasonal' button (pl-seasonal-list-btn) → dialog (pl-seasonal-dialog) listing all seasonal items (new GET /api/purchase-list/seasonal-items, admin) with month badges; click opens the item editor even when out of season (metrics guarded with '—' when item not in day's rows; patchRow also patches openItem for live dialog updates). DialogDescription added for a11y.
- Tested iteration_46.json: 100% backend (21/21 incl. regressions) + 100% frontend. New suite tests/test_purchase_list_seasonal_v46.py. REDEPLOY required.

## Perm Delete + Removal Buttons + Opening Cache (Aug 19, 2026 — session 9 cont.)
- Left-swipe REMOVED (was unreliable on mobile). Item dialog footer now has 'Remove temporarily' (pl-temp-delete-btn, = old swipe, restored by Refresh) and 'Delete permanently' (pl-perm-delete-btn, perm_removed flag, NOT restored by Refresh). Red 'Permanently Deleted Items' link on top (pl-deleted-list-btn) → dialog with Undelete per item (GET /api/purchase-list/deleted-items; undelete via item-state perm_removed:false). Rows filter excludes perm_removed client-side.
- Performance: `purchase_opening_cache` Mongo collection caches the heavy as-of-baseline-start-1 opening inventory (entries list, fingerprint = txn count ≤ prev_day + anchor count) so snapshot recomputes only stream the in-window transactions. Verified: opening not recomputed after snapshot wipes.
- Tested iteration_47.json: 100% backend (25/25 incl. all regressions) + 100% frontend. New suite tests/test_purchase_list_perm_v47.py. DialogDescription a11y added to all purchase dialogs. REDEPLOY required.

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

## Item-wise Current Stock Formula Verification (Jun 8, 2026)
- **User suspicion**: logical mistake in current stock (= old + purchase + received − sales − issue), introduced by the last 2 changes.
- **Verification (dummy data, iteration_35.json — 4/4 PASS, independent)**:
  1. Formula check: opening 100 + P 30 + PR(−5) + Rcv 10 − S 20 − SR(−3) − I 7 = 111kg → engine returns exactly 111. NOTE: Tally exports RETURNS WITH NEGATIVE WEIGHTS (verified in real data: 234/238 sale_returns, 28/29 purchase_returns negative), so stock_service's ADD-purchase-family / SUBTRACT-sale-family sign convention is correct.
  2. OLD-style data (continuation date='' + default type) vs NEW-style (inherited date+type): IDENTICAL stock (17kg both) → the 2 changes did NOT alter stock math for normal items.
  3. E2E through the new pipeline (P+S+BT files with continuation + negative return rows): matches hand-computation, idempotent on re-upload.
  4. Baseline items (physical stock baselines): the ONLY behavior change — continuation rows dated after the baseline now count (previously silently skipped as no-date). More correct, not a bug.
- **No numeric-only item names** exist in real data (new parser filter drops nothing real; stock engine already excluded integer names).
- **Regression suite added**: `tests/test_itemwise_stock_formula.py` (~93s due to 30s inventory cache waits).
- **Production note**: if stock still looks wrong on production, the DB there still contains the doubled ghost rows — REDEPLOY + re-upload each file once to self-repair (iter34 fix).

## Opening Stock as Global Anchor — COMPLETE (Jun 16, 2026)
- **User request**: uploading Opening/Master stock on a specific date must become the absolute baseline. Items not in the file → zero; transactions on/before that date must NOT alter current stock.
- **Implementation** (was ~95% done by previous fork, finished here):
  - Fixed critical interrupted-edit bug: `@api_router.post("/opening-stock/upload")` decorator was attached to the helper `_set_opening_effective_date` instead of `upload_opening_stock` (server.py ~line 950) → the upload endpoint was completely broken. Decorator moved to the correct function.
  - `app_settings` doc `opening_stock_effective_date` stores the anchor; set automatically by `/api/opening-stock/upload?effective_date=` and `/api/master-stock/upload?effective_date=`, or manually via PUT `/api/opening-stock/effective-date`.
  - `stock_service.py` (`get_current_inventory`, `get_book_closing_stock_as_of_date`, `get_stamp_closing_stock`): transactions/polythene with date <= anchor skipped; baselines older than anchor superseded; unlisted items start at 0.
  - Frontend: Master Stock tab has "Stock as on date" picker (defaults today) + "Opening Stock Effective Date" card (GET/PUT, testids: effective-date-card/input/save/value/missing). Chunked path passes date via `start_date` in `/upload/init`; direct path via query param.
- **Verified (self-test, all PASS, preview data backed up/restored)**: upload anchors date; pre-anchor purchase+sale ignored (opening 1000 + post-anchor 100 = 1100 exact); unlisted item = post-anchor txns only (50); moving anchor via PUT re-bakes all txns; master-stock upload also anchors; UI renders card correctly.
- **Opening stock parser format reminder**: columns `Item Name, Stamp, Gr.Wt., Net.Wt.` with weights in KG. Master stock: `Item Name, Stamp, Gross weigth, Net Weight` in grams.

## Stock Delta Investigation + Stock Movement Audit Feature (Jul 17, 2026)
- **User report**: stock jumped 7437.699 → 7451.759 kg net (+14.060) overnight after "updates from mobile"; asked whether all 6 txn types (sale/sale_return/purchase/purchase_return/issue/receive) are handled.
- **Forensic findings (preview DB mirror of same uploads)**:
  - The "mobile updates" were file uploads at 07:40–07:44 UTC Jul 17: sales Jun13–Jul13, sales Jul14–15, purchases Jun13–Jul15 (uploaded TWICE — idempotency cleanly deduped, net effect 0.000), plus 2025 full-year sale+purchase files.
  - Verified via `replaced_records` lineage: no duplication; every overlapping upload replaced its exact date range.
  - +14.06 kg = (fresh files' effect) − (old rows replaced) + new Jul 14–15 trading days. Not a calculation bug.
  - Sign audit confirmed: purchase/purchase_return/receive ADD raw values, sale/sale_return/issue SUBTRACT raw values; returns stored NEGATIVE in Tally exports so math nets correctly. Header total sums ALL items incl. negatives.
- **New feature: Stock Movement Audit** (so day-over-day changes are always explainable):
  - Backend: GET `/api/stock-audit/uploads?limit=20` (admin-only) in server.py (before `_replace_physical_stock_for_date`). Per upload batch: rows inserted/replaced, per-type net kg breakdown, inserted vs replaced impact, `net_change_kg`, rows excluded by anchor/baselines (`rows_before_anchor`). Honors opening anchor + item baselines + EXCLUDED_ITEMS (same rules as Current Stock).
  - Frontend: `/stock-audit` page (`pages/StockAudit.jsx`), sidebar Inventory → "Stock Audit" (Scale icon). Summary cards (uploads shown, combined net movement, anchor date) + Upload Impact History table with "new X − old Y" reconciliation line for replacements. testids: stock-audit-page/-upload-count/-total-movement/-anchor-date/-refresh-btn/-row-<batch8>.
- **Tested**: iteration_36.json — 100% backend + frontend (10 pytest cases in `tests/test_stock_audit.py`); idempotent duplicates show 0.000; 403 for executive; /current-stock regression intact.

## Production OOM: Current Stock/Dashboard All Zeros After 2025 Sales Upload — FIXED (Jul 17, 2026)
- **User report**: full-2025 sales file (~210K rows) uploaded with success message, then Current Stock + Dashboard permanently showed zeros on production (stock-tracker-722.emergent.host, 1Gi memory pods, 2 replicas).
- **Root cause (measured)**: heavy read paths loaded ALL transactions as FULL documents into RAM: get_current_inventory ~815MB, get_book_closing_stock_as_of_date ~780MB, post-upload background `_compute_year` ~700MB → OOM-killed the 1Gi pods on every heavy request; login (light) still worked, so app looked alive but data pages showed zeros. Production DB data is INTACT — serving layer failure only.
- **Fixes**:
  1. `stock_service.py`: get_current_inventory, get_book_closing_stock_as_of_date, get_stamp_closing_stock — transactions now STREAMED (`async for`) with field projections; EXCLUDED/digit filter moved into loop.
  2. `monthly_summary_service._compute_year`: fetches month-by-month with projection (was whole year full-docs).
  3. `server.py _backup_replaced_records`: now takes a query and streams backups in 5000-row chunks (was materializing all replaced rows — would have OOMed the recovery re-upload). Both call sites updated (chunked ~1510, direct ~1917).
- **Verified (iteration_37.json, 100% both)**: peak RSS 82MB (was ~950MB, 11x); outputs bit-identical (inventory totals, book closing, summaries); upload idempotency suite 8/8 with new streaming backup; frontend Current Stock/Dashboard/Stock Audit non-zero.
- **USER ACTION: REDEPLOY production** — data is intact; pages recover immediately, no re-upload needed.
- **Preview-only incident (no production impact)**: `tests/test_upload_idempotency.py` generated test files with random 2025 dates → its uploads date-replaced the REAL 2025 rows in the PREVIEW DB (210,226 sales + 560 purchases deleted; backups+action_history also removed by its cleanup). Suite now uses 2019 dates everywhere so it can never collide with real data. Preview DB now has 31,837 txns; re-upload 2025 files to preview only if parity is wanted.
- **Backlog note**: analytics endpoints (party analysis ~4538, visualization ~7415, profit ~4196 etc.) still load date-filtered FULL docs via .to_list(None) — full-year ranges could still spike memory; candidates for same projection/streaming treatment.

## Approvals OOM Fix + Full Memory Sweep + Party Profit Graphs (Jul 17, 2026 — session 3)
- **User report (production)**: Approvals page crash ("calculations crash server", Cloudflare unparseable response); asked to audit all heavy spots; asked for decision on 115-credit/month plan upgrade; requested expandable month-wise profit graphs in Cust Profit / Supp Profit tabs.
- **Approvals root cause**: ManagerApprovals fires `/api/manager/approval-details/{stamp}` for ALL pending stamps in parallel; each ran UNCACHED full-scan `get_current_inventory(as_of_date)`. FIX: `get_current_inventory_cached()` in server.py — 30s TTL + per-key asyncio.Lock in-flight dedup; all 11 call sites switched.
- **Memory sweep (streamed cursors + projections)**: customer-profit (stream), supplier-profit (rewritten to aggregate math — same formulas, deterministic), sales-summary (stream), analytics/profit (single-pass stream), party-analysis (stream), visualization (projection), mappings/unmapped (distinct()), stamp-detail queries (projection).
- **New feature**: per-party monthly PROFIT summaries in monthly_summary_service (`party_customer_profit`: silver_profit_kg/labor_profit_inr/sold_kg; `party_supplier_profit`: +purchased_kg/items_count). PROFIT_LOGIC_VERSION 2→3 (auto-recompute on first read). New endpoint `GET /api/analytics/party-monthly-profit/{party}?year&party_type`. Frontend PartyAnalytics.jsx: Cust/Supp Profit rows expandable → PartyProfitChart with metric toggles (Silver Profit kg #16a34a, Labour Profit INR #2563eb, Sold/Purchased kg #d97706). testids: cust-profit-row-N, cust-profit-expanded-row, supp-profit-row-N, supp-profit-expanded-row, party-profit-chart, party-profit-metric-*.
- **Tested**: iteration_38.json — 100% backend (16 new + 10 stock-audit tests) + 100% frontend. React key warning in pre-existing Customers/Suppliers fragments also fixed.
- **Preview DB note**: orphaned 2025 purchases (8,029 rows) deleted → preview now 23,808 txns, inventory 15.163 kg / 105 items (2026 data only). Production unaffected.
- **Plan recommendation given to user**: redeploy first; crashes were code bugs now fixed (peak RSS ~950MB→<200MB + dedup). Upgrade only if analytics still feel slow with multi-year data / more concurrent users (250m CPU is the remaining constraint, not memory).

## Anchor Query-Pruning + Year Comparison Analytics (Jul 20, 2026 — session 4)
- **User request 1**: multi-year data made Current Stock slow; asked for caching of pre-anchor data. IMPLEMENTED (user approved): query-level pruning instead of caching — transactions dated <= opening anchor (oed) can never affect stock (every item's cutoff >= oed), so stock_service now adds `date $gt oed` to the Mongo query in get_current_inventory / get_book_closing_stock_as_of_date / get_stamp_closing_stock (in-loop skip kept as safety net; equivalence proven with synthetic anchor test). date indexes already existed. Old-year analytics stay cached via monthly_summaries fingerprints.
- **User request 2** (chose "a: 3D-styled readable bars, constant scales"): new **Year Comparison** page (/year-comparison, sidebar Analytics & ML):
  - Backend: PROFIT_LOGIC_VERSION 4; new `item_sales` monthly summary type (stamp-independent, group-aware); endpoints: /api/analytics/year-comparison/overview | /top?entity=items|customers|suppliers | /party-detail?party&party_type | /parties?party_type. All read pre-computed summaries; `_get_data_years()` from transactions.
  - Frontend YearComparison.jsx: year legend chips, yearly totals cards + sales growth % badges, Monthly Comparison chart (6 metric toggles: sales kg/value, purchases kg, silver profit, labour profit, transactions), Top Items/Customers/Suppliers tabs (grouped 3D bars + chips → month-by-month drill chart), customer/supplier drill-down with datalist search (4 metrics). Custom SVG Bar3D shape; 3D Bars ⇄ Lines toggle; string-year dataKeys so legend/tooltips show year labels. YEAR_COLORS palette (#6366f1, #f59e0b, #10b981, ...).
- **Preview demo seed**: stock-neutral 2024 (794 rows) + 2025 (1000 rows) demo data, batch_id demo-seed-YYYY (each sale paired with equal-weight purchase). Ground truths: yearly sales_kg 2024=852.934, 2025=1060.154 (+24.3%), 2026=3487.531 (+229%); current stock unchanged 15.163 kg / 105 items.
- **Tested**: iteration_39.json — 100% (12/12 backend + full frontend flows).

## Graph Corrections + Profit Root-Cause Fix + Seasonal/Viz OOM (Jul 21, 2026 — session 5)
- **Year Comparison corrections (user request)**: pastel 2D bars (YEAR_PALETTE bar/dark pairs, Bar3D removed), 8 overview metrics (sales net/fine kg, sales value, purchases net/fine kg, silver profit, labour profit, transactions), top-N dropdown 10-50 (top-limit-select) with horizontally scrollable chart, year cards show net/fine/value/purchases/profits. ModeToggle testids scoped (overview-/top-/party-chart-mode-*).
- **2024 profit inflation ROOT CAUSE (user hypothesis confirmed)**: items with NO entry in the cumulative PURCHASE_CUMUL ledger were computed with purchase_tunch=0 → full sale tunch counted as silver profit. FIX: /analytics/customer-profit endpoint (~server.py:4141) + _compute_customer_profit_month now SKIP no-ledger items; Year Comparison silver/labour profit now sums item_profit summaries = EXACT Profit Analysis math. PROFIT_LOGIC_VERSION=5.
- **Answers given to user**: (1) 2025: Profit Analysis (~1700kg, cumulative-ledger method) is correct per their running-average methodology; Historical page (~1500kg) uses same-year-only purchase averages from historical_transactions. (2) Historical uploads play NO role in purchase tunch/labour — ledger comes only from PURCHASE_CUMUL file uploads (full replace) + manual Purchase Rates edits; regular purchase uploads don't update it either.
- **Seasonal fail fix**: _load_data streams column-wise into DataFrames (no list-of-dicts), margins query only sale rows, results persisted to db.app_cache key 'seasonal_results' (1h TTL, survives restarts/replicas).
- **Visualization fail fix**: single streamed pass with 7-field projection (was full-range materialization ~750MB on production).
- **Tested**: iteration_40.json — 14/14 backend + 100% frontend. Preview note: silver/labour profit legitimately 0.0 in preview (only 1 stamped master item); production has full stamps.
