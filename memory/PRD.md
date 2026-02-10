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
- Auto chunked upload for files > 4MB (4MB binary chunks)
- 3-step API: init -> chunk -> finalize with same parse_excel_file logic
- Optimized: single Excel read, dict iteration, batch MongoDB inserts, thread pool

## Date-Based Stock Entry Model (Feb 10, 2026)
- Entries keyed by {stamp, entered_by, entry_day}
- Same stamp + same day = UPDATE (overwrite, reset to pending)
- Different day = INSERT new (old entries locked/historical)
- Approved entries from previous days remain untouched
- stamp_approvals includes approval_day for per-day tracking
- my-entries returns latest per stamp (deduped)
- Frontend: date label, Re-submit for approved entries

## Approval View Details & Rejection Fix (Feb 10, 2026)
- Approved stamps now show full "View Details" panel with comparison table
- Rejection message textarea inside details panel (required for rejection)
- Reject button placed alongside the message input

## Order Management (Full Workflow)
- Quick Order from Alerts, Create/Track Orders
- Mark as Received, Cancel Orders, Overdue Detection

## AI Seasonal Analysis (Hindu Calendar) - PLACEHOLDER
- Historical Data Upload page exists, core LLM logic NOT implemented

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Backlog
- (P1) Complete Browser Notifications integration
- (P1) Further split server.py into route modules
- (P2) Implement Core AI Seasonal Analysis Logic
- (P2) Enhance Item Mapping with similarity suggestions
- (P2) Auto-check stock returns to green after purchase received
