# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI (modular: server.py + database.py + auth.py + models.py + services/), Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

## Core Features (All Implemented)
- Multi-user roles, JWT auth, Excel uploads with auto stamp normalization
- Current Stock, Physical vs Book comparison, Stamp verification
- Profit Analysis, Party Analytics, Purchase Rates, Polythene Mgmt
- Manager approval workflow, Notifications, CSV export

## Chunked Upload (Feb 10, 2026)
- Auto chunked for files > 4MB on BOTH Upload Files and Historical Upload pages
- 3-step API: init -> chunk -> finalize
- Supports: sale, purchase, branch_transfer, opening_stock, physical_stock, historical_sale, historical_purchase

## Date-Based Stock Entry Model (Feb 10, 2026)
- Entries keyed by {stamp, entered_by, entry_day}
- Same day = update, different day = new entry, old approvals untouched

## Approval View Details Fix (Feb 10, 2026)
- View Details works for approved stamps (was missing details panel)
- Rejection requires message (textarea inside details panel)

## Historical Summary Fix (Feb 10, 2026)
- Summary aggregation groups sale+sale_return as "sale", purchase+purchase_return as "purchase"
- Previously purchase entries were invisible due to type mismatch

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
