# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses. It provides real-time stock tracking, profit analysis, seasonal ordering, physical vs book stock comparison, multi-role access control, and AI-powered insights.

## Core Requirements
1. Excel-based data upload (opening stock, purchase/sale ledgers)
2. Real-time inventory calculation (Opening + Purchases - Sales)
3. Physical vs Book stock comparison with date-scoped operations
4. Profit analysis (silver + labour)
5. Item mapping and grouping
6. Seasonal buffer management with Indian festival awareness
7. Order management with deficit alerts
8. Multi-role access (Admin, Manager, Executive, Polythene Executive)
9. AI-powered insights via Claude/Emergent LLM
10. Data visualization and party analytics

## What's Been Implemented

### Session 1-N (Previous sessions)
- Full application built with all core features
- Security hardening (Codex recommendations)
- Bug fixes (role-based deletion, file upload UX, deployment, item grouping)
- Physical stock partial update with date-scoping, stamp-aware matching & ambiguity detection
- Serialized upload queue

### Current Session (Mar 18, 2026)
- **Dashboard Redesign**: Removed "Software Capabilities" section, added transaction date range (DD/MM/YYYY), redesigned with tech-savvy stat cards with color-coded borders
- **API Enhancement**: `/api/stats` now returns `date_range` (from_date, to_date) and `total_items`
- **PDF Manuals**: Generated static English and Hindi user manuals with annotated screenshots (arrows pointing to UI elements), ordered from least to most complex features. Stored at `/manuals/StockBud_Manual_EN.pdf` and `/manuals/StockBud_Manual_HI.pdf`
- **Bug Fix**: Fixed `useMemo` → `useEffect` in `PhysicalStockPreview.jsx` for proper React side-effect handling

## Architecture
- Frontend: React + Tailwind + Shadcn/UI
- Backend: FastAPI (Python) - monolithic `server.py`
- Database: MongoDB
- Auth: JWT (18-hour expiry)
- AI: Claude via Emergent LLM integration

## Prioritized Backlog

### P1 - High Priority
- Refactor `server.py` into proper FastAPI structure (routers, services, models)

### P2 - Medium Priority
- Review skipped Codex issues (RBAC on GET endpoints, history/undo behavior, dedup with empty stamps)
- Clean up older test files (pre-existing failures)

### P3 - Low Priority
- Additional data visualization features
- Mobile responsiveness improvements

## Key Files
- `backend/server.py` - Monolithic backend (needs refactoring)
- `frontend/src/pages/Dashboard.jsx` - Redesigned dashboard
- `frontend/src/components/PhysicalStockPreview.jsx` - Stock preview modal
- `frontend/src/context/UploadContext.jsx` - Serialized upload queue
- `frontend/public/manuals/` - Static PDF manuals
- `backend/generate_manuals.py` - PDF generation script

## Test Reports
- `/app/test_reports/iteration_21.json` - Latest (all passed)
- `/app/backend/tests/test_dashboard_features.py`
- `/app/backend/tests/test_physical_stock.py`
- `/app/backend/tests/test_upload_flows.py`
