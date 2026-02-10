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
  server.py            -> Main entry point with route handlers (~3500 lines)
  database.py          -> Shared MongoDB connection
  auth.py              -> JWT auth helpers
  models.py            -> All Pydantic models
  services/
    helpers.py         -> Shared helpers (normalize_stamp, save_action, etc.)
    stock_service.py   -> get_current_inventory() - single source of truth
```

## Core Features (Implemented)
- Multi-user roles: Admin, Manager, SEE, PEE with JWT authentication
- Excel file uploads: purchases, sales, issues/receives, master stock, physical stock
- Item name mapping (transaction names -> master names)
- Stamp management with ALL CAPS auto-normalization on every upload
- Current Stock page with real-time inventory calculation
- Physical vs Book comparison with stamp verification + cancel capability
- Profit Analysis, Party Analytics, Purchase Rates
- Polythene weight adjustments
- Manager approval workflow for stock entries
- Activity log, notifications (in-app + browser push)
- CSV export, mobile-responsive UI
- 3-decimal rounding for all silver weights

## Navigation Structure (Grouped - Feb 10, 2026)
- **Main:** Dashboard, Notifications
- **Inventory:** Upload Files, Historical Upload, Current Stock, Item Mapping, Manage Mappings, Purchase Rates, Polythene Mgmt
- **Verification:** Physical vs Book, Approvals, Stamp Mgmt, Stamp Assign
- **Analytics & AI:** Visualization, Item Buffers, Orders, Party Analytics, Profit Analysis
- **Admin:** User Mgmt, History, Activity Log

## Smart Inventory Management
- Item Categorization into 5 movement tiers (numpy percentiles)
- Buffer Calculation with seasonal adjustments
- Stock Alert System with browser notifications
- Stamp-User Assignments for notification routing

## AI Seasonal Analysis (Hindu Calendar)
- Historical Data Upload (separate collection, doesn't affect stock)
- Analyzes by festivals: Sankrant, Holi, Akshaya Tritiya, Salakh/Wedding Season, Karva Chauth, Dhanteras/Diwali
- Seasonal boost calculations per item
- Claude AI-powered insights and ordering recommendations
- Seasonal buffer updates

## Stamp Verification System
- Quick stamp verification in Physical vs Book page
- Save verification records to DB
- Verification history with cancel/delete for admin/manager
- Dashboard shows verification status per stamp
- Auto-normalizes stamp names on save

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Key API Endpoints
- `/api/inventory/current` (GET) - Authoritative inventory calculation
- `/api/inventory/stamp-breakdown/{stamp}` (GET) - Per-stamp details (uses same source)
- `/api/stamp-verification/save` (POST) - Save verification
- `/api/stamp-verification/all` (GET) - All saved verifications
- `/api/stamp-verification/{stamp}/{date}` (DELETE) - Cancel verification
- `/api/historical/upload` (POST) - Upload historical data for AI
- `/api/ai/seasonal-analysis` (POST) - Run seasonal AI analysis
- `/api/manager/approval-details/{stamp}` (GET) - Approval details (includes mapped items)

## Pending Issues
- None critical

## Backlog
- (P1) Full order placement workflow (mark ordered → track → notify admin)
- (P1) Further split server.py into route modules
- (P2) Enhance Item Mapping with similarity suggestions
- (P2) Auto-check stock returns to green after purchase received
