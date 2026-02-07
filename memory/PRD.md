# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI (monolithic server.py ~2900 lines), Motor (async MongoDB), JWT auth
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

## Core Features (Implemented)
- Multi-user roles: Admin, Manager, SEE, PEE with JWT authentication
- Excel file uploads: purchases, sales, issues/receives, master stock, physical stock
- Item name mapping (transaction names → master names)
- Stamp management with ALL CAPS normalization
- Current Stock page with real-time inventory calculation
- Physical vs Book comparison
- Profit Analysis (silver + labour profit)
- Party Analytics (customer/supplier analysis)
- Purchase Rates ledger
- Polythene weight adjustments
- Manager approval workflow for stock entries
- Activity log and notifications
- CSV export
- Mobile-responsive UI

## What's Been Implemented (Latest Session - Feb 7, 2026)
- **3-Decimal Rounding:** All silver weight values (gross, net, fine, labor) now display with 3 decimal places across the entire app
  - Frontend: Updated CurrentStock, BookInventory, InventoryMatching, Analytics pages
  - Backend: Added round(value, 3) to inventory items, totals, stamp breakdown, party analysis, customer profit endpoints
- **Selective Reset Data:** Replaced old "nuke everything" reset with a checklist dialog
  - Categories: Sales, Purchases, Issue/Receive, Polythene, Item Mappings, Physical Stock, Purchase Ledger, Notifications & Logs, Action History
  - Select All / individual toggle, password-protected ("CLOSE")
  - Master stock & users are never deleted
- **Bug Fix:** Clear Transactions endpoint no longer incorrectly deletes opening stock

## Pending Issues
- **Issue 1 (P1):** Re-verify profit analysis calculation logic for correctness
- **Issue 2 (P2):** Implement perpetual admin login (frontend session persistence)

## Backlog
- (P0) Refactor server.py into modular structure (routers/, models/, services/)
- (P1) Enhance Item Mapping with similarity-based suggestions

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Important Notes
- Opening stock import is correct (9365.543 gross, 7790.799 net kg)
- Current Stock page shows inventory after transactions (opening ± purchases/sales/issues)
- ALL CAPS stamp normalization must be applied post-deployment via "Normalize Stamps" button
