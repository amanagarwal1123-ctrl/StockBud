# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI (modular: server.py + database.py + auth.py + models.py + services/), Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

### Modular Structure (Feb 10, 2026)
```
backend/
  server.py            -> Main entry point with all route handlers
  database.py          -> Shared MongoDB connection (db, client)
  auth.py              -> JWT auth helpers (get_current_user, verify_password, create_access_token)
  models.py            -> All Pydantic models (Transaction, OpeningStock, etc.)
  services/
    helpers.py         -> Shared helpers (normalize_stamp, save_action, auto_normalize_stamps, stamp_sort_key)
    stock_service.py   -> get_current_inventory() calculation
  routes/              -> Future: split route handlers into modules
```

## Core Features (Implemented)
- Multi-user roles: Admin, Manager, SEE, PEE with JWT authentication
- Excel file uploads: purchases, sales, issues/receives, master stock, physical stock
- Item name mapping (transaction names -> master names)
- Stamp management with ALL CAPS normalization
- Current Stock page with real-time inventory calculation
- Physical vs Book comparison
- Profit Analysis (silver + labour profit)
- Party Analytics (customer/supplier analysis)
- Purchase Rates ledger
- Polythene weight adjustments
- Manager approval workflow for stock entries
- Activity log and notifications
- CSV export, mobile-responsive UI
- 3-decimal rounding for all silver weights

## Smart Inventory Management (Phase 1 - Complete)
- **Item Categorization**: Auto-categorizes items into 5 movement tiers using numpy percentiles
- **Buffer Calculation**: Auto-calculates upper/lower buffers per tier
- **Item Buffer Page**: Shows all items with tier badge, velocity, editable minimum stock
- **Stock Alert System**: Generates notifications for stock deficits/excess
- **Stamp-User Assignments**: Configurable stamp-to-user assignment for notifications

## Data Visualization & AI (Phase 3 - Complete)
- **Visualization Tab**: 6 sub-tabs (Sales, Purchases, Stock Health, Seasonal, Historical, Smart AI)
- **AI Smart Analytics**: Claude Opus 4.6 powered insights via Emergent LLM key
- **Selective Reset**: Checklist-based reset

## Bug Fixes (Feb 10, 2026)
- **Stamp normalization**: normalize_all_stamps now updates ALL 7 collections (master_items, transactions, opening_stock, stock_entries, stamp_approvals, stamp_verifications, physical_inventory)
- **Dashboard verification**: stamp-verification/history now reads from BOTH stamp_verifications AND stamp_approvals
- **Stamp sort**: Fixed numeric sort key for stamps (Stamp 1, 2, 3...10 instead of 1, 10, 11, 2)
- **Auto-normalize**: Stamps auto-normalized after every upload (opening_stock, transactions, physical_stock, master_stock)
- **Dead code cleanup**: Removed ~550 lines of orphaned/duplicate code

## New Features (Feb 10, 2026)

### Browser Notifications
- Web Notification API integrated in AuthContext.jsx
- Permission requested on login
- Polls every 60 seconds for new notifications
- Shows browser toast for new stock alerts

### Historical Data Upload (AI Training)
- Separate upload endpoint: POST /api/historical/upload
- Stores in `historical_transactions` collection (does NOT affect current stock)
- Upload previous years' sales/purchase files for AI seasonal analysis
- Year selection, type selection, delete functionality
- Summary view of uploaded historical data

### AI Seasonal Analysis with Hindu Calendar
- POST /api/ai/seasonal-analysis
- Analyzes sales patterns by Hindu calendar festivals:
  - Makar Sankranti (Jan), Holi (Mar), Akshaya Tritiya (Apr-May)
  - Wedding Season/Salakh (Apr-Jun, Nov-Dec)
  - Karva Chauth (Oct), Dhanteras/Diwali (Oct-Nov)
- Combines current + historical transactions
- Calculates seasonal boost per item
- Generates ordering recommendations with urgency levels
- Claude AI provides festival-aware insights
- POST /api/ai/update-buffers-seasonal updates item buffers with seasonal adjustments

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Key API Endpoints
- `/api/historical/upload` (POST) - Upload historical data for AI training
- `/api/historical/summary` (GET) - Summary of historical data
- `/api/ai/seasonal-analysis` (POST) - Run seasonal AI analysis
- `/api/ai/update-buffers-seasonal` (POST) - Update buffers with seasonal data
- `/api/stamp-verification/history` (GET) - Dashboard stamp verification
- `/api/admin/normalize-stamps` (POST) - Normalize all stamps
- `/api/inventory/current` (GET) - Current inventory calculation

## Pending Issues
- (P1) Re-verify profit analysis calculation logic
- (P2) Full order placement workflow (mark as ordered, track pending, notify admin on delay)

## Backlog
- (P1) Further split server.py routes into separate route files (routes/auth.py, routes/uploads.py, etc.)
- (P1) Enhance Item Mapping with similarity-based suggestions
- (P2) Auto-check stock returns to green band after purchase received
- (P2) Implement perpetual admin login (frontend session persistence)

## Important Notes
- Opening stock import is correct (9365.543 gross, 7790.799 net kg)
- ALL CAPS stamp normalization auto-applied on every upload
- AI insights require Emergent LLM key balance
- Historical data upload is SEPARATE from regular transactions
