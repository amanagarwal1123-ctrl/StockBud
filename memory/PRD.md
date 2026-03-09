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

## Upcoming Tasks
- P1: Refactor server.py into proper FastAPI structure (routers, services, models)
- Ongoing: Data parity between deployed and preview environments

## Credentials
- Admin: username=admin, password=admin123
