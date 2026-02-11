# StockBud - Product Requirements Document

## Problem Statement
Silver wholesale inventory management software. Calculates "book inventory" by processing sales, purchase, and branch transfer Excel files, comparing against a "physical inventory" file.

## Architecture
- **Backend:** FastAPI, Motor (async MongoDB), JWT auth, emergentintegrations (Claude AI)
- **Frontend:** React, TailwindCSS, shadcn/ui, Recharts, Axios
- **Database:** MongoDB (test_database)

## Data Architecture
- `transactions` collection: Current operational data (daily sales, purchases, branch transfers) — used for dashboard stats, profit calculations, inventory
- `historical_transactions` collection: Historical data for analytics, seasonal patterns, buffer calculations — does NOT affect dashboard or profit
- Upload Files page → `transactions` (current operations)
- Historical Upload page → `historical_transactions` (analytics only)

## Chunked Upload with MongoDB Storage (Feb 11, 2026)
- Files >768KB auto-chunked into 768KB binary chunks (safe for deployment proxy limits)
- 3-step API: init -> chunk(s) -> finalize
- **Finalize returns immediately**, processing runs in background via FastAPI BackgroundTasks
- Frontend polls `GET /api/upload/status/{upload_id}` every 5s until complete/error
- Upload metadata and chunks stored in **MongoDB** (`upload_sessions` + `upload_chunks` collections) — works across multiple pods in deployment
- Supports: sale, purchase, branch_transfer, opening_stock, physical_stock, historical_sale, historical_purchase

## Historical Profit Analysis (Feb 11, 2026)
- Endpoint: `GET /api/analytics/historical-profit?year=2025&view={yearly|customer|supplier|item|month}`
- Views: Yearly summary (6 KPI cards), Customer-wise (chart + table), Supplier-wise, Item-wise (with tunch comparison), Month-wise (bar + line charts)
- Frontend: New "Profit" tab in Data Visualization page with year/view selectors, charts, sortable/searchable/paginated tables
- Uses only `historical_transactions` — zero impact on current operations

## Historical Summary Fix (Feb 11, 2026)  
- Aggregation groups sale+sale_return as "sale", purchase+purchase_return as "purchase"

## Date-Based Stock Entry Model (Feb 10, 2026)
- Entries keyed by {stamp, entered_by, entry_day}
- Same day = update, different day = new entry, old approvals untouched

## Key Credentials
- Admin: admin / admin123  
- Manager: SMANAGER / manager123
- SEE: SEE1 / executive123

## Backlog
- (P1) Upload queue UI lock — block concurrent uploads with user-facing message
- (P1) Complete Browser Notifications integration
- (P1) Further split server.py into route modules
- (P2) Implement Core AI Seasonal Analysis Logic
