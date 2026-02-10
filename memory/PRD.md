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

## Large File Upload Optimization (Feb 10, 2026)
- **Single Excel read**: `_read_excel_once()` detects headers and reads file in one pass (no double read)
- **Fast dict-based parsing**: Replaced `iterrows()` with `to_dict('records')` + dict iteration (~5x faster)
- **Column pre-resolution**: `_resolve_col()` finds column names once, not per-row
- **Batch MongoDB inserts**: `batch_insert()` inserts in chunks of 5000 (handles 200K+ records)
- **Skip per-row Pydantic**: `_prepare_transactions()` applies defaults without model validation
- **Thread pool parsing**: CPU-bound Excel parsing runs in `ThreadPoolExecutor` to not block async loop
- **Frontend timeout**: 10-minute timeout on axios upload with progress indicator
- **Performance**: 100K records upload in ~20s, estimated 205K in ~45s

## Order Management (Full Workflow - Feb 10, 2026)
- **Quick Order from Alerts**: One-click "Order" button on stock deficit notifications
- **Create/Track Orders**: Item, quantity, supplier, notes
- **Mark as Received**: Updates status, notifies admin
- **Cancel Orders**: Admin/Manager can cancel pending orders
- **Overdue Detection**: Orders >7 days old flagged as overdue, admin notified
- **Status Filter**: All/Pending/Received views

## AI Seasonal Analysis (Hindu Calendar)
- **Historical Data Upload**: Dedicated page, separate collection (doesn't affect stock)
- **Festival Analysis**: Sankrant, Holi, Akshaya Tritiya, Salakh, Karva Chauth, Dhanteras/Diwali
- **Seasonal Ordering Recommendations**: Boost-adjusted demand forecasts
- **Claude AI Insights**: Festival-aware analysis and recommendations

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
