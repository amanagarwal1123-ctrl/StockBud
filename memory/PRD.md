# StockBud - Silver Stock Trading Application

## Original Problem Statement
Silver stock tracking application for managing inventory, sales, purchases, branch transfers, and profit analysis for a jewelry business. Key features include file upload for transaction data, stamp-based inventory management, executive stock verification workflow, and analytics.

## Core Architecture
- **Backend**: FastAPI (Python) + MongoDB
- **Frontend**: React + Shadcn/UI
- **Database**: MongoDB (motor async driver)

## Key Collections
- `transactions` - Sales, purchases, returns, branch transfers
- `master_items` - Item catalog with stamp assignments
- `item_mappings` - Maps transaction names to master item names
- `item_groups` - Groups related items under leaders
- `purchase_ledger` - Purchase cost basis for profit calculation
- `opening_stock` - Starting inventory
- `physical_stock` - Physical count data
- `stock_entries` - Executive stock verification entries
- `stamp_approvals` - Manager approval records
- `polythene_adjustments` - Weight adjustments
- `upload_sessions` / `upload_chunks` - Chunked upload state

## What's Been Implemented
- Full CRUD for transactions, stock, mappings, groups
- File upload (direct + chunked) for purchase/sale/branch/stock
- Profit calculation (silver + labour) with group-aware resolution
- Stamp-based inventory with approval workflow
- Historical data upload and analytics
- User management with role-based access

## Key Fixes (Feb-Mar 2026)
1. **Date parsing bug** - Fixed month/day swap in normalize_date
2. **Memory crash** - Removed top-level pandas import
3. **Data truncation** - Removed to_list(10000) limits
4. **Comma number parsing** - Fixed _safe_float for Indian number formats
5. **Upload data loss** - Fixed delete logic to only delete dates present in uploaded file
6. **Stamp approval date bug** - Fixed approval-details endpoint to accept verification_date parameter (multiple entries for same stamp now show correct Book values per date)
7. **Upload stops after 2 files** - Reset file input value after selection
8. **Item mappings** - Imported 216 mappings from user's deployed version
9. **P0: Auth on all data-changing endpoints** - Added Depends(get_current_user) to upload, reset, delete endpoints
10. **P1: Reset collection mismatch** - Reset/normalization now targets physical_stock (not just physical_inventory)
11. **P1: Identity spoofing** - entered_by/adjusted_by now derived from current_user, not client request
12. **P1: Stamp verification date** - stamp_verifications now uses entry's verification_date, not approval date
13. **P2: Item stats math** - Returns properly included in weight totals, averages, and current stock
14. **P2: Notification schema** - Read query now matches write schema (target_user + for_role)
15. **P2: Polythene delete auth** - Only admins can delete polythene entries

## Pending / Known Issues
- User needs to re-upload sale data for Feb 26-27 if preview data was affected
- Profit discrepancy between deployed/preview explained by data differences + new data

## Key Fixes (Mar 2026 - Session 2)
16. **AI seasonal-analysis timeout** - Switched from claude-sonnet-4-5 to gemini-3-flash-preview + added 30s asyncio.wait_for timeout with fallback
17. **season_boost field restored** - Added season_boost (seasonal/overall velocity ratio) back to item-buffers/categorize endpoint
18. **Session mixing across tabs** - Switched all auth token storage from localStorage to sessionStorage (12 files), enabling independent per-tab sessions
19. **Security Hardening Batch 2** - Added auth to 15+ unauthenticated write endpoints (upload/client-batch, mappings/create-new-item, physical-stock/upload, purchase-ledger/upload, mappings/create, stamp-verification/save, DELETE mappings, history/undo, item/assign-stamp, item-buffers update, analytics/smart-insights)
20. **Admin-only undo-upload & recent-uploads** - Added admin role check to history/undo-upload and history/recent-uploads
21. **Horizontal access fix** - executive/my-entries/{username} now restricts to own entries or admin/manager
22. **Polythene today auth** - polythene/today/{username} now requires authentication
23. **Notification read scoping** - mark_notification_read now scoped to current user's target_user
24. **KeyError fix** - executive entries stamp dedup uses e.get('stamp', '') instead of e['stamp']
25. **Duplicate item check** - create-new-item now checks for existing item before inserting
26. **Role checks on write endpoints** - Admin-only restriction on 10 sensitive write endpoints (upload/client-batch, mappings/create-new-item, purchase-ledger/upload, mappings/create, DELETE mappings, history/undo, item/assign-stamp, item-buffers update, analytics/smart-insights). Physical-stock/upload allows admin+manager.
27. **IDOR fix polythene/today** - Ownership check added: only own entries or admin/manager
28. **Auth on 31 GET routes** - All read endpoints now require authentication (transactions, inventory, analytics, orders, mappings, etc.)
29. **JWT secret hardening** - Removed insecure fallback; generates random secret if env var missing; explicit key in .env
30. **initialize-admin no password in response** - Removed default credentials from API response
31. **Notification mark-read mismatch** - Expanded update filter to match fetch scope ($or with target_user, role, and for_role)
32. **history/undo ObjectId fix** - Added _id:0 projection to prevent serialization error

## Key Fixes (Feb 2026 - Session 3: Codex Batch 3)
33. **Admin role on upload/mass-write endpoints** - Added admin/manager role check to 6 upload endpoints: opening-stock/upload, upload/init, upload/chunk, upload/finalize, transactions/upload, master-stock/upload
34. **Upload session ownership** - upload/init now stores owner_username; chunk, finalize, and status endpoints verify the caller owns the session
35. **Stamp verification role guard** - stamp-verification/save restricted to admin/manager, now stores verified_by=current_user['username']
36. **Order operations RBAC** - GET /orders scoped to own orders for non-admin users; PUT /orders/{id}/received and GET /orders/overdue restricted to admin/manager
37. **Dead code removal** - Removed unreachable `return {'success': True}` at line 2219
38. **Unused param cleanup** - Removed unused `adjusted_by` parameter from /polythene/adjust endpoint
39. **Stray docstring cleanup** - Removed duplicate docstring inside save_stamp_verification

## Key Feature (Mar 2026 - Session 4: Physical Stock Staged Partial Update)
40. **Physical stock parser** - New `physical_stock` parser type in both `parse_excel_file` and `parse_excel_streaming` with flexible header support:
    - 2-col: Item Name + Gross Weight (updates gross only, preserves net)
    - 3-col: + Net Weight (updates both)
    - 4-col: + Stamp (backward-compatible)
    - Headers accepted: Gr.Wt. / Gr Wt / Gross Wt / Gross Weight | Net.Wt. / Net Wt / Net Weight / Gold Std.
41. **Preview endpoint** - `POST /api/physical-stock/upload-preview` parses file and diffs against db.physical_stock scoped to selected verification_date only
42. **Apply endpoint** - `POST /api/physical-stock/apply-updates` persists only approved items for the specific verification_date, logs via audit pattern
43. **Preview modal** - New `PhysicalStockPreview.jsx` component: per-row diff, per-row Approve, Approve All, CSV export, success banner with date+count
44. **Upload queue** - Rewrote `UploadContext.jsx` with real serialized queue (queued→uploading→processing→done→error), one-at-a-time execution
45. **Deterministic upload flow** - Removed fragile `window.confirm()` in onChange; physical stock → preview modal; other types → confirmation card
46. **Date-scoped operations** - verification_date is required for preview/apply; compare endpoint supports optional date filter; no cross-date mutation
47. **Compare page date filter** - Added verification_date selector to PhysicalStockComparison.jsx to scope comparison to a specific date

## Upcoming Tasks
- P1: Refactor server.py into proper FastAPI structure (routers, services, models)
- Ongoing: Data parity between deployed and preview environments

## Credentials
- Admin: username=admin, password=admin123
