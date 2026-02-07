# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI (monolithic server.py ~3500 lines), Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

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

## New Features (Feb 7, 2026)

### Phase 1: Smart Inventory Management
- **Item Categorization**: Auto-categorizes items into 5 movement tiers (fastest/fast/medium/slow/dead) based on sales velocity using numpy percentiles
- **Buffer Calculation**: Auto-calculates upper/lower buffers per tier (e.g., fastest: 2-week lower, 6-week upper)
- **Item Buffer Page**: Shows all items with tier badge, velocity, current stock, editable minimum stock, color-coded status (red=below min, green=healthy, yellow=overstocked)
- **Stock Alert System**: Generates notifications for stock deficits/excess, routes to stamp-assigned users
- **Stamp-User Assignments**: Configurable page to assign users to stamps for notification routing

### Phase 2: Order Management
- **Order Creation**: Create restock orders with item, quantity, supplier, notes
- **Order Tracking**: Track order status (ordered/received) with verification
- **Stock Deficit Alerts**: Shows orderable quantity range on orders page

### Phase 3: Data Visualization & AI Analytics
- **Visualization Tab**: 4 sub-tabs (Sales, Purchases, Stock Health, Smart AI)
  - Sales: Top items by weight (color-coded by tier), sales by customer, monthly trend
  - Purchases: Purchases by supplier
  - Stock Health: Tier distribution pie chart, stock health progress bars
- **AI Smart Analytics**: Claude Opus 4.6 powered insights via Emergent LLM key
- **Selective Reset**: Checklist-based reset (sales, purchases, issues, polythene, mappings, etc.)

### Auto-Refresh Stock Alerts (Feb 7, 2026)
- Backend `/api/stock-alerts/auto` — lightweight auto-check, throttled to every 30 min
- Executive Stock Entry page: red stock deficit alerts with pulsing indicators, order ranges, auto-polls every 5 min
- Notifications page: 5 category tabs (Stock, Orders, Stamps, Polythene, General), auto-refresh every 60s
- Alerts route to stamp-assigned users; unassigned default to admin; critical also notify admin

## Key Credentials
- Admin: admin / admin123
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123
- PEE: PEE1 / poly123

## Pending Issues
- (P1) Re-verify profit analysis calculation logic
- (P2) Implement perpetual admin login (frontend session persistence)

## Backlog
- (P0) Refactor server.py into modular structure (routers/, models/, services/)
- (P1) Enhance Item Mapping with similarity-based suggestions
- (P1) Unverified order notifications to admin after timeout
- (P2) Auto-check stock returns to green band after purchase received

## Important Notes
- Opening stock import is correct (9365.543 gross, 7790.799 net kg)
- ALL CAPS stamp normalization must be applied post-deployment via "Normalize Stamps" button
- AI insights require Emergent LLM key balance
