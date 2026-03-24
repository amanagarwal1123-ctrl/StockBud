# StockBud PRD

## Original Problem Statement
StockBud is an intelligent inventory management system for jewelry businesses.

## Core Inventory Logic
- **Book Stock**: Opening Stock + Purchases - Sales +/- Branch Transfers +/- Polythene
- **Physical Stock Baseline**: When physical stock is approved, it becomes the new starting point. Current Stock = Baseline + Post-Baseline Transactions.
- **Reverse**: Undoing a session removes the baseline and reverts to book calculation.

## Unified Stock Computation (Mar 20, 2026)
All stock-dependent features use `get_current_inventory(as_of_date)` as the single source of truth.

## Member-Level Baselines (FIXED Mar 24, 2026)
### The Bug
Merged group members into one baseline at the leader level, causing negative stock for members (TULSI 70 BELT: -4.644 kg).
### The Fix
1. `_flat_base_from_inventory()` decomposes groups into member-level entries
2. Upload-preview shows members as separate rows (no merging)
3. Each approved member gets its own baseline
4. Admin fix endpoint: `POST /api/physical-stock/fix-group-baselines` splits existing leader-level baselines

## Key Endpoints
- `POST /api/physical-stock/upload-preview` — member-level comparison
- `POST /api/physical-stock/apply-updates` — member-level baselines
- `POST /api/physical-stock/fix-group-baselines` — splits existing group baselines (admin only)
- `GET /api/physical-stock/compare` — member-level comparison
- `GET /api/inventory/current` — baseline-aware, group member breakdowns
- `GET /api/manager/approval-details/{stamp}` — baseline-aware stamp book values

## Backlog
- P1: User to run fix-group-baselines on production after deploy
- P1: Refactor server.py into proper FastAPI structure
- P2: Mobile responsiveness
