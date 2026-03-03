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

## Pending / Known Issues
- User needs to re-upload sale data for Feb 26-27 if preview data was affected
- Profit discrepancy between deployed/preview explained by data differences + new data

## Upcoming Tasks
- P1: Refactor server.py into proper FastAPI structure (routers, services, models)
- Ongoing: Data parity between deployed and preview environments

## Credentials
- Admin: username=admin, password=admin123
