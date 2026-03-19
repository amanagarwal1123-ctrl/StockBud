# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Current Session (Mar 19, 2026) — Session Lifecycle, Reverse, UI Clarity

### 1. One Upload = One Session
- Preview creates a draft session with `preview_session_id`
- Apply updates the SAME session (no new session per click)
- Approve-single then approve-all stays in one session
- Session tracks full row list: applied, rejected, unmatched, skipped, pending

### 2. Session Finalization
- Modal close triggers finalize: remaining pending rows → rejected
- Zero-applied sessions → abandoned (hidden from history)
- `POST /api/physical-stock/finalize-session`

### 3. Reverse/Undo
- `POST /api/physical-stock/update-history/{session_id}/reverse`
- Only latest unreversed session per date can be reversed
- Restores old weights for applied rows
- Marks session as reversed

### 4. UI Clarity
- Blue "Preview only" info banner before any approval
- Session history shows: status counts, gross/net deltas, reverse button
- Detail view shows per-row status (applied/rejected/unmatched/skipped)

### 5. Session History Model
Collection: `physical_stock_update_sessions`
Fields: session_id, verification_date, session_state (draft/finalized/reversed/abandoned),
created_at, applied_at, applied_by, reversed_at, reversed_by, is_reversed,
uploaded_count, applied_count, rejected_count, unmatched_count, skipped_count,
totals (old/new/delta for gr/net), items (full row list sorted by stamp+name)

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — returns preview_session_id
- `POST /api/physical-stock/apply-updates` — requires preview_session_id
- `POST /api/physical-stock/finalize-session` — finalize draft
- `POST /api/physical-stock/update-history/{id}/reverse` — reverse latest
- `GET /api/physical-stock/update-history` — filtered, reversible flag
- `GET /api/physical-stock/update-history/{id}` — full details

## Files Changed
- `backend/server.py` — preview, apply, finalize, reverse, history endpoints
- `backend/services/stock_service.py` — date-scoped helpers (unchanged this session)
- `frontend/src/components/PhysicalStockPreview.jsx` — session lifecycle, info banner
- `frontend/src/pages/PhysicalStockComparison.jsx` — session history UI, reverse button

## Tests
- 36/36 existing backend tests pass
- Live smoke: preview→approve→finalize→history→reverse all working
- 3/3 rejected-row-weight tests pass (test_rejected_row_weights.py)

## Bug Fix: Rejected Rows Stored Wrong Final Weights (Feb 2026)
- **Root cause**: Draft init set `final_gr_wt = proposed_gr_wt` for pending rows; finalization only flipped status to `rejected` without resetting weights
- **Fix 1** (line ~2459): Draft init now sets `final_gr_wt = old_gr_wt`, `gr_delta = 0` for pending rows
- **Fix 2** (line ~2650): Finalization resets rejected rows: `final_*` → `old_*`, deltas → 0

## Backlog
- P1: Refactor server.py into proper FastAPI structure
- P2: Fix pre-existing dashboard test file
