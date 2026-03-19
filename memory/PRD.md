# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses with real-time stock tracking, profit analysis, seasonal ordering, physical vs book stock comparison, multi-role access, and AI insights.

## What's Been Implemented (Current Session - Mar 19, 2026)

### Date-Scoped Book Closing Stock
- New `get_book_closing_stock_as_of_date(date)` in stock_service.py
- Computes: Opening Stock + Purchases(<=date) - Sales(<=date) +/- Branch Transfers +/- Polythene
- Respects mappings, grouping, negative items
- Tags items as `is_negative_grouped` for special handling

### Effective Base Resolution
- New `get_effective_physical_base_for_date(date)` helper
- If physical stock snapshot exists for date → use it
- Else → compute book closing stock for that date
- Enables chaining: 2nd upload sees 1st upload's changes

### Rewritten Physical Stock Preview
- Uses effective base (not today's inventory)
- Grouped/negative items: always preserve net weight
- Normal items, gross_only: preserve net
- Normal items, gross+net: update both
- No pre-existing snapshot required

### Rewritten Physical Stock Apply
- First apply for a date: materializes FULL snapshot from book closing stock (279+ items)
- Then overlays approved changes
- Non-uploaded items remain unchanged
- Future uploads chain correctly against updated snapshot
- Net-weight rules enforced (grouped/negative always preserve)

### Session History
- New `physical_stock_update_sessions` collection
- Stores: session_id, verification_date, applied_by, applied_at, totals, sorted item rows
- Items tagged with is_negative_grouped, sorted by stamp then name
- New endpoints: GET /physical-stock/update-history, GET /physical-stock/update-history/{id}
- UI section in Physical vs Book page (expandable session cards)

### Compare Uses Date-Scoped Book Stock
- `GET /physical-stock/compare` now compares against `get_book_closing_stock_as_of_date(date)`, not today's inventory

## Architecture
- Frontend: React + Tailwind + Shadcn/UI
- Backend: FastAPI (Python) - monolithic server.py
- Database: MongoDB
- Auth: JWT (18-hour expiry)

## Key Files Changed
- `backend/services/stock_service.py` — New functions: get_book_closing_stock_as_of_date, get_effective_physical_base_for_date
- `backend/server.py` — Rewritten preview, apply, compare endpoints; new session history endpoints
- `frontend/src/components/PhysicalStockPreview.jsx` — Passes is_negative_grouped to apply
- `frontend/src/pages/PhysicalStockComparison.jsx` — Session history UI section

## Prioritized Backlog
### P1
- Refactor server.py into proper FastAPI structure (routers/services/models)
### P2
- Review remaining Codex issues (RBAC on GETs)
- Fix pre-existing test file bugs (dashboard_features.py BASE_URL)
