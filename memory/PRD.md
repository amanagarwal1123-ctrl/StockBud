# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI, Motor (async MongoDB), JWT auth
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios, SheetJS (xlsx)
- **Database:** MongoDB (test_database)

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123

## Upload Logic (CRITICAL — Feb 28, 2026)
- **Date-based replacement**: Only deletes records for dates that EXIST in the new upload file (not the full user-selected range). Prevents data loss for dates not in the file.
- **Backup on replace**: Replaced records saved in `replaced_records` collection keyed by batch_id
- **Undo restores**: Undo deletes new records AND restores backed-up previous records
- **Type-safe**: Purchase upload only touches purchase/purchase_return. Sale only touches sale/sale_return. Branch transfer touches issue/receive.
- **Master Date Range**: Shared date picker on Transactions tab applies to all file types at once. Individual overrides still possible.
- **Success message**: Includes actual date range from file data

## Query Limits
- All `to_list()` calls use `None` (unlimited). No silent truncation regardless of data volume (supports 2-3 lakh entries/year).

## Critical Bugs Fixed

### Upload Data Loss (Feb 28, 2026)
- **Bug**: Uploading with date range Jan 27-Feb 26 deleted ALL records in that range, even if file only had some dates
- **Fix**: Delete only targets dates present in the new file via `$in` query

### Undo Upload Restore (Feb 28, 2026)
- **Bug**: Undoing a replacing upload permanently lost the original data
- **Fix**: Backup replaced records in `replaced_records` collection, restore on undo

### to_list(10000) Truncation (Feb 27, 2026)
- **Bug**: MongoDB queries capped at 10,000 records. 10,500+ sale records were silently truncated (~80 kg missing)
- **Fix**: All queries now use to_list(None) — no limit

### Date Parsing (Feb 23, 2026)
- **Bug**: `pd.to_datetime('YYYY-MM-DD', dayfirst=True)` swapped month/day for ISO dates
- **Fix**: Detect ISO format, skip dayfirst. Migration corrected 2,037 records.

### Memory (Feb 27, 2026)
- **Bug**: `helpers.py` top-level `import pandas` loaded 150MB on startup
- **Fix**: Lazy import, `_is_na()` replaces `pd.isna()`. Startup: 26MB

### Branch Transfer Delete (Feb 27, 2026)
- **Bug**: Re-upload used type `branch_transfer` but stored types are `issue`/`receive`
- **Fix**: Delete correctly targets `['issue', 'receive']`

## Backlog
- (P1) Refactor server.py into proper FastAPI modules
- (P2) Upload validation preview (record count + weight totals before confirming)
- (P2) Item mapping cleanup tooling after master stock re-uploads
