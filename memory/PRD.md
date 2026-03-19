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

### Previous Sessions
- Full application built with all core features
- Security hardening (Codex recommendations)
- Bug fixes (role-based deletion, file upload UX, deployment, item grouping)
- Physical stock partial update with date-scoping, stamp-aware matching & ambiguity detection
- Serialized upload queue

### Current Session (Mar 18, 2026)
**Dashboard Redesign:**
- Removed "Software Capabilities" section, added transaction date range (DD/MM/YYYY)
- Redesigned stat cards with color-coded borders and gradient backgrounds
- `/api/stats` now returns `date_range` (from_date, to_date) and `total_items`

**PDF Manuals:**
- Generated bilingual (EN + HI) static user manuals with annotated screenshots
- Stored at `/manuals/StockBud_Manual_EN.pdf` and `/manuals/StockBud_Manual_HI.pdf`

**Bug Fix:** Fixed `useMemo` → `useEffect` in `PhysicalStockPreview.jsx`

**Codex Patches (6 fixes):**
1. **Physical stock direct-only**: `/api/upload/init` returns 400 for `physical_stock`. Frontend already excluded it from chunked path. Backend now explicitly blocks it.
2. **Physical vs Book always date-scoped**: New `GET /api/physical-stock/dates` endpoint. Compare now requires `verification_date` (not optional). Frontend fetches dates on mount, auto-selects latest, uses Select dropdown.
3. **Fix false success in apply flow**: `handleApproveSingle` and `handleApproveAll` now inspect per-row backend results. Only marks rows approved if backend says `applied`. Shows warning for partial, error for zero-updated.
4. **Preserved existing behavior**: All date-scoped upload/preview/apply still work.
5. **Non-physical uploads unaffected**: Purchase, sale, branch transfer, etc. still use chunked path.
6. **Cleanup**: Apply response now includes `skipped_count`. Result banner is typed (success/warning/error).

**Incremental Physical Stock Upload (Bug Fix):**
- Removed requirement that a full physical stock snapshot must exist before partial uploads
- When no physical stock exists for a date, preview now matches items against **book stock** (current inventory) to show meaningful old values
- Apply endpoint can now INSERT new physical stock records (not just update existing ones) when item exists in book stock
- Stamp info is auto-resolved from book stock for new inserts
- Items not found in book stock OR physical stock are still properly skipped

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
- `backend/server.py` - Monolithic backend
- `frontend/src/pages/Dashboard.jsx` - Dashboard with date range + manual downloads
- `frontend/src/components/PhysicalStockPreview.jsx` - Stock preview with accurate apply handling
- `frontend/src/pages/PhysicalStockComparison.jsx` - Date-required comparison page
- `frontend/src/context/UploadContext.jsx` - Serialized upload queue (physical_stock direct-only)
- `frontend/public/manuals/` - Static PDF manuals
- `backend/generate_manuals.py` - PDF generation script

## Test Reports
- `/app/test_reports/iteration_22.json` - Latest (all passed, 15 backend + all frontend)
- `/app/backend/tests/test_codex_fixes.py` - 10 tests for Codex patches
- `/app/backend/tests/test_codex_physical_stock_v22.py` - Additional testing agent tests
- `/app/backend/tests/test_physical_stock.py` - Date-scoped physical stock tests
- `/app/backend/tests/test_upload_flows.py` - Upload flow tests
- `/app/backend/tests/test_dashboard_features.py` - Dashboard tests

## Key API Endpoints (Physical Stock)
- `POST /api/upload/init` - Returns 400 for physical_stock (direct-only)
- `GET /api/physical-stock/dates` - Returns distinct dates sorted descending
- `GET /api/physical-stock/compare?verification_date=X` - Required param, date-scoped
- `POST /api/physical-stock/upload` - Direct full upload, date-scoped
- `POST /api/physical-stock/upload-preview` - Preview with stamp-aware matching
- `POST /api/physical-stock/apply-updates` - Returns updated_count, skipped_count, per-row results
