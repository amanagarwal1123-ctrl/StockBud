# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Core Inventory Logic
- **Book Stock**: Opening Stock + Purchases - Sales +/- Branch Transfers +/- Polythene
- **Physical Stock Baseline**: When physical stock is approved, it becomes the new starting point for that item. Current Stock = Baseline + Post-Baseline Transactions.
- **Reverse**: Undoing a physical stock session removes the baseline and reverts to book calculation.

## Unified Stock Computation (Mar 20, 2026)
All stock-dependent features use `get_current_inventory(as_of_date)` as the single source of truth:
- **Current Stock page**: `get_current_inventory()` (no date filter)
- **Upload Preview base**: `_flat_base_from_inventory(verification_date)` — member-level for groups
- **Compare page**: `_flat_base_from_inventory(verification_date)` — member-level for groups
- **Stamp Approvals**: `get_current_inventory(as_of_date).by_stamp[stamp]`
- **Apply Updates snapshot**: `get_effective_physical_base_for_date(verification_date)`

## Member-Level Baselines (FIXED Mar 24, 2026)
### The Bug
When a physical file had both leader (TULSI 70 -264) and member (TULSI 70 BELT) items:
1. Upload-preview MERGED them into one row under the leader
2. Approval created ONE baseline for the leader with combined weight
3. `get_current_inventory()` attributed all baseline weight to the leader member
4. TULSI 70 BELT got zero baseline → post-baseline sales made it go negative (-4.644 kg)

### The Fix
1. `_flat_base_from_inventory()` now decomposes groups with 2+ members into individual member entries
2. Upload-preview NO LONGER merges group members — each uploaded item stays as its own row
3. Each approved item creates its own baseline at the member level
4. This prevents negative stock for group members after reconciliation

### Impact
- TULSI 70 -264 and TULSI 70 BELT each get their own baseline
- MADRASI YASH -186 and MADRASI YASH SHOLDER -186 are handled separately
- SNT 40-256 and SNT-40 PREMIUM are handled separately

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — member-level comparison, no group merging
- `POST /api/physical-stock/apply-updates` — member-level baselines
- `GET /api/physical-stock/compare` — member-level comparison
- `GET /api/inventory/current` — baseline-aware, group member breakdowns
- `GET /api/manager/approval-details/{stamp}` — baseline-aware stamp book values

## Files Changed (Mar 24, 2026)
- `backend/services/stock_service.py` — `_flat_base_from_inventory()` decomposes groups into members
- `backend/server.py` — upload-preview resolver prefers member-level matching over leader
- `frontend/src/context/AuthContext.jsx` — notification polling reduced to 120s with visibility check

## Tests
- All 5 key endpoints tested and passing
- Upload preview confirmed: 4 separate rows for 4 items (no merging)
- Compare endpoint: correctly shows member-level discrepancies

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P1: User to verify member-level baselines on production
- P2: Mobile responsiveness
