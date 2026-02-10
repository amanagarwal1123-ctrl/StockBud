# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI (modular: server.py + database.py + auth.py + models.py + services/), Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

### Modular Structure
```
backend/
  server.py            -> Main entry + route handlers
  database.py          -> Shared MongoDB connection
  auth.py              -> JWT auth helpers
  models.py            -> All Pydantic models
  services/
    helpers.py         -> Shared helpers (normalize_stamp, save_action, etc.)
    stock_service.py   -> get_current_inventory() - single source of truth
```

## Navigation Structure (Grouped Sidebar)
- **Main:** Dashboard, Notifications
- **Inventory:** Upload Files, Historical Upload, Current Stock, Item Mapping, Manage Mappings, Purchase Rates, Polythene Mgmt
- **Verification:** Physical vs Book, Approvals, Stamp Mgmt, Stamp Assign
- **Analytics & AI:** Visualization, Item Buffers, Orders, Party Analytics, Profit Analysis
- **Admin:** User Mgmt, History, Activity Log

## Core Features (All Implemented)
- Multi-user roles: Admin, Manager, SEE, PEE with JWT authentication
- Excel file uploads with auto stamp normalization
- Item name mapping, Stamp management (ALL CAPS auto-normalize)
- Current Stock (single source of truth), Physical vs Book comparison
- Stamp verification with save/cancel history
- Profit Analysis, Party Analytics, Purchase Rates
- Polythene weight adjustments
- Manager approval workflow (includes mapped items)
- Notifications (in-app + browser push, 60s polling)
- Selective data reset, CSV export, mobile-responsive UI

## Large File Upload - Chunked Upload (Feb 10, 2026)
- **Problem**: 205K row Excel files (24MB) fail in deployed environment due to proxy body size limits
- **Solution**: Automatic chunked upload for files > 4MB
  - Frontend splits file into 4MB binary chunks
  - 3-step API: `/api/upload/init` -> `/api/upload/chunk/{id}` -> `/api/upload/finalize/{id}`
  - Backend reassembles chunks and processes with EXACT same parse_excel_file logic
  - Progress indicator shows chunk-by-chunk progress
- **Optimized parsing**: Single Excel read, dict-based iteration, batch MongoDB inserts (5K chunks), thread pool

## Date-Based Stock Entry Model (Feb 10, 2026)
- **Problem**: Approved stamps blocked new stock entries. Old approach: single entry per stamp, approval blocks re-submission
- **New Model**:
  - Entries keyed by `{stamp, entered_by, entry_day}` (YYYY-MM-DD)
  - Same stamp + same day = UPDATE existing (overwrite values, reset to pending)
  - Different day = INSERT new entry (old entries locked/historical)
  - Approved entries from previous days remain untouched forever
  - `stamp_approvals` includes `approval_day` to track per-day approval
  - `my-entries` returns latest entry per stamp (deduped)
  - Frontend shows date label and "Re-submit" button for approved entries

## Order Management (Full Workflow)
- Quick Order from Alerts, Create/Track Orders
- Mark as Received, Cancel Orders, Overdue Detection
- Status Filter: All/Pending/Received views

## AI Seasonal Analysis (Hindu Calendar) - PLACEHOLDER
- Historical Data Upload page exists
- Festival Analysis endpoint is a stub
- Core LLM logic NOT yet implemented

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Backlog
- (P1) Complete Browser Notifications integration (trigger on new alerts)
- (P1) Further split server.py into route modules
- (P2) Implement Core AI Seasonal Analysis Logic
- (P2) Enhance Item Mapping with similarity suggestions
- (P2) Auto-check stock returns to green after purchase received
