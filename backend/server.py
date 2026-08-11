from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query, Depends, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import re
import gc
import math

# Thread pool for CPU-bound Excel parsing
_parse_executor = ThreadPoolExecutor(max_workers=1)

BATCH_INSERT_SIZE = 2000
STALE_HEARTBEAT_SECONDS = 90
MAX_UPLOAD_ATTEMPTS = 3

from dotenv import load_dotenv
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=False)

# Import shared modules
from database import db, client
from auth import (
    get_current_user, verify_password, get_password_hash,
    create_access_token, security
)
from models import (
    Transaction, OpeningStock, PhysicalStock, MasterItem, ItemMapping,
    PurchaseLedger, User, LoginRequest, CreateUserRequest, Token,
    ActionHistory, ResetRequest, StampAssignment, OrderCreate,
    HistoricalUploadRequest, ItemGroup
)
from services.helpers import (
    normalize_stamp, get_column_value, parse_labor_value,
    normalize_date, stamp_sort_key, save_action, auto_normalize_stamps
)
from services.stock_service import get_current_inventory, get_effective_physical_base_for_date, _flat_base_from_inventory, get_opening_effective_date
from services.group_utils import build_group_maps, build_group_ledger, resolve_to_leader
from services.monthly_summary_service import (
    recompute_monthly_summaries, ensure_year_summary_fresh, get_year_meta
)
from services.profit_helpers import (
    compute_daily_profits, compute_date_profit_detail,
    ledger_cost_basis, aggregate_sale_profit, fetch_ledger_with_fallback,
    invalidate_fallback_cache,
)

# Simple TTL cache for heavy inventory computations
import time

class InventoryCache:
    """In-memory cache with TTL for expensive inventory computations."""
    def __init__(self, ttl_seconds=30):
        self._cache = {}
        self._ttl = ttl_seconds

    def get(self, key):
        entry = self._cache.get(key)
        if entry and (time.time() - entry['ts']) < self._ttl:
            return entry['data']
        if entry:
            del self._cache[key]
        return None

    def set(self, key, data):
        self._cache[key] = {'data': data, 'ts': time.time()}

    def invalidate(self, key=None):
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

_inv_cache = InventoryCache(ttl_seconds=30)
_inv_locks: Dict[str, asyncio.Lock] = {}


async def get_current_inventory_cached(as_of_date: str = None):
    """Cached + deduplicated inventory computation. Concurrent requests for the
    same as_of_date share a single computation (protects small-memory pods)."""
    key = f'current_inventory:{as_of_date or "latest"}'
    cached = _inv_cache.get(key)
    if cached is not None:
        return cached
    lock = _inv_locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _inv_cache.get(key)
        if cached is not None:
            return cached
        result = await get_current_inventory(as_of_date=as_of_date)
        _inv_cache.set(key, result)
        return result


async def _safe_recompute_summaries(year: int = None):
    """Background-safe wrapper around recompute_monthly_summaries.

    Wraps the heavy recompute in try/except + structured logging so failures
    (DB errors, worker restarts, etc.) are visible in supervisor logs instead
    of being swallowed by ``asyncio.create_task``.
    """
    try:
        result = await recompute_monthly_summaries(db, year)
        _log = logging.getLogger(__name__)
        _log.info(f"[monthly_summaries] recomputed: {result}")
    except Exception as e:
        _log = logging.getLogger(__name__)
        _log.error(f"[monthly_summaries] recompute FAILED (year={year}): {e}", exc_info=True)


async def seed_admin():
    """Idempotent admin seed run on startup.

    Guarantees an active 'admin' account always exists in whatever database the deployment
    connects to (covers a fresh / migrated production DB that has no users). It does NOT
    overwrite an existing admin's password, so a custom password set by the user is preserved.
    """
    existing = await db.users.find_one({"username": "admin"})
    if not existing:
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            full_name="System Administrator",
            role="admin",
            created_by="system",
        )
        await db.users.insert_one(admin.model_dump())
        logger.info("[seed] Created default admin user (username=admin)")
    elif not existing.get('is_active', True):
        await db.users.update_one({"username": "admin"}, {"$set": {"is_active": True}})
        logger.info("[seed] Reactivated inactive admin user")


app = FastAPI()

@app.on_event("startup")
async def create_upload_indexes():
    """Create indexes for chunked upload collections and clean stale tasks"""
    await db.upload_sessions.create_index("upload_id", unique=True)
    await db.upload_chunks.create_index([("upload_id", 1), ("chunk_index", 1)], unique=True)
    # Indexes for fast aggregation on historical_transactions (200k+ docs)
    await db.historical_transactions.create_index([("historical_year", 1), ("type", 1)])
    await db.historical_transactions.create_index([("type", 1), ("item_name", 1)])
    await db.historical_transactions.create_index("batch_id")
    await db.transactions.create_index([("type", 1), ("item_name", 1)])

    # Performance indexes for inventory computation (critical at 17K+ transactions)
    await db.transactions.create_index("date")
    await db.transactions.create_index([("date", 1), ("type", 1)])
    await db.inventory_baselines.create_index("item_key")
    await db.inventory_baselines.create_index("baseline_date")
    await db.inventory_baselines.create_index([("item_key", 1), ("baseline_date", -1)])
    await db.physical_stock.create_index("verification_date")
    await db.physical_stock.create_index([("verification_date", 1), ("item_name", 1)])
    await db.stock_entries.create_index([("stamp", 1), ("status", 1)])
    await db.stock_entries.create_index([("stamp", 1), ("entry_day", 1)])
    await db.stock_entries.create_index([("stamp", 1), ("verification_date", 1), ("status", 1)])
    await db.stock_entries.create_index([("entered_by", 1), ("status", 1)])
    await db.stock_entries.create_index("entry_date")
    await db.polythene_adjustments.create_index("date")
    await db.polythene_adjustments.create_index("item_name")
    await db.master_items.create_index("stamp")
    await db.master_items.create_index("item_name", unique=True)
    await db.notifications.create_index([("target_user", 1), ("read", 1)])
    await db.notifications.create_index("timestamp")
    await db.physical_stock_update_sessions.create_index("verification_date")
    await db.activity_log.create_index("timestamp")
    await db.stamp_approvals.create_index([("stamp", 1), ("approval_day", 1)])
    # Monthly summaries indexes for fast queries
    await db.monthly_summaries.create_index([("year", 1), ("month", 1), ("summary_type", 1)])
    await db.monthly_summaries.create_index([("year", 1), ("summary_type", 1), ("name", 1)])
    # Performance index for party/date queries
    await db.transactions.create_index([("date", 1), ("type", 1), ("party_name", 1)])

    # Recover 'processing' upload sessions from a previous run: resume from stored chunks
    # if attempts remain, otherwise roll back partial writes and mark as failed.
    async def _recover_upload_sessions():
        try:
            sessions = await db.upload_sessions.find({"status": "processing"}, {"_id": 0}).to_list(None)
            stale_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=STALE_HEARTBEAT_SECONDS)).isoformat()
            for sess in sessions:
                uid = sess["upload_id"]
                if await _try_resume_upload(uid):
                    continue
                hb = sess.get("heartbeat")
                if not hb or hb < stale_cutoff:
                    await _fail_upload_session(sess, "Server restarted during processing. Please re-upload.")
                    logger.info(f"[Upload {uid}] Marked failed on startup (attempts exhausted or no chunks)")
        except Exception as e:
            logger.error(f"Upload session recovery failed: {e}", exc_info=True)

    await _recover_upload_sessions()

    async def _delayed_upload_recovery():
        await asyncio.sleep(STALE_HEARTBEAT_SECONDS + 30)
        await _recover_upload_sessions()
    asyncio.create_task(_delayed_upload_recovery())

    # --- Auth hardening (fixes production login) ---
    # 1) Resolve a STABLE JWT secret shared by all workers (prevents random-per-worker key
    #    causing tokens to be rejected right after login).
    from auth import ensure_secret_key
    await ensure_secret_key(db)
    # 2) Guarantee an admin account exists in this deployment's DB.
    await seed_admin()

# Health check endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "stockbud-backend", "version": "2.1-individual-stock"}

@app.get("/api/health")
async def api_health_check():
    return {"status": "healthy", "service": "stockbud-backend", "version": "2.1-individual-stock"}

api_router = APIRouter(prefix="/api")

# Include modular routers
from routes.seasonal_analytics import router as seasonal_router
api_router.include_router(seasonal_router)

# ==================== EXCEL PARSING ====================

def _resolve_col(df_columns_set, possible_names):
    """Resolve which column name exists in the DataFrame - called once per column"""
    for name in possible_names:
        if name in df_columns_set:
            return name
    return None


def _safe_float(val, default=0.0):
    """Fast float conversion — handles comma-separated numbers (e.g., 1,705.433)"""
    if val is None or val == '':
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        # Try removing commas (Indian/international thousand separators)
        try:
            f = float(str(val).replace(',', ''))
            return default if math.isnan(f) else f
        except (ValueError, TypeError):
            return default


def _safe_str(val, default=''):
    """Fast string conversion"""
    if val is None:
        return default
    s = str(val).strip()
    return default if s in ('', 'nan', 'None') else s


def _safe_int(val, default=0):
    """Fast int conversion"""
    try:
        f = float(val) if val not in (None, '', 'nan') else default
        return default if math.isnan(f) else int(f)
    except (ValueError, TypeError):
        return default


def _read_excel_once(file_content: bytes):
    """Read Excel file ONCE and detect header row efficiently"""
    import pandas as pd
    df = pd.read_excel(BytesIO(file_content), header=None, dtype=str)
    return _detect_header_and_clean(df)


def _read_excel_from_path(file_path: str):
    """Read Excel file from disk path (memory-efficient for large files)"""
    import pandas as pd
    df = pd.read_excel(file_path, header=None, dtype=str, engine='openpyxl')
    return _detect_header_and_clean(df)


def _detect_header_and_clean(df):
    """Detect header row and clean up DataFrame"""
    header_row_idx = None
    search_limit = min(20, len(df))
    for idx in range(search_limit):
        row_str = ' '.join(str(val).lower() for val in df.iloc[idx] if val is not None and str(val) != 'nan')
        if 'item name' in row_str or 'particular' in row_str or 'party name' in row_str or 'lnarr' in row_str:
            header_row_idx = idx
            break
    
    if header_row_idx is not None:
        df.columns = df.iloc[header_row_idx].astype(str).str.strip()
        df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
    else:
        df.columns = df.iloc[0].astype(str).str.strip()
        df = df.iloc[1:].reset_index(drop=True)
    
    return df


def parse_excel_file(file_content, file_type: str) -> List[Dict]:
    """Parse Excel file using fast dict-based iteration. Weights in KG -> grams.
    file_content can be bytes OR a file path string (for memory-efficient large file processing)."""
    try:
        if isinstance(file_content, str):
            df = _read_excel_from_path(file_content)
        else:
            df = _read_excel_once(file_content)
        cols = set(df.columns)
        KG_TO_GRAMS = 1000

        # Convert DataFrame to list of dicts ONCE (much faster than iterrows)
        raw_rows = df.to_dict('records')

        if file_type == 'purchase':
            item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name'])
            type_col = _resolve_col(cols, ['Type', 'type'])
            tag_col = _resolve_col(cols, ['Tag.No.', 'Tag No', 'tag no'])
            wt_rs_col = _resolve_col(cols, ['Wt/Rs', 'Wt Rs'])
            total_col = _resolve_col(cols, ['Total', 'total'])
            tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
            wstg_col = _resolve_col(cols, ['Wstg', 'wstg'])
            date_col = _resolve_col(cols, ['Date', 'date'])
            refno_col = _resolve_col(cols, ['Refno', 'refno', 'Ref No'])
            party_col = _resolve_col(cols, ['Party Name', 'party name', 'Party'])
            stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
            gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
            net_col = _resolve_col(cols, ['Net.Wt.', 'Net Wt'])
            fine_col = _resolve_col(cols, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'])
            dia_col = _resolve_col(cols, ['Dia.Wt.', 'Dia Wt'])
            stn_col = _resolve_col(cols, ['Stn.Wt.', 'Stn Wt'])
            rate_col = _resolve_col(cols, ['Rate', 'rate'])
            pc_col = _resolve_col(cols, ['Pc', 'pc', 'Pieces'])

            records = []
            pf_state = {'date': '', 'refno': '', 'party': '', 'ttype': None}
            for r in raw_rows:
                item_name = _safe_str(r.get(item_col) if item_col else None)
                if len(item_name) < 2 or item_name.replace('.', '', 1).isdigit():
                    continue
                date = normalize_date(r.get(date_col) if date_col else '')
                refno = _safe_str(r.get(refno_col) if refno_col else None)
                party = _safe_str(r.get(party_col) if party_col else None)
                type_raw = r.get(type_col) if type_col else None
                if date:
                    pf_state['date'], pf_state['refno'], pf_state['party'], pf_state['ttype'] = date, refno, party, type_raw
                else:
                    date = pf_state['date']
                    refno = refno or pf_state['refno']
                    party = party or pf_state['party']
                    type_raw = type_raw if (type_raw is not None and str(type_raw) != 'nan' and str(type_raw).strip()) else pf_state['ttype']
                trans_type = _safe_str(type_raw, 'P').upper()
                if trans_type.isdigit():
                    continue

                tag_no = _safe_str(r.get(tag_col) if tag_col else None)
                labor_val, labor_on = parse_labor_value(tag_no)
                wt_rs = r.get(wt_rs_col) if wt_rs_col else None
                if wt_rs and str(wt_rs).replace('.', '').isdigit():
                    labor_val = float(wt_rs)

                total_amount = _safe_float(r.get(total_col) if total_col else None)
                tunch_v = _safe_float(r.get(tunch_col) if tunch_col else None)
                wstg_v = _safe_float(r.get(wstg_col) if wstg_col else None)
                purchase_tunch = tunch_v + wstg_v

                records.append({
                    'date': date,
                    'type': 'purchase' if trans_type in ('P', 'PURCHASE') else 'purchase_return',
                    'refno': refno,
                    'party_name': party,
                    'item_name': item_name,
                    'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                    'tag_no': tag_no,
                    'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                    'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                    'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                    'labor': labor_val,
                    'labor_on': labor_on,
                    'dia_wt': _safe_float(r.get(dia_col) if dia_col else None) * KG_TO_GRAMS,
                    'stn_wt': _safe_float(r.get(stn_col) if stn_col else None) * KG_TO_GRAMS,
                    'tunch': str(purchase_tunch),
                    'rate': _safe_float(r.get(rate_col) if rate_col else None),
                    'total_pc': _safe_int(r.get(pc_col) if pc_col else None),
                    'total_amount': total_amount,
                })
            return records

        elif file_type == 'sale':
            item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name'])
            type_col = _resolve_col(cols, ['Type', 'type'])
            tag_col = _resolve_col(cols, ['Lbr. On Tag.No.', 'Tag.No.', 'Tag No'])
            on_col = _resolve_col(cols, ['On', 'on'])
            total_col = _resolve_col(cols, ['Total', 'total'])
            tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
            date_col = _resolve_col(cols, ['Date', 'date'])
            refno_col = _resolve_col(cols, ['Refno', 'refno', 'Ref No'])
            party_col = _resolve_col(cols, ['Party Name', 'party name', 'Party'])
            stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
            gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
            net_col = _resolve_col(cols, ['Gold Std.', 'Net.Wt.', 'Net Wt'])
            fine_col = _resolve_col(cols, ['Fine', 'Sil.Fine', 'Sil Fine'])
            dia_col = _resolve_col(cols, ['Dia.Wt.', 'Dia Wt'])
            stn_col = _resolve_col(cols, ['Stn.Wt.', 'Stn Wt'])
            taxable_col = _resolve_col(cols, ['Taxable Val.', 'Taxable Value'])
            pc_col = _resolve_col(cols, ['Pc', 'pc'])

            records = []
            sf_state = {'date': '', 'refno': '', 'party': '', 'ttype': None}
            for r in raw_rows:
                item_name = _safe_str(r.get(item_col) if item_col else None)
                if len(item_name) < 2 or item_name.replace('.', '', 1).isdigit():
                    continue
                date = normalize_date(r.get(date_col) if date_col else '')
                refno = _safe_str(r.get(refno_col) if refno_col else None)
                party = _safe_str(r.get(party_col) if party_col else None)
                type_raw = r.get(type_col) if type_col else None
                if date:
                    sf_state['date'], sf_state['refno'], sf_state['party'], sf_state['ttype'] = date, refno, party, type_raw
                else:
                    date = sf_state['date']
                    refno = refno or sf_state['refno']
                    party = party or sf_state['party']
                    type_raw = type_raw if (type_raw is not None and str(type_raw) != 'nan' and str(type_raw).strip()) else sf_state['ttype']
                trans_type = _safe_str(type_raw, 'S').upper()
                if trans_type.isdigit():
                    continue

                tag_no = _safe_str(r.get(tag_col) if tag_col else None)
                labor_val, labor_on = parse_labor_value(tag_no)
                on_val = r.get(on_col) if on_col else None
                if on_val and str(on_val).replace('.', '').isdigit():
                    labor_val = float(on_val)

                total_amount = _safe_float(r.get(total_col) if total_col else None)
                sale_tunch = _safe_float(r.get(tunch_col) if tunch_col else None)

                records.append({
                    'type': 'sale' if trans_type in ('S', 'SALE') else 'sale_return',
                    'date': date,
                    'refno': refno,
                    'party_name': party,
                    'item_name': item_name,
                    'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                    'tag_no': tag_no,
                    'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                    'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                    'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                    'labor': labor_val,
                    'labor_on': labor_on,
                    'dia_wt': _safe_float(r.get(dia_col) if dia_col else None) * KG_TO_GRAMS,
                    'stn_wt': _safe_float(r.get(stn_col) if stn_col else None) * KG_TO_GRAMS,
                    'tunch': str(sale_tunch),
                    'total_amount': total_amount,
                    'taxable_value': _safe_float(r.get(taxable_col) if taxable_col else None),
                    'total_pc': _safe_int(r.get(pc_col) if pc_col else None),
                })
            return records

        elif file_type == 'branch_transfer':
            item_col = _resolve_col(cols, ['Lnarr'])
            type_col = _resolve_col(cols, ['Type'])
            date_col = _resolve_col(cols, ['Date'])
            refno_col = _resolve_col(cols, ['Refno'])
            gr_col = _resolve_col(cols, ['Gr.Wt.'])
            net_col = _resolve_col(cols, ['Net.Wt.'])
            bt_tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
            bt_wstg_col = _resolve_col(cols, ['Wstg', 'wstg'])
            bt_fine_col = _resolve_col(cols, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'])
            bt_labor_col = _resolve_col(cols, ['Labour', 'Labor', 'Lbr', 'Wt/Rs', 'Wt Rs'])
            bt_total_col = _resolve_col(cols, ['Total', 'total'])
            bt_rate_col = _resolve_col(cols, ['Rate', 'rate'])

            records = []
            for r in raw_rows:
                item_name = _safe_str(r.get(item_col) if item_col else None)
                if len(item_name) < 2:
                    continue
                if 'opening' in item_name.lower() and 'balance' in item_name.lower():
                    continue
                if 'total' in item_name.lower():
                    continue
                if item_name.isdigit():
                    continue

                trans_type = _safe_str(r.get(type_col) if type_col else None).upper()
                if not trans_type or trans_type in ('', 'NAN'):
                    continue

                bt_tunch = _safe_float(r.get(bt_tunch_col) if bt_tunch_col else None) + _safe_float(r.get(bt_wstg_col) if bt_wstg_col else None)
                records.append({
                    'type': 'receive' if trans_type == 'R' else 'issue',
                    'date': normalize_date(r.get(date_col) if date_col else ''),
                    'refno': _safe_str(r.get(refno_col) if refno_col else None),
                    'party_name': 'MMI Jewelly Branch',
                    'item_name': item_name,
                    'stamp': '',
                    'tag_no': '',
                    'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                    'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                    'fine': _safe_float(r.get(bt_fine_col) if bt_fine_col else None) * KG_TO_GRAMS,
                    'labor': _safe_float(r.get(bt_labor_col) if bt_labor_col else None),
                    'labor_on': None,
                    'dia_wt': 0.0,
                    'stn_wt': 0.0,
                    'tunch': str(bt_tunch),
                    'rate': _safe_float(r.get(bt_rate_col) if bt_rate_col else None),
                    'total_pc': 0,
                    'total_amount': _safe_float(r.get(bt_total_col) if bt_total_col else None),
                    'taxable_value': 0.0,
                })
            return records

        elif file_type == 'opening_stock':
            item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name', 'Stock'])
            stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
            unit_col = _resolve_col(cols, ['Unit', 'unit'])
            pc_col = _resolve_col(cols, ['Pc', 'pc', 'Pieces'])
            gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
            net_col = _resolve_col(cols, ['Gold Std.', 'Net.Wt.', 'Net Wt'])
            fine_col = _resolve_col(cols, ['Sil.Fine', 'Fine', 'fine'])
            rate_col = _resolve_col(cols, ['Rate', 'rate'])
            total_col = _resolve_col(cols, ['Total', 'total'])
            tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
            wstg_col = _resolve_col(cols, ['Wstg', 'wstg'])

            records = []
            for r in raw_rows:
                item_name = _safe_str(r.get(item_col) if item_col else None)
                if len(item_name) < 2:
                    continue
                if 'total' in item_name.lower():
                    continue

                tunch_v = _safe_float(r.get(tunch_col) if tunch_col else None)
                wstg_v = _safe_float(r.get(wstg_col) if wstg_col else None)

                records.append({
                    'item_name': item_name,
                    'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                    'unit': _safe_str(r.get(unit_col) if unit_col else None),
                    'pc': _safe_int(r.get(pc_col) if pc_col else None),
                    'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                    'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                    'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                    'labor_wt': 0.0,
                    'labor_rs': 0.0,
                    'rate': _safe_float(r.get(rate_col) if rate_col else None),
                    'total': _safe_float(r.get(total_col) if total_col else None),
                })
            return records

        elif file_type == 'physical_stock':
            item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name', 'Stock'])
            stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
            gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt', 'Gross Weight'])
            net_col = _resolve_col(cols, ['Net.Wt.', 'Net Wt', 'Net Weight', 'Gold Std.'])
            pc_col = _resolve_col(cols, ['Pc', 'pc', 'Pieces', 'Pcs'])
            fine_col = _resolve_col(cols, ['Sil.Fine', 'Fine', 'fine'])

            has_net = net_col is not None
            records = []
            for r in raw_rows:
                item_name = _safe_str(r.get(item_col) if item_col else None)
                if len(item_name) < 2:
                    continue
                if 'total' in item_name.lower():
                    continue
                rec = {
                    'item_name': item_name,
                    'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                    'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                    'has_net': has_net,
                    'pc': _safe_int(r.get(pc_col) if pc_col else None),
                    'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                }
                if has_net:
                    rec['net_wt'] = _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS
                else:
                    rec['net_wt'] = 0.0
                records.append(rec)
            return records

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Excel file: {str(e)}")


def _memory_headroom_mb():
    """Available memory headroom in MB from cgroup limits (None if unknown/unlimited)"""
    try:
        with open('/sys/fs/cgroup/memory.max') as f:
            limit = f.read().strip()
        with open('/sys/fs/cgroup/memory.current') as f:
            current = int(f.read().strip())
        if limit == 'max':
            return None
        return (int(limit) - current) / (1024 * 1024)
    except Exception:
        pass
    try:
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes') as f:
            limit = int(f.read().strip())
        with open('/sys/fs/cgroup/memory/memory.usage_in_bytes') as f:
            current = int(f.read().strip())
        if limit > (1 << 60):
            return None
        return (limit - current) / (1024 * 1024)
    except Exception:
        return None


def _choose_excel_reader(file_path: str) -> str:
    """Pick calamine (fast, loads whole sheet) when memory allows, else openpyxl (slow, true streaming)"""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    need_mb = size_mb * 30 + 150  # rough peak: ~30x compressed size as Python objects + safety margin
    headroom = _memory_headroom_mb()
    if headroom is not None:
        choice = 'calamine' if headroom > need_mb else 'openpyxl'
        logger.info(f"[Excel] file={size_mb:.1f}MB need~{need_mb:.0f}MB headroom={headroom:.0f}MB -> {choice}")
        return choice
    return 'calamine' if size_mb <= 10 else 'openpyxl'


def _iter_excel_rows(file_path: str):
    """Return rows of the first sheet: a list (calamine, freeable in place) or a generator (openpyxl streaming)"""
    if _choose_excel_reader(file_path) == 'calamine':
        try:
            from python_calamine import CalamineWorkbook
            rows = CalamineWorkbook.from_path(file_path).get_sheet_by_index(0).to_python()
            logger.info(f"[Excel] Loaded {len(rows)} rows via calamine")
            return rows
        except Exception as e:
            logger.warning(f"[Excel] calamine failed ({e}), falling back to openpyxl")
    logger.info("[Excel] Using openpyxl streaming reader")

    def _gen():
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        try:
            for row in ws.iter_rows(values_only=True):
                yield row
        finally:
            wb.close()
    return _gen()


def _detect_header(head_rows: list):
    """Detect the header row within the first rows of the sheet"""
    header_names = None
    header_row_idx = None
    for i, row in enumerate(head_rows):
        str_vals = [str(v).strip() if v is not None else '' for v in row]
        if header_row_idx is None:
            row_str = ' '.join(s.lower() for s in str_vals if s)
            if 'item name' in row_str or 'particular' in row_str or 'party name' in row_str or 'lnarr' in row_str:
                header_row_idx = i
                header_names = str_vals
    if header_names is None:
        header_names = [str(v).strip() if v is not None else '' for v in (head_rows[0] if head_rows else [])]
        header_row_idx = 0
    return header_names, header_row_idx


def _build_row_mapper(file_type: str, header_names: list):
    """Return a mapper(row) -> record dict (or None to skip) for the given file type"""
    KG_TO_GRAMS = 1000
    cols_set = set(header_names)
    col_map = {name: idx for idx, name in enumerate(header_names)}

    def _get(row, col_name):
        if not col_name or col_name not in col_map:
            return None
        idx = col_map[col_name]
        return str(row[idx]).strip() if idx < len(row) and row[idx] is not None else None

    if file_type == 'purchase':
        item_col = _resolve_col(cols_set, ['Item Name', 'Particular', 'item name'])
        type_col = _resolve_col(cols_set, ['Type', 'type'])
        tag_col = _resolve_col(cols_set, ['Tag.No.', 'Tag No', 'tag no'])
        wt_rs_col = _resolve_col(cols_set, ['Wt/Rs', 'Wt Rs'])
        total_col = _resolve_col(cols_set, ['Total', 'total'])
        tunch_col = _resolve_col(cols_set, ['Tunch', 'tunch'])
        wstg_col = _resolve_col(cols_set, ['Wstg', 'wstg'])
        date_col = _resolve_col(cols_set, ['Date', 'date'])
        refno_col = _resolve_col(cols_set, ['Refno', 'refno', 'Ref No'])
        party_col = _resolve_col(cols_set, ['Party Name', 'party name', 'Party'])
        stamp_col = _resolve_col(cols_set, ['Stamp', 'stamp'])
        gr_col = _resolve_col(cols_set, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
        net_col = _resolve_col(cols_set, ['Net.Wt.', 'Net Wt'])
        fine_col = _resolve_col(cols_set, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'])
        dia_col = _resolve_col(cols_set, ['Dia.Wt.', 'Dia Wt'])
        stn_col = _resolve_col(cols_set, ['Stn.Wt.', 'Stn Wt'])
        rate_col = _resolve_col(cols_set, ['Rate', 'rate'])
        pc_col = _resolve_col(cols_set, ['Pc', 'pc', 'Pieces'])

        pf_state = {'date': '', 'refno': '', 'party': '', 'ttype': None}

        def mapper(row):
            item_name = _safe_str(_get(row, item_col))
            if len(item_name) < 2 or item_name.replace('.', '', 1).isdigit():
                return None
            date = normalize_date(_get(row, date_col) or '')
            refno = _safe_str(_get(row, refno_col))
            party = _safe_str(_get(row, party_col))
            type_raw = _get(row, type_col)
            if date:
                pf_state['date'], pf_state['refno'], pf_state['party'], pf_state['ttype'] = date, refno, party, type_raw
            else:
                # Voucher continuation line (Tally omits repeated date/refno/party/type)
                date = pf_state['date']
                refno = refno or pf_state['refno']
                party = party or pf_state['party']
                type_raw = type_raw or pf_state['ttype']
            trans_type = _safe_str(type_raw, 'P').upper()
            if trans_type.isdigit():
                return None
            tag_no = _safe_str(_get(row, tag_col))
            labor_val, labor_on = parse_labor_value(tag_no)
            wt_rs = _get(row, wt_rs_col)
            if wt_rs and str(wt_rs).replace('.', '').isdigit():
                labor_val = float(wt_rs)
            tunch_v = _safe_float(_get(row, tunch_col))
            wstg_v = _safe_float(_get(row, wstg_col))
            return {
                'date': date,
                'type': 'purchase' if trans_type in ('P', 'PURCHASE') else 'purchase_return',
                'refno': refno,
                'party_name': party,
                'item_name': item_name,
                'stamp': normalize_stamp(_get(row, stamp_col) or ''),
                'tag_no': tag_no,
                'gr_wt': _safe_float(_get(row, gr_col)) * KG_TO_GRAMS,
                'net_wt': _safe_float(_get(row, net_col)) * KG_TO_GRAMS,
                'fine': _safe_float(_get(row, fine_col)) * KG_TO_GRAMS,
                'labor': labor_val,
                'labor_on': labor_on,
                'dia_wt': _safe_float(_get(row, dia_col)) * KG_TO_GRAMS,
                'stn_wt': _safe_float(_get(row, stn_col)) * KG_TO_GRAMS,
                'tunch': str(tunch_v + wstg_v),
                'rate': _safe_float(_get(row, rate_col)),
                'total_pc': _safe_int(_get(row, pc_col)),
                'total_amount': _safe_float(_get(row, total_col)),
            }
        return mapper

    if file_type == 'sale':
        item_col = _resolve_col(cols_set, ['Item Name', 'Particular', 'item name'])
        type_col = _resolve_col(cols_set, ['Type', 'type'])
        tag_col = _resolve_col(cols_set, ['Lbr. On Tag.No.', 'Tag.No.', 'Tag No'])
        on_col = _resolve_col(cols_set, ['On', 'on'])
        total_col = _resolve_col(cols_set, ['Total', 'total'])
        tunch_col = _resolve_col(cols_set, ['Tunch', 'tunch'])
        date_col = _resolve_col(cols_set, ['Date', 'date'])
        refno_col = _resolve_col(cols_set, ['Refno', 'refno', 'Ref No'])
        party_col = _resolve_col(cols_set, ['Party Name', 'party name', 'Party'])
        stamp_col = _resolve_col(cols_set, ['Stamp', 'stamp'])
        gr_col = _resolve_col(cols_set, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
        net_col = _resolve_col(cols_set, ['Gold Std.', 'Net.Wt.', 'Net Wt'])
        fine_col = _resolve_col(cols_set, ['Fine', 'Sil.Fine', 'Sil Fine'])
        dia_col = _resolve_col(cols_set, ['Dia.Wt.', 'Dia Wt'])
        stn_col = _resolve_col(cols_set, ['Stn.Wt.', 'Stn Wt'])
        taxable_col = _resolve_col(cols_set, ['Taxable Val.', 'Taxable Value'])
        pc_col = _resolve_col(cols_set, ['Pc', 'pc'])

        sf_state = {'date': '', 'refno': '', 'party': '', 'ttype': None}

        def mapper(row):
            item_name = _safe_str(_get(row, item_col))
            if len(item_name) < 2 or item_name.replace('.', '', 1).isdigit():
                return None
            date = normalize_date(_get(row, date_col) or '')
            refno = _safe_str(_get(row, refno_col))
            party = _safe_str(_get(row, party_col))
            type_raw = _get(row, type_col)
            if date:
                sf_state['date'], sf_state['refno'], sf_state['party'], sf_state['ttype'] = date, refno, party, type_raw
            else:
                # Voucher continuation line (Tally omits repeated date/refno/party/type)
                date = sf_state['date']
                refno = refno or sf_state['refno']
                party = party or sf_state['party']
                type_raw = type_raw or sf_state['ttype']
            trans_type = _safe_str(type_raw, 'S').upper()
            if trans_type.isdigit():
                return None
            tag_no = _safe_str(_get(row, tag_col))
            labor_val, labor_on = parse_labor_value(tag_no)
            on_val = _get(row, on_col)
            if on_val and str(on_val).replace('.', '').isdigit():
                labor_val = float(on_val)
            return {
                'type': 'sale' if trans_type in ('S', 'SALE') else 'sale_return',
                'date': date,
                'refno': refno,
                'party_name': party,
                'item_name': item_name,
                'stamp': normalize_stamp(_get(row, stamp_col) or ''),
                'tag_no': tag_no,
                'gr_wt': _safe_float(_get(row, gr_col)) * KG_TO_GRAMS,
                'net_wt': _safe_float(_get(row, net_col)) * KG_TO_GRAMS,
                'fine': _safe_float(_get(row, fine_col)) * KG_TO_GRAMS,
                'labor': labor_val,
                'labor_on': labor_on,
                'dia_wt': _safe_float(_get(row, dia_col)) * KG_TO_GRAMS,
                'stn_wt': _safe_float(_get(row, stn_col)) * KG_TO_GRAMS,
                'tunch': str(_safe_float(_get(row, tunch_col))),
                'total_amount': _safe_float(_get(row, total_col)),
                'taxable_value': _safe_float(_get(row, taxable_col)),
                'total_pc': _safe_int(_get(row, pc_col)),
            }
        return mapper

    if file_type == 'branch_transfer':
        item_col = _resolve_col(cols_set, ['Lnarr'])
        type_col = _resolve_col(cols_set, ['Type'])
        date_col = _resolve_col(cols_set, ['Date'])
        refno_col = _resolve_col(cols_set, ['Refno'])
        gr_col = _resolve_col(cols_set, ['Gr.Wt.'])
        net_col = _resolve_col(cols_set, ['Net.Wt.'])
        bt_tunch_col = _resolve_col(cols_set, ['Tunch', 'tunch'])
        bt_wstg_col = _resolve_col(cols_set, ['Wstg', 'wstg'])
        bt_fine_col = _resolve_col(cols_set, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'])
        bt_labor_col = _resolve_col(cols_set, ['Labour', 'Labor', 'Lbr', 'Wt/Rs', 'Wt Rs'])
        bt_total_col = _resolve_col(cols_set, ['Total', 'total'])
        bt_rate_col = _resolve_col(cols_set, ['Rate', 'rate'])

        bf_state = {'date': ''}

        def mapper(row):
            item_name = _safe_str(_get(row, item_col))
            if len(item_name) < 2:
                return None
            low = item_name.lower()
            if ('opening' in low and 'balance' in low) or 'total' in low or item_name.isdigit():
                return None
            trans_type = _safe_str(_get(row, type_col)).upper()
            if not trans_type or trans_type in ('', 'NAN'):
                return None
            date = normalize_date(_get(row, date_col) or '')
            if date:
                bf_state['date'] = date
            else:
                date = bf_state['date']
            bt_tunch = _safe_float(_get(row, bt_tunch_col)) + _safe_float(_get(row, bt_wstg_col))
            return {
                'type': 'receive' if trans_type == 'R' else 'issue',
                'date': date,
                'refno': _safe_str(_get(row, refno_col)),
                'party_name': 'MMI Jewelly Branch',
                'item_name': item_name,
                'stamp': '',
                'tag_no': '',
                'gr_wt': _safe_float(_get(row, gr_col)) * KG_TO_GRAMS,
                'net_wt': _safe_float(_get(row, net_col)) * KG_TO_GRAMS,
                'fine': _safe_float(_get(row, bt_fine_col)) * KG_TO_GRAMS,
                'labor': _safe_float(_get(row, bt_labor_col)),
                'labor_on': None,
                'dia_wt': 0.0,
                'stn_wt': 0.0,
                'tunch': str(bt_tunch),
                'rate': _safe_float(_get(row, bt_rate_col)),
                'total_pc': 0,
                'total_amount': _safe_float(_get(row, bt_total_col)),
                'taxable_value': 0.0,
            }
        return mapper

    if file_type == 'opening_stock':
        item_col = _resolve_col(cols_set, ['Item Name', 'Particular', 'item name'])
        stamp_col = _resolve_col(cols_set, ['Stamp', 'stamp'])
        unit_col = _resolve_col(cols_set, ['Unit', 'unit'])
        gr_col = _resolve_col(cols_set, ['Gr.Wt.', 'Gr Wt', 'Gross Wt', 'Gross Weight'])
        net_col = _resolve_col(cols_set, ['Net.Wt.', 'Net Wt', 'Net Weight'])
        fine_col = _resolve_col(cols_set, ['Fine', 'Sil.Fine', 'Silver Fine'])
        pc_col = _resolve_col(cols_set, ['Pc', 'pc', 'Pieces', 'Pcs'])
        rate_col = _resolve_col(cols_set, ['Rate', 'rate'])
        total_col = _resolve_col(cols_set, ['Total', 'total', 'Amount'])

        def mapper(row):
            item_name = _safe_str(_get(row, item_col))
            if len(item_name) < 2:
                return None
            return {
                'item_name': item_name,
                'stamp': normalize_stamp(_get(row, stamp_col) or ''),
                'unit': _safe_str(_get(row, unit_col)),
                'pc': _safe_int(_get(row, pc_col)),
                'gr_wt': _safe_float(_get(row, gr_col)) * KG_TO_GRAMS,
                'net_wt': _safe_float(_get(row, net_col)) * KG_TO_GRAMS,
                'fine': _safe_float(_get(row, fine_col)) * KG_TO_GRAMS,
                'labor_wt': 0.0,
                'labor_rs': 0.0,
                'rate': _safe_float(_get(row, rate_col)),
                'total': _safe_float(_get(row, total_col)),
            }
        return mapper

    if file_type == 'physical_stock':
        item_col = _resolve_col(cols_set, ['Item Name', 'Particular', 'item name', 'Stock'])
        stamp_col = _resolve_col(cols_set, ['Stamp', 'stamp'])
        gr_col = _resolve_col(cols_set, ['Gr.Wt.', 'Gr Wt', 'Gross Wt', 'Gross Weight'])
        net_col = _resolve_col(cols_set, ['Net.Wt.', 'Net Wt', 'Net Weight', 'Gold Std.'])
        pc_col = _resolve_col(cols_set, ['Pc', 'pc', 'Pieces', 'Pcs'])
        fine_col = _resolve_col(cols_set, ['Sil.Fine', 'Fine', 'fine'])
        has_net = net_col is not None

        def mapper(row):
            item_name = _safe_str(_get(row, item_col))
            if len(item_name) < 2:
                return None
            if 'total' in item_name.lower():
                return None
            return {
                'item_name': item_name,
                'stamp': normalize_stamp(_get(row, stamp_col) or ''),
                'gr_wt': _safe_float(_get(row, gr_col)) * KG_TO_GRAMS,
                'has_net': has_net,
                'pc': _safe_int(_get(row, pc_col)),
                'fine': _safe_float(_get(row, fine_col)) * KG_TO_GRAMS,
                'net_wt': _safe_float(_get(row, net_col)) * KG_TO_GRAMS if has_net else 0.0,
            }
        return mapper

    raise ValueError(f"Unsupported file_type for Excel parsing: {file_type}")


def _validate_headers(file_type: str, header_names: list):
    """Reject wrong-format files up-front so bad uploads never touch the data."""
    cols = set(header_names)
    item_ok = _resolve_col(cols, ['Item Name', 'Particular', 'item name']) is not None
    date_ok = _resolve_col(cols, ['Date', 'date']) is not None
    lnarr_ok = _resolve_col(cols, ['Lnarr']) is not None
    if file_type in ('sale', 'purchase'):
        if lnarr_ok and not item_ok:
            raise ValueError(f"File rejected: this looks like a Branch Transfer file (has 'Lnarr' column), not a {file_type} file. No data was changed.")
        if not item_ok or not date_ok:
            raise ValueError(f"File rejected: missing required columns for a {file_type} file (need 'Item Name'/'Particular' and 'Date'). No data was changed.")
    elif file_type == 'branch_transfer':
        if not lnarr_ok or _resolve_col(cols, ['Type', 'type']) is None:
            raise ValueError("File rejected: not a Branch Transfer file (need 'Lnarr' and 'Type' columns). No data was changed.")
    elif file_type == 'opening_stock':
        if not item_ok:
            raise ValueError("File rejected: missing 'Item Name' column for a stock file. No data was changed.")
        if date_ok:
            raise ValueError("File rejected: this looks like a transaction file (has a 'Date' column), not a stock file. No data was changed.")


def _iter_excel_records(file_path: str, file_type: str, prog: dict = None):
    """Yield parsed records one at a time with bounded memory (raw rows freed as consumed)"""
    from itertools import islice
    rows = _iter_excel_rows(file_path)
    if isinstance(rows, list):
        head = rows[:25]
    else:
        head = list(islice(rows, 25))
    header_names, header_row_idx = _detect_header(head)
    _validate_headers(file_type, header_names)
    mapper = _build_row_mapper(file_type, header_names)
    count = 0

    def _emit(row):
        nonlocal count
        count += 1
        if prog is not None and count % 20000 == 0:
            prog['msg'] = f'Parsing rows... {count:,} processed'
        return mapper(row)

    if isinstance(rows, list):
        for i in range(header_row_idx + 1, len(rows)):
            rec = _emit(rows[i])
            rows[i] = None
            if rec is not None:
                yield rec
    else:
        for row in head[header_row_idx + 1:]:
            rec = _emit(row)
            if rec is not None:
                yield rec
        for row in rows:
            rec = _emit(row)
            if rec is not None:
                yield rec


def parse_excel_streaming(file_path: str, file_type: str) -> List[Dict]:
    """Parse an Excel file fully into a records list (use _iter_excel_records for large files)"""
    try:
        records = list(_iter_excel_records(file_path, file_type))
        logger.info(f"[Streaming parser] Parsed {len(records)} {file_type} records from {file_path}")
        return records
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"[Streaming parser] Error: {e}", exc_info=True)
        return []

# ==================== UPLOAD ENDPOINTS ====================

async def _set_opening_effective_date(effective_date: str = None) -> str:
    """Persist the opening stock effective date (defaults to today). Anchors current stock."""
    eff = (effective_date or '').strip() or datetime.now(timezone.utc).date().isoformat()
    try:
        datetime.strptime(eff, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="effective_date must be YYYY-MM-DD")
    await db.app_settings.update_one(
        {'key': 'opening_stock_effective_date'},
        {'$set': {'value': eff, 'updated_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    _inv_cache.invalidate()
    return eff


@api_router.post("/opening-stock/upload")
async def upload_opening_stock(file: UploadFile = File(...), effective_date: str = None, current_user: dict = Depends(get_current_user)):
    """Upload opening stock - Parse and MERGE items by name (sum weights regardless of stamp).
    Sets the opening stock effective date: stock is anchored to these values as of that date."""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    content = await file.read()
    
    try:
        # Parse in thread pool so we don't block the event loop
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(_parse_executor, parse_excel_file, content, 'opening_stock')
        
        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in file")
        
        # MERGE items by name - sum all weights for same item
        merged_items = {}
        for record in records:
            key = record['item_name'].strip().lower()
            if key not in merged_items:
                merged_items[key] = {
                    'item_name': record['item_name'],
                    'stamp': record.get('stamp', ''),
                    'unit': record.get('unit', ''),
                    'pc': 0,
                    'gr_wt': 0.0,
                    'net_wt': 0.0,
                    'fine': 0.0,
                    'labor_wt': record.get('labor_wt', 0.0),
                    'labor_rs': record.get('labor_rs', 0.0),
                    'rate': record.get('rate', 0.0),
                    'total': 0.0
                }
            
            # Sum weights (including negative values)
            merged_items[key]['gr_wt'] += record.get('gr_wt', 0)
            merged_items[key]['net_wt'] += record.get('net_wt', 0)
            merged_items[key]['fine'] += record.get('fine', 0)
            merged_items[key]['pc'] += record.get('pc', 0)
            merged_items[key]['total'] += record.get('total', 0)
            
            # Keep stamp if this entry has one
            if record.get('stamp') and not merged_items[key]['stamp']:
                merged_items[key]['stamp'] = record['stamp']
        
        # Clear existing opening stock
        await db.opening_stock.delete_many({})
        
        # Insert merged items
        stock_items = [OpeningStock(**item).model_dump() for item in merged_items.values()]
        await db.opening_stock.insert_many(stock_items)
        
        # Calculate totals for response
        total_net_wt = sum(item['net_wt'] for item in stock_items)
        total_gr_wt = sum(item['gr_wt'] for item in stock_items)
        
        await save_action('upload_opening_stock', f"Uploaded {len(stock_items)} merged opening stock items, total: {total_net_wt/1000:.3f} kg")

        eff = await _set_opening_effective_date(effective_date)
        
        # Auto-normalize stamps after upload
        await auto_normalize_stamps()
        
        return {
            "success": True,
            "count": len(stock_items),
            "original_rows": len(records),
            "merged_items": len(stock_items),
            "total_net_wt_kg": round(total_net_wt/1000, 3),
            "total_gr_wt_kg": round(total_gr_wt/1000, 3),
            "effective_date": eff,
            "message": f"Merged {len(records)} rows into {len(stock_items)} items. Total: {total_net_wt/1000:.3f} kg (stock as on {eff})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


# ==================== AUTHENTICATION ENDPOINTS ====================

@api_router.post("/auth/login", response_model=Token)
async def login(request: LoginRequest):
    """Login endpoint - Returns JWT token (18 hours for regular users, 365 days for admin)"""
    user = await db.users.find_one({"username": request.username})
    
    if not user or not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.get('is_active', True):
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    # Create JWT token with different expiry for admin (perpetual - 365 days)
    if user.get('role') == 'admin':
        access_token = create_access_token({"sub": user['username'], "role": user['role']}, expire_hours=365*24)
    else:
        # Regular users: 18 hours
        access_token = create_access_token({"sub": user['username'], "role": user['role']})
    
    # Remove sensitive data
    user_data = {k: v for k, v in user.items() if k not in ['_id', 'password_hash']}
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@api_router.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user info"""
    return current_user

@api_router.post("/auth/logout")
async def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully"}

# ==================== USER MANAGEMENT (Admin Only) ====================

@api_router.post("/users/create")
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create new user (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can create users")
    
    # Check if username exists
    existing = await db.users.find_one({"username": request.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Validate role
    if request.role not in ['admin', 'manager', 'executive', 'polythene_executive', 'sales_manager', 'uploader']:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Create user
    user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        role=request.role,
        created_by=current_user['username']
    )
    
    await db.users.insert_one(user.model_dump())
    
    return {
        "success": True,
        "message": f"User {request.username} created successfully",
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }

@api_router.get("/users/list")
async def list_users(current_user: dict = Depends(get_current_user)):
    """List all users (Admin and Manager can view)"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
    return users

@api_router.delete("/users/{username}")
async def delete_user(
    username: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete user (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    
    if username == current_user['username']:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await db.users.delete_one({"username": username})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "message": f"User {username} deleted"}

@api_router.put("/users/{username}")
async def update_user(
    username: str,
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Update user details (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can update users")
    
    # Get existing user
    existing_user = await db.users.find_one({"username": username})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare update data
    update_data = {}
    
    # Update full_name if provided
    if 'full_name' in request and request['full_name']:
        update_data['full_name'] = request['full_name']
    
    # Update role if provided
    if 'role' in request and request['role']:
        if request['role'] not in ['admin', 'manager', 'executive', 'polythene_executive', 'sales_manager', 'uploader']:
            raise HTTPException(status_code=400, detail="Invalid role")
        update_data['role'] = request['role']
    
    # Update active status if provided
    if 'is_active' in request:
        update_data['is_active'] = request['is_active']
    
    # Update password if provided
    if 'password' in request and request['password']:
        update_data['password_hash'] = get_password_hash(request['password'])
    
    # Update new username if provided and different
    if 'new_username' in request and request['new_username'] and request['new_username'] != username:
        # Check if new username already exists
        existing_new = await db.users.find_one({"username": request['new_username']})
        if existing_new:
            raise HTTPException(status_code=400, detail="New username already exists")
        update_data['username'] = request['new_username']
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Perform update
    await db.users.update_one(
        {"username": username},
        {"$set": update_data}
    )
    
    return {
        "success": True,
        "message": f"User {username} updated successfully",
        "updated_fields": list(update_data.keys())
    }

@api_router.post("/users/initialize-admin")
async def initialize_admin():
    """Create initial admin user if no users exist (one-time setup)"""
    count = await db.users.count_documents({})
    
    if count > 0:
        raise HTTPException(status_code=400, detail="Users already exist. Use login.")
    
    # Create default admin
    admin = User(
        username="admin",
        password_hash=get_password_hash("admin123"),  # Change on first login!
        full_name="System Administrator",
        role="admin",
        created_by="system"
    )
    
    await db.users.insert_one(admin.model_dump())
    
    return {
        "success": True,
        "message": "Admin user created. Use the credentials you set to login.",
        "username": "admin"
    }

async def batch_insert(collection, documents: list):
    """Insert documents in batches to handle large datasets"""
    total = 0
    for i in range(0, len(documents), BATCH_INSERT_SIZE):
        batch = documents[i:i + BATCH_INSERT_SIZE]
        await collection.insert_many(batch, ordered=False)
        total += len(batch)
    return total


async def _backup_replaced_records(batch_id: str, repl_q: dict) -> int:
    """Backup replaced records for undo, streamed in 5000-row chunks to keep memory
    flat and stay under Mongo's 16MB document limit. Returns rows backed up."""
    now = datetime.now(timezone.utc).isoformat()
    part, buf, total = 0, [], 0
    async for doc in db.transactions.find(repl_q, {"_id": 0}):
        buf.append(doc)
        if len(buf) >= 5000:
            await db.replaced_records.insert_one({
                "batch_id": batch_id, "part": part, "records": buf, "replaced_at": now
            })
            part += 1
            total += len(buf)
            buf = []
    if buf:
        await db.replaced_records.insert_one({
            "batch_id": batch_id, "part": part, "records": buf, "replaced_at": now
        })
        total += len(buf)
    return total


def _prepare_transactions(records: list, batch_id: str) -> list:
    """Prepare transaction dicts with defaults (skip per-row Pydantic for speed)"""
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for r in records:
        r['batch_id'] = batch_id
        r.setdefault('id', str(uuid.uuid4()))
        r.setdefault('upload_date', now)
        r.setdefault('rate', 0.0)
        r.setdefault('total_amount', 0.0)
        r.setdefault('taxable_value', 0.0)
        docs.append(r)
    return docs


# ==================== CHUNKED UPLOAD (MongoDB-backed for multi-pod deployments) ====================

async def _save_upload_meta(upload_id: str, meta: dict, expected_attempts: int = None):
    """Persist upload metadata to MongoDB. When expected_attempts is given, write only
    if this attempt still owns the session (prevents a superseded task clobbering a retry)."""
    q = {"upload_id": upload_id}
    if expected_attempts is not None:
        q["attempts"] = expected_attempts
    await db.upload_sessions.update_one(
        q,
        {"$set": {**meta, "upload_id": upload_id, "heartbeat": datetime.now(timezone.utc).isoformat()}},
        upsert=(expected_attempts is None)
    )

async def _load_upload_meta(upload_id: str) -> dict:
    """Load upload metadata from MongoDB"""
    doc = await db.upload_sessions.find_one({"upload_id": upload_id}, {"_id": 0})
    return doc


@api_router.post("/upload/init")
async def init_chunked_upload(request: Dict, current_user: dict = Depends(get_current_user)):
    """Initialize a chunked file upload"""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    file_type = request.get('file_type')
    if file_type not in ['purchase', 'sale', 'branch_transfer', 'opening_stock', 'physical_stock', 'master_stock', 'historical_sale', 'historical_purchase']:
        raise HTTPException(status_code=400, detail="Invalid file_type")

    # Physical stock must always use the direct upload flow, never chunked
    if file_type == 'physical_stock':
        raise HTTPException(status_code=400, detail="physical_stock uploads must use the direct upload flow")

    upload_id = str(uuid.uuid4())

    meta = {
        'file_type': file_type,
        'start_date': request.get('start_date'),
        'end_date': request.get('end_date'),
        'verification_date': request.get('verification_date'),
        'year': request.get('year'),
        'total_chunks': request.get('total_chunks', 0),
        'received': 0,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'owner_username': current_user['username'],
    }
    await _save_upload_meta(upload_id, meta)

    return {"upload_id": upload_id}


@api_router.post("/upload/chunk/{upload_id}")
async def upload_chunk(upload_id: str, chunk_index: int, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Receive a single chunk of a large file — stored in MongoDB for cross-pod access"""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    meta = await _load_upload_meta(upload_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Upload session not found")
    if meta.get('owner_username') and meta['owner_username'] != current_user['username']:
        raise HTTPException(status_code=403, detail="Not the owner of this upload session")

    content = await file.read()

    # Store chunk in MongoDB (using Binary for efficient storage)
    from bson import Binary
    await db.upload_chunks.update_one(
        {"upload_id": upload_id, "chunk_index": chunk_index},
        {"$set": {"upload_id": upload_id, "chunk_index": chunk_index, "data": Binary(content)}},
        upsert=True
    )

    meta['received'] = meta.get('received', 0) + 1
    await _save_upload_meta(upload_id, meta)

    return {"received": meta['received'], "chunk_index": chunk_index}


async def _rollback_partial_upload(meta: dict):
    """Remove partially-inserted batch docs and restore any replaced records (crash/retry safety)"""
    bid = meta.get('batch_id')
    if not bid:
        return
    await db.transactions.delete_many({'batch_id': bid})
    await db.historical_transactions.delete_many({'batch_id': bid})
    backups = await db.replaced_records.find({'batch_id': bid}, {'_id': 0}).sort('part', 1).to_list(None)
    old = [r for b in backups for r in b.get('records', [])]
    if old:
        await batch_insert(db.transactions, old)
    await db.replaced_records.delete_many({'batch_id': bid})


async def _fail_upload_session(meta: dict, error_msg: str):
    """Mark a session as failed: rollback partial writes, drop chunks, set error status"""
    uid = meta['upload_id']
    await _rollback_partial_upload(meta)
    await db.upload_chunks.delete_many({'upload_id': uid})
    await db.upload_sessions.update_one(
        {'upload_id': uid, 'status': 'processing'},
        {'$set': {'status': 'error', 'error': error_msg}}
    )


async def _try_resume_upload(upload_id: str) -> bool:
    """Atomically claim a dead 'processing' session and re-run it from its stored chunks.
    Only claims when the heartbeat is stale (task truly dead) and attempts remain."""
    from pymongo import ReturnDocument
    now = datetime.now(timezone.utc)
    stale_cutoff = (now - timedelta(seconds=STALE_HEARTBEAT_SECONDS)).isoformat()
    doc = await db.upload_sessions.find_one_and_update(
        {'upload_id': upload_id, 'status': 'processing',
         'attempts': {'$lt': MAX_UPLOAD_ATTEMPTS}, 'heartbeat': {'$lt': stale_cutoff}},
        {'$inc': {'attempts': 1},
         '$set': {'heartbeat': now.isoformat(), 'progress': 'Resuming after server restart...'}},
        return_document=ReturnDocument.AFTER
    )
    if not doc:
        return False
    if await db.upload_chunks.count_documents({'upload_id': upload_id}) == 0:
        return False
    meta = {k: v for k, v in doc.items() if k != '_id'}
    await _rollback_partial_upload(meta)
    meta.pop('batch_id', None)
    logger.info(f"[Upload {upload_id}] Resuming after restart (attempt {meta.get('attempts')})")
    asyncio.create_task(_process_upload(upload_id, meta))
    return True


async def _await_with_heartbeat(upload_id: str, meta: dict, my_attempt: int, prog: dict, fut):
    """Await an executor future while writing heartbeat/progress and detecting supersession"""
    while not fut.done():
        await asyncio.sleep(5)
        meta['progress'] = prog.get('msg', 'Processing...')
        await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
        cur = await db.upload_sessions.find_one({"upload_id": upload_id}, {"attempts": 1})
        if not cur or cur.get('attempts', 1) != my_attempt:
            prog['abort'] = True
    return fut.result()


async def _process_upload(upload_id: str, meta: dict):
    """Background task: reassemble chunks to temp file, then stream-parse and insert into DB.
    Memory-bounded (batched inserts during parse) and resumable (chunks kept until final state)."""
    import tempfile as _tempfile
    tmp_path = None
    my_attempt = meta.get('attempts', 1)
    prog = {'msg': 'Processing...'}
    try:
        logger.info(f"[Upload {upload_id}] Starting processing, file_type={meta['file_type']}, attempt={my_attempt}")
        meta['progress'] = 'Reassembling file from chunks...'
        await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)

        # Write chunks directly to a temp file (avoids holding entire file in memory).
        # Chunks stay in MongoDB until success/final error so processing can be retried after a crash.
        tmp_fd, tmp_path = _tempfile.mkstemp(suffix='.xlsx')
        total_bytes = 0
        cursor = db.upload_chunks.find(
            {"upload_id": upload_id},
            {"chunk_index": 1, "data": 1, "_id": 0}
        ).sort("chunk_index", 1)
        import os as _os
        with _os.fdopen(tmp_fd, 'wb') as f:
            async for chunk_doc in cursor:
                data = chunk_doc['data']
                f.write(data)
                total_bytes += len(data)

        logger.info(f"[Upload {upload_id}] Wrote {total_bytes} bytes to disk")
        prog['msg'] = f'Parsing Excel file ({total_bytes // 1024} KB)...'
        meta['progress'] = prog['msg']
        await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)

        file_type = meta['file_type']
        parse_type = file_type
        if file_type in ('opening_stock', 'master_stock'):
            parse_type = 'opening_stock'
        elif file_type == 'historical_sale':
            parse_type = 'sale'
        elif file_type == 'historical_purchase':
            parse_type = 'purchase'

        loop = asyncio.get_event_loop()
        start_date = meta.get('start_date')
        end_date = meta.get('end_date')

        if file_type in ('purchase', 'sale', 'branch_transfer', 'historical_sale', 'historical_purchase'):
            # Streaming pipeline: parse rows and insert in 5K batches -> memory stays bounded.
            batch_id = str(uuid.uuid4())
            meta['batch_id'] = batch_id
            await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
            is_hist = file_type in ('historical_sale', 'historical_purchase')
            target = db.historical_transactions if is_hist else db.transactions
            year = meta.get('year', '2025')

            def _pipeline():
                saved = 0
                dates = set()
                batch = []
                type_counts = {}

                def flush():
                    nonlocal saved, batch
                    if not batch:
                        return
                    docs = _prepare_transactions(batch, batch_id)
                    if is_hist:
                        for d in docs:
                            d['historical_year'] = year
                            d['is_historical'] = True
                    asyncio.run_coroutine_threadsafe(batch_insert(target, docs), loop).result()
                    saved += len(docs)
                    batch = []
                    prog['msg'] = f'Saved {saved:,} records to database...'

                for rec in _iter_excel_records(tmp_path, parse_type, prog):
                    if prog.get('abort'):
                        raise RuntimeError('superseded')
                    if rec.get('date'):
                        dates.add(rec['date'])
                    type_counts[rec.get('type')] = type_counts.get(rec.get('type'), 0) + 1
                    batch.append(rec)
                    if len(batch) >= 5000:
                        flush()
                flush()
                return saved, sorted(dates), type_counts

            pipeline_future = loop.run_in_executor(_parse_executor, _pipeline)
            count, new_dates, type_counts = await _await_with_heartbeat(upload_id, meta, my_attempt, prog, pipeline_future)
            logger.info(f"[Upload {upload_id}] Streamed {count} records into DB (batch {batch_id})")

            # Content sanity check: a wrong file parsed as sale/purchase turns almost every
            # row into a *_return (Type letters don't match) — reject and roll back cleanly.
            base_type = 'sale' if parse_type == 'sale' else ('purchase' if parse_type == 'purchase' else None)
            if base_type and count > 0 and type_counts.get(f'{base_type}_return', 0) > type_counts.get(base_type, 0):
                raise ValueError(f"File rejected: content does not match the {base_type} file format (transaction types don't look like {base_type} rows). No data was changed.")

            if count == 0:
                meta['status'] = 'error'
                meta['error'] = 'No valid records found in file'
                await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
                await db.upload_chunks.delete_many({"upload_id": upload_id})
                return

            if not is_hist:
                delete_types = ['issue', 'receive'] if file_type == 'branch_transfer' else [file_type, f"{file_type}_return"]
                deleted_count = 0
                if new_dates:
                    # Replace old records for the uploaded dates (new batch excluded)
                    meta['progress'] = 'Replacing previous records for uploaded dates...'
                    await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
                    repl_q = {"type": {"$in": delete_types}, "date": {"$in": new_dates + ["", None]}, "batch_id": {"$ne": batch_id}}
                    await _backup_replaced_records(batch_id, repl_q)
                    deleted_count = (await db.transactions.delete_many(repl_q)).deleted_count
                dates_str = f"{new_dates[0]} to {new_dates[-1]}" if new_dates else "unknown"
                message = f"Uploaded {count} {file_type} records for {dates_str}"
                if deleted_count > 0:
                    message += f" (replaced {deleted_count} old records)"
                await save_action(f'upload_{file_type}', message, {
                    'batch_id': batch_id, 'file_type': file_type, 'count': count
                })
                await auto_normalize_stamps()
                invalidate_fallback_cache()
                asyncio.create_task(_safe_recompute_summaries())
                meta['status'] = 'complete'
                meta['result'] = {"success": True, "count": count, "replaced_count": deleted_count,
                                  "batch_id": batch_id, "message": message}
            else:
                actual_type = 'sale' if file_type == 'historical_sale' else 'purchase'
                verify_count = await target.count_documents({"batch_id": batch_id})
                logger.info(f"[Upload {upload_id}] Verified {verify_count} historical records for batch {batch_id}")
                meta['status'] = 'complete'
                meta['result'] = {"success": True, "count": verify_count, "year": year,
                                  "message": f"Uploaded {verify_count} historical {actual_type} records for {year}"}

        elif file_type in ('opening_stock', 'master_stock', 'physical_stock'):
            # Small files: parse fully, then process
            parse_future = loop.run_in_executor(_parse_executor, parse_excel_streaming, tmp_path, parse_type)
            records = await _await_with_heartbeat(upload_id, meta, my_attempt, prog, parse_future)
            logger.info(f"[Upload {upload_id}] Parsed {len(records) if records else 0} records")

            if not records:
                meta['status'] = 'error'
                meta['error'] = 'No valid records found in file'
                await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
                await db.upload_chunks.delete_many({"upload_id": upload_id})
                return

            if file_type in ('opening_stock', 'master_stock'):
                merged_items = {}
                for record in records:
                    key = record['item_name'].strip().lower()
                    if key not in merged_items:
                        merged_items[key] = {'item_name': record['item_name'], 'stamp': record.get('stamp', ''),
                            'unit': record.get('unit', ''), 'pc': 0, 'gr_wt': 0.0, 'net_wt': 0.0,
                            'fine': 0.0, 'labor_wt': 0.0, 'labor_rs': 0.0, 'rate': record.get('rate', 0.0), 'total': 0.0}
                    merged_items[key]['gr_wt'] += record.get('gr_wt', 0)
                    merged_items[key]['net_wt'] += record.get('net_wt', 0)
                    merged_items[key]['fine'] += record.get('fine', 0)
                    merged_items[key]['pc'] += record.get('pc', 0)
                    merged_items[key]['total'] += record.get('total', 0)
                    if record.get('stamp') and not merged_items[key]['stamp']:
                        merged_items[key]['stamp'] = record['stamp']
                await db.opening_stock.delete_many({})
                stock_items = [OpeningStock(**item).model_dump() for item in merged_items.values()]
                await db.opening_stock.insert_many(stock_items)
                total_net_wt = sum(i['net_wt'] for i in stock_items)
                eff = await _set_opening_effective_date(meta.get('start_date'))
                await save_action('upload_opening_stock', f"Uploaded {len(stock_items)} merged opening stock items (as on {eff})")
                await auto_normalize_stamps()
                meta['status'] = 'complete'
                meta['result'] = {"success": True, "count": len(stock_items), "effective_date": eff,
                                  "message": f"Opening stock uploaded: {len(stock_items)} items, {total_net_wt/1000:.3f} kg (stock as on {eff})"}
            else:
                verification_date = meta.get('verification_date') or datetime.now(timezone.utc).isoformat()[:10]
                count, message = await _replace_physical_stock_for_date(records, verification_date)
                meta['status'] = 'complete'
                meta['result'] = {"success": True, "count": count,
                                  "verification_date": verification_date, "message": message}
        else:
            meta['status'] = 'error'
            meta['error'] = f"Unsupported file_type: {file_type}"

        await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
        await db.upload_chunks.delete_many({"upload_id": upload_id})

    except Exception as e:
        if prog.get('abort') or str(e) == 'superseded':
            logger.info(f"[Upload {upload_id}] attempt {my_attempt} superseded by a newer attempt, exiting quietly")
            return
        logger.error(f"[Upload {upload_id}] FAILED: {e}", exc_info=True)
        meta['status'] = 'error'
        meta['error'] = str(e)
        try:
            await _save_upload_meta(upload_id, meta, expected_attempts=my_attempt)
            await _rollback_partial_upload(meta)
            await db.upload_chunks.delete_many({"upload_id": upload_id})
        except Exception:
            pass
    finally:
        # Always clean up temp file
        if tmp_path:
            try:
                import os as _os
                _os.unlink(tmp_path)
            except Exception:
                pass


@api_router.post("/upload/finalize/{upload_id}")
async def finalize_chunked_upload(upload_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Reassemble chunks and process the complete file in background"""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    meta = await _load_upload_meta(upload_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Upload session not found")
    if meta.get('owner_username') and meta['owner_username'] != current_user['username']:
        raise HTTPException(status_code=403, detail="Not the owner of this upload session")

    # Verify ALL chunks are present before processing
    chunk_count = await db.upload_chunks.count_documents({"upload_id": upload_id})
    expected = meta.get('total_chunks', 0)
    if chunk_count == 0:
        raise HTTPException(status_code=400, detail="No chunks received")
    if expected > 0 and chunk_count < expected:
        # Find which chunks are missing
        received = set()
        async for doc in db.upload_chunks.find({"upload_id": upload_id}, {"chunk_index": 1, "_id": 0}):
            received.add(doc["chunk_index"])
        missing = [i for i in range(expected) if i not in received]
        raise HTTPException(status_code=400, detail=f"Missing {len(missing)} of {expected} chunks: {missing[:10]}")

    # Mark as processing and kick off background task
    meta['status'] = 'processing'
    meta['attempts'] = 1
    await _save_upload_meta(upload_id, meta)

    background_tasks.add_task(_process_upload, upload_id, meta)

    return {"status": "processing", "upload_id": upload_id,
            "message": "File is being processed. Poll /api/upload/status/{upload_id} for progress."}


@api_router.get("/upload/status/{upload_id}")
async def get_upload_status(upload_id: str, current_user: dict = Depends(get_current_user)):
    """Poll processing status of a chunked upload"""
    meta = await _load_upload_meta(upload_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Upload session not found")
    if meta.get('owner_username') and meta['owner_username'] != current_user['username']:
        raise HTTPException(status_code=403, detail="Not the owner of this upload session")

    status = meta.get('status', 'unknown')

    if status == 'complete':
        result = meta.get('result', {})
        # Clean up session from MongoDB
        await db.upload_sessions.delete_one({"upload_id": upload_id})
        return {"status": "complete", **result}
    elif status == 'error':
        error_detail = meta.get('error', 'Unknown error')
        await db.upload_sessions.delete_one({"upload_id": upload_id})
        return {"status": "error", "detail": error_detail}
    else:
        # Stale heartbeat = the background task died (pod OOM/restart). Try to auto-resume
        # from the stored chunks; only fail out once retry attempts are exhausted.
        hb = meta.get('heartbeat')
        stale = False
        if status == 'processing' and hb:
            try:
                stale = (datetime.now(timezone.utc) - datetime.fromisoformat(hb)).total_seconds() > STALE_HEARTBEAT_SECONDS
            except (ValueError, TypeError):
                stale = False
        if stale:
            if await _try_resume_upload(upload_id):
                return {"status": "processing", "message": "Resuming after server restart..."}
            await _fail_upload_session(meta, "Processing stopped unexpectedly and could not be resumed. Please re-upload the file.")
            await db.upload_sessions.delete_one({"upload_id": upload_id})
            return {"status": "error", "detail": "Processing stopped unexpectedly (server may have run out of memory). Automatic retries were exhausted — please re-upload the file."}
        progress = meta.get('progress', 'Processing...')
        return {"status": "processing", "message": progress}


# ==================== CLIENT-SIDE PARSED UPLOAD (no server-side Excel parsing — OOM-safe) ====================

def _parse_raw_rows(raw_rows: List[Dict], cols: set, file_type: str) -> List[Dict]:
    """Convert pre-parsed row dicts (from SheetJS in browser) to transaction records.
    Reuses the same column-mapping logic as parse_excel_file but without pandas/openpyxl."""
    KG_TO_GRAMS = 1000
    records = []

    if file_type == 'purchase':
        item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name'])
        type_col = _resolve_col(cols, ['Type', 'type'])
        tag_col = _resolve_col(cols, ['Tag.No.', 'Tag No', 'tag no'])
        wt_rs_col = _resolve_col(cols, ['Wt/Rs', 'Wt Rs'])
        total_col = _resolve_col(cols, ['Total', 'total'])
        tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
        wstg_col = _resolve_col(cols, ['Wstg', 'wstg'])
        date_col = _resolve_col(cols, ['Date', 'date'])
        refno_col = _resolve_col(cols, ['Refno', 'refno', 'Ref No'])
        party_col = _resolve_col(cols, ['Party Name', 'party name', 'Party'])
        stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
        gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
        net_col = _resolve_col(cols, ['Net.Wt.', 'Net Wt'])
        fine_col = _resolve_col(cols, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'])
        dia_col = _resolve_col(cols, ['Dia.Wt.', 'Dia Wt'])
        stn_col = _resolve_col(cols, ['Stn.Wt.', 'Stn Wt'])
        rate_col = _resolve_col(cols, ['Rate', 'rate'])
        pc_col = _resolve_col(cols, ['Pc', 'pc', 'Pieces'])

        for r in raw_rows:
            item_name = _safe_str(r.get(item_col) if item_col else None)
            if len(item_name) < 2:
                continue
            trans_type = _safe_str(r.get(type_col) if type_col else None, 'P').upper()
            if trans_type.isdigit():
                continue
            tag_no = _safe_str(r.get(tag_col) if tag_col else None)
            labor_val, labor_on = parse_labor_value(tag_no)
            wt_rs = r.get(wt_rs_col) if wt_rs_col else None
            if wt_rs and str(wt_rs).replace('.', '').isdigit():
                labor_val = float(wt_rs)
            total_amount = _safe_float(r.get(total_col) if total_col else None)
            tunch_v = _safe_float(r.get(tunch_col) if tunch_col else None)
            wstg_v = _safe_float(r.get(wstg_col) if wstg_col else None)
            purchase_tunch = tunch_v + wstg_v
            records.append({
                'date': normalize_date(r.get(date_col) if date_col else ''),
                'type': 'purchase' if trans_type in ('P', 'PURCHASE') else 'purchase_return',
                'refno': _safe_str(r.get(refno_col) if refno_col else None),
                'party_name': _safe_str(r.get(party_col) if party_col else None),
                'item_name': item_name,
                'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                'tag_no': tag_no,
                'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                'labor': labor_val,
                'labor_on': labor_on,
                'dia_wt': _safe_float(r.get(dia_col) if dia_col else None) * KG_TO_GRAMS,
                'stn_wt': _safe_float(r.get(stn_col) if stn_col else None) * KG_TO_GRAMS,
                'tunch': str(purchase_tunch),
                'rate': _safe_float(r.get(rate_col) if rate_col else None),
                'total_pc': _safe_int(r.get(pc_col) if pc_col else None),
                'total_amount': total_amount,
            })

    elif file_type == 'sale':
        item_col = _resolve_col(cols, ['Item Name', 'Particular', 'item name'])
        type_col = _resolve_col(cols, ['Type', 'type'])
        tag_col = _resolve_col(cols, ['Lbr. On Tag.No.', 'Tag.No.', 'Tag No'])
        on_col = _resolve_col(cols, ['On', 'on'])
        total_col = _resolve_col(cols, ['Total', 'total'])
        tunch_col = _resolve_col(cols, ['Tunch', 'tunch'])
        date_col = _resolve_col(cols, ['Date', 'date'])
        refno_col = _resolve_col(cols, ['Refno', 'refno', 'Ref No'])
        party_col = _resolve_col(cols, ['Party Name', 'party name', 'Party'])
        stamp_col = _resolve_col(cols, ['Stamp', 'stamp'])
        gr_col = _resolve_col(cols, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'])
        net_col = _resolve_col(cols, ['Gold Std.', 'Net.Wt.', 'Net Wt'])
        fine_col = _resolve_col(cols, ['Fine', 'Sil.Fine', 'Sil Fine'])
        dia_col = _resolve_col(cols, ['Dia.Wt.', 'Dia Wt'])
        stn_col = _resolve_col(cols, ['Stn.Wt.', 'Stn Wt'])
        taxable_col = _resolve_col(cols, ['Taxable Val.', 'Taxable Value'])
        pc_col = _resolve_col(cols, ['Pc', 'pc'])

        for r in raw_rows:
            item_name = _safe_str(r.get(item_col) if item_col else None)
            if len(item_name) < 2:
                continue
            trans_type = _safe_str(r.get(type_col) if type_col else None, 'S').upper()
            if trans_type.isdigit():
                continue
            tag_no = _safe_str(r.get(tag_col) if tag_col else None)
            labor_val, labor_on = parse_labor_value(tag_no)
            on_val = r.get(on_col) if on_col else None
            if on_val and str(on_val).replace('.', '').isdigit():
                labor_val = float(on_val)
            total_amount = _safe_float(r.get(total_col) if total_col else None)
            sale_tunch = _safe_float(r.get(tunch_col) if tunch_col else None)
            records.append({
                'type': 'sale' if trans_type in ('S', 'SALE') else 'sale_return',
                'date': normalize_date(r.get(date_col) if date_col else ''),
                'refno': _safe_str(r.get(refno_col) if refno_col else None),
                'party_name': _safe_str(r.get(party_col) if party_col else None),
                'item_name': item_name,
                'stamp': normalize_stamp(r.get(stamp_col) if stamp_col else ''),
                'tag_no': tag_no,
                'gr_wt': _safe_float(r.get(gr_col) if gr_col else None) * KG_TO_GRAMS,
                'net_wt': _safe_float(r.get(net_col) if net_col else None) * KG_TO_GRAMS,
                'fine': _safe_float(r.get(fine_col) if fine_col else None) * KG_TO_GRAMS,
                'labor': labor_val,
                'labor_on': labor_on,
                'dia_wt': _safe_float(r.get(dia_col) if dia_col else None) * KG_TO_GRAMS,
                'stn_wt': _safe_float(r.get(stn_col) if stn_col else None) * KG_TO_GRAMS,
                'tunch': str(sale_tunch),
                'total_amount': total_amount,
                'taxable_value': _safe_float(r.get(taxable_col) if taxable_col else None),
                'total_pc': _safe_int(r.get(pc_col) if pc_col else None),
            })
    return records


@api_router.post("/upload/client-batch")
async def client_batch_upload(request: Dict, current_user: dict = Depends(get_current_user)):
    """Accept a batch of pre-parsed rows from client-side Excel reading.
    No file upload, no Excel parsing on server — completely OOM-safe."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    file_type = request.get('file_type')
    if not file_type:
        raise HTTPException(status_code=400, detail="file_type is required")

    batch_id = request.get('batch_id')
    if not batch_id:
        raise HTTPException(status_code=400, detail="batch_id is required")

    headers = request.get('headers', [])
    rows = request.get('rows', [])
    year = request.get('year', '2025')
    is_final = request.get('is_final', False)
    batch_index = request.get('batch_index', 0)

    if not rows:
        if is_final:
            # Final call with no rows — just return totals
            total = await db.historical_transactions.count_documents({"batch_id": batch_id})
            return {"success": True, "batch_records": 0, "total_so_far": total, "message": f"Upload complete. {total} records total."}
        raise HTTPException(status_code=400, detail="No rows in batch")

    # Convert rows (arrays) to dicts using headers
    raw_rows = []
    for row in rows:
        d = {}
        for i, h in enumerate(headers):
            d[h] = str(row[i]).strip() if i < len(row) and row[i] is not None else ''
        raw_rows.append(d)

    # Determine parse type
    parse_type = file_type
    if file_type in ('historical_sale',):
        parse_type = 'sale'
    elif file_type in ('historical_purchase',):
        parse_type = 'purchase'

    # Apply column mapping
    cols = set(headers)
    records = _parse_raw_rows(raw_rows, cols, parse_type)

    if not records:
        return {"success": True, "batch_records": 0, "total_so_far": 0, "message": "No valid records in this batch"}

    # Determine target collection
    is_historical = file_type.startswith('historical_')
    collection = db.historical_transactions if is_historical else db.transactions

    # Prepare and insert
    for rec in records:
        rec['batch_id'] = batch_id
        if is_historical:
            rec['historical_year'] = year
            rec['is_historical'] = True

    docs = _prepare_transactions(records, batch_id)
    await batch_insert(collection, docs)
    inserted_count = len(docs)
    del raw_rows, records, docs
    gc.collect()

    total = await collection.count_documents({"batch_id": batch_id})
    logger.info(f"[Client batch] batch_index={batch_index}, inserted={inserted_count}, total_so_far={total}")

    result = {"success": True, "batch_records": inserted_count, "total_so_far": total}
    if is_final:
        actual_type = parse_type
        result["message"] = f"Uploaded {total} historical {actual_type} records for {year}"
    return result


@api_router.post("/transactions/upload/{file_type}")
async def upload_transaction_file(
    file_type: str, 
    file: UploadFile = File(...),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload purchase, sale, or branch_transfer Excel file"""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    if file_type not in ['purchase', 'sale', 'branch_transfer']:
        raise HTTPException(status_code=400, detail="file_type must be 'purchase', 'sale', or 'branch_transfer'")
    
    content = await file.read()
    
    # Parse in thread pool so we don't block the event loop
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(_parse_executor, parse_excel_file, content, file_type)
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")
    
    batch_id = str(uuid.uuid4())
    
    # DELETE only dates that exist in the new file (prevents losing data for dates not in the file)
    deleted_count = 0
    if file_type == 'branch_transfer':
        delete_types = ['issue', 'receive']
    else:
        delete_types = [file_type, f"{file_type}_return"]

    new_dates = sorted(set(r.get('date', '') for r in records if r.get('date')))
    if new_dates:
        # Backup replaced records for undo (dated + no-date ghost rows of this type)
        repl_q = {"type": {"$in": delete_types}, "date": {"$in": new_dates + ["", None]}}
        await _backup_replaced_records(batch_id, repl_q)
        delete_result = await db.transactions.delete_many(repl_q)
        deleted_count = delete_result.deleted_count
    
    # Prepare and batch-insert
    transactions = _prepare_transactions(records, batch_id)
    await batch_insert(db.transactions, transactions)
    
    dates_str = f"{new_dates[0]} to {new_dates[-1]}" if new_dates else "unknown"
    message = f"Uploaded {len(transactions)} {file_type} records for {dates_str}"
    if deleted_count > 0:
        message += f" (replaced {deleted_count} old records)"
    
    await save_action(
        f'upload_{file_type}',
        message,
        {
            'batch_id': batch_id,
            'file_name': file.filename,
            'file_type': file_type,
            'count': len(transactions),
            'start_date': start_date,
            'end_date': end_date
        }
    )
    
    # Auto-normalize stamps after upload
    await auto_normalize_stamps()
    
    return {
        "success": True,
        "count": len(transactions),
        "replaced_count": deleted_count,
        "batch_id": batch_id,
        "message": message
    }

@api_router.get("/executive/my-entries/{username}")
async def get_executive_entries(username: str, current_user: dict = Depends(get_current_user)):
    """Get stock entries by an executive — latest per stamp shown first"""
    # Only allow viewing own entries, or admin/manager can view any
    if current_user['username'] != username and current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Can only view your own entries")
    entries = await db.stock_entries.find(
        {'entered_by': username},
        {"_id": 0}
    ).sort('entry_date', -1).to_list(500)
    
    # Return latest entry per stamp (deduplicate by stamp, keep most recent)
    seen_stamps = set()
    latest_entries = []
    for e in entries:
        stamp = e.get('stamp', '')
        if stamp not in seen_stamps:
            seen_stamps.add(stamp)
            latest_entries.append(e)
    return latest_entries

@api_router.put("/executive/update-entry/{stamp}")
async def update_stock_entry(
    stamp: str,
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Update a rejected stock entry (same day only)"""
    entries = request.get('entries', [])
    verification_date = request.get('verification_date')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    update_fields = {
        'entries': entries,
        'entry_date': datetime.now(timezone.utc).isoformat(),
        'status': 'pending'
    }
    if verification_date:
        update_fields['verification_date'] = verification_date
    
    # Try to update today's entry first, fallback to latest pending/rejected
    result = await db.stock_entries.update_one(
        {'stamp': stamp, 'entered_by': current_user['username'], 'entry_day': today, 'status': {'$in': ['pending', 'rejected']}},
        {'$set': update_fields}
    )
    
    if result.modified_count == 0:
        # Fallback: update the latest pending/rejected entry for this stamp
        fallback_fields = {
            'entries': entries,
            'entry_date': datetime.now(timezone.utc).isoformat(),
            'entry_day': today,
            'status': 'pending'
        }
        if verification_date:
            fallback_fields['verification_date'] = verification_date
        await db.stock_entries.update_one(
            {'stamp': stamp, 'entered_by': current_user['username'], 'status': {'$in': ['pending', 'rejected']}},
            {'$set': fallback_fields},
            upsert=False
        )
    
    return {'success': True, 'message': 'Entry updated'}

@api_router.get("/manager/all-entries")
async def get_all_entries(current_user: dict = Depends(get_current_user)):
    """Get all stock entries for manager — latest per stamp, sorted by entry_date desc"""
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = await db.stock_entries.find({}, {"_id": 0}).sort('entry_date', -1).to_list(None)
    return entries

@api_router.delete("/executive/delete-entry/{stamp}/{username}")
async def delete_executive_entry(stamp: str, username: str, current_user: dict = Depends(get_current_user)):
    """Delete the latest stock entry for a stamp"""
    if current_user['username'] != username and current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Can only delete your own entries")
    
    # Delete the most recent entry for this stamp by this user
    latest = await db.stock_entries.find_one(
        {'stamp': stamp, 'entered_by': username},
        sort=[('entry_date', -1)]
    )
    if not latest:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    await db.stock_entries.delete_one({'_id': latest['_id']})
    
    return {'success': True, 'message': 'Entry deleted'}

# ==================== EXECUTIVE ENDPOINTS ====================

@api_router.post("/executive/stock-entry")
async def save_executive_stock_entry(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Save stock entry from executive (for manager approval).
    Rules:
    - Same stamp + same day = update existing (overwrite)
    - Different day = new entry (previous day's entry is locked/historical)
    - Approved entries from previous days remain untouched
    - Each stamp shown by its last submission timestamp
    """
    
    if current_user['role'] not in ['executive', 'manager', 'admin', 'sales_manager']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    stamp = request.get('stamp')
    entries = request.get('entries', [])
    entered_by = current_user['username']  # Always use authenticated user, never trust client
    verification_date = request.get('verification_date')  # Date for which stock is being entered
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if not verification_date:
        # Check if there's a rejected entry for this stamp — inherit its verification_date
        rejected = await db.stock_entries.find_one(
            {'stamp': stamp, 'entered_by': entered_by, 'status': 'rejected'},
            {"_id": 0},
            sort=[('entry_date', -1)]
        )
        if rejected and rejected.get('verification_date'):
            verification_date = rejected['verification_date']
        else:
            verification_date = today
    
    # Save stock entry keyed by stamp + user + today's date
    entry_record = {
        'stamp': stamp,
        'entries': entries,
        'entered_by': entered_by,
        'entry_date': datetime.now(timezone.utc).isoformat(),
        'entry_day': today,
        'verification_date': verification_date,
        'status': 'pending',
        'approved_by': None,
        'approved_at': None,
    }
    
    # Check if an entry exists for this stamp + user + today
    existing_today = await db.stock_entries.find_one({
        'stamp': stamp, 'entered_by': entered_by, 'entry_day': today
    })
    
    if existing_today:
        # Same day — overwrite (update values, reset status to pending)
        entry_record['iteration'] = existing_today.get('iteration', 0) + 1
        await db.stock_entries.update_one(
            {'stamp': stamp, 'entered_by': entered_by, 'entry_day': today},
            {'$set': entry_record}
        )
    else:
        # New day — insert new entry (old entries remain as history)
        entry_record['iteration'] = 1
        await db.stock_entries.insert_one(entry_record)
    
    # If there was a same-day approval in stamp_approvals, clear it so manager can re-approve
    await db.stamp_approvals.delete_one({'stamp': stamp, 'approval_day': today})
    
    # Create notification for manager
    await db.notifications.insert_one({
        'id': str(uuid.uuid4()),
        'category': 'stamp',
        'type': 'stock_entry',
        'message': f'{entered_by} submitted stock for {stamp}',
        'severity': 'info',
        'target_user': 'manager',
        'stamp': stamp,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'read': False
    })
    
    # Log to activity log for accountability
    await db.activity_log.insert_one({
        'user': entered_by,
        'user_role': current_user['role'],
        'action_type': 'stock_entry',
        'description': f'Submitted stock for {stamp} ({len(entries)} items)',
        'details': {
            'stamp': stamp,
            'items_count': len(entries),
            'iteration': entry_record['iteration']
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    return {'success': True, 'message': 'Stock entry saved successfully'}

@api_router.get("/manager/approval-details/{stamp}")
async def get_approval_details(stamp: str, verification_date: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get detailed approval data — compares entered stock vs expected closing stock
    for the verification_date. Auto-refreshes when transactions change.
    If verification_date is provided, looks up that specific entry instead of the latest."""
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # If verification_date provided, find the SPECIFIC entry for that date
    if verification_date:
        entry = await db.stock_entries.find_one(
            {'stamp': stamp, 'verification_date': verification_date, 'status': {'$in': ['pending', 'approved']}},
            {"_id": 0},
            sort=[('entry_date', -1)]
        )
    else:
        entry = None
    
    # Fallback: get latest pending or approved entry for this stamp
    if not entry:
        entry = await db.stock_entries.find_one(
            {'stamp': stamp, 'status': {'$in': ['pending', 'approved']}},
            {"_id": 0},
            sort=[('entry_date', -1)]
        )
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    verification_date = entry.get('verification_date', entry.get('entry_day', datetime.now(timezone.utc).strftime('%Y-%m-%d')))
    
    # Get ALL items in this stamp from master
    master_items = await db.master_items.find({'stamp': stamp}, {"_id": 0}).to_list(None)
    master_item_names = {m['item_name'] for m in master_items}
    
    # Create map of entered weights
    entered_map = {}
    for entered in entry.get('entries', []):
        entered_map[entered['item_name']] = entered['gross_wt']
    
    # Calculate expected closing stock for the verification_date
    # Use get_current_inventory (baseline-aware) and extract stamp items
    current_inv = await get_current_inventory_cached(as_of_date=verification_date)
    stamp_items_list = current_inv.get('by_stamp', {}).get(stamp, [])
    closing_stock = {}
    for si in stamp_items_list:
        closing_stock[si['item_name']] = round(si['gr_wt'] / 1000, 3)
    
    # Build comparison for ALL items in stamp
    comparison = []
    total_entered = 0.0
    total_book = 0.0
    
    all_item_names = sorted(master_item_names | set(closing_stock.keys()))
    
    for item_name in all_item_names:
        entered_gross = entered_map.get(item_name, 0.0)
        book_gross = closing_stock.get(item_name, 0.0)
        difference = round(entered_gross - book_gross, 3)
        
        comparison.append({
            'item_name': item_name,
            'entered_gross': entered_gross,
            'book_gross': book_gross,
            'difference': difference,
            'was_entered': item_name in entered_map,
            'is_mapped': item_name not in master_item_names
        })
        
        total_entered += entered_gross
        total_book += book_gross
    
    return {
        'entry': entry,
        'verification_date': verification_date,
        'comparison': comparison,
        'total_items': len(comparison),
        'items_entered': len(entered_map),
        'total_entered': round(total_entered, 3),
        'total_book': round(total_book, 3),
        'total_difference': round(total_entered - total_book, 3)
    }


# ==================== MANAGER ENDPOINTS ====================

@api_router.get("/manager/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(get_current_user)):
    """Get all pending stock entries for manager approval"""
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = await db.stock_entries.find({'status': 'pending'}, {"_id": 0}).to_list(None)
    return entries

@api_router.get("/polythene/all")
async def get_all_polythene_adjustments(current_user: dict = Depends(get_current_user)):
    """Get ALL polythene adjustments from all time (admin and executive)"""
    if current_user['role'] not in ['admin', 'executive', 'sales_manager']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = await db.polythene_adjustments.find({}, {"_id": 0}).sort('created_at', -1).to_list(None)
    return entries

@api_router.get("/polythene/item/{item_name}")
async def get_item_polythene_history(item_name: str, current_user: dict = Depends(get_current_user)):
    """Get all polythene adjustments for a specific item"""
    
    entries = await db.polythene_adjustments.find(
        {'item_name': item_name},
        {"_id": 0}
    ).sort('created_at', -1).to_list(None)
    
    return entries


@api_router.put("/manager/update-verification-date/{stamp}")
async def update_verification_date(stamp: str, request: Dict, current_user: dict = Depends(get_current_user)):
    """Admin/Manager can update verification_date on any entry to recalculate book values"""
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    new_date = request.get('verification_date')
    if not new_date:
        raise HTTPException(status_code=400, detail="verification_date required")
    
    # Find latest entry for this stamp
    entry = await db.stock_entries.find_one(
        {'stamp': stamp, 'status': {'$in': ['pending', 'approved']}},
        sort=[('entry_date', -1)]
    )
    
    if entry:
        await db.stock_entries.update_one(
            {'_id': entry['_id']},
            {'$set': {'verification_date': new_date}}
        )
    else:
        # Try any entry for this stamp
        await db.stock_entries.update_many(
            {'stamp': stamp},
            {'$set': {'verification_date': new_date}}
        )
    
    return {'success': True, 'message': f'Verification date updated to {new_date}'}

@api_router.post("/manager/approve-stamp")
async def approve_stamp(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a stamp's stock entry.
    Only affects the latest pending/approved entry for this stamp.
    Old approved entries from previous days remain untouched.
    """
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Only managers can approve")
    
    stamp = request.get('stamp')
    approve = request.get('approve')
    total_difference = request.get('total_difference', 0)
    verification_date = request.get('verification_date')
    
    # Build query — use verification_date to target the correct entry when multiple exist
    query = {'stamp': stamp, 'status': {'$in': ['pending', 'approved']}}
    if verification_date:
        query['verification_date'] = verification_date
    
    # Get the LATEST pending or approved entry for this stamp (+ verification_date)
    entry = await db.stock_entries.find_one(
        query,
        sort=[('entry_date', -1)]
    )
    
    # Fallback: if verification_date filter returned nothing, try without it but prefer pending
    if not entry and verification_date:
        entry = await db.stock_entries.find_one(
            {'stamp': stamp, 'status': 'pending'},
            sort=[('entry_date', -1)]
        )
    if not entry and verification_date:
        entry = await db.stock_entries.find_one(
            {'stamp': stamp, 'status': {'$in': ['pending', 'approved']}},
            sort=[('entry_date', -1)]
        )
    
    if not entry:
        raise HTTPException(status_code=404, detail="No pending entry found for this stamp")
    
    iteration = entry.get('iteration', 1)
    entry_day = entry.get('entry_day', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Update ONLY this specific entry (by _id to be precise)
    await db.stock_entries.update_one(
        {'_id': entry['_id']},
        {'$set': {
            'status': 'approved' if approve else 'rejected',
            'approved_by': current_user['username'],
            'approved_at': now_iso,
            'rejection_message': request.get('rejection_message', '') if not approve else None
        }}
    )
    
    # If approving, record approval (keyed by stamp + day so previous approvals remain)
    if approve:
        await db.stamp_approvals.update_one(
            {'stamp': stamp, 'approval_day': entry_day},
            {'$set': {
                'stamp': stamp,
                'is_approved': True,
                'approved_by': current_user['username'],
                'approved_at': now_iso,
                'approval_day': entry_day,
                'iterations': iteration,
                'total_difference': total_difference
            }},
            upsert=True
        )
        
        # Also write to stamp_verifications so dashboard sees this as verified
        # Use the entry's verification_date (the date stock was counted FOR), not today
        entry_verification_date = entry.get('verification_date', entry_day)
        diff_kg = total_difference / 1000 if total_difference else 0
        is_match = abs(total_difference) <= 50
        await db.stamp_verifications.update_one(
            {'stamp': stamp, 'verification_date': entry_verification_date},
            {'$set': {
                'stamp': stamp,
                'physical_gross_wt': 0,
                'book_gross_wt': 0,
                'difference': diff_kg,
                'is_match': is_match,
                'verification_date': entry_verification_date,
                'verified_at': now_iso,
                'approved_by': current_user['username']
            }},
            upsert=True
        )
    else:
        # Rejecting — remove today's approval lock only (not historical)
        await db.stamp_approvals.delete_one({'stamp': stamp, 'approval_day': entry_day})
    
    # Notify admin
    is_matching = abs(total_difference) <= 50
    
    if approve:
        if is_matching:
            notification_message = f'{current_user["username"]} approved {stamp} - ✓ MATCHING (Diff: {total_difference/1000:.3f}kg)'
        else:
            notification_message = f'{current_user["username"]} approved {stamp} - ⚠️ NOT MATCHING (Diff: {total_difference/1000:.3f}kg) - APPROVED DESPITE MISMATCH'
    else:
        rejection_msg = request.get('rejection_message', '')
        notification_message = f'{current_user["username"]} rejected {stamp} (Diff: {total_difference/1000:.3f}kg)'
        if rejection_msg:
            notification_message += f' - Message: "{rejection_msg}"'
    
    await db.notifications.insert_one({
        'id': str(uuid.uuid4()),
        'category': 'stamp',
        'type': 'stamp_approval',
        'message': notification_message,
        'severity': 'success' if (approve and is_matching) else 'warning',
        'target_user': entry.get('entered_by', 'admin'),
        'stamp': stamp,
        'details': {
            'approved_by': current_user['username'],
            'iterations': iteration,
            'total_difference_kg': total_difference / 1000,
            'is_matching': is_matching,
            'entered_by': entry.get('entered_by') if entry else 'unknown',
            'action': 'approved' if approve else 'rejected',
            'approved_despite_mismatch': approve and not is_matching,
            'rejection_message': request.get('rejection_message') if not approve else None
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'read': False
    })

    # Also notify admin if the executive's entry was approved/rejected
    if entry.get('entered_by') != 'admin':
        await db.notifications.insert_one({
            'id': str(uuid.uuid4()),
            'category': 'stamp',
            'type': 'stamp_approval',
            'message': notification_message,
            'severity': 'success' if (approve and is_matching) else 'warning',
            'target_user': 'admin',
            'stamp': stamp,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    
    await db.activity_log.insert_one({
        'user': current_user['username'],
        'user_role': current_user['role'],
        'action_type': 'stamp_approval' if approve else 'stamp_rejection',
        'description': f'{"Approved" if approve else "Rejected"} {stamp} by {entry.get("entered_by") if entry else "unknown"} - Diff: {total_difference/1000:.3f}kg',
        'details': {
            'stamp': stamp,
            'action': 'approved' if approve else 'rejected',
            'total_difference_kg': total_difference / 1000,
            'iterations': iteration,
            'entered_by': entry.get('entered_by') if entry else 'unknown'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    _inv_cache.invalidate()
    return {'success': True, 'message': f'{stamp} {"approved" if approve else "rejected"}', 'iterations': iteration}

@api_router.get("/stamp-verification/history")
async def get_stamp_verification_history(current_user: dict = Depends(get_current_user)):
    """Get verification history for all stamps"""
    
    # Get stamps from ALL relevant sources, not just master_items
    stamps_set = set()
    for coll_name in ['master_items', 'opening_stock', 'physical_stock', 'transactions']:
        coll = db[coll_name]
        stamps = await coll.distinct('stamp')
        stamps_set.update(s for s in stamps if s and s != 'Unassigned')
    # Also include stamp_assignments stamps
    sa_stamps = await db.stamp_assignments.distinct('stamp')
    stamps_set.update(s for s in sa_stamps if s and s != 'Unassigned')
    
    all_stamps = sorted(stamps_set, key=stamp_sort_key)
    
    # Get latest verification for each
    history = []
    for stamp in all_stamps:
        
        # Check stamp_verifications first (physical verification)
        latest = await db.stamp_verifications.find_one(
            {'stamp': stamp},
            {"_id": 0},
            sort=[('verified_at', -1)]
        )
        
        # Also check stamp_approvals (manager approval = verification) — get latest
        approval = await db.stamp_approvals.find_one(
            {'stamp': stamp, 'is_approved': True},
            {"_id": 0},
            sort=[('approved_at', -1)]
        )
        
        # Use whichever is more recent
        verified_date = None
        is_match = None
        difference = None
        
        if latest:
            verified_date = latest.get('verification_date')
            is_match = latest.get('is_match')
            raw_diff = latest.get('difference', 0)
            # Normalize difference to kg (could be stored as grams or kg)
            difference = round(raw_diff / 1000, 3) if abs(raw_diff) > 100 else round(raw_diff, 3)
        
        if approval:
            approval_date = approval.get('approved_at', '')
            latest_date = latest.get('verified_at', '') if latest else ''
            if approval_date > latest_date:
                verified_date = approval_date[:10] if approval_date else None
                diff_kg = approval.get('total_difference', 0) / 1000 if approval.get('total_difference') else 0
                is_match = abs(diff_kg) < 0.05
                difference = round(diff_kg, 3)
        
        history.append({
            'stamp': stamp,
            'last_verified_date': verified_date,
            'verified_by': approval.get('approved_by') if approval else (latest.get('verified_at') if latest else None),
            'is_match': is_match,
            'difference': difference
        })
    
    return history

@api_router.get("/notifications/my")
async def get_my_notifications(current_user: dict = Depends(get_current_user)):
    """Get notifications for current user — matches by target_user or role"""
    
    notifications = await db.notifications.find(
        {'$or': [
            {'target_user': current_user['username']},
            {'target_user': current_user['role']},
            {'target_user': 'all'},
            {'for_role': {'$in': [current_user['role'], 'all']}}
        ]},
        {"_id": 0}
    ).sort('timestamp', -1).limit(50).to_list(50)
    
    return notifications

@api_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark notification as read (matches same scope as fetch query)"""
    await db.notifications.update_one(
        {'id': notification_id, '$or': [
            {'target_user': current_user['username']},
            {'target_user': current_user['role']},
            {'target_user': 'all'},
            {'for_role': {'$in': [current_user['role'], 'all']}}
        ]},
        {'$set': {'read': True}}
    )


# ==================== POLYTHENE EXECUTIVE ENDPOINTS ====================

@api_router.post("/polythene/adjust")
async def adjust_polythene(
    item_name: str,
    poly_weight: float,
    operation: str,
    current_user: dict = Depends(get_current_user)
):
    """Adjust polythene weight for an item (gross weight changes, net stays same)"""
    
    if current_user['role'] not in ['polythene_executive', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    actual_user = current_user['username']  # Always use authenticated user
    
    # Dedup: reject if identical entry by same user within 20 seconds
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    existing = await db.polythene_adjustments.find_one({
        'item_name': item_name,
        'poly_weight': poly_weight,
        'operation': operation,
        'adjusted_by': actual_user,
        'created_at': {'$gte': cutoff}
    })
    if existing:
        return {'success': True, 'message': 'Duplicate skipped — identical entry within last 20s', 'duplicate': True}
    
    # Save polythene adjustment
    adjustment = {
        'id': str(uuid.uuid4()),
        'item_name': item_name,
        'poly_weight': poly_weight,
        'operation': operation,
        'adjusted_by': actual_user,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'date': datetime.now(timezone.utc).date().isoformat()
    }
    
    await db.polythene_adjustments.insert_one(adjustment)
    
    await db.notifications.insert_one({
        'id': str(uuid.uuid4()),
        'category': 'polythene',
        'type': 'polythene_adjustment',
        'message': f'{actual_user} {operation}ed {poly_weight} kg polythene for {item_name}',
        'severity': 'info',
        'target_user': 'admin',
        'item_name': item_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'read': False
    })

    await db.activity_log.insert_one({
        'user': actual_user,
        'user_role': current_user['role'],
        'action_type': 'polythene_adjustment',
        'description': f'{operation.upper()} {poly_weight} kg polythene for {item_name}',
        'details': {'item': item_name, 'weight': poly_weight, 'operation': operation},
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    return {'success': True, 'message': 'Polythene adjustment saved'}

@api_router.post("/polythene/adjust-batch")
async def adjust_polythene_batch(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Save multiple polythene adjustments at once"""
    
    if current_user['role'] not in ['polythene_executive', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = request.get('entries', [])
    actual_user = current_user['username']  # Always use authenticated user
    
    # Dedup: check for identical entries by same user within 20 seconds
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    
    saved_entries = []
    skipped = 0
    
    for entry in entries:
        existing = await db.polythene_adjustments.find_one({
            'item_name': entry['item_name'],
            'poly_weight': entry['poly_weight'],
            'operation': entry['operation'],
            'adjusted_by': actual_user,
            'created_at': {'$gte': cutoff}
        })
        if existing:
            skipped += 1
            continue

        adjustment = {
            'id': str(uuid.uuid4()),
            'item_name': entry['item_name'],
            'stamp': entry.get('stamp', ''),
            'poly_weight': entry['poly_weight'],
            'operation': entry['operation'],
            'adjusted_by': actual_user,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'date': datetime.now(timezone.utc).date().isoformat()
        }
        
        saved_entries.append(adjustment)
        
        # Log activity
        await db.activity_log.insert_one({
            'user': actual_user,
            'user_role': current_user['role'],
            'action_type': 'polythene_adjustment',
            'description': f'{entry["operation"].upper()} {entry["poly_weight"]} kg polythene for {entry["item_name"]}',
            'details': entry,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    # Insert all at once
    if saved_entries:
        await db.polythene_adjustments.insert_many(saved_entries)
        await db.notifications.insert_one({
            'id': str(uuid.uuid4()),
            'category': 'polythene',
            'type': 'polythene_batch',
            'message': f'{actual_user} adjusted polythene for {len(saved_entries)} items',
            'severity': 'info',
            'target_user': 'admin',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    
    _inv_cache.invalidate()
    return {
        'success': True,
        'message': f'{len(saved_entries)} polythene adjustments saved',
        'saved': len(saved_entries),
        'skipped': skipped,
        'count': len(saved_entries)
    }

@api_router.get("/polythene/today/{username}")
async def get_today_polythene_entries(username: str, current_user: dict = Depends(get_current_user)):
    """Get ALL polythene entries by user for today (no limit)"""
    if current_user['username'] != username and current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Can only view your own entries")
    today = datetime.now(timezone.utc).date().isoformat()
    
    entries = await db.polythene_adjustments.find(
        {'adjusted_by': username, 'date': today},
        {"_id": 0}
    ).to_list(None)  # Increased limit to 10000
    
    return entries

@api_router.delete("/polythene/{entry_id}")
async def delete_polythene_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a polythene entry (admin or own entry for polythene_executive)"""
    entry = await db.polythene_adjustments.find_one({'id': entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if current_user['role'] == 'admin':
        pass  # admin can delete any entry
    elif current_user['role'] == 'polythene_executive' and entry.get('adjusted_by') == current_user['username']:
        pass  # polythene_executive can delete own entries
    else:
        raise HTTPException(status_code=403, detail="You can only delete your own polythene entries")
    result = await db.polythene_adjustments.delete_one({'id': entry_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    _inv_cache.invalidate()
    return {'success': True}

# ==================== ADMIN ACCOUNTABILITY ====================

@api_router.get("/activity-log")
async def get_activity_log(current_user: dict = Depends(get_current_user)):
    """Get complete activity log for admin accountability"""
    
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    activities = await db.activity_log.find({}, {"_id": 0}).sort('timestamp', -1).limit(200).to_list(200)
    return activities




@api_router.post("/mappings/create-new-item")
async def create_new_item_from_unmapped(
    transaction_name: str,
    stamp: str = "Unassigned",
    current_user: dict = Depends(get_current_user)
):
    """Create a completely new item from unmapped transaction name"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Check for duplicates
    existing = await db.master_items.find_one({"item_name": transaction_name})
    if existing:
        return {'success': False, 'message': f'Item "{transaction_name}" already exists in master items'}
    
    # Add to master_items as new item
    new_item = {
        'item_name': transaction_name,
        'stamp': stamp,
        'gr_wt': 0.0,
        'net_wt': 0.0,
        'is_master': True
    }
    
    await db.master_items.insert_one(new_item)
    
    # Also add to opening_stock with 0 quantity
    new_stock = {
        'item_name': transaction_name,
        'stamp': stamp,
        'unit': 'kg',
        'pc': 0,
        'gr_wt': 0.0,
        'net_wt': 0.0,
        'fine': 0.0,
        'labor_wt': 0.0,
        'labor_rs': 0.0,
        'rate': 0.0,
        'total': 0.0
    }
    
    await db.opening_stock.insert_one(new_stock)
    
    return {'success': True, 'message': f'New item "{transaction_name}" created with stamp: {stamp}'}


@api_router.get("/transactions")
async def get_transactions(type: Optional[str] = None, limit: int = 5000, current_user: dict = Depends(get_current_user)):
    """Get all transactions"""
    query = {} if not type else {"type": type}
    transactions = await db.transactions.find(query, {"_id": 0}).sort("date", -1).to_list(limit)
    return transactions

@api_router.get("/opening-stock/effective-date")
async def get_opening_stock_effective_date_endpoint(current_user: dict = Depends(get_current_user)):
    """The date the opening stock was taken 'as on'. Transactions on/before it don't affect stock."""
    return {"effective_date": await get_opening_effective_date()}


@api_router.put("/opening-stock/effective-date")
async def set_opening_stock_effective_date_endpoint(payload: dict, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    eff = await _set_opening_effective_date(payload.get('effective_date'))
    await save_action('set_opening_effective_date', f"Opening stock effective date set to {eff}")
    return {"success": True, "effective_date": eff}


@api_router.get("/inventory/current")
async def get_current_inventory_endpoint(current_user: dict = Depends(get_current_user)):
    """Calculate current inventory: Opening Stock + Purchases - Sales (cached 30s)"""
    return await get_current_inventory_cached()


@api_router.get("/stock-audit/uploads")
async def get_stock_audit_uploads(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Audit trail: exact net-stock impact of each upload (inserted minus replaced),
    honoring the opening-stock anchor and item baselines, per transaction type."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    batches_meta = await db.transactions.aggregate([
        {"$group": {"_id": "$batch_id", "uploaded_at": {"$min": "$upload_date"}, "rows": {"$sum": 1},
                    "types": {"$addToSet": "$type"}, "date_min": {"$min": "$date"}, "date_max": {"$max": "$date"}}},
        {"$sort": {"uploaded_at": -1}}, {"$limit": limit}
    ]).to_list(None)
    batch_ids = [b['_id'] for b in batches_meta]

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    baselines_raw = await db.inventory_baselines.find({}, {"_id": 0}).to_list(None)
    oed = await get_opening_effective_date()
    baselines = {b['item_key']: b for b in baselines_raw}
    if oed:
        baselines = {k: b for k, b in baselines.items() if b['baseline_date'] >= oed}
    mapping_dict, _, _ = build_group_maps(groups, mappings)
    baseline_by_key = {}
    for bval in baselines.values():
        master = mapping_dict.get(bval['item_name'].strip(), bval['item_name'].strip())
        dk = master.strip().lower()
        if dk not in baseline_by_key or bval['baseline_date'] > baseline_by_key[dk]['baseline_date']:
            baseline_by_key[dk] = bval
    for bval in baselines.values():
        rk = bval['item_key']
        if rk not in baseline_by_key:
            baseline_by_key[rk] = bval

    EXCLUDED = {"SILVER ORNAMENTS"}
    ADD_TYPES = ('purchase', 'purchase_return', 'receive')

    def impact_of(rows):
        counted = skipped = 0
        net = gr = 0.0
        by_type = defaultdict(lambda: {'rows': 0, 'net_wt': 0.0})
        for r in rows:
            name = (r.get('item_name') or '').strip()
            if name in EXCLUDED or name.isdigit():
                continue
            n = r.get('n', 1)
            key = mapping_dict.get(name, name).strip().lower()
            bl = baseline_by_key.get(key)
            cutoff = bl['baseline_date'] if bl else oed
            if cutoff and (r.get('date') or '') <= cutoff:
                skipped += n
                continue
            sign = 1 if r.get('type') in ADD_TYPES else -1
            net += sign * (r.get('net_wt') or 0)
            gr += sign * (r.get('gr_wt') or 0)
            counted += n
            bt = by_type[r.get('type')]
            bt['rows'] += n
            bt['net_wt'] += sign * (r.get('net_wt') or 0)
        return counted, skipped, net, gr, by_type

    grouped = await db.transactions.aggregate([
        {"$match": {"batch_id": {"$in": batch_ids}}},
        {"$group": {"_id": {"b": "$batch_id", "i": "$item_name", "t": "$type", "d": "$date"},
                    "net_wt": {"$sum": "$net_wt"}, "gr_wt": {"$sum": "$gr_wt"}, "n": {"$sum": 1}}}
    ]).to_list(None)
    rows_by_batch = defaultdict(list)
    for g in grouped:
        rows_by_batch[g['_id']['b']].append({
            'item_name': g['_id']['i'], 'type': g['_id']['t'], 'date': g['_id']['d'],
            'net_wt': g['net_wt'], 'gr_wt': g['gr_wt'], 'n': g['n']})

    uploads = []
    for meta in batches_meta:
        bid = meta['_id']
        counted, skipped, in_net, in_gr, by_type = impact_of(rows_by_batch.get(bid, []))
        repl_rows = []
        async for doc in db.replaced_records.find({"batch_id": bid}, {"_id": 0, "records": 1}):
            repl_rows.extend(doc.get('records', []))
        _, _, out_net, out_gr, _ = impact_of(repl_rows)
        uploads.append({
            'batch_id': bid,
            'uploaded_at': meta['uploaded_at'],
            'types': sorted(t for t in meta['types'] if t),
            'date_min': meta['date_min'], 'date_max': meta['date_max'],
            'rows_inserted': meta['rows'], 'rows_replaced': len(repl_rows),
            'rows_counted': counted, 'rows_before_anchor': skipped,
            'inserted_net_kg': round(in_net / 1000, 3),
            'replaced_net_kg': round(out_net / 1000, 3),
            'net_change_kg': round((in_net - out_net) / 1000, 3),
            'gross_change_kg': round((in_gr - out_gr) / 1000, 3),
            'by_type': {t: {'rows': v['rows'], 'net_kg': round(v['net_wt'] / 1000, 3)}
                        for t, v in by_type.items()},
        })
    return {
        'anchor_date': oed,
        'uploads': uploads,
        'total_net_change_kg': round(sum(u['net_change_kg'] for u in uploads), 3),
    }


async def _replace_physical_stock_for_date(records: list, verification_date: str):
    """Shared helper: merge parsed records by (item name + stamp), delete only the selected date's rows,
    insert the new merged rows. Returns (count, message)."""
    merged_items = {}
    for record in records:
        name_key = record['item_name'].strip().lower()
        stamp_val = record.get('stamp', '') or ''
        # Merge by (name + stamp) to preserve separate stamp entries
        if stamp_val and stamp_val != 'Unassigned':
            merge_key = f"{name_key}||{stamp_val.strip().lower()}"
        else:
            merge_key = name_key
        if merge_key not in merged_items:
            merged_items[merge_key] = {
                'item_name': record['item_name'],
                'stamp': stamp_val,
                'pc': 0, 'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'verification_date': verification_date,
            }
        merged_items[merge_key]['gr_wt'] += record.get('gr_wt', 0)
        merged_items[merge_key]['net_wt'] += record.get('net_wt', 0)
        merged_items[merge_key]['fine'] += record.get('fine', 0)
        merged_items[merge_key]['pc'] += record.get('pc', 0)
        if stamp_val and not merged_items[merge_key]['stamp']:
            merged_items[merge_key]['stamp'] = stamp_val

    # Delete ONLY rows for the selected date — other dates untouched
    await db.physical_stock.delete_many({'verification_date': verification_date})

    stock_items = [PhysicalStock(**item).model_dump() for item in merged_items.values()]
    if stock_items:
        await db.physical_stock.insert_many(stock_items)
    await auto_normalize_stamps()

    total_net_wt = sum(i['net_wt'] for i in stock_items)
    message = f"Physical stock snapshot for {verification_date}: {len(stock_items)} items, {total_net_wt/1000:.3f} kg"
    return len(stock_items), message


@api_router.post("/physical-stock/upload")
async def upload_physical_stock(
    file: UploadFile = File(...),
    verification_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload physical stock file — replaces snapshot for the selected verification_date ONLY.
    Rows for other dates are preserved."""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or manager only")
    if not verification_date:
        raise HTTPException(status_code=400, detail="verification_date is required")
    content = await file.read()
    
    try:
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(_parse_executor, parse_excel_file, content, 'physical_stock')
        
        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in file")
        
        count, message = await _replace_physical_stock_for_date(records, verification_date)
        
        return {
            "success": True,
            "count": count,
            "verification_date": verification_date,
            "message": message,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@api_router.post("/physical-stock/upload-preview")
async def upload_physical_stock_preview(
    file: UploadFile = File(...),
    verification_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Parse physical stock file and return a preview diff. Creates a draft session."""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or manager only")

    if not verification_date:
        raise HTTPException(status_code=400, detail="verification_date is required")

    content = await file.read()
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(_parse_executor, parse_excel_file, content, 'physical_stock')

    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")

    has_net = any(r.get('has_net', False) for r in records)
    update_mode = 'gross_and_net' if has_net else 'gross_only'

    uploaded = {}
    for rec in records:
        item_key = rec['item_name'].strip().lower()
        if item_key not in uploaded:
            uploaded[item_key] = {'item_name': rec['item_name'], 'stamp': rec.get('stamp', ''), 'gr_wt': 0.0, 'net_wt': 0.0}
        uploaded[item_key]['gr_wt'] += rec.get('gr_wt', 0)
        uploaded[item_key]['net_wt'] += rec.get('net_wt', 0)

    base = await get_effective_physical_base_for_date(verification_date)
    has_existing_snapshot = await db.physical_stock.count_documents({'verification_date': verification_date}) > 0

    # Build comprehensive name→base_key reverse lookup
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    ps_mapping_dict, _, _ = build_group_maps(all_groups, all_mappings)

    # Step 1: direct base key lookup
    name_to_base_key = {k: k for k in base}

    # Step 2: group members → base key (prefer member's own key; NO leader fallback)
    # Groups are for display only. Each member must resolve to its own base entry.
    for g in all_groups:
        for member in g.get('members', []):
            member_key = member.strip().lower()
            if member_key in base and member_key not in name_to_base_key:
                name_to_base_key[member_key] = member_key

    # Step 3: mapping transaction_name → master_name → base key (individual level only)
    for m in all_mappings:
        txn_key = m['transaction_name'].strip().lower()
        master_name = m['master_name'].strip()
        master_key = master_name.strip().lower()
        # Resolve to the master_name's own base entry (NOT group leader)
        if master_key in base:
            if txn_key not in name_to_base_key:
                name_to_base_key[txn_key] = master_key
            if master_key not in name_to_base_key:
                name_to_base_key[master_key] = master_key

    # Resolve uploaded items to base keys using the comprehensive lookup
    # No longer merges group members — each uploaded item stays as its own row
    resolved_uploads = {}  # base_key -> {base_item, gr_wt, net_wt}
    unmatched_uploads = []
    for item_key, upl in uploaded.items():
        resolved_base_key = name_to_base_key.get(item_key)

        if not resolved_base_key:
            # Fallback: try mapping resolution to master_name (individual level, no leader merge)
            raw_name = upl['item_name'].strip()
            master = ps_mapping_dict.get(raw_name, raw_name)
            master_key = master.strip().lower()
            if master_key in base:
                resolved_base_key = master_key

        if not resolved_base_key:
            unmatched_uploads.append(upl)
            continue

        base_item = base[resolved_base_key]

        # Merge into resolved_uploads keyed by the base entry key
        if resolved_base_key not in resolved_uploads:
            resolved_uploads[resolved_base_key] = {
                'base_item': base_item, 'gr_wt': 0.0, 'net_wt': 0.0,
            }
        resolved_uploads[resolved_base_key]['gr_wt'] += upl['gr_wt']
        resolved_uploads[resolved_base_key]['net_wt'] += upl['net_wt']

    preview_rows = []

    # Unmatched items
    for upl in unmatched_uploads:
        preview_rows.append({
            'item_name': upl['item_name'], 'stamp': upl.get('stamp', ''),
            'update_mode': update_mode, 'is_negative_grouped': False,
            'old_gr_wt': 0, 'new_gr_wt': round(upl['gr_wt'], 3), 'gr_delta': round(upl['gr_wt'], 3),
            'old_net_wt': 0, 'new_net_wt': round(upl['net_wt'], 3) if has_net else 0,
            'net_delta': round(upl['net_wt'], 3) if has_net else 0,
            'status': 'unmatched',
        })

    # Matched items (merged)
    for base_key, merged in resolved_uploads.items():
        base_item = merged['base_item']
        old_gr = base_item.get('gr_wt', 0)
        old_net = base_item.get('net_wt', 0)
        new_gr = round(merged['gr_wt'], 3)
        is_neg_grouped = base_item.get('is_negative_grouped', False)
        new_net = round(old_net, 3) if (is_neg_grouped or not has_net) else round(merged['net_wt'], 3)

        preview_rows.append({
            'item_name': base_item['item_name'], 'stamp': base_item.get('stamp', ''),
            'update_mode': update_mode, 'is_negative_grouped': is_neg_grouped,
            'old_gr_wt': round(old_gr, 3), 'new_gr_wt': new_gr, 'gr_delta': round(new_gr - old_gr, 3),
            'old_net_wt': round(old_net, 3), 'new_net_wt': new_net, 'net_delta': round(new_net - old_net, 3),
            'status': 'pending',
        })

    # Create draft session
    session_id = str(uuid.uuid4())
    draft_items = []
    for r in preview_rows:
        draft_items.append({
            'item_name': r['item_name'], 'stamp': r.get('stamp', ''),
            'status': r['status'], 'update_mode': r.get('update_mode', update_mode),
            'is_negative_grouped': r.get('is_negative_grouped', False),
            'old_gr_wt': r.get('old_gr_wt', 0), 'proposed_gr_wt': r.get('new_gr_wt', 0),
            'final_gr_wt': r.get('old_gr_wt', 0),
            'gr_delta': 0,
            'old_net_wt': r.get('old_net_wt', 0), 'proposed_net_wt': r.get('new_net_wt', 0),
            'final_net_wt': r.get('old_net_wt', 0),
            'net_delta': 0,
        })
    draft_items.sort(key=lambda x: ((x.get('stamp', '') or '').lower(), x['item_name'].lower()))

    await db.physical_stock_update_sessions.insert_one({
        'session_id': session_id,
        'verification_date': verification_date,
        'session_state': 'draft',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'applied_by': current_user['username'],
        'update_mode': update_mode,
        'uploaded_count': len(preview_rows),
        'applied_count': 0, 'rejected_count': 0,
        'unmatched_count': sum(1 for r in preview_rows if r['status'] == 'unmatched'),
        'skipped_count': 0,
        'items': draft_items,
    })

    matched_count = sum(1 for r in preview_rows if r['status'] == 'pending')
    return {
        "success": True,
        "preview_session_id": session_id,
        "update_mode": update_mode,
        "verification_date": verification_date,
        "has_existing_snapshot": has_existing_snapshot,
        "preview_rows": preview_rows,
        "summary": {
            "total_uploaded": len(preview_rows),
            "matched": matched_count,
            "unmatched": sum(1 for r in preview_rows if r['status'] == 'unmatched'),
            "base_item_count": len(base),
        }
    }


@api_router.post("/physical-stock/apply-updates")
async def apply_physical_stock_updates(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Apply approved items within an existing preview session."""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or manager only")

    items = request.get('items', [])
    verification_date = request.get('verification_date')
    preview_session_id = request.get('preview_session_id')

    if not verification_date:
        raise HTTPException(status_code=400, detail="verification_date is required")
    if not items:
        raise HTTPException(status_code=400, detail="No items to apply")

    # Materialize snapshot if needed
    has_snapshot = await db.physical_stock.count_documents({'verification_date': verification_date}) > 0
    if not has_snapshot:
        book_base = await get_effective_physical_base_for_date(verification_date)
        if book_base:
            bulk_docs = [{
                'item_name': bi['item_name'], 'stamp': bi.get('stamp', ''),
                'gr_wt': bi['gr_wt'], 'net_wt': bi['net_wt'],
                'is_negative_grouped': bi.get('is_negative_grouped', False),
                'verification_date': verification_date,
            } for bi in book_base.values()]
            if bulk_docs:
                await db.physical_stock.insert_many(bulk_docs)

    updated_count = 0
    results = []
    applied_items_detail = []
    for item in items:
        item_name = item.get('item_name', '')
        key = item_name.strip().lower()
        update_mode = item.get('update_mode', 'gross_only')
        new_gr = item.get('new_gr_wt', 0)
        new_net = item.get('new_net_wt', 0)
        is_neg_grouped = item.get('is_negative_grouped', False)

        existing = await db.physical_stock.find_one(
            {'item_name': {'$regex': f'^{re.escape(key)}$', '$options': 'i'}, 'verification_date': verification_date},
            {"_id": 0}
        )
        if not existing:
            results.append({'item_name': item_name, 'status': 'skipped', 'reason': 'not_found_for_date'})
            continue

        old_gr = existing.get('gr_wt', 0)
        old_net = existing.get('net_wt', 0)
        update_fields = {'gr_wt': new_gr}
        if is_neg_grouped or update_mode == 'gross_only':
            update_fields['net_wt'] = old_net
        else:
            update_fields['net_wt'] = new_net

        await db.physical_stock.update_one(
            {'item_name': existing['item_name'], 'verification_date': verification_date},
            {'$set': update_fields}
        )
        updated_count += 1
        applied_items_detail.append({
            'item_name': existing['item_name'],
            'old_gr_wt': round(old_gr, 3), 'final_gr_wt': round(new_gr, 3), 'gr_delta': round(new_gr - old_gr, 3),
            'old_net_wt': round(old_net, 3), 'final_net_wt': round(update_fields['net_wt'], 3),
            'net_delta': round(update_fields['net_wt'] - old_net, 3),
        })
        results.append({'item_name': existing['item_name'], 'status': 'applied'})

        # Upsert inventory baseline — physical stock becomes the new starting point
        baseline_key = existing['item_name'].strip().lower()
        await db.inventory_baselines.update_one(
            {'item_key': baseline_key},
            {'$set': {
                'item_key': baseline_key,
                'item_name': existing['item_name'],
                'baseline_date': verification_date,
                'gr_wt': round(new_gr, 3),
                'net_wt': round(update_fields['net_wt'], 3),
                'stamp': existing.get('stamp', ''),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'session_id': preview_session_id or '',
            }},
            upsert=True
        )

    # Update draft session if provided
    if preview_session_id and updated_count > 0:
        session = await db.physical_stock_update_sessions.find_one({'session_id': preview_session_id})
        if session:
            applied_names = {d['item_name'].lower() for d in applied_items_detail}
            updated_items = []
            for si in session.get('items', []):
                name_lower = si['item_name'].strip().lower()
                if name_lower in applied_names and si.get('status') == 'pending':
                    detail = next((d for d in applied_items_detail if d['item_name'].lower() == name_lower), None)
                    if detail:
                        si['status'] = 'applied'
                        si['final_gr_wt'] = detail['final_gr_wt']
                        si['final_net_wt'] = detail['final_net_wt']
                        si['gr_delta'] = detail['gr_delta']
                        si['net_delta'] = detail['net_delta']
                updated_items.append(si)

            applied_rows = [i for i in updated_items if i.get('status') == 'applied']
            await db.physical_stock_update_sessions.update_one(
                {'session_id': preview_session_id},
                {'$set': {
                    'items': updated_items,
                    'applied_count': len(applied_rows),
                    'applied_at': datetime.now(timezone.utc).isoformat(),
                    'applied_by': current_user['username'],
                    'old_total_gr_wt': round(sum(i.get('old_gr_wt', 0) for i in applied_rows), 3),
                    'new_total_gr_wt': round(sum(i.get('final_gr_wt', 0) for i in applied_rows), 3),
                    'gr_delta_total': round(sum(i.get('gr_delta', 0) for i in applied_rows), 3),
                    'old_total_net_wt': round(sum(i.get('old_net_wt', 0) for i in applied_rows), 3),
                    'new_total_net_wt': round(sum(i.get('final_net_wt', 0) for i in applied_rows), 3),
                    'net_delta_total': round(sum(i.get('net_delta', 0) for i in applied_rows), 3),
                }}
            )

    await save_action(
        'physical_stock_partial_update',
        f"Partial physical stock update for {verification_date}: {updated_count} items",
        {'updated_count': updated_count, 'verification_date': verification_date, 'by': current_user['username']}
    )

    return {
        "success": True,
        "updated_count": updated_count,
        "skipped_count": len(items) - updated_count,
        "verification_date": verification_date,
        "results": results,
        "message": f"Physical stock updated for {verification_date}: {updated_count} item{'s' if updated_count != 1 else ''} applied"
    }

@api_router.post("/physical-stock/finalize-session")
async def finalize_physical_stock_session(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Finalize a draft session: remaining pending rows become rejected. Empty sessions get abandoned."""
    session_id = request.get('session_id')
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = await db.physical_stock_update_sessions.find_one({'session_id': session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get('session_state') != 'draft':
        return {"success": True, "message": "Session already finalized"}

    items = session.get('items', [])
    applied_count = sum(1 for i in items if i.get('status') == 'applied')

    if applied_count == 0:
        # Abandon empty session
        await db.physical_stock_update_sessions.update_one(
            {'session_id': session_id},
            {'$set': {'session_state': 'abandoned'}}
        )
        return {"success": True, "message": "Session abandoned (no items applied)"}

    # Mark remaining pending as rejected — reset final weights to old values
    for i in items:
        if i.get('status') == 'pending':
            i['status'] = 'rejected'
            i['final_gr_wt'] = i.get('old_gr_wt', 0)
            i['final_net_wt'] = i.get('old_net_wt', 0)
            i['gr_delta'] = 0
            i['net_delta'] = 0

    rejected_count = sum(1 for i in items if i.get('status') == 'rejected')
    await db.physical_stock_update_sessions.update_one(
        {'session_id': session_id},
        {'$set': {
            'session_state': 'finalized',
            'finalized_at': datetime.now(timezone.utc).isoformat(),
            'items': items,
            'rejected_count': rejected_count,
        }}
    )
    _inv_cache.invalidate()
    return {"success": True, "message": f"Session finalized: {applied_count} applied, {rejected_count} rejected"}

@api_router.post("/physical-stock/update-history/{session_id}/reverse")
async def reverse_physical_stock_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reverse the latest unreversed session for its date. Restores old weights."""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or manager only")

    session = await db.physical_stock_update_sessions.find_one({'session_id': session_id}, {'_id': 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get('is_reversed'):
        raise HTTPException(status_code=400, detail="Session already reversed")
    if session.get('session_state') not in ('finalized', 'draft'):
        raise HTTPException(status_code=400, detail="Only finalized/draft sessions can be reversed")

    v_date = session['verification_date']

    # Check it's the latest unreversed session for this date
    later = await db.physical_stock_update_sessions.find_one({
        'verification_date': v_date,
        'session_state': {'$in': ['finalized', 'draft']},
        'is_reversed': {'$ne': True},
        'applied_at': {'$gt': session.get('applied_at', session.get('created_at', ''))},
    })
    if later:
        raise HTTPException(status_code=400, detail="Cannot reverse: a later unreversed session exists for this date. Reverse the latest session first.")

    # Restore old weights for applied rows
    restored = 0
    for item in session.get('items', []):
        if item.get('status') != 'applied':
            continue
        key = item['item_name'].strip().lower()
        await db.physical_stock.update_one(
            {'item_name': {'$regex': f'^{re.escape(key)}$', '$options': 'i'}, 'verification_date': v_date},
            {'$set': {'gr_wt': item['old_gr_wt'], 'net_wt': item['old_net_wt']}}
        )
        # Remove inventory baseline only if it belongs to THIS session
        existing_bl = await db.inventory_baselines.find_one({'item_key': key}, {'_id': 0})
        if existing_bl and existing_bl.get('session_id') == session_id:
            await db.inventory_baselines.delete_one({'item_key': key})
        elif existing_bl and existing_bl.get('session_id') != session_id:
            pass  # Baseline belongs to a different session — keep it
        else:
            # No session_id recorded or no baseline — safe to delete
            await db.inventory_baselines.delete_one({'item_key': key})
        restored += 1

    await db.physical_stock_update_sessions.update_one(
        {'session_id': session_id},
        {'$set': {
            'is_reversed': True,
            'reversed_at': datetime.now(timezone.utc).isoformat(),
            'reversed_by': current_user['username'],
            'session_state': 'reversed',
        }}
    )

    await save_action(
        'physical_stock_reverse',
        f"Reversed physical stock session for {v_date}: {restored} items restored",
        {'session_id': session_id, 'verification_date': v_date, 'restored': restored, 'by': current_user['username']}
    )

    _inv_cache.invalidate()
    return {"success": True, "restored_count": restored, "message": f"Reversed: {restored} items restored to previous values"}

@api_router.post("/physical-stock/fix-group-baselines")
async def fix_group_baselines(current_user: dict = Depends(get_current_user)):
    """Fix existing group-level baselines by splitting them into member-level baselines.
    Uses get_current_inventory (without baselines) to compute each member's actual
    stock as of the baseline date, then assigns each member its share of the combined
    baseline based on those proportions."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    all_baselines = await db.inventory_baselines.find({}, {"_id": 0}).to_list(None)

    group_leaders = {g['group_name'] for g in all_groups}
    group_members_map = {g['group_name']: g.get('members', []) for g in all_groups}

    # Index all baselines by item_key for quick lookup
    baseline_keys = {bl['item_key'] for bl in all_baselines}

    # Find group-level baselines that need splitting.
    # A baseline is "group-level" ONLY if the leader has a baseline but NOT all members
    # have their own separate baselines. If every member already has its own baseline,
    # the leader's baseline is just its individual entry — skip it.
    to_fix = []
    for bl in all_baselines:
        bl_name = bl['item_name']
        if bl_name in group_leaders and len(group_members_map.get(bl_name, [])) >= 2:
            members = group_members_map[bl_name]
            # Check if all OTHER members (non-leader) already have their own baselines
            non_leader_members = [m for m in members if m != bl_name]
            all_members_have_baselines = all(
                m.strip().lower() in baseline_keys for m in non_leader_members
            )
            if not all_members_have_baselines:
                to_fix.append(bl)

    if not to_fix:
        return {"success": True, "fixed_count": 0, "details": [], "message": "No group-level baselines found"}

    fixed = []
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    for bl in to_fix:
        bl_name = bl['item_name']
        bl_key = bl['item_key']
        members = group_members_map[bl_name]
        baseline_date = bl['baseline_date']
        session_id = bl.get('session_id', '')

        # Temporarily remove this baseline so we can compute raw book stock
        await db.inventory_baselines.delete_one({'item_key': bl_key})

        # Compute inventory as of baseline_date WITHOUT the baseline
        inv = await get_current_inventory_cached(as_of_date=baseline_date)
        all_inv_items = inv.get('inventory', []) + inv.get('negative_items', [])

        # Find the group item and get member-level breakdown
        group_item = next((it for it in all_inv_items if it['item_name'] == bl_name), None)
        member_book = {}
        if group_item and group_item.get('members'):
            for m in group_item['members']:
                member_book[m['item_name']] = {'gr_wt': m['gr_wt'], 'net_wt': m['net_wt']}
        else:
            # Group item exists but no member breakdown — assign all to leader
            if group_item:
                member_book[bl_name] = {'gr_wt': group_item['gr_wt'], 'net_wt': group_item['net_wt']}

        # Compute what the baseline should be for each member:
        # baseline_member = book_member + (baseline_total - book_total) * (book_member / book_total)
        # Simplified: each member's baseline = baseline_total * (book_member / book_total)
        # But better: use book value + proportional delta
        total_book_gr = sum(m['gr_wt'] for m in member_book.values()) or 1
        total_book_net = sum(m['net_wt'] for m in member_book.values()) or 1
        baseline_total_gr = bl['gr_wt']
        baseline_total_net = bl['net_wt']
        delta_gr = baseline_total_gr - total_book_gr
        delta_net = baseline_total_net - total_book_net

        member_baselines = {}
        for m_name in members:
            m_data = member_book.get(m_name, {'gr_wt': 0, 'net_wt': 0})
            # Distribute delta proportionally based on absolute book values
            abs_total = sum(abs(m['gr_wt']) for m in member_book.values()) or 1
            ratio = abs(m_data['gr_wt']) / abs_total if abs_total > 0 else (1.0 / len(members))
            m_baseline_gr = round(m_data['gr_wt'] + delta_gr * ratio, 3)
            m_baseline_net = round(m_data['net_wt'] + delta_net * ratio, 3)

            m_key = m_name.strip().lower()
            await db.inventory_baselines.update_one(
                {'item_key': m_key},
                {'$set': {
                    'item_key': m_key,
                    'item_name': m_name,
                    'baseline_date': baseline_date,
                    'gr_wt': m_baseline_gr,
                    'net_wt': m_baseline_net,
                    'stamp': master_stamp_dict.get(m_name, bl.get('stamp', '')),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'session_id': session_id,
                }},
                upsert=True
            )
            member_baselines[m_name] = m_baseline_gr

        fixed.append({
            'leader': bl_name,
            'members_created': list(member_baselines.keys()),
            'original_gr': bl['gr_wt'],
            'book_at_date': {m: d['gr_wt'] for m, d in member_book.items()},
            'new_baselines': member_baselines,
        })

    return {
        "success": True,
        "fixed_count": len(fixed),
        "details": fixed,
        "message": f"Split {len(fixed)} group-level baseline(s) into member-level baselines"
    }


@api_router.post("/physical-stock/restore-group-baselines")
async def restore_group_baselines(current_user: dict = Depends(get_current_user)):
    """One-time fix: Delete all member baselines for groups, restore the original
    group-level baseline from the physical_stock session, then run the split once.
    This fixes double-split corruption."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    group_members_map = {g['group_name']: g.get('members', []) for g in all_groups}
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    results = []
    for gname, members in group_members_map.items():
        if len(members) < 2:
            continue

        # Delete ALL baselines for this group's members
        deleted = 0
        for m in members:
            m_key = m.strip().lower()
            r = await db.inventory_baselines.delete_many({'item_key': m_key})
            deleted += r.deleted_count

        if deleted == 0:
            continue

        # Find the original physical stock session that created these baselines
        # Look for sessions with verification_date, find any that applied this group's leader
        sessions = await db.physical_stock_update_sessions.find(
            {'session_state': 'finalized', 'is_reversed': {'$ne': True}},
            {'_id': 0}
        ).sort('applied_at', -1).to_list(50)

        # Find the session that has data for this group
        orig_session = None
        orig_gr = 0
        orig_net = 0
        for sess in sessions:
            for item in sess.get('items', []):
                item_name = item.get('item_name', '').strip()
                if item_name == gname and item.get('status') == 'applied':
                    orig_session = sess
                    orig_gr = item.get('final_gr_wt', 0)
                    orig_net = item.get('final_net_wt', 0)
                    break
            if orig_session:
                break

        if not orig_session or (orig_gr == 0 and orig_net == 0):
            results.append({'group': gname, 'status': 'no_session_found', 'deleted': deleted})
            continue

        baseline_date = orig_session['verification_date']

        # Now compute book stock as of baseline_date WITHOUT any baselines
        _inv_cache.invalidate()
        inv = await get_current_inventory_cached(as_of_date=baseline_date)

        # Get member-level book stock from by_stamp (individual level)
        member_book = {}
        for stamp_items in inv.get('by_stamp', {}).values():
            for si in stamp_items:
                if si['item_name'] in members:
                    member_book[si['item_name']] = si.get('gr_wt', 0)

        # Split the original physical stock value proportionally
        total_book = sum(abs(v) for v in member_book.values()) or 1
        member_baselines = {}
        for m_name in members:
            m_book = member_book.get(m_name, 0)
            ratio = abs(m_book) / total_book if total_book > 0 else 1.0 / len(members)
            m_baseline_gr = round(orig_gr * ratio, 3)

            # Net weight: proportional too
            m_baseline_net = round(orig_net * ratio, 3)

            m_key = m_name.strip().lower()
            await db.inventory_baselines.update_one(
                {'item_key': m_key},
                {'$set': {
                    'item_key': m_key,
                    'item_name': m_name,
                    'baseline_date': baseline_date,
                    'gr_wt': m_baseline_gr,
                    'net_wt': m_baseline_net,
                    'stamp': master_stamp_dict.get(m_name, ''),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'session_id': orig_session.get('session_id', ''),
                    'is_member_baseline': True,
                }},
                upsert=True
            )
            member_baselines[m_name] = m_baseline_gr

        results.append({
            'group': gname,
            'original_physical_gr': orig_gr,
            'baseline_date': baseline_date,
            'member_baselines': member_baselines,
            'book_at_date': member_book,
        })

    _inv_cache.invalidate()
    return {"success": True, "results": results}

@api_router.get("/physical-stock/dates")
async def get_physical_stock_dates(current_user: dict = Depends(get_current_user)):
    """Return distinct physical stock verification_date values sorted descending."""
    dates = await db.physical_stock.distinct("verification_date")
    dates = sorted([d for d in dates if d], reverse=True)
    return {"dates": dates}

@api_router.get("/physical-stock/update-history")
async def get_physical_stock_update_history(
    verification_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Return session summaries for physical stock updates (excluding abandoned and empty drafts)."""
    query = {'session_state': {'$in': ['finalized', 'reversed']}}
    if verification_date:
        query['verification_date'] = verification_date
    # Also include drafts that have applied items (still open)
    draft_query = {'session_state': 'draft', 'applied_count': {'$gt': 0}}
    if verification_date:
        draft_query['verification_date'] = verification_date

    finalized = await db.physical_stock_update_sessions.find(
        query, {"_id": 0, "items": 0}
    ).sort("created_at", -1).to_list(100)
    drafts = await db.physical_stock_update_sessions.find(
        draft_query, {"_id": 0, "items": 0}
    ).sort("created_at", -1).to_list(20)
    sessions = drafts + finalized

    # Determine which session is reversible (latest unreversed per date)
    latest_unreversed = {}
    for s in sessions:
        vd = s['verification_date']
        if not s.get('is_reversed') and s.get('session_state') in ('finalized', 'draft') and s.get('applied_count', 0) > 0:
            if vd not in latest_unreversed:
                latest_unreversed[vd] = s['session_id']
    for s in sessions:
        s['reversible'] = s['session_id'] == latest_unreversed.get(s['verification_date'])

    return {"sessions": sessions}

@api_router.get("/physical-stock/update-history/{session_id}")
async def get_physical_stock_update_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Return full session details including sorted item rows."""
    session = await db.physical_stock_update_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@api_router.get("/physical-stock/compare")
async def compare_physical_with_book(verification_date: str, current_user: dict = Depends(get_current_user)):
    """Compare physical stock with book stock for a specific date.
    Book stock = computed closing stock as of verification_date.
    Physical stock = saved snapshot for that date."""
    
    if not verification_date:
        raise HTTPException(status_code=400, detail="verification_date is required")
    
    # Get date-scoped book stock using same identity model as current stock page
    book_base = await _flat_base_from_inventory(verification_date)
    book_items = book_base  # already keyed by normalized name
    
    # Get physical stock snapshot for this date
    physical = await db.physical_stock.find({'verification_date': verification_date}, {"_id": 0}).to_list(None)
    physical_items = {item['item_name'].strip().lower(): item for item in physical}
    
    # Compare
    matches = []
    discrepancies = []
    only_in_book = []
    only_in_physical = []
    
    for key, book_item in book_items.items():
        if key in physical_items:
            phys_item = physical_items[key]
            book_net = book_item['net_wt']
            phys_net = phys_item.get('net_wt', 0)
            book_gross = book_item.get('gr_wt', 0)
            phys_gross = phys_item.get('gr_wt', 0)
            diff_net = phys_net - book_net
            diff_gross = phys_gross - book_gross
            
            comparison = {
                'item_name': book_item['item_name'],
                'stamp': book_item.get('stamp', ''),
                'book_net_wt': book_net,
                'physical_net_wt': phys_net,
                'book_gross_wt': book_gross,
                'physical_gross_wt': phys_gross,
                'difference': diff_net,
                'difference_kg': round(diff_net/1000, 3),
                'gross_difference': diff_gross,
                'gross_difference_kg': round(diff_gross/1000, 3),
                'match_percentage': round((min(abs(book_net), abs(phys_net)) / max(abs(book_net), abs(phys_net)) * 100) if max(abs(book_net), abs(phys_net)) > 0 else 100, 2)
            }
            
            # Use gross difference for classification when net values are identical (gross-only files)
            classify_diff = diff_gross if (abs(diff_net) < 1 and abs(diff_gross) >= 1) else diff_net
            if abs(classify_diff) < 10:
                matches.append(comparison)
            else:
                discrepancies.append(comparison)
        else:
            only_in_book.append({
                'item_name': book_item['item_name'],
                'stamp': book_item.get('stamp', ''),
                'book_net_wt': book_item['net_wt'],
                'book_net_wt_kg': round(book_item['net_wt']/1000, 3)
            })
    
    for key in physical_items:
        if key not in book_items:
            only_in_physical.append({
                'item_name': physical_items[key]['item_name'],
                'stamp': physical_items[key].get('stamp', ''),
                'physical_net_wt': physical_items[key].get('net_wt', 0),
                'physical_net_wt_kg': round(physical_items[key].get('net_wt', 0)/1000, 3)
            })
    
    discrepancies.sort(key=lambda x: abs(x['difference']), reverse=True)
    
    total_book_net = sum(item['net_wt'] for item in book_items.values())
    total_physical_net = sum(item.get('net_wt', 0) for item in physical_items.values())
    total_book_gross = sum(item.get('gr_wt', 0) for item in book_items.values())
    total_physical_gross = sum(item.get('gr_wt', 0) for item in physical_items.values())
    
    return {
        "summary": {
            "total_book_kg": round(total_book_net/1000, 3),
            "total_physical_kg": round(total_physical_net/1000, 3),
            "total_difference_kg": round((total_physical_net - total_book_net)/1000, 3),
            "total_book_gross_kg": round(total_book_gross/1000, 3),
            "total_physical_gross_kg": round(total_physical_gross/1000, 3),
            "total_difference_gross_kg": round((total_physical_gross - total_book_gross)/1000, 3),
            "match_count": len(matches),
            "discrepancy_count": len(discrepancies),
            "only_in_book_count": len(only_in_book),
            "only_in_physical_count": len(only_in_physical)
        },
        "matches": matches[:50],
        "discrepancies": discrepancies[:50],
        "only_in_book": only_in_book[:50],
        "only_in_physical": only_in_physical[:50]
    }

@api_router.get("/history/recent-uploads")
async def get_recent_uploads(current_user: dict = Depends(get_current_user)):
    """Get ALL file uploads for undo selection (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    actions = await db.action_history.find(
        {"action_type": {"$in": [
            "upload_purchase", "upload_sale", "upload_branch_transfer",
            "upload_opening_stock", "upload_master_stock", "upload_physical_stock",
            "client_batch_upload"
        ]}},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(1000)
    
    return actions


@api_router.get("/inventory/stamp-breakdown/{stamp}")
async def get_stamp_breakdown(stamp: str, current_user: dict = Depends(get_current_user)):
    """Get detailed breakdown for a specific stamp using the authoritative inventory calculation"""
    
    # Use the single source of truth: get_current_inventory
    inventory_response = await get_current_inventory_cached()
    all_items = inventory_response.get('inventory', []) + inventory_response.get('negative_items', [])
    
    # Filter items in this stamp
    stamp_items = [item for item in all_items if item.get('stamp') == stamp]
    
    # Calculate totals from inventory
    current_gross = sum(item.get('gr_wt', 0) for item in stamp_items)
    current_net = sum(item.get('net_wt', 0) for item in stamp_items)
    
    # Get opening stock for breakdown display
    opening = await db.opening_stock.find({"stamp": stamp}, {"_id": 0}).to_list(None)
    opening_gross = sum(item.get('gr_wt', 0) for item in opening)
    opening_net = sum(item.get('net_wt', 0) for item in opening)
    
    # Collect all item names (master + mapped) for transaction queries
    item_names = [item['item_name'] for item in stamp_items]
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapped_names = [m['transaction_name'] for m in all_mappings if m['master_name'] in item_names]
    all_names = list(set(item_names + mapped_names))
    
    # Get purchase/sale breakdown for display
    purchases = await db.transactions.find({
        "item_name": {"$in": all_names},
        "type": {"$in": ["purchase", "purchase_return"]}
    }, {"_id": 0, "gr_wt": 1, "net_wt": 1}).to_list(None)
    purchase_gross = sum(t.get('gr_wt', 0) for t in purchases)
    purchase_net = sum(t.get('net_wt', 0) for t in purchases)
    
    sales = await db.transactions.find({
        "item_name": {"$in": all_names},
        "type": {"$in": ["sale", "sale_return"]}
    }, {"_id": 0, "gr_wt": 1, "net_wt": 1}).to_list(None)
    sale_gross = sum(t.get('gr_wt', 0) for t in sales)
    sale_net = sum(t.get('net_wt', 0) for t in sales)
    
    # Count master vs mapped
    master_count = len([i for i in stamp_items if not any(m['transaction_name'] == i['item_name'] for m in all_mappings)])
    mapped_count = len(stamp_items) - master_count
    
    return {
        "stamp": stamp,
        "opening_gross": round(opening_gross, 3),
        "opening_net": round(opening_net, 3),
        "purchase_gross": round(purchase_gross, 3),
        "purchase_net": round(purchase_net, 3),
        "sale_gross": round(sale_gross, 3),
        "sale_net": round(sale_net, 3),
        "current_gross": round(current_gross, 3),
        "current_net": round(current_net, 3),
        "item_count": len(stamp_items),
        "mapped_count": mapped_count
    }


@api_router.post("/admin/normalize-stamps")
async def normalize_all_stamps(current_user: dict = Depends(get_current_user)):
    """Normalize all stamps to CAPS format (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    total_updated = await auto_normalize_stamps()
    
    if total_updated == 0:
        return {"success": True, "message": "All stamps already normalized!", "stamps_updated": 0}
    
    await save_action('normalize_stamps', f'Normalized {total_updated} documents to CAPS format', {'count': total_updated})
    
    return {
        "success": True,
        "message": f"Normalized {total_updated} documents to CAPS format",
        "total_documents": total_updated
    }

@api_router.post("/history/undo-upload")
async def undo_upload(batch_id: str, current_user: dict = Depends(get_current_user)):
    """Undo a specific file upload by batch_id — restores previously replaced data"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Find the action
    action = await db.action_history.find_one({"data_snapshot.batch_id": batch_id})
    if not action:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Delete all transactions with this batch_id
    delete_result = await db.transactions.delete_many({"batch_id": batch_id})
    
    # Restore backed-up records if they exist (may be split across multiple chunked parts)
    restored_count = 0
    backups = await db.replaced_records.find({"batch_id": batch_id}, {"_id": 0}).sort("part", 1).to_list(None)
    old_recs = [r for b in backups for r in b.get("records", [])]
    if old_recs:
        await batch_insert(db.transactions, old_recs)
        restored_count = len(old_recs)
        await db.replaced_records.delete_many({"batch_id": batch_id})
    
    # Mark action as undone
    await db.action_history.update_one(
        {"data_snapshot.batch_id": batch_id},
        {"$set": {"can_undo": False}}
    )
    
    msg = f"Undone: {action.get('description', 'Upload')}. Removed {delete_result.deleted_count} records"
    if restored_count > 0:
        msg += f", restored {restored_count} previous records"
    
    return {
        "success": True,
        "message": msg,
        "deleted_count": delete_result.deleted_count,
        "restored_count": restored_count
    }


@api_router.post("/master-stock/upload")
async def upload_master_stock(file: UploadFile = File(...), effective_date: str = None, current_user: dict = Depends(get_current_user)):
    """Upload STOCK 2026 as master reference - FINAL item names and stamps.
    Also anchors stock: these values become the stock 'as on' effective_date."""
    if current_user['role'] not in ['admin', 'manager', 'uploader']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    content = await file.read()
    
    try:
        import pandas as pd
        df = pd.read_excel(BytesIO(content), header=0)
        df = df.fillna('')
        df.columns = df.columns.str.strip()
        
        # Remove totals row
        df = df[~df['Item Name'].astype(str).str.lower().str.contains('total', na=False)]
        
        # Clear existing opening stock and master items
        await db.opening_stock.delete_many({})
        await db.master_items.delete_many({})
        
        opening_items = []
        master_items = []
        
        for _, row in df.iterrows():
            item_name = str(row.get('Item Name', '')).strip()
            if not item_name or len(item_name) < 2:
                continue
            
            stamp = str(row.get('Stamp', '')).strip()
            gr_wt = float(row.get('Gross weigth', 0) or 0)
            net_wt = float(row.get('Net Weight', 0) or 0)
            
            # Opening stock
            opening_items.append({
                'item_name': item_name,
                'stamp': stamp,
                'unit': 'kg',
                'pc': 0,
                'gr_wt': gr_wt,
                'net_wt': net_wt,
                'fine': 0.0,
                'labor_wt': 0.0,
                'labor_rs': 0.0,
                'rate': 0.0,
                'total': 0.0
            })
            
            # Master reference
            master_items.append({
                'item_name': item_name,
                'stamp': stamp,
                'gr_wt': gr_wt,
                'net_wt': net_wt,
                'is_master': True
            })
        
        await db.opening_stock.insert_many(opening_items)
        await db.master_items.insert_many(master_items)
        
        # Auto-normalize stamps after upload
        await auto_normalize_stamps()
        
        total_net = sum(i['net_wt'] for i in opening_items)
        eff = await _set_opening_effective_date(effective_date)

        return {
            "success": True,
            "count": len(opening_items),
            "total_net_kg": round(total_net / 1000, 3),
            "effective_date": eff,
            "message": f"Master stock uploaded: {len(opening_items)} items, {total_net/1000:.3f} kg (stock as on {eff})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@api_router.post("/purchase-ledger/upload")
async def upload_purchase_ledger(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload PURCHASE_CUMUL file to create/update purchase rate ledger"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    content = await file.read()
    
    try:
        import pandas as pd
        df = pd.read_excel(BytesIO(content), header=2)
        df = df.fillna(0)
        df.columns = df.columns.str.strip()
        
        await db.purchase_ledger.delete_many({})
        
        ledger_items = []
        
        for _, row in df.iterrows():
            item_name = str(row.get('Particular', '')).strip()
            if not item_name or len(item_name) < 2:
                continue
            
            if 'total' in item_name.lower():
                continue
            
            less = float(row.get('Less', 0) or 0)
            sil_fine = float(row.get('Sil.Fine', 0) or 0)
            total = float(row.get('Total', 0) or 0)
            
            if less > 0:
                purchase_tunch = (sil_fine / less * 100)
                labour_per_kg = (total / less)
                
                ledger_items.append({
                    'item_name': item_name,
                    'purchase_tunch': purchase_tunch,
                    'labour_per_kg': labour_per_kg,
                    'total_purchased_kg': less,
                    'total_fine_kg': sil_fine,
                    'total_labour': total
                })
        
        if ledger_items:
            await db.purchase_ledger.insert_many(ledger_items)
        
        return {
            "success": True,
            "count": len(ledger_items),
            "message": f"Purchase ledger created with {len(ledger_items)} items"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@api_router.get("/analytics/customer-profit")
async def get_customer_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Calculate profit per customer (silver & labour).
    Sale returns are treated as purchases — we 'buy back' at the return rate,
    profiting if the return rate is below our purchase cost."""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Get purchase ledger — GROUP AWARE (+ estimated fallback from purchase history)
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    ledger = await fetch_ledger_with_fallback(db, all_groups, all_mappings)
    grp_ledger = build_group_ledger(ledger, all_groups, all_mappings)
    mapping_dict, member_to_leader, _ = build_group_maps(all_groups, all_mappings)
    
    # Group by customer
    customer_profit = defaultdict(lambda: {
        'customer_name': '',
        'silver_profit_kg': 0.0,
        'labour_profit_inr': 0.0,
        'total_sold_kg': 0.0,
        'transaction_count': 0
    })
    
    _cp_proj = {"_id": 0, "party_name": 1, "item_name": 1, "type": 1,
                "net_wt": 1, "tunch": 1, "total_amount": 1, "labor": 1}
    async for txn in db.transactions.find(
            {**query, "type": {"$in": ["sale", "sale_return"]}}, _cp_proj):
        customer = txn.get('party_name', 'Unknown')
        if not customer:
            continue
        
        raw_item_name = txn.get('item_name', '')
        leader_name = resolve_to_leader(raw_item_name, mapping_dict, member_to_leader)
        
        txn_tunch = float(txn.get('tunch', 0) or 0)
        txn_net_wt = txn.get('net_wt', 0)
        txn_total = txn.get('total_amount', 0) or txn.get('labor', 0)  # Total Rs (labour charges)
        is_return = txn['type'] == 'sale_return'
        
        # Get purchase cost from GROUP-AWARE ledger
        ledger_item = grp_ledger.get(leader_name) or grp_ledger.get(raw_item_name)
        if ledger_item is None:
            # No cumulative purchase cost basis -> profit unknowable; skip so
            # discontinued/legacy items can't inflate profit at zero cost
            continue
        purchase_tunch = ledger_item.get('purchase_tunch', 0)
        purchase_cost_per_gram = ledger_item.get('labour_per_kg', 0) / 1000
        
        if is_return:
            # SALE RETURN → treated as PURCHASE from customer
            # We "buy back" goods at return_tunch/return_rate
            # Profit = (our_cost_basis - return_cost) for both silver & labour
            abs_wt = abs(txn_net_wt)
            abs_total = abs(txn_total)
            
            # Silver profit: difference between our purchase cost (what goods are worth to us)
            # and the return tunch (what we're accepting back at)
            # Positive if return_tunch < purchase_tunch (we accepted cheap)
            silver_profit_grams = (purchase_tunch - txn_tunch) * abs_wt / 100
            silver_profit_kg = silver_profit_grams / 1000
            
            # Labour/Total profit: we refund abs_total, goods cost us purchase_cost * weight
            # Positive if we refunded less than goods cost us
            labour_profit = (purchase_cost_per_gram * abs_wt) - abs_total
            
            # Returns reduce the net sold weight
            customer_profit[customer]['total_sold_kg'] -= abs_wt / 1000
        else:
            # REGULAR SALE → profit = (sale_rate - purchase_cost) * weight
            silver_profit_grams = (txn_tunch - purchase_tunch) * txn_net_wt / 100
            silver_profit_kg = silver_profit_grams / 1000
            
            # Labour/Total profit: we charged txn_total, our cost is purchase_cost * weight
            labour_profit = txn_total - (purchase_cost_per_gram * txn_net_wt)
            
            customer_profit[customer]['total_sold_kg'] += txn_net_wt / 1000
        
        customer_profit[customer]['customer_name'] = customer
        customer_profit[customer]['silver_profit_kg'] += silver_profit_kg
        customer_profit[customer]['labour_profit_inr'] += labour_profit
        customer_profit[customer]['transaction_count'] += 1
    
    # Convert to list, round values, and sort
    for v in customer_profit.values():
        v['silver_profit_kg'] = round(v['silver_profit_kg'], 3)
        v['labour_profit_inr'] = round(v['labour_profit_inr'], 2)
        v['total_sold_kg'] = round(v['total_sold_kg'], 3)
    
    customers = sorted(
        [v for v in customer_profit.values()],
        key=lambda x: x['silver_profit_kg'],
        reverse=True
    )
    
    return {
        "customers": customers,
        "total_customers": len(customers)
    }

@api_router.get("/analytics/supplier-profit")
async def get_supplier_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Calculate profit per supplier based on items they supply"""
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Group-aware mappings
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    s_mapping_dict, s_member_to_leader, _ = build_group_maps(all_groups, all_mappings)
    
    def _resolve_supplier(name):
        return resolve_to_leader(name, s_mapping_dict, s_member_to_leader)
    
    # Streamed single pass: per (supplier,item) purchase aggregates + per item sale aggregates
    _sp_proj = {"_id": 0, "party_name": 1, "item_name": 1, "type": 1,
                "net_wt": 1, "tunch": 1, "total_amount": 1, "labor": 1}
    purch_agg = defaultdict(lambda: {'wt': 0.0, 'abs_wt': 0.0, 'tunch_wt': 0.0, 'labour': 0.0, 'n': 0})
    sale_agg = defaultdict(lambda: {'wt': 0.0, 'abs_wt': 0.0, 'tunch_wt': 0.0, 'labour': 0.0, 'n': 0})
    async for trans in db.transactions.find(query, _sp_proj):
        item_name = _resolve_supplier(trans.get('item_name', ''))
        net = trans.get('net_wt', 0) or 0
        a = abs(net)
        tv = abs(trans.get('total_amount', 0) or trans.get('labor', 0) or 0)
        tn = float(trans.get('tunch', 0) or 0)
        if trans['type'] in ['purchase', 'purchase_return'] or (trans['type'] == 'receive' and (tn > 0 or tv > 0)):
            supplier = trans.get('party_name', 'Unknown')
            if not supplier:
                continue
            p = purch_agg[(supplier, item_name)]
            p['wt'] += net; p['abs_wt'] += a; p['tunch_wt'] += tn * a; p['labour'] += tv; p['n'] += 1
        elif trans['type'] in ['sale', 'sale_return']:
            sagg = sale_agg[item_name]
            sagg['wt'] += net; sagg['abs_wt'] += a; sagg['tunch_wt'] += tn * a; sagg['labour'] += tv; sagg['n'] += 1

    supplier_totals = defaultdict(lambda: {'silver': 0.0, 'labor': 0.0, 'purchased_kg': 0.0, 'items': 0})
    for (supplier, item_name), p in purch_agg.items():
        sagg = sale_agg.get(item_name)
        if not sagg or sagg['n'] == 0 or p['n'] == 0:
            continue
        st = supplier_totals[supplier]
        st['items'] += 1
        purchase_wt = p['wt']
        sale_wt = sagg['wt']
        if abs(purchase_wt) < 0.001 or abs(sale_wt) < 0.001:
            continue
        avg_purchase_tunch = p['tunch_wt'] / p['abs_wt'] if p['abs_wt'] else 0
        avg_sale_tunch = sagg['tunch_wt'] / sagg['abs_wt'] if sagg['abs_wt'] else 0
        purchase_labour_per_gram = p['labour'] / p['abs_wt'] if p['abs_wt'] else 0
        sale_labour_per_gram = sagg['labour'] / sagg['abs_wt'] if sagg['abs_wt'] else 0
        st['silver'] += (avg_sale_tunch - avg_purchase_tunch) * purchase_wt / 100 / 1000
        st['labor'] += (sale_labour_per_gram - purchase_labour_per_gram) * purchase_wt
        st['purchased_kg'] += purchase_wt / 1000

    supplier_profits = []
    for supplier, st in supplier_totals.items():
        if st['purchased_kg'] > 0:
            supplier_profits.append({
                'supplier_name': supplier,
                'total_purchased_kg': round(st['purchased_kg'], 3),
                'silver_profit_kg': round(st['silver'], 3),
                'labor_profit_inr': round(st['labor'], 2),
                'items_count': st['items']
            })
    
    supplier_profits.sort(key=lambda x: x['silver_profit_kg'], reverse=True)
    
    return {
        "suppliers": supplier_profits,
        "total_suppliers": len(supplier_profits)
    }


@api_router.get("/purchase-ledger/all")
async def get_purchase_ledger(current_user: dict = Depends(get_current_user)):
    """Get all purchase rate ledger items"""
    ledger = await db.purchase_ledger.find({}, {"_id": 0}).sort("item_name", 1).to_list(None)
    return ledger

@api_router.get("/mappings/unmapped")
async def get_unmapped_items(current_user: dict = Depends(get_current_user)):
    """Get all unmapped items from transactions AND historical_transactions"""
    # Get item names from both collections
    trans_names = set(await db.transactions.distinct('item_name')) | set(
        await db.historical_transactions.distinct('item_name'))
    
    # Get all master item names
    master = await db.master_items.find({}, {"_id": 0, "item_name": 1}).to_list(None)
    master_names = set(m['item_name'] for m in master)
    
    # Get existing mappings
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapped_names = set(m['transaction_name'] for m in mappings)
    
    # Find unmapped: in transactions but not in master and not already mapped
    unmapped = []
    for name in trans_names:
        if name not in master_names and name not in mapped_names:
            # Filter out purely numeric names (e.g., "136" from branch transfer summary lines)
            if name.isdigit():
                continue
            # Filter out test data items
            if name.startswith('TEST_SILVER_ITEM_') or name.startswith('Item ') or name.startswith('Batch'):
                continue
            unmapped.append(name)
    
    return {
        "unmapped_items": sorted(unmapped),
        "count": len(unmapped)
    }

@api_router.post("/mappings/create")
async def create_mapping(transaction_name: str, master_name: str, current_user: dict = Depends(get_current_user)):
    """Create a mapping from transaction name to master name"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    # Verify master name exists
    master = await db.master_items.find_one({"item_name": master_name}, {"_id": 0})
    if not master:
        raise HTTPException(status_code=404, detail="Master item not found")
    
    # Check if mapping already exists
    existing = await db.item_mappings.find_one({"transaction_name": transaction_name})
    if existing:
        # Update existing
        await db.item_mappings.update_one(
            {"transaction_name": transaction_name},
            {"$set": {"master_name": master_name}}
        )
    else:
        # Create new
        mapping = ItemMapping(
            transaction_name=transaction_name,
            master_name=master_name
        )
        await db.item_mappings.insert_one(mapping.model_dump())
    
    return {"success": True, "message": f"Mapped '{transaction_name}' → '{master_name}'"}

@api_router.post("/stamp-verification/save")
async def save_stamp_verification(request: Dict, current_user: dict = Depends(get_current_user)):
    """Save stamp verification record"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    stamp = request.get('stamp', '')
    # Normalize stamp format to match master items
    import re as _re
    _match = _re.search(r'(\d+)', stamp)
    if _match:
        stamp = f'STAMP {_match.group(1)}'
    
    physical_gross_wt = request.get('physical_gross_wt', 0)
    book_gross_wt = request.get('book_gross_wt', 0)
    difference = request.get('difference', 0)
    is_match = request.get('is_match', False)
    verification_date = request.get('verification_date', datetime.now(timezone.utc).isoformat()[:10])
    
    # Save to history
    await save_action(
        'stamp_verification',
        f"{stamp} verified: {'MATCH' if is_match else 'MISMATCH'} (Diff: {difference/1000:.3f} kg)",
        {
            'stamp': stamp,
            'physical_gross_wt': physical_gross_wt,
            'book_gross_wt': book_gross_wt,
            'difference': difference,
            'is_match': is_match,
            'verification_date': verification_date
        }
    )
    
    # Save stamp verification record
    verification = {
        'stamp': stamp,
        'physical_gross_wt': physical_gross_wt,
        'book_gross_wt': book_gross_wt,
        'difference': difference,
        'is_match': is_match,
        'verification_date': verification_date,
        'verified_at': datetime.now(timezone.utc).isoformat(),
        'verified_by': current_user['username']
    }
    
    # Update or insert
    await db.stamp_verifications.update_one(
        {'stamp': stamp, 'verification_date': verification_date},
        {'$set': verification},
        upsert=True
    )
    
    # Check if all stamps verified
    total_stamps = await db.master_items.distinct('stamp')
    verified_stamps = await db.stamp_verifications.distinct('stamp', {'verification_date': verification_date})
    
    notification_msg = f"{stamp} {'matched' if is_match else 'mismatched'}"
    
    if len(verified_stamps) >= len(total_stamps):
        notification_msg += " - ALL STAMPS VERIFIED!"
        
        # Create notification for admin
        await db.notifications.insert_one({
            'id': str(uuid.uuid4()),
            'category': 'stamp',
            'type': 'full_stock_match',
            'message': f'Full stock verification complete for {verification_date}',
            'severity': 'success',
            'target_user': 'admin',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    else:
        # Individual stamp notification
        await db.notifications.insert_one({
            'id': str(uuid.uuid4()),
            'category': 'stamp',
            'type': 'stamp_verification',
            'message': notification_msg,
            'severity': 'warning' if not is_match else 'info',
            'target_user': 'admin',
            'stamp': stamp,
            'is_match': is_match,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    
    return {
        'success': True,
        'message': notification_msg,
        'verified_stamps': len(verified_stamps),
        'total_stamps': len(total_stamps)
    }

@api_router.get("/stamp-verification/all")
async def get_all_verifications(current_user: dict = Depends(get_current_user)):
    """Get all saved stamp verifications with details"""
    verifications = await db.stamp_verifications.find({}, {"_id": 0}).sort("verified_at", -1).to_list(500)
    for v in verifications:
        v['difference_kg'] = round(v.get('difference', 0) / 1000, 3) if abs(v.get('difference', 0)) > 1 else round(v.get('difference', 0), 3)
    return {"verifications": verifications}

@api_router.delete("/stamp-verification/{stamp}/{verification_date}")
async def delete_stamp_verification(stamp: str, verification_date: str, current_user: dict = Depends(get_current_user)):
    """Delete a stamp verification record (admin/manager only)"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    
    # Normalize stamp
    _match = re.search(r'(\d+)', stamp)
    if _match:
        stamp = f'STAMP {_match.group(1)}'
    
    result = await db.stamp_verifications.delete_one({'stamp': stamp, 'verification_date': verification_date})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    await save_action('delete_verification', f"Deleted verification for {stamp} on {verification_date}", user=current_user)
    return {"success": True, "message": f"Verification for {stamp} on {verification_date} deleted"}

@api_router.get("/mappings/all")
async def get_all_mappings(current_user: dict = Depends(get_current_user)):
    """Get all item mappings"""
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    return mappings

@api_router.delete("/mappings/{transaction_name}")
async def delete_mapping(transaction_name: str, current_user: dict = Depends(get_current_user)):
    """Delete a mapping"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.item_mappings.delete_one({"transaction_name": transaction_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"success": True, "message": "Mapping deleted"}

@api_router.get("/master-items")
async def get_master_items(search: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all master items with optional search"""
    query = {}
    if search:
        query = {"item_name": {"$regex": search, "$options": "i"}}
    
    items = await db.master_items.find(query, {"_id": 0}).sort("item_name", 1).to_list(None)
    
    # Return with cache-control headers to prevent browser caching of stamp data
    return JSONResponse(
        content=items,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@api_router.get("/analytics/party-analysis")
async def get_party_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Analyze parties (customers and suppliers) with silver weight comparisons"""
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    customers = defaultdict(lambda: {
        'party_name': '',
        'total_sales_value': 0.0,
        'total_net_wt': 0.0,
        'total_fine_wt': 0.0,
        'total_gr_wt': 0.0,
        'transaction_count': 0
    })
    
    suppliers = defaultdict(lambda: {
        'party_name': '',
        'total_purchases_value': 0.0,
        'total_net_wt': 0.0,
        'total_fine_wt': 0.0,
        'total_gr_wt': 0.0,
        'transaction_count': 0
    })
    
    _pa_proj = {"_id": 0, "party_name": 1, "type": 1, "net_wt": 1, "fine": 1, "gr_wt": 1, "total_amount": 1}
    async for trans in db.transactions.find(query, _pa_proj):
        party = trans.get('party_name', 'Unknown')
        if not party:
            continue
        
        amount = trans.get('total_amount', 0)
        net_wt = trans.get('net_wt', 0)
        fine_wt = trans.get('fine', 0)
        gr_wt = trans.get('gr_wt', 0)
        
        if trans['type'] in ['sale', 'sale_return']:
            multiplier = 1 if trans['type'] == 'sale' else -1
            customers[party]['party_name'] = party
            customers[party]['total_sales_value'] += amount * multiplier
            customers[party]['total_net_wt'] += net_wt * multiplier
            customers[party]['total_fine_wt'] += fine_wt * multiplier
            customers[party]['total_gr_wt'] += gr_wt * multiplier
            customers[party]['transaction_count'] += 1
        
        elif trans['type'] in ['purchase', 'purchase_return']:
            multiplier = 1 if trans['type'] == 'purchase' else -1
            suppliers[party]['party_name'] = party
            suppliers[party]['total_purchases_value'] += amount * multiplier
            suppliers[party]['total_net_wt'] += net_wt * multiplier
            suppliers[party]['total_fine_wt'] += fine_wt * multiplier
            suppliers[party]['total_gr_wt'] += gr_wt * multiplier
            suppliers[party]['transaction_count'] += 1
    
    # Convert to lists, round values, and sort by net weight
    for party_data in list(customers.values()) + list(suppliers.values()):
        party_data['total_net_wt'] = round(party_data['total_net_wt'], 3)
        party_data['total_fine_wt'] = round(party_data['total_fine_wt'], 3)
        party_data['total_gr_wt'] = round(party_data['total_gr_wt'], 3)
        party_data['total_sales_value'] = round(party_data.get('total_sales_value', 0), 2)
        party_data['total_purchases_value'] = round(party_data.get('total_purchases_value', 0), 2)
    
    customers_list = sorted(
        [v for v in customers.values()],
        key=lambda x: x['total_net_wt'],
        reverse=True
    )
    
    suppliers_list = sorted(
        [v for v in suppliers.values()],
        key=lambda x: x['total_net_wt'],
        reverse=True
    )
    
    return {
        "customers": customers_list[:50],
        "suppliers": suppliers_list[:50],
        "top_customer": customers_list[0] if customers_list else None,
        "top_supplier": suppliers_list[0] if suppliers_list else None
    }

@api_router.get("/analytics/sales-summary")
async def get_sales_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get total sales summary with net weight, fine weight, and labour (including returns)"""
    
    # Items to exclude
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]
    
    query = {"type": {"$in": ["sale", "sale_return"]}}
    if start_date and end_date:
        # Add time component to end_date to include full day
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Get ALL sale transactions (S and SR). Apply signed canonicalization so
    # returns subtract regardless of whether DB stored them signed or unsigned.
    def _s(t, field):
        v = abs(t.get(field, 0) or 0)
        return -v if t['type'] == 'sale_return' else v
    
    _ss_proj = {"_id": 0, "item_name": 1, "type": 1, "net_wt": 1, "fine": 1, "total_amount": 1, "labor": 1}
    total_net_wt = total_fine_wt = total_labor = total_sales_value = 0.0
    txn_count = 0
    async for t in db.transactions.find(query, _ss_proj):
        if t.get('item_name') in EXCLUDED_ITEMS:
            continue
        txn_count += 1
        total_net_wt += _s(t, 'net_wt')
        total_fine_wt += _s(t, 'fine')
        total_labor += _s(t, 'total_amount') if t.get('total_amount') else _s(t, 'labor')
        total_sales_value += _s(t, 'total_amount')
    
    return {
        "total_net_wt_kg": round(total_net_wt / 1000, 3),
        "total_fine_wt_kg": round(total_fine_wt / 1000, 3),
        "total_labor": round(total_labor, 2),
        "total_sales_value": round(total_sales_value, 2),
        "transaction_count": txn_count
    }

@api_router.get("/analytics/profit")
async def calculate_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Calculate profit: Silver profit (in kg) and Labour profit (in INR)"""
    
    # Items to exclude from profit calculation
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]
    
    # Get all master items to check for stamps
    master_items = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    master_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in master_items}
    
    # Get item mappings + groups for group-aware resolution
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    p_mapping_dict, p_member_to_leader, _ = build_group_maps(all_groups, mappings)
    
    def _resolve_profit(name):
        return resolve_to_leader(name, p_mapping_dict, p_member_to_leader)
    
    query = {}
    if start_date and end_date:
        # Add time component to end_date to include full day
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Group-aware purchase ledger (+ estimated fallback from purchase history)
    all_ledger = await fetch_ledger_with_fallback(db, all_groups, mappings)
    grp_ledger = build_group_ledger(all_ledger, all_groups, mappings)
    
    # Single streamed pass: filter excluded/unstamped, group by leader, accumulate totals
    _pf_proj = {"_id": 0, "item_name": 1, "type": 1, "date": 1,
                "net_wt": 1, "tunch": 1, "total_amount": 1, "labor": 1}
    item_transactions = defaultdict(lambda: {'purchases': [], 'sales': []})
    total_sales_value = 0.0
    total_purchase_value = 0.0
    async for trans in db.transactions.find(query, _pf_proj):
        trans_name = trans.get('item_name', '')
        leader_name = _resolve_profit(trans_name)
        
        if leader_name in EXCLUDED_ITEMS:
            continue
        
        item_stamp = master_stamps.get(leader_name, master_stamps.get(p_mapping_dict.get(trans_name, trans_name), 'Unassigned'))
        if not item_stamp or item_stamp == 'Unassigned':
            continue
        
        # Signed value totals: returns subtract regardless of DB sign
        _amt = abs(trans.get('total_amount', 0) or 0)
        if trans['type'] in ('sale_return', 'purchase_return'):
            _amt = -_amt
        if trans['type'] in ['sale', 'sale_return']:
            total_sales_value += _amt
        elif trans['type'] in ['purchase', 'purchase_return', 'receive']:
            total_purchase_value += _amt
        
        if not trans_name:
            continue
        item_name = leader_name
        
        # Canonicalize signs: returns always carry negative regardless of DB storage
        sign = -1 if trans['type'] in ('sale_return', 'purchase_return') else 1
        trans_data = {
            'date': trans.get('date'),
            'net_wt': abs(trans.get('net_wt', 0) or 0) * sign,
            'tunch': float(trans.get('tunch', 0) or 0),
            'labor': abs(trans.get('labor', 0) or 0) * sign,
            'total_amount': abs(trans.get('total_amount', 0) or 0) * sign
        }
        
        if trans['type'] in ['purchase', 'purchase_return'] or (trans['type'] == 'receive' and (trans_data['tunch'] > 0 or trans_data['total_amount'] > 0 or trans_data['labor'] > 0)):
            item_transactions[item_name]['purchases'].append(trans_data)
        elif trans['type'] in ['sale', 'sale_return']:
            item_transactions[item_name]['sales'].append(trans_data)
    
    # Calculate profits per user's formula
    total_silver_profit_kg = 0.0  # Silver profit in KG
    total_labor_profit_inr = 0.0  # Labour profit in INR
    item_profits = []
    
    for item_name, data in item_transactions.items():
        sales = data['sales']

        # Skip if no sales
        if not sales:
            continue

        # Cost basis = long-run CUMULATIVE ledger (goods sold now were purchased earlier).
        cb = ledger_cost_basis(grp_ledger, item_name)
        if cb is None:
            continue  # no long-run cost basis -> skip (effectively unassigned)
        cost_tunch, cost_lpg = cb

        # Per-ENTRY silver/labour profit (atom-by-atom) so totals reconcile exactly.
        silver_profit_kg, labor_profit_inr, total_sale_wt, avg_sale_tunch = aggregate_sale_profit(
            sales, cost_tunch, cost_lpg)
        if abs(total_sale_wt) < 0.001:
            continue

        total_silver_profit_kg += silver_profit_kg
        total_labor_profit_inr += labor_profit_inr

        item_profits.append({
            'item_name': item_name,
            'silver_profit_kg': round(silver_profit_kg, 3),
            'labor_profit_inr': round(labor_profit_inr, 2),
            'avg_purchase_tunch': round(cost_tunch, 2),
            'avg_sale_tunch': round(avg_sale_tunch, 2),
            'net_wt_sold_kg': round(total_sale_wt / 1000, 3),
            'cost_basis_source': 'estimated' if (grp_ledger.get(item_name) or {}).get('fallback') else 'ledger'
        })
    
    # Sort by silver profit
    item_profits.sort(key=lambda x: x['silver_profit_kg'], reverse=True)
    
    
    return {
        "silver_profit_kg": round(total_silver_profit_kg, 3),
        "labor_profit_inr": round(total_labor_profit_inr, 2),
        "total_sales_value": round(total_sales_value, 2),
        "total_purchase_value": round(total_purchase_value, 2),
        "all_items": item_profits,
        "total_items_analyzed": len(item_profits)
    }


# ==================== MONTHLY SUMMARY ENDPOINTS ====================

@api_router.get("/analytics/sale-debug-breakdown")
async def sale_debug_breakdown(
    year: int = Query(...),
    month: int = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Debug breakdown of sales sums for a given month.
    Shows raw sums for S and SR rows separately, plus the signed (canonical) net
    used by the UI — so we can verify the 1445/1494 discrepancy transparently.
    """
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    import calendar as _cal
    last_day = _cal.monthrange(year, month)[1]
    q = {'date': {'$gte': f"{year}-{month:02d}-01",
                  '$lte': f"{year}-{month:02d}-{last_day} 23:59:59"},
         'type': {'$in': ['sale', 'sale_return']}}
    txns = await db.transactions.find(q, {"_id": 0, "type": 1, "net_wt": 1,
                                          "fine": 1, "total_amount": 1,
                                          "item_name": 1}).to_list(None)
    
    # Build the SAME filter as /analytics/monthly-profit (excluded + unassigned)
    EXCLUDED = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    m_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    m_master = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    m_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in m_master}
    m_map, m_m2l, _ = build_group_maps(all_groups, m_mappings)
    
    def _inc(name: str) -> bool:
        leader = resolve_to_leader(name, m_map, m_m2l)
        if leader in EXCLUDED:
            return False
        stamp = m_stamps.get(leader, m_stamps.get(m_map.get(name, name), 'Unassigned'))
        return bool(stamp) and stamp != 'Unassigned'
    
    def _raw(t, f):
        return t.get(f, 0) or 0
    
    s = [t for t in txns if t['type'] == 'sale']
    sr = [t for t in txns if t['type'] == 'sale_return']
    
    sale_raw_sum_g = sum(_raw(t, 'net_wt') for t in s)
    sale_return_raw_sum_g = sum(_raw(t, 'net_wt') for t in sr)
    sale_return_abs_sum_g = sum(abs(_raw(t, 'net_wt')) for t in sr)
    
    # Signed canonical: S always + ; SR always -
    def _signed(t, f):
        v = abs(_raw(t, f))
        return -v if t['type'] == 'sale_return' else v
    
    signed_net_total_g = sum(_signed(t, 'net_wt') for t in txns)
    displayed_filtered_g = sum(_signed(t, 'net_wt') for t in txns if _inc(t.get('item_name', '')))
    
    # Also compute how many rows the filter drops
    dropped = [t for t in txns if not _inc(t.get('item_name', ''))]
    dropped_sale_g = sum(_signed(t, 'net_wt') for t in dropped)
    
    return {
        "year": year,
        "month": month,
        "counts": {
            "sale_rows": len(s),
            "sale_return_rows": len(sr),
            "total_rows": len(txns),
            "dropped_by_filter": len(dropped),
        },
        "raw_kg": {
            "sale_raw_sum_kg": round(sale_raw_sum_g / 1000, 3),
            "sale_return_raw_sum_kg": round(sale_return_raw_sum_g / 1000, 3),
            "sale_return_abs_sum_kg": round(sale_return_abs_sum_g / 1000, 3),
        },
        "totals_kg": {
            "signed_net_total_all_items_kg": round(signed_net_total_g / 1000, 3),
            "displayed_net_total_kg": round(displayed_filtered_g / 1000, 3),
            "dropped_by_filter_kg": round(dropped_sale_g / 1000, 3),
        },
        "diagnostics": {
            "sr_storage": "SR rows are " + (
                "stored with NEGATIVE net_wt (Excel sign preserved)"
                if sale_return_raw_sum_g < 0 else
                "stored with POSITIVE net_wt (sign stripped)"
            ),
            "double_negation_would_produce_kg": round(
                (sale_raw_sum_g - sale_return_raw_sum_g) / 1000, 3
            ),
            "canonical_formula": "signed_sale_value(t, f) = abs(v) * (-1 if SR else 1)",
        }
    }


@api_router.get("/analytics/sales-reconciliation")
async def sales_reconciliation(
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Item-by-item sale reconciliation for any date range.

    Emits one row per **raw item name** (as stored in transactions) so the user
    can diff each row against the Tally Excel without any group resolution
    masking discrepancies. Also includes the resolved leader + stamp so mapping
    issues are visible.

    Use this to find:
      * items whose net_wt is wrong because of mapping/duplication
      * items being silently excluded by EXCLUDED_ITEMS or 'Unassigned' filter
      * the precise contribution of returns per item
    """
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    txns = await db.transactions.find({
        'date': {'$gte': start_date, '$lte': end_date + ' 23:59:59'},
        'type': {'$in': ['sale', 'sale_return']}
    }, {"_id": 0, "type": 1, "item_name": 1, "net_wt": 1, "gr_wt": 1,
        "fine": 1, "total_amount": 1, "tunch": 1, "party_name": 1,
        "date": 1, "pc": 1}).to_list(None)

    EXCLUDED = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    rec_maps = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    rec_master = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    rec_stamps = {m['item_name']: (m.get('stamp') or 'Unassigned') for m in rec_master}
    rec_map_dict, rec_m2l, _ = build_group_maps(all_groups, rec_maps)

    def _resolve(name: str) -> str:
        return resolve_to_leader(name, rec_map_dict, rec_m2l)

    def _stamp_for(leader: str, raw: str) -> str:
        return rec_stamps.get(leader, rec_stamps.get(rec_map_dict.get(raw, raw), 'Unassigned'))

    from collections import defaultdict as _dd
    by_raw = _dd(lambda: {
        'raw_item_name': '', 'leader': '', 'stamp': '',
        'is_excluded': False, 'is_unassigned': False,
        'sale_gross_wt_g': 0.0, 'sale_ret_gross_wt_g': 0.0,
        'sale_net_wt_g': 0.0, 'sale_ret_net_wt_g': 0.0,
        'sale_fine_g': 0.0, 'sale_ret_fine_g': 0.0,
        'sale_amount': 0.0, 'sale_ret_amount': 0.0,
        'sale_pc': 0, 'sale_ret_pc': 0,
        'sale_rows': 0, 'sale_ret_rows': 0,
        'customers': set(), 'first_date': '', 'last_date': '',
    })

    for t in txns:
        raw = t.get('item_name', '') or ''
        leader = _resolve(raw)
        stamp = _stamp_for(leader, raw)
        is_excluded = leader in EXCLUDED
        is_unassigned = (not stamp) or stamp == 'Unassigned'

        is_ret = t['type'] == 'sale_return'
        gw = abs(t.get('gr_wt', 0) or 0)
        nw = abs(t.get('net_wt', 0) or 0)
        fw = abs(t.get('fine', 0) or 0)
        amt = abs(t.get('total_amount', 0) or 0)
        pc = int(t.get('pc', 0) or 0)
        dt = (t.get('date') or '')[:10]

        b = by_raw[raw]
        b['raw_item_name'] = raw
        b['leader'] = leader
        b['stamp'] = stamp
        b['is_excluded'] = is_excluded
        b['is_unassigned'] = is_unassigned
        if is_ret:
            b['sale_ret_gross_wt_g'] += gw
            b['sale_ret_net_wt_g'] += nw
            b['sale_ret_fine_g'] += fw
            b['sale_ret_amount'] += amt
            b['sale_ret_pc'] += pc
            b['sale_ret_rows'] += 1
        else:
            b['sale_gross_wt_g'] += gw
            b['sale_net_wt_g'] += nw
            b['sale_fine_g'] += fw
            b['sale_amount'] += amt
            b['sale_pc'] += pc
            b['sale_rows'] += 1
        if t.get('party_name'):
            b['customers'].add(t['party_name'])
        if dt:
            if not b['first_date'] or dt < b['first_date']:
                b['first_date'] = dt
            if not b['last_date'] or dt > b['last_date']:
                b['last_date'] = dt

    rows = []
    grand = {
        'sale_gross_kg': 0.0, 'ret_gross_kg': 0.0,
        'sale_net_kg': 0.0, 'ret_net_kg': 0.0,
        'net_after_returns_kg': 0.0,
        'sale_fine_kg': 0.0, 'ret_fine_kg': 0.0, 'net_fine_kg': 0.0,
        'sale_amount': 0.0, 'ret_amount': 0.0, 'net_amount': 0.0,
        'sale_pc': 0, 'ret_pc': 0,
        'sale_rows': 0, 'ret_rows': 0,
    }
    excluded_totals = dict(net_after_returns_kg=0.0, net_amount=0.0, rows=0)
    unassigned_totals = dict(net_after_returns_kg=0.0, net_amount=0.0, rows=0)

    for raw, b in by_raw.items():
        sale_g_kg = b['sale_gross_wt_g'] / 1000
        ret_g_kg = b['sale_ret_gross_wt_g'] / 1000
        sale_n_kg = b['sale_net_wt_g'] / 1000
        ret_n_kg = b['sale_ret_net_wt_g'] / 1000
        sale_f_kg = b['sale_fine_g'] / 1000
        ret_f_kg = b['sale_ret_fine_g'] / 1000
        net_after_returns_kg = sale_n_kg - ret_n_kg
        net_fine_kg = sale_f_kg - ret_f_kg
        net_amount = b['sale_amount'] - b['sale_ret_amount']
        rows.append({
            'raw_item_name': b['raw_item_name'],
            'leader': b['leader'],
            'stamp': b['stamp'],
            'is_excluded': b['is_excluded'],
            'is_unassigned': b['is_unassigned'],
            'excluded_reason': (
                'EXCLUDED_ITEMS list' if b['is_excluded']
                else ('Unassigned stamp' if b['is_unassigned'] else None)
            ),
            'sale_gross_kg': round(sale_g_kg, 3),
            'ret_gross_kg': round(ret_g_kg, 3),
            'sale_net_kg': round(sale_n_kg, 3),
            'ret_net_kg': round(ret_n_kg, 3),
            'net_after_returns_kg': round(net_after_returns_kg, 3),
            'sale_fine_kg': round(sale_f_kg, 3),
            'ret_fine_kg': round(ret_f_kg, 3),
            'net_fine_kg': round(net_fine_kg, 3),
            'sale_amount': round(b['sale_amount'], 2),
            'ret_amount': round(b['sale_ret_amount'], 2),
            'net_amount': round(net_amount, 2),
            'sale_pc': b['sale_pc'],
            'ret_pc': b['sale_ret_pc'],
            'sale_rows': b['sale_rows'],
            'ret_rows': b['sale_ret_rows'],
            'customers': len(b['customers']),
            'first_date': b['first_date'],
            'last_date': b['last_date'],
        })
        grand['sale_gross_kg'] += sale_g_kg
        grand['ret_gross_kg'] += ret_g_kg
        grand['sale_net_kg'] += sale_n_kg
        grand['ret_net_kg'] += ret_n_kg
        grand['net_after_returns_kg'] += net_after_returns_kg
        grand['sale_fine_kg'] += sale_f_kg
        grand['ret_fine_kg'] += ret_f_kg
        grand['net_fine_kg'] += net_fine_kg
        grand['sale_amount'] += b['sale_amount']
        grand['ret_amount'] += b['sale_ret_amount']
        grand['net_amount'] += net_amount
        grand['sale_pc'] += b['sale_pc']
        grand['ret_pc'] += b['sale_ret_pc']
        grand['sale_rows'] += b['sale_rows']
        grand['ret_rows'] += b['sale_ret_rows']
        if b['is_excluded']:
            excluded_totals['net_after_returns_kg'] += net_after_returns_kg
            excluded_totals['net_amount'] += net_amount
            excluded_totals['rows'] += b['sale_rows'] + b['sale_ret_rows']
        elif b['is_unassigned']:
            unassigned_totals['net_after_returns_kg'] += net_after_returns_kg
            unassigned_totals['net_amount'] += net_amount
            unassigned_totals['rows'] += b['sale_rows'] + b['sale_ret_rows']

    rows.sort(key=lambda r: r['net_after_returns_kg'], reverse=True)

    for k in ('sale_gross_kg', 'ret_gross_kg', 'sale_net_kg', 'ret_net_kg',
              'net_after_returns_kg', 'sale_fine_kg', 'ret_fine_kg', 'net_fine_kg'):
        grand[k] = round(grand[k], 3)
    for k in ('sale_amount', 'ret_amount', 'net_amount'):
        grand[k] = round(grand[k], 2)
    for k in ('net_after_returns_kg', 'net_amount'):
        excluded_totals[k] = round(excluded_totals[k], 3 if 'kg' in k else 2)
        unassigned_totals[k] = round(unassigned_totals[k], 3 if 'kg' in k else 2)

    # Headline counters used for quick Tally tally
    visible_net_kg = round(grand['net_after_returns_kg']
                           - excluded_totals['net_after_returns_kg']
                           - unassigned_totals['net_after_returns_kg'], 3)

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "total_raw_items": len(rows),
        "grand_totals_all_items": grand,
        "excluded_items_totals": excluded_totals,
        "unassigned_stamp_totals": unassigned_totals,
        "visible_net_after_returns_kg": visible_net_kg,
        "tally_comparison_note": (
            "grand_totals_all_items.net_after_returns_kg should match Tally's "
            "Less column total. visible_net_after_returns_kg shows what Profit "
            "Analysis and Dashboard see after EXCLUDED_ITEMS + Unassigned filter."
        ),
        "items": rows,
    }


@api_router.post("/analytics/recompute-summaries")
async def trigger_recompute_summaries(
    request: Optional[Dict] = None,
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger recomputation of monthly summaries (admin only)."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    request = request or {}
    year = request.get('year')
    result = await recompute_monthly_summaries(db, year)
    # Return latest meta for the targeted year (or the most recent year if year=None)
    last_year = year if year else (result.get("years") or [None])[-1]
    meta = await get_year_meta(db, last_year) if last_year else None
    return {
        "success": True,
        "last_computed_at": (meta or {}).get('computed_at'),
        "txn_count": (meta or {}).get('txn_count', 0),
        **result,
    }


@api_router.get("/analytics/summary-status")
async def get_summary_status(
    year: int = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Lightweight freshness probe for the UI.

    Returns the stored fingerprint vs. the live transactions fingerprint so
    the frontend can show 'data is current' / 'X new transactions waiting' UX.
    """
    meta = await get_year_meta(db, year)
    from services.monthly_summary_service import _get_year_fingerprint
    current_count, current_max_created = await _get_year_fingerprint(db, year)
    is_stale = False
    if not meta:
        is_stale = True
    else:
        if meta.get('txn_count') != current_count:
            is_stale = True
        if (meta.get('max_created_at') or '') != (current_max_created or ''):
            is_stale = True
    return {
        "year": year,
        "is_stale": is_stale,
        "last_computed_at": (meta or {}).get('computed_at'),
        "stored_txn_count": (meta or {}).get('txn_count', 0),
        "live_txn_count": current_count,
        "stored_max_created_at": (meta or {}).get('max_created_at'),
        "live_max_created_at": current_max_created,
    }


@api_router.get("/analytics/sales-report")
async def get_sales_report(
    year: Optional[int] = Query(None),
    month: int = Query(0),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Stamp-wise and item-wise sales report for a period.
    
    Period selection:
      * Custom range: pass start_date + end_date (YYYY-MM-DD)
      * Year + Month: pass year, plus month (0 = full year, 1..12 = specific month)
    
    Uses signed_sale_value canonical formula:
      signed = abs(value) * (-1 if sale_return else 1)
    so totals work regardless of how SR rows were stored in DB.
    
    Same exclusion filter as Profit Analysis (EXCLUDED_ITEMS), but Unassigned-
    stamp items ARE included under an "Unassigned" stamp group — the UI uses
    per-stamp checkboxes to include/exclude from totals.
    """
    # Determine date range
    if start_date and end_date:
        sd, ed = start_date, end_date
    elif year is not None:
        import calendar as _cal
        if month == 0:
            sd = f"{year}-01-01"
            ed = f"{year}-12-31"
        else:
            last_day = _cal.monthrange(year, month)[1]
            sd = f"{year}-{month:02d}-01"
            ed = f"{year}-{month:02d}-{last_day:02d}"
    else:
        raise HTTPException(status_code=400, detail="Provide either start_date+end_date or year[+month]")
    
    # Pull sales + sale_returns in range
    txns = await db.transactions.find({
        'date': {'$gte': sd, '$lte': ed + ' 23:59:59'},
        'type': {'$in': ['sale', 'sale_return']}
    }, {"_id": 0, "type": 1, "item_name": 1, "net_wt": 1, "gr_wt": 1,
        "fine": 1, "tunch": 1, "total_amount": 1, "party_name": 1, "date": 1}).to_list(None)
    
    # Build resolution context
    EXCLUDED = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_list = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    stamp_lookup = {m['item_name']: (m.get('stamp') or 'Unassigned') for m in master_list}
    map_dict, m2l, _ = build_group_maps(all_groups, mappings)
    
    def _resolve(name: str) -> str:
        return resolve_to_leader(name, map_dict, m2l)
    
    def _stamp_for(name: str) -> str:
        leader = _resolve(name)
        return stamp_lookup.get(leader, stamp_lookup.get(map_dict.get(name, name), 'Unassigned'))
    
    # Aggregate
    from collections import defaultdict as _dd
    by_stamp = _dd(lambda: {'gross_wt_g': 0.0, 'net_wt_g': 0.0, 'fine_g': 0.0,
                            'total_amount': 0.0, 'tunch_num': 0.0, 'abs_net_g': 0.0,
                            'transactions': 0, 'items': set(), 'sale_kg_g': 0.0,
                            'return_kg_g': 0.0, 'customers': set()})
    by_item = _dd(lambda: {'stamp': '', 'gross_wt_g': 0.0, 'net_wt_g': 0.0, 'fine_g': 0.0,
                           'total_amount': 0.0, 'tunch_num': 0.0, 'abs_net_g': 0.0,
                           'transactions': 0, 'sale_kg_g': 0.0, 'return_kg_g': 0.0,
                           'variants': set()})
    
    excluded_kg_g = 0.0
    excluded_count = 0
    excluded_amount_inr = 0.0
    excluded_fine_g = 0.0
    # Per-item breakdown of what's silently dropped so users can see exactly
    # which "hidden" items account for any Tally vs App gap.
    from collections import defaultdict as _dd2
    excluded_by_item = _dd2(lambda: {'net_g': 0.0, 'amount': 0.0, 'fine_g': 0.0, 'rows': 0})
    
    for t in txns:
        item_raw = t.get('item_name', '')
        leader = _resolve(item_raw)
        if leader in EXCLUDED:
            is_ret_x = t['type'] == 'sale_return'
            sign_x = -1 if is_ret_x else 1
            net_x = abs(t.get('net_wt', 0) or 0) * sign_x
            amt_x = abs(t.get('total_amount', 0) or 0) * sign_x
            fine_x = abs(t.get('fine', 0) or 0) * sign_x
            excluded_kg_g += net_x
            excluded_amount_inr += amt_x
            excluded_fine_g += fine_x
            excluded_count += 1
            eb = excluded_by_item[leader]
            eb['net_g'] += net_x
            eb['amount'] += amt_x
            eb['fine_g'] += fine_x
            eb['rows'] += 1
            continue
        stamp = _stamp_for(item_raw) or 'Unassigned'
        
        is_ret = t['type'] == 'sale_return'
        sign = -1 if is_ret else 1
        abs_net = abs(t.get('net_wt', 0) or 0)
        gw = abs(t.get('gr_wt', 0) or 0) * sign
        nw = abs_net * sign
        fw = abs(t.get('fine', 0) or 0) * sign
        amt = abs(t.get('total_amount', 0) or 0) * sign
        tunch_val = float(t.get('tunch', 0) or 0)
        
        # by stamp
        s = by_stamp[stamp]
        s['gross_wt_g'] += gw
        s['net_wt_g'] += nw
        s['fine_g'] += fw
        s['total_amount'] += amt
        s['tunch_num'] += tunch_val * abs_net
        s['abs_net_g'] += abs_net
        s['transactions'] += 1
        s['items'].add(leader)
        if t.get('party_name'):
            s['customers'].add(t['party_name'])
        if is_ret:
            s['return_kg_g'] += abs_net
        else:
            s['sale_kg_g'] += abs_net
        
        # by item (leader-level — mapped/grouped variants combine here)
        i = by_item[leader]
        i['stamp'] = stamp
        if item_raw and item_raw != leader:
            i['variants'].add(item_raw)
        i['gross_wt_g'] += gw
        i['net_wt_g'] += nw
        i['fine_g'] += fw
        i['total_amount'] += amt
        i['tunch_num'] += tunch_val * abs_net
        i['abs_net_g'] += abs_net
        i['transactions'] += 1
        if is_ret:
            i['return_kg_g'] += abs_net
        else:
            i['sale_kg_g'] += abs_net
    
    def _avg_tunch(d):
        return (d['tunch_num'] / d['abs_net_g']) if d['abs_net_g'] > 0 else 0
    
    def _avg_labour_per_kg(d):
        # avg labour per kg of sold weight (using net absolute weight)
        abs_kg = d['abs_net_g'] / 1000
        return (d['total_amount'] / abs_kg) if abs_kg > 0 else 0
    
    # ---- Stock:Sale ratio = avg day-opening stock ÷ AVG MONTHLY sale ----
    today_s = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
    ed_eff = min(ed, today_s)
    if ed_eff < sd:
        ed_eff = sd
    sd_dt = datetime.strptime(sd, "%Y-%m-%d")
    n_days = (datetime.strptime(ed_eff, "%Y-%m-%d") - sd_dt).days + 1
    months_equiv = max(n_days / 30.44, 0.033)
    
    prev_day = (sd_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    inv = await get_current_inventory_cached(as_of_date=prev_day)
    opening_by_leader = _dd(float)
    for si in inv.get('stamp_items', []):
        ldr = _resolve(si.get('item_name', '') or '')
        if ldr and ldr not in EXCLUDED:
            opening_by_leader[ldr] += si.get('net_wt', 0) or 0
    
    ADD_T = ("purchase", "purchase_return", "receive")
    SUB_T = ("sale", "sale_return", "issue")
    delta_by_leader = _dd(lambda: _dd(float))
    async for t in db.transactions.find(
            {'date': {'$gte': sd, '$lte': ed_eff + ' 23:59:59'},
             'type': {'$in': list(ADD_T + SUB_T)}},
            {"_id": 0, "date": 1, "type": 1, "item_name": 1, "net_wt": 1}):
        raw = t.get('item_name', '') or ''
        if not raw or raw.isdigit():
            continue
        ldr = _resolve(raw)
        if ldr in EXCLUDED:
            continue
        dkey = (t.get('date') or '')[:10]
        w = t.get('net_wt', 0) or 0
        delta_by_leader[ldr][dkey] += w if t['type'] in ADD_T else -w
    
    date_seq = [(sd_dt + timedelta(days=k)).strftime('%Y-%m-%d') for k in range(n_days)]
    avg_stock_by_leader = {}
    for ldr in set(opening_by_leader) | set(delta_by_leader) | set(by_item):
        running = opening_by_leader.get(ldr, 0.0)
        tot = 0.0
        dmap = delta_by_leader.get(ldr) or {}
        for ds in date_seq:
            tot += running
            running += dmap.get(ds, 0.0)
        avg_stock_by_leader[ldr] = tot / n_days
    
    def _ratio(avg_stock_g, net_sale_g):
        monthly_sale_g = net_sale_g / months_equiv
        if monthly_sale_g <= 1:
            return None
        return round(avg_stock_g / monthly_sale_g, 2)
    
    stamp_avg_stock = _dd(float)
    for ldr, st_g in avg_stock_by_leader.items():
        stamp_avg_stock[_stamp_for(ldr) or 'Unassigned'] += st_g
    
    stamps_rows = []
    for stamp_name, d in by_stamp.items():
        stamps_rows.append({
            'stamp': stamp_name,
            'gross_wt_kg': round(d['gross_wt_g'] / 1000, 3),
            'net_wt_kg': round(d['net_wt_g'] / 1000, 3),
            'avg_tunch': round(_avg_tunch(d), 2),
            'avg_labour_per_kg': round(_avg_labour_per_kg(d), 2),
            'stock_sale_ratio': _ratio(stamp_avg_stock.get(stamp_name, 0.0), d['net_wt_g']),
            'avg_stock_kg': round(stamp_avg_stock.get(stamp_name, 0.0) / 1000, 3),
            'total_fine_kg': round(d['fine_g'] / 1000, 3),
            'total_labour_inr': round(d['total_amount'], 2),
            'sale_kg': round(d['sale_kg_g'] / 1000, 3),
            'return_kg': round(d['return_kg_g'] / 1000, 3),
            'transactions': d['transactions'],
            'items_count': len(d['items']),
            'customers_count': len(d['customers']),
        })
    stamps_rows.sort(key=lambda r: r['net_wt_kg'], reverse=True)
    
    items_rows = []
    for item_name, d in by_item.items():
        items_rows.append({
            'item_name': item_name,
            'stamp': d['stamp'],
            'gross_wt_kg': round(d['gross_wt_g'] / 1000, 3),
            'net_wt_kg': round(d['net_wt_g'] / 1000, 3),
            'avg_tunch': round(_avg_tunch(d), 2),
            'avg_labour_per_kg': round(_avg_labour_per_kg(d), 2),
            'stock_sale_ratio': _ratio(avg_stock_by_leader.get(item_name, 0.0), d['net_wt_g']),
            'avg_stock_kg': round(avg_stock_by_leader.get(item_name, 0.0) / 1000, 3),
            'merged_names': sorted(d['variants'])[:10],
            'total_fine_kg': round(d['fine_g'] / 1000, 3),
            'total_labour_inr': round(d['total_amount'], 2),
            'sale_kg': round(d['sale_kg_g'] / 1000, 3),
            'return_kg': round(d['return_kg_g'] / 1000, 3),
            'transactions': d['transactions'],
        })
    items_rows.sort(key=lambda r: r['net_wt_kg'], reverse=True)
    
    # Default totals (ALL stamps included). Frontend will recompute when user
    # toggles per-stamp checkboxes.
    default_totals = {
        'gross_wt_kg': round(sum(r['gross_wt_kg'] for r in stamps_rows), 3),
        'net_wt_kg': round(sum(r['net_wt_kg'] for r in stamps_rows), 3),
        'total_fine_kg': round(sum(r['total_fine_kg'] for r in stamps_rows), 3),
        'total_labour_inr': round(sum(r['total_labour_inr'] for r in stamps_rows), 2),
        'transactions': sum(r['transactions'] for r in stamps_rows),
    }
    
    return {
        'period': {'start_date': sd, 'end_date': ed, 'year': year, 'month': month},
        'by_stamp': stamps_rows,
        'by_item': items_rows,
        'totals': default_totals,
        # Hidden (silently-dropped EXCLUDED_ITEMS): expose weight, labour AND fine
        # so users can see exactly how much sales the Profit/Sales pages mask out.
        'excluded_items_kg': round(excluded_kg_g / 1000, 3),
        'excluded_items_amount_inr': round(excluded_amount_inr, 2),
        'excluded_items_fine_kg': round(excluded_fine_g / 1000, 3),
        'excluded_rows': excluded_count,
        'excluded_items_breakdown': sorted([
            {
                'item_name': name,
                'net_kg': round(v['net_g'] / 1000, 3),
                'amount_inr': round(v['amount'], 2),
                'fine_kg': round(v['fine_g'] / 1000, 3),
                'rows': v['rows'],
            }
            for name, v in excluded_by_item.items()
        ], key=lambda r: r['amount_inr'], reverse=True),
    }


@api_router.get("/analytics/sales-manager-report")
async def get_sales_manager_report(
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Restricted sales view for sales managers: gross + net weight only,
    limited to stamps assigned to the user (stamp_assignments) and to the
    last 2 months (rolling 60 days, extended to cover the full previous month)."""
    if current_user['role'] not in ['sales_manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD")
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    today_dt = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    today_s = today_dt.strftime('%Y-%m-%d')
    first_prev_month = (today_dt.replace(day=1) - timedelta(days=1)).replace(day=1)
    earliest = min(today_dt - timedelta(days=60), first_prev_month).strftime('%Y-%m-%d')
    if start_date < earliest or end_date > today_s:
        raise HTTPException(status_code=400, detail=f"Date range limited to the last 2 months ({earliest} to {today_s})")

    assignments = await db.stamp_assignments.find(
        {'assigned_user': current_user['username']}, {"_id": 0, "stamp": 1}).to_list(None)
    my_stamps = {a['stamp'] for a in assignments}
    restrict = current_user['role'] == 'sales_manager'
    if restrict and not my_stamps:
        return {'period': {'start_date': start_date, 'end_date': end_date},
                'window': {'earliest_allowed': earliest, 'latest_allowed': today_s},
                'assigned_stamps': [], 'no_stamps_assigned': True,
                'by_stamp': [], 'by_item': []}

    EXCLUDED = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_list = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    stamp_lookup = {m['item_name']: (m.get('stamp') or 'Unassigned') for m in master_list}
    map_dict, m2l, _ = build_group_maps(all_groups, mappings)

    from collections import defaultdict as _dd
    by_stamp = _dd(lambda: {'gross_g': 0.0, 'net_g': 0.0})
    by_item = _dd(lambda: {'stamp': '', 'gross_g': 0.0, 'net_g': 0.0})

    async for t in db.transactions.find({
            'date': {'$gte': start_date, '$lte': end_date + ' 23:59:59'},
            'type': {'$in': ['sale', 'sale_return']}},
            {"_id": 0, "type": 1, "item_name": 1, "net_wt": 1, "gr_wt": 1}):
        raw = t.get('item_name', '') or ''
        if not raw or raw.isdigit():
            continue
        leader = resolve_to_leader(raw, map_dict, m2l)
        if leader in EXCLUDED:
            continue
        stamp = stamp_lookup.get(leader, stamp_lookup.get(map_dict.get(raw, raw), 'Unassigned')) or 'Unassigned'
        if restrict and stamp not in my_stamps:
            continue
        sign = -1 if t['type'] == 'sale_return' else 1
        gw = abs(t.get('gr_wt', 0) or 0) * sign
        nw = abs(t.get('net_wt', 0) or 0) * sign
        s = by_stamp[stamp]
        s['gross_g'] += gw
        s['net_g'] += nw
        i = by_item[leader]
        i['stamp'] = stamp
        i['gross_g'] += gw
        i['net_g'] += nw

    stamps_rows = sorted([
        {'stamp': k, 'gross_wt_kg': round(v['gross_g'] / 1000, 3), 'net_wt_kg': round(v['net_g'] / 1000, 3)}
        for k, v in by_stamp.items()], key=lambda r: r['net_wt_kg'], reverse=True)
    items_rows = sorted([
        {'item_name': k, 'stamp': v['stamp'], 'gross_wt_kg': round(v['gross_g'] / 1000, 3), 'net_wt_kg': round(v['net_g'] / 1000, 3)}
        for k, v in by_item.items()], key=lambda r: r['net_wt_kg'], reverse=True)

    return {
        'period': {'start_date': start_date, 'end_date': end_date},
        'window': {'earliest_allowed': earliest, 'latest_allowed': today_s},
        'assigned_stamps': sorted(my_stamps),
        'no_stamps_assigned': False,
        'by_stamp': stamps_rows,
        'by_item': items_rows,
    }


@api_router.get("/analytics/sales-report-drill")
async def get_sales_report_drill(
    name: str = Query(...),
    entity_type: str = Query("item"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Day-wise opening net stock (bars) vs day sales (line) for one item or stamp.

    Stock series: opening stock of each day, seeded from get_current_inventory(as_of =
    day before start) and rolled forward with the stock engine's sign rules
    (purchase/purchase_return/receive ADD raw values; sale/sale_return/issue SUBTRACT).
    Sales series: canonical signed sale weights (returns subtract).
    stock_to_sale_ratio = avg day-opening stock / total period sale — lower is better."""
    if entity_type not in ("item", "stamp"):
        raise HTTPException(status_code=400, detail="entity_type must be item|stamp")
    try:
        sd_dt = datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD")
    # Don't chart future days (IST business dates)
    today_s = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
    ed_eff = min(end_date, today_s)
    if ed_eff < start_date:
        ed_eff = start_date
    ed_dt = datetime.strptime(ed_eff, "%Y-%m-%d")

    EXCLUDED = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_list = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    stamp_lookup = {m['item_name']: (m.get('stamp') or 'Unassigned') for m in master_list}
    map_dict, m2l, _ = build_group_maps(all_groups, mappings)

    def _resolve(n):
        return resolve_to_leader(n, map_dict, m2l)

    def _match(raw_name: str) -> bool:
        leader = _resolve(raw_name)
        if leader in EXCLUDED:
            return False
        if entity_type == 'item':
            return leader == name
        stamp = stamp_lookup.get(leader, stamp_lookup.get(map_dict.get(raw_name, raw_name), 'Unassigned'))
        return (stamp or 'Unassigned') == name

    # Opening stock at range start = closing of the previous day (baseline/anchor aware)
    prev_day = (sd_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    inv = await get_current_inventory_cached(as_of_date=prev_day)
    opening_g = 0.0
    for si in inv.get('stamp_items', []):
        if _match(si.get('item_name', '')):
            opening_g += si.get('net_wt', 0) or 0

    ADD_TYPES = ("purchase", "purchase_return", "receive")
    SUB_TYPES = ("sale", "sale_return", "issue")
    daily_delta = defaultdict(float)  # raw stock delta per day (grams, engine sign rules)
    daily_sold = defaultdict(float)   # canonical signed sale per day (grams)
    async for t in db.transactions.find(
            {'date': {'$gte': start_date, '$lte': ed_eff + ' 23:59:59'},
             'type': {'$in': list(ADD_TYPES + SUB_TYPES)}},
            {"_id": 0, "date": 1, "type": 1, "item_name": 1, "net_wt": 1}):
        raw = t.get('item_name', '') or ''
        if not raw or raw.isdigit() or not _match(raw):
            continue
        d = (t.get('date') or '')[:10]
        if not d:
            continue
        w = t.get('net_wt', 0) or 0
        if t['type'] in ADD_TYPES:
            daily_delta[d] += w
        else:
            daily_delta[d] -= w
        if t['type'] in ('sale', 'sale_return'):
            daily_sold[d] += abs(w) * (-1 if t['type'] == 'sale_return' else 1)

    days = []
    running = opening_g
    stock_sum = 0.0
    total_sold_g = 0.0
    cur = sd_dt
    while cur <= ed_dt:
        ds = cur.strftime('%Y-%m-%d')
        sold = daily_sold.get(ds, 0.0)
        days.append({'date': ds, 'stock_kg': round(running / 1000, 3), 'sold_kg': round(sold / 1000, 3)})
        stock_sum += running
        total_sold_g += sold
        running += daily_delta.get(ds, 0.0)
        cur += timedelta(days=1)

    avg_stock_kg = stock_sum / (len(days) or 1) / 1000
    total_sold_kg = total_sold_g / 1000
    # Ratio uses AVERAGE MONTHLY sale so multi-month ranges aren't diluted
    months_equiv = max((len(days) or 1) / 30.44, 0.033)
    avg_monthly_sale_kg = total_sold_kg / months_equiv
    ratio = round(avg_stock_kg / avg_monthly_sale_kg, 2) if avg_monthly_sale_kg > 0.001 else None
    return {
        'name': name,
        'entity_type': entity_type,
        'start_date': start_date,
        'end_date': ed_eff,
        'days': days,
        'avg_stock_kg': round(avg_stock_kg, 3),
        'total_sold_kg': round(total_sold_kg, 3),
        'avg_monthly_sale_kg': round(avg_monthly_sale_kg, 3),
        'stock_to_sale_ratio': ratio,
    }


@api_router.post("/analytics/find-orphan-transactions")
async def find_orphan_transactions(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Diagnose and fix data discrepancies. Finds duplicate/orphan transactions in a date range."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    start_date = request.get('start_date')  # e.g. "2026-04-01"
    end_date = request.get('end_date')      # e.g. "2026-04-28"
    file_type = request.get('file_type', 'sale')
    delete_orphans = request.get('delete', False)
    
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="start_date and end_date required")
    
    # Map file_type to transaction types
    if file_type == 'branch_transfer':
        types = ['issue', 'receive']
    elif file_type == 'purchase':
        types = ['purchase', 'purchase_return']
    else:
        types = ['sale', 'sale_return']
    
    # Get ALL sale/sale_return transactions in the range
    all_txns = await db.transactions.find(
        {"type": {"$in": types}, "date": {"$gte": start_date, "$lte": end_date + " 23:59:59"}},
        {"_id": 1, "date": 1, "net_wt": 1, "item_name": 1, "type": 1, "batch_id": 1, "refno": 1, "party_name": 1}
    ).to_list(None)
    
    total_net_wt = sum(t.get('net_wt', 0) * (1 if t['type'] in ['sale', 'purchase', 'issue'] else -1) for t in all_txns)
    
    # Group by batch_id
    from collections import defaultdict, Counter
    batch_groups = defaultdict(list)
    for t in all_txns:
        bid = t.get('batch_id', 'NO_BATCH')
        batch_groups[bid].append(t)
    
    batch_summary = []
    for bid, txns in sorted(batch_groups.items(), key=lambda x: -len(x[1])):
        batch_net = sum(t.get('net_wt', 0) * (1 if t['type'] in ['sale', 'purchase', 'issue'] else -1) for t in txns)
        dates = sorted(set(t.get('date', '')[:10] for t in txns))
        batch_summary.append({
            "batch_id": bid[:12] + "..." if len(bid) > 12 else bid,
            "count": len(txns),
            "net_wt_kg": round(batch_net / 1000, 3),
            "date_range": f"{dates[0]} to {dates[-1]}" if dates else "?",
            "unique_dates": len(dates)
        })
    
    # Group by date for date-level analysis
    date_counts = Counter(t.get('date', '')[:10] for t in all_txns)
    
    # Find potential duplicates (same date + item + refno + type)
    seen = set()
    duplicates = []
    for t in all_txns:
        key = (t.get('date', '')[:10], t.get('item_name', ''), t.get('refno', ''), t.get('type', ''), t.get('party_name', ''))
        if key in seen:
            duplicates.append({"date": key[0], "item": key[1], "refno": key[2], "type": key[3], "party": key[4], "net_wt": t.get('net_wt', 0)})
        seen.add(key)
    
    dup_net_wt = sum(d['net_wt'] for d in duplicates)
    
    result = {
        "date_range": f"{start_date} to {end_date}",
        "total_transactions": len(all_txns),
        "total_net_wt_kg": round(total_net_wt / 1000, 3),
        "batch_count": len(batch_groups),
        "batches": batch_summary[:10],
        "duplicate_count": len(duplicates),
        "duplicate_net_wt_kg": round(dup_net_wt / 1000, 3),
        "duplicates_sample": duplicates[:20],
    }
    
    # If duplicates found and delete requested, remove them
    if delete_orphans and duplicates:
        # Keep one of each, delete extras
        seen_for_delete = set()
        ids_to_delete = []
        for t in all_txns:
            key = (t.get('date', '')[:10], t.get('item_name', ''), t.get('refno', ''), t.get('type', ''), t.get('party_name', ''))
            if key in seen_for_delete:
                ids_to_delete.append(t['_id'])
            seen_for_delete.add(key)
        
        if ids_to_delete:
            del_result = await db.transactions.delete_many({"_id": {"$in": ids_to_delete}})
            result["deleted_duplicates"] = del_result.deleted_count
            _inv_cache.invalidate()
            asyncio.create_task(_safe_recompute_summaries())
    
    return result




@api_router.get("/analytics/monthly-profit")
async def get_monthly_profit(
    year: int = Query(...),
    month: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """Get pre-computed item profit for a specific month (0 = all year).

    Auto-recomputes the year if the live transactions diverged from the stored
    fingerprint (so dashboards stay fresh even if the background task failed
    after a recent upload).
    """
    freshness = await ensure_year_summary_fresh(db, year)
    
    if month == 0:
        # ALL: aggregate across all months of the year
        pipeline = [
            {"$match": {"year": year, "summary_type": "item_profit"}},
            {"$group": {
                "_id": "$name",
                "silver_profit_kg": {"$sum": "$silver_profit_kg"},
                "labor_profit_inr": {"$sum": "$labor_profit_inr"},
                "net_wt_sold_kg": {"$sum": "$net_wt_sold_kg"},
                "total_sales_value": {"$sum": "$total_sales_value"},
                "avg_purchase_tunch": {"$avg": "$avg_purchase_tunch"},
                "avg_sale_tunch": {"$avg": "$avg_sale_tunch"},
                "cost_source": {"$max": "$cost_source"},
            }}
        ]
        results = await db.monthly_summaries.aggregate(pipeline).to_list(None)
        items = [{
            "item_name": r["_id"],
            "silver_profit_kg": round(r["silver_profit_kg"], 3),
            "labor_profit_inr": round(r["labor_profit_inr"], 2),
            "net_wt_sold_kg": round(r["net_wt_sold_kg"], 3),
            "total_sales_value": round(r.get("total_sales_value", 0), 2),
            "avg_purchase_tunch": round(r.get("avg_purchase_tunch", 0), 2),
            "avg_sale_tunch": round(r.get("avg_sale_tunch", 0), 2),
            "cost_source": r.get("cost_source") or "ledger",
        } for r in results]
    else:
        docs = await db.monthly_summaries.find(
            {"year": year, "month": month, "summary_type": "item_profit"},
            {"_id": 0}
        ).to_list(None)
        items = [{
            "item_name": d["name"],
            "silver_profit_kg": d["silver_profit_kg"],
            "labor_profit_inr": d["labor_profit_inr"],
            "net_wt_sold_kg": d["net_wt_sold_kg"],
            "total_sales_value": d.get("total_sales_value", 0),
            "avg_purchase_tunch": d.get("avg_purchase_tunch", 0),
            "avg_sale_tunch": d.get("avg_sale_tunch", 0),
            "cost_source": d.get("cost_source", "ledger"),
        } for d in docs]
    
    items.sort(key=lambda x: x['silver_profit_kg'], reverse=True)
    total_silver = sum(i['silver_profit_kg'] for i in items)
    total_labor = sum(i['labor_profit_inr'] for i in items)
    total_sales = sum(i['total_sales_value'] for i in items)
    
    # Total Sales: compute from transactions with SAME filter used in profit calc
    # (exclude SILVER ORNAMENTS / COURIER / etc + unassigned-stamp items).
    # This matches Tally's user-facing Net Sale (1445.294 kg) exactly.
    if month == 0:
        sales_query = {'date': {'$gte': f"{year}-01-01", '$lte': f"{year}-12-31 23:59:59"}, 'type': {'$in': ['sale', 'sale_return']}}
    else:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        sales_query = {'date': {'$gte': f"{year}-{month:02d}-01", '$lte': f"{year}-{month:02d}-{last_day} 23:59:59"}, 'type': {'$in': ['sale', 'sale_return']}}
    
    sale_txns = await db.transactions.find(sales_query, {"_id": 0, "type": 1, "net_wt": 1, "fine": 1, "total_amount": 1, "party_name": 1, "item_name": 1}).to_list(None)
    
    # Build the same filter the profit pipeline uses
    EXCLUDED_ITEMS = {"SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"}
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    ms_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    ms_master = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    ms_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in ms_master}
    ms_map_dict, ms_member_to_leader, _ = build_group_maps(all_groups, ms_mappings)
    
    def _inc(item_name: str) -> bool:
        leader = resolve_to_leader(item_name, ms_map_dict, ms_member_to_leader)
        if leader in EXCLUDED_ITEMS:
            return False
        stamp = ms_stamps.get(leader, ms_stamps.get(ms_map_dict.get(item_name, item_name), 'Unassigned'))
        return bool(stamp) and stamp != 'Unassigned'
    
    total_net_wt_sold = 0.0
    total_fine_wt_sold = 0.0
    total_labour_sold = 0.0
    customer_set = set()
    for st in sale_txns:
        if not _inc(st.get('item_name', '')):
            continue
        # Canonicalize: returns always subtract, whether DB stored them signed or unsigned
        is_ret = st['type'] == 'sale_return'
        sign = -1 if is_ret else 1
        total_net_wt_sold += abs(st.get('net_wt', 0) or 0) * sign
        total_fine_wt_sold += abs(st.get('fine', 0) or 0) * sign
        total_labour_sold += abs(st.get('total_amount', 0) or 0) * sign
        if st.get('party_name'):
            customer_set.add(st['party_name'])
    
    unique_customers = len(customer_set)
    
    return {
        "year": year,
        "month": month,
        "silver_profit_kg": round(total_silver, 3),
        "labor_profit_inr": round(total_labor, 2),
        "total_sales_value": round(total_sales, 2),
        "total_net_wt_sold": round(total_net_wt_sold, 3),
        "total_fine_wt_sold": round(total_fine_wt_sold, 3),
        "total_labour_sold": round(total_labour_sold, 2),
        "unique_customers": unique_customers,
        "all_items": items,
        "total_items_analyzed": len(items),
        "last_computed_at": freshness.get("last_computed_at"),
        "was_recomputed": freshness.get("recomputed", False),
    }


@api_router.get("/analytics/monthly-party")
async def get_monthly_party(
    year: int = Query(...),
    month: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """Get pre-computed party analysis for a specific month (0 = all year)."""
    # Auto-recompute if the live transactions diverged from the stored fingerprint
    freshness = await ensure_year_summary_fresh(db, year)
    
    if month == 0:
        # Aggregate across all months
        cust_pipeline = [
            {"$match": {"year": year, "summary_type": "party_customer"}},
            {"$group": {
                "_id": "$name",
                "total_net_wt": {"$sum": "$total_net_wt"},
                "total_fine_wt": {"$sum": "$total_fine_wt"},
                "total_gr_wt": {"$sum": "$total_gr_wt"},
                "total_sales_value": {"$sum": "$total_sales_value"},
                "transaction_count": {"$sum": "$transaction_count"},
            }}
        ]
        supp_pipeline = [
            {"$match": {"year": year, "summary_type": "party_supplier"}},
            {"$group": {
                "_id": "$name",
                "total_net_wt": {"$sum": "$total_net_wt"},
                "total_fine_wt": {"$sum": "$total_fine_wt"},
                "total_gr_wt": {"$sum": "$total_gr_wt"},
                "total_purchases_value": {"$sum": "$total_purchases_value"},
                "transaction_count": {"$sum": "$transaction_count"},
            }}
        ]
        cust_results = await db.monthly_summaries.aggregate(cust_pipeline).to_list(None)
        supp_results = await db.monthly_summaries.aggregate(supp_pipeline).to_list(None)
        
        customers = [{"party_name": r["_id"], "total_net_wt": round(r["total_net_wt"], 3),
                      "total_fine_wt": round(r["total_fine_wt"], 3), "total_gr_wt": round(r["total_gr_wt"], 3),
                      "total_sales_value": round(r["total_sales_value"], 2),
                      "transaction_count": r["transaction_count"]} for r in cust_results]
        suppliers = [{"party_name": r["_id"], "total_net_wt": round(r["total_net_wt"], 3),
                      "total_fine_wt": round(r["total_fine_wt"], 3), "total_gr_wt": round(r["total_gr_wt"], 3),
                      "total_purchases_value": round(r["total_purchases_value"], 2),
                      "transaction_count": r["transaction_count"]} for r in supp_results]
    else:
        cust_docs = await db.monthly_summaries.find(
            {"year": year, "month": month, "summary_type": "party_customer"}, {"_id": 0}
        ).to_list(None)
        supp_docs = await db.monthly_summaries.find(
            {"year": year, "month": month, "summary_type": "party_supplier"}, {"_id": 0}
        ).to_list(None)
        
        customers = [{"party_name": d["name"], "total_net_wt": d["total_net_wt"],
                      "total_fine_wt": d["total_fine_wt"], "total_gr_wt": d["total_gr_wt"],
                      "total_sales_value": d.get("total_sales_value", 0),
                      "transaction_count": d["transaction_count"]} for d in cust_docs]
        suppliers = [{"party_name": d["name"], "total_net_wt": d["total_net_wt"],
                      "total_fine_wt": d["total_fine_wt"], "total_gr_wt": d["total_gr_wt"],
                      "total_purchases_value": d.get("total_purchases_value", 0),
                      "transaction_count": d["transaction_count"]} for d in supp_docs]
    
    customers.sort(key=lambda x: x['total_net_wt'], reverse=True)
    suppliers.sort(key=lambda x: x['total_net_wt'], reverse=True)
    
    return {
        "year": year,
        "month": month,
        "customers": customers,
        "suppliers": suppliers,
        "top_customer": customers[0] if customers else None,
        "top_supplier": suppliers[0] if suppliers else None,
        "last_computed_at": freshness.get("last_computed_at"),
        "was_recomputed": freshness.get("recomputed", False),
    }


@api_router.get("/analytics/daily-profit")
async def get_daily_profit(
    year: int = Query(...),
    month: int = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get daily silver and labour profit for each day of the month.

    Uses the shared, ADDITIVE ``compute_daily_profits`` helper which applies a per-item
    month-level cost basis (same as the monthly summary). This guarantees the sum of the
    daily profits equals the monthly total shown in the header (Profit Analysis page).
    """
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day} 23:59:59"

    # Load required data (mappings, groups, stamps, ledger, month transactions)
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    master_items_list = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    master_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in master_items_list}
    all_ledger = await fetch_ledger_with_fallback(db, all_groups, mappings)
    transactions = await db.transactions.find(
        {'date': {'$gte': f"{year}-{month:02d}-01", '$lte': end_date}},
        {"_id": 0}
    ).to_list(None)

    daily_profits = compute_daily_profits(
        transactions, all_ledger, all_groups, mappings, master_stamps, year, month
    )
    return {"year": year, "month": month, "daily": daily_profits}


@api_router.get("/analytics/daily-profit-detail")
async def get_daily_profit_detail(
    date: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get top 20 customers and top 20 items profit for a specific date.

    Uses the shared month-level cost basis (compute_date_profit_detail) so per-item silver
    profits stay consistent with the daily totals shown on the Profit Analysis page.
    """
    # date is YYYY-MM-DD; load the whole MONTH so the cost basis matches the daily/monthly calc
    year = int(date[:4])
    month = int(date[5:7])
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{last_day} 23:59:59"

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    master_items_list = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    master_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in master_items_list}
    all_ledger = await fetch_ledger_with_fallback(db, all_groups, mappings)
    month_txns = await db.transactions.find(
        {'date': {'$gte': month_start, '$lte': month_end}}, {"_id": 0}
    ).to_list(None)

    return compute_date_profit_detail(
        month_txns, date, all_ledger, all_groups, mappings, master_stamps, top_n=20
    )



@api_router.get("/analytics/item-monthly-breakdown/{item_name}")
async def get_item_monthly_breakdown(
    item_name: str,
    year: int = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get monthly breakdown for a specific item (for bar chart)."""
    docs = await db.monthly_summaries.find(
        {"year": year, "summary_type": "item_profit", "name": item_name},
        {"_id": 0}
    ).to_list(None)
    
    # Build 12-month array
    months = []
    for m in range(1, 13):
        doc = next((d for d in docs if d['month'] == m), None)
        months.append({
            "month": m,
            "silver_profit_kg": doc['silver_profit_kg'] if doc else 0,
            "labor_profit_inr": doc['labor_profit_inr'] if doc else 0,
            "net_wt_sold_kg": doc['net_wt_sold_kg'] if doc else 0,
        })
    
    return {"item_name": item_name, "year": year, "months": months}


@api_router.get("/analytics/party-monthly-breakdown/{party_name}")
async def get_party_monthly_breakdown(
    party_name: str,
    year: int = Query(...),
    party_type: str = Query("customer"),
    current_user: dict = Depends(get_current_user)
):
    """Get monthly breakdown for a specific party (for bar chart)."""
    stype = "party_customer" if party_type == "customer" else "party_supplier"
    docs = await db.monthly_summaries.find(
        {"year": year, "summary_type": stype, "name": party_name},
        {"_id": 0}
    ).to_list(None)
    
    months = []
    for m in range(1, 13):
        doc = next((d for d in docs if d['month'] == m), None)
        if stype == "party_customer":
            months.append({
                "month": m,
                "total_net_wt": doc['total_net_wt'] if doc else 0,
                "total_sales_value": doc.get('total_sales_value', 0) if doc else 0,
                "transaction_count": doc['transaction_count'] if doc else 0,
            })
        else:
            months.append({
                "month": m,
                "total_net_wt": doc['total_net_wt'] if doc else 0,
                "total_purchases_value": doc.get('total_purchases_value', 0) if doc else 0,
                "transaction_count": doc['transaction_count'] if doc else 0,
            })
    
    return {"party_name": party_name, "year": year, "party_type": party_type, "months": months}


@api_router.get("/analytics/party-monthly-profit/{party_name}")
async def get_party_monthly_profit(
    party_name: str,
    year: int = Query(...),
    party_type: str = Query("customer"),
    current_user: dict = Depends(get_current_user)
):
    """Monthly PROFIT breakdown for a customer/supplier (silver, labour, weight) — reads pre-computed summaries."""
    await ensure_year_summary_fresh(db, year)
    stype = "party_customer_profit" if party_type == "customer" else "party_supplier_profit"
    docs = await db.monthly_summaries.find(
        {"year": year, "summary_type": stype, "name": party_name},
        {"_id": 0}
    ).to_list(None)
    
    months = []
    for mnum in range(1, 13):
        doc = next((d for d in docs if d['month'] == mnum), None)
        months.append({
            "month": mnum,
            "silver_profit_kg": doc.get('silver_profit_kg', 0) if doc else 0,
            "labor_profit_inr": doc.get('labor_profit_inr', 0) if doc else 0,
            "net_wt_kg": (doc.get('sold_kg', 0) if party_type == "customer" else doc.get('purchased_kg', 0)) if doc else 0,
        })
    
    return {"party_name": party_name, "year": year, "party_type": party_type, "months": months}


async def _get_data_years():
    """Distinct years present in transactions (valid 4-digit)."""
    years = set()
    async for r in db.transactions.aggregate([{"$group": {"_id": {"$substr": ["$date", 0, 4]}}}]):
        y = r['_id']
        if y and y.isdigit() and 2000 <= int(y) <= 2100:
            years.add(int(y))
    return sorted(years)


@api_router.get("/analytics/year-comparison/overview")
async def year_comparison_overview(current_user: dict = Depends(get_current_user)):
    """Monthwise metrics for every year, on one scale — from pre-computed summaries."""
    years = await _get_data_years()
    for y in years:
        await ensure_year_summary_fresh(db, y)
    keys = ('sales_kg', 'sales_fine_kg', 'sales_value', 'purchases_kg', 'purchases_fine_kg',
            'silver_profit_kg', 'labor_profit_inr', 'transactions')
    metrics = {k: {} for k in keys}
    for y in years:
        by_m = {k: [0.0] * 12 for k in keys}
        async for d in db.monthly_summaries.find(
                {"year": y, "summary_type": {"$in": ["party_customer", "party_supplier", "item_profit"]}},
                {"_id": 0}):
            i = d['month'] - 1
            st = d['summary_type']
            if st == 'party_customer':
                by_m['sales_kg'][i] += d.get('total_net_wt', 0) / 1000
                by_m['sales_fine_kg'][i] += d.get('total_fine_wt', 0) / 1000
                by_m['sales_value'][i] += d.get('total_sales_value', 0)
                by_m['transactions'][i] += d.get('transaction_count', 0)
            elif st == 'party_supplier':
                by_m['purchases_kg'][i] += d.get('total_net_wt', 0) / 1000
                by_m['purchases_fine_kg'][i] += d.get('total_fine_wt', 0) / 1000
            else:
                # item_profit — EXACT same math as the Profit Analysis page
                by_m['silver_profit_kg'][i] += d.get('silver_profit_kg', 0)
                by_m['labor_profit_inr'][i] += d.get('labor_profit_inr', 0)
        for k in keys:
            metrics[k][str(y)] = [round(v, 3) for v in by_m[k]]
    yearly_totals = []
    prev = None
    for y in years:
        tot = {k: round(sum(metrics[k][str(y)]), 3) for k in keys}
        growth = None
        if prev and prev.get('sales_kg'):
            growth = round((tot['sales_kg'] - prev['sales_kg']) / abs(prev['sales_kg']) * 100, 1)
        yearly_totals.append({"year": y, **tot, "sales_growth_pct": growth})
        prev = tot
    return {"years": years, "monthly": metrics, "yearly_totals": yearly_totals}


@api_router.get("/analytics/year-comparison/top")
async def year_comparison_top(
    entity: str = Query("items"),
    limit: int = Query(8),
    current_user: dict = Depends(get_current_user)
):
    """Top items/customers/suppliers across all years with per-year monthly series."""
    cfg = {
        'items': ('item_sales', 'sold_kg', 1.0, 'sales_value'),
        'customers': ('party_customer', 'total_net_wt', 1000.0, 'total_sales_value'),
        'suppliers': ('party_supplier', 'total_net_wt', 1000.0, 'total_purchases_value'),
    }
    if entity not in cfg:
        raise HTTPException(status_code=400, detail="entity must be items|customers|suppliers")
    years = await _get_data_years()
    for y in years:
        await ensure_year_summary_fresh(db, y)
    stype, field, div, val_field = cfg[entity]
    agg = {}
    async for d in db.monthly_summaries.find({"summary_type": stype, "year": {"$in": years}}, {"_id": 0}):
        name = d.get('name')
        if not name:
            continue
        e = agg.setdefault(name, {
            'name': name, 'total_kg': 0.0, 'total_value': 0.0,
            'yearly': {str(y): 0.0 for y in years},
            'monthly': {str(y): [0.0] * 12 for y in years}})
        kg = (d.get(field, 0) or 0) / div
        e['total_kg'] += kg
        e['total_value'] += d.get(val_field, 0) or 0
        e['yearly'][str(d['year'])] += kg
        e['monthly'][str(d['year'])][d['month'] - 1] += kg
    top = sorted(agg.values(), key=lambda x: x['total_kg'], reverse=True)[:limit]
    for e in top:
        e['total_kg'] = round(e['total_kg'], 3)
        e['total_value'] = round(e['total_value'], 2)
        e['yearly'] = {ys: round(v, 3) for ys, v in e['yearly'].items()}
        e['monthly'] = {ys: [round(v, 3) for v in arr] for ys, arr in e['monthly'].items()}
    return {"years": years, "entity": entity, "top": top}


@api_router.get("/analytics/year-comparison/party-detail")
async def year_comparison_party_detail(
    party: str = Query(...),
    party_type: str = Query("customer"),
    current_user: dict = Depends(get_current_user)
):
    """Monthwise multi-year series for one customer/supplier (kg, value, profits)."""
    years = await _get_data_years()
    for y in years:
        await ensure_year_summary_fresh(db, y)
    base_type = 'party_customer' if party_type == 'customer' else 'party_supplier'
    profit_type = 'party_customer_profit' if party_type == 'customer' else 'party_supplier_profit'
    out = {'kg': {}, 'value': {}, 'silver_profit_kg': {}, 'labor_profit_inr': {}}
    for y in years:
        for k in out:
            out[k][str(y)] = [0.0] * 12
    async for d in db.monthly_summaries.find(
            {"summary_type": {"$in": [base_type, profit_type]}, "name": party, "year": {"$in": years}},
            {"_id": 0}):
        ys = str(d['year'])
        i = d['month'] - 1
        if d['summary_type'] == base_type:
            out['kg'][ys][i] += (d.get('total_net_wt', 0) or 0) / 1000
            out['value'][ys][i] += d.get('total_sales_value', d.get('total_purchases_value', 0)) or 0
        else:
            out['silver_profit_kg'][ys][i] += d.get('silver_profit_kg', 0) or 0
            out['labor_profit_inr'][ys][i] += d.get('labor_profit_inr', 0) or 0
    yearly_kg = {str(y): round(sum(out['kg'][str(y)]), 3) for y in years}
    for k in out:
        for ys in out[k]:
            out[k][ys] = [round(v, 3) for v in out[k][ys]]
    return {"party": party, "party_type": party_type, "years": years, "monthly": out, "yearly_kg": yearly_kg}


@api_router.get("/analytics/year-comparison/parties")
async def year_comparison_parties(
    party_type: str = Query("customer"),
    current_user: dict = Depends(get_current_user)
):
    stype = 'party_customer' if party_type == 'customer' else 'party_supplier'
    names = await db.monthly_summaries.distinct('name', {'summary_type': stype})
    return {"parties": sorted(n for n in names if n)}


@api_router.get("/analytics/dashboard-year-summary")
async def get_dashboard_year_summary(
    year: int = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get year-wise dashboard comparison data from pre-computed summaries.

    Auto-recomputes the year if the live transactions diverged from the stored
    fingerprint, so the Dashboard always reflects the latest upload.
    """
    freshness = await ensure_year_summary_fresh(db, year)
    
    # Monthly sales totals (for bar chart)
    monthly_pipeline = [
        {"$match": {"year": year, "summary_type": "party_customer"}},
        {"$group": {
            "_id": "$month",
            "total_net_wt": {"$sum": "$total_net_wt"},
            "total_sales_value": {"$sum": "$total_sales_value"},
            "transaction_count": {"$sum": "$transaction_count"},
        }}
    ]
    monthly_results = await db.monthly_summaries.aggregate(monthly_pipeline).to_list(None)
    monthly_sales = []
    for m in range(1, 13):
        doc = next((r for r in monthly_results if r['_id'] == m), None)
        monthly_sales.append({
            "month": m,
            "total_net_wt": round(doc['total_net_wt'], 3) if doc else 0,
            "total_sales_value": round(doc['total_sales_value'], 2) if doc else 0,
            "transaction_count": doc['transaction_count'] if doc else 0,
        })
    
    # Top 5 customers by net weight (year-wide)
    top_cust_pipeline = [
        {"$match": {"year": year, "summary_type": "party_customer"}},
        {"$group": {
            "_id": "$name",
            "total_net_wt": {"$sum": "$total_net_wt"},
            "total_sales_value": {"$sum": "$total_sales_value"},
        }},
        {"$sort": {"total_net_wt": -1}},
        {"$limit": 5}
    ]
    top_customers = await db.monthly_summaries.aggregate(top_cust_pipeline).to_list(None)
    top_customers = [{"party_name": r["_id"], "total_net_wt": round(r["total_net_wt"], 3), "total_sales_value": round(r["total_sales_value"], 2)} for r in top_customers]
    
    # Top 5 items by profit (year-wide)
    top_items_pipeline = [
        {"$match": {"year": year, "summary_type": "item_profit"}},
        {"$group": {
            "_id": "$name",
            "net_wt_sold_kg": {"$sum": "$net_wt_sold_kg"},
            "silver_profit_kg": {"$sum": "$silver_profit_kg"},
            "total_sales_value": {"$sum": "$total_sales_value"},
        }},
        {"$sort": {"net_wt_sold_kg": -1}},
        {"$limit": 5}
    ]
    top_items = await db.monthly_summaries.aggregate(top_items_pipeline).to_list(None)
    top_items = [{"item_name": r["_id"], "net_wt_sold_kg": round(r["net_wt_sold_kg"], 3), "silver_profit_kg": round(r["silver_profit_kg"], 3), "total_sales_value": round(r.get("total_sales_value", 0), 2)} for r in top_items]
    
    # Year totals
    year_total_net_wt = sum(m['total_net_wt'] for m in monthly_sales)
    year_total_sales = sum(m['total_sales_value'] for m in monthly_sales)
    year_total_txns = sum(m['transaction_count'] for m in monthly_sales)
    
    return {
        "year": year,
        "monthly_sales": monthly_sales,
        "top_customers": top_customers,
        "top_items": top_items,
        "year_totals": {
            "total_net_wt": round(year_total_net_wt, 3),
            "total_sales_value": round(year_total_sales, 2),
            "transaction_count": year_total_txns,
        },
        "last_computed_at": freshness.get("last_computed_at"),
        "was_recomputed": freshness.get("recomputed", False),
    }




@api_router.get("/history/actions")
async def get_action_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get recent actions for undo/redo"""
    actions = await db.action_history.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return actions

@api_router.post("/history/undo")
async def undo_last_action(current_user: dict = Depends(get_current_user)):
    """Undo last action"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    last_action = await db.action_history.find_one({"can_undo": True}, {"_id": 0}, sort=[("timestamp", -1)])
    
    if not last_action:
        raise HTTPException(status_code=404, detail="No action to undo")
    
    # Mark as undone
    await db.action_history.update_one(
        {"id": last_action['id']},
        {"$set": {"can_undo": False}}
    )
    
    return {
        "success": True,
        "message": f"Undone: {last_action['description']}",
        "action": last_action
    }

@api_router.post("/system/reset")
async def reset_system(request: ResetRequest, current_user: dict = Depends(get_current_user)):
    """Selective system reset with password protection (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    if request.password != "CLOSE":
        raise HTTPException(status_code=403, detail="Invalid password")
    
    if not request.categories:
        raise HTTPException(status_code=400, detail="No categories selected for reset")
    
    # Map category names to DB collections and transaction type filters
    results = {}
    
    if 'sales' in request.categories:
        r = await db.transactions.delete_many({"type": {"$in": ["sale", "sale_return"]}})
        results['sales'] = r.deleted_count
    
    if 'purchases' in request.categories:
        r = await db.transactions.delete_many({"type": {"$in": ["purchase", "purchase_return"]}})
        results['purchases'] = r.deleted_count
    
    if 'issues' in request.categories:
        r = await db.transactions.delete_many({"type": {"$in": ["issue", "receive"]}})
        results['issues'] = r.deleted_count
    
    if 'polythene' in request.categories:
        r = await db.polythene_adjustments.delete_many({})
        results['polythene'] = r.deleted_count
    
    if 'mappings' in request.categories:
        r = await db.item_mappings.delete_many({})
        results['mappings'] = r.deleted_count
    
    if 'physical_stock' in request.categories:
        r1 = await db.physical_stock.delete_many({})
        r2 = await db.physical_inventory.delete_many({})
        r3 = await db.stock_entries.delete_many({})
        results['physical_stock'] = r1.deleted_count + r2.deleted_count + r3.deleted_count
    
    if 'purchase_ledger' in request.categories:
        r = await db.purchase_ledger.delete_many({})
        results['purchase_ledger'] = r.deleted_count
    
    if 'stock_reconciliation' in request.categories:
        r1 = await db.physical_stock_update_sessions.delete_many({})
        r2 = await db.replaced_records.delete_many({})
        r3 = await db.inventory_snapshots.delete_many({})
        r4 = await db.inventory_baselines.delete_many({})
        results['stock_reconciliation'] = r1.deleted_count + r2.deleted_count + r3.deleted_count + r4.deleted_count
    
    if 'stamp_verification' in request.categories:
        r1 = await db.stamp_verifications.delete_many({})
        r2 = await db.stamp_approvals.delete_many({})
        results['stamp_verification'] = r1.deleted_count + r2.deleted_count
    
    if 'historical' in request.categories:
        r1 = await db.historical_transactions.delete_many({})
        r2 = await db.monthly_summaries.delete_many({})
        results['historical'] = r1.deleted_count + r2.deleted_count
    
    if 'item_buffers' in request.categories:
        r = await db.item_buffers.delete_many({})
        results['item_buffers'] = r.deleted_count
    
    if 'item_groups' in request.categories:
        r = await db.item_groups.delete_many({})
        results['item_groups'] = r.deleted_count
    
    if 'orders' in request.categories:
        r = await db.orders.delete_many({})
        results['orders'] = r.deleted_count
    
    if 'notifications' in request.categories:
        r1 = await db.notifications.delete_many({})
        r2 = await db.activity_log.delete_many({})
        results['notifications'] = r1.deleted_count + r2.deleted_count
    
    if 'history' in request.categories:
        r = await db.action_history.delete_many({})
        results['history'] = r.deleted_count
    
    if 'master_stock' in request.categories:
        # Zero out quantities but keep items & stamps intact so mappings/groups don't break
        r1 = await db.master_items.update_many({}, {"$set": {"gr_wt": 0, "net_wt": 0}})
        r2 = await db.opening_stock.update_many({}, {"$set": {"gr_wt": 0, "net_wt": 0, "fine": 0, "labor_wt": 0, "labor_rs": 0, "rate": 0, "total": 0, "pc": 0}})
        results['master_stock'] = f"{r1.modified_count} items zeroed, {r2.modified_count} opening stock zeroed"
    
    if 'all_data' in request.categories:
        # Nuclear option: clear everything except users, keep master items structure intact
        for coll in ['transactions', 'polythene_adjustments', 'item_mappings',
                      'physical_inventory', 'physical_stock', 'stock_entries', 'purchase_ledger',
                      'notifications', 'activity_log', 'action_history',
                      'stamp_approvals', 'inventory_snapshots',
                      'physical_stock_update_sessions', 'replaced_records', 'inventory_baselines',
                      'stamp_verifications', 'historical_transactions', 'monthly_summaries',
                      'item_buffers', 'item_groups', 'orders',
                      'upload_sessions', 'upload_chunks', 'app_cache']:
            await db[coll].delete_many({})
        # Zero out master stock quantities but keep items & stamps
        await db.master_items.update_many({}, {"$set": {"gr_wt": 0, "net_wt": 0}})
        await db.opening_stock.update_many({}, {"$set": {"gr_wt": 0, "net_wt": 0, "fine": 0, "labor_wt": 0, "labor_rs": 0, "rate": 0, "total": 0, "pc": 0}})
        results['all_data'] = 'All cleared, master stock zeroed (items/stamps/mappings preserved)'
    
    desc = ', '.join(f"{k}: {v}" for k, v in results.items())
    await save_action('system_reset', f"Selective reset: {desc}")
    
    return {
        "success": True,
        "results": results,
        "message": f"Reset complete: {desc}"
    }


@api_router.post("/system/fix-dates")
async def fix_swapped_dates(current_user: dict = Depends(get_current_user)):
    """Fix dates that were incorrectly stored due to month/day swap bug in normalize_date.
    The bug: pd.to_datetime('YYYY-MM-DD', dayfirst=True) swaps month/day for ISO strings.
    Strategy: detect dates where month/day are both ≤12, and swapping would produce a date
    that fills a gap in the otherwise sequential date stream."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    from datetime import datetime as dt_cls, timedelta
    fixed_count = 0
    fix_log = []

    all_dates = sorted(await db.transactions.distinct('date'))
    if not all_dates:
        return {"success": True, "fixed_count": 0, "fixes": [], "message": "No dates to fix"}

    # Parse all dates
    date_objs = []
    for d in all_dates:
        try:
            date_objs.append((d, dt_cls.strptime(d, '%Y-%m-%d')))
        except ValueError:
            continue

    # Detect suspicious gaps: if sorted dates have a gap > 28 days, something is wrong
    # For each date where month ≤ 12 and day ≤ 12 (swappable), check if swapping
    # produces a date that falls within the expected range
    if len(date_objs) < 2:
        return {"success": True, "fixed_count": 0, "fixes": [], "message": "Not enough dates"}

    # Find dates where day > 12 (unambiguous) to establish the valid date range
    unambiguous = [(d, dt) for d, dt in date_objs if dt.day > 12]
    if unambiguous:
        min_date = min(dt for _, dt in unambiguous) - timedelta(days=15)
        max_date = max(dt for _, dt in unambiguous) + timedelta(days=15)
    else:
        min_date = date_objs[0][1] - timedelta(days=15)
        max_date = date_objs[-1][1]

    # For each swappable date, check if swapping puts it in the valid range
    for date_str, dt in date_objs:
        if dt.month == dt.day:
            continue  # Swap would give same result
        if dt.day > 12 or dt.month > 12:
            continue  # Not swappable
        # Try swapping
        try:
            swapped_dt = dt_cls(dt.year, dt.day, dt.month)
        except ValueError:
            continue
        swapped_str = swapped_dt.strftime('%Y-%m-%d')

        # If current date is outside the valid range but swapped is inside, fix it
        current_in_range = min_date <= dt <= max_date
        swapped_in_range = min_date <= swapped_dt <= max_date

        if not current_in_range and swapped_in_range:
            result = await db.transactions.update_many(
                {'date': date_str},
                {'$set': {'date': swapped_str}}
            )
            if result.modified_count > 0:
                fix_log.append(f"{date_str} → {swapped_str} ({result.modified_count} txns)")
                fixed_count += result.modified_count

    await save_action('fix_dates', f"Fixed {fixed_count} transaction dates (month/day swap correction)")

    return {
        "success": True,
        "fixed_count": fixed_count,
        "fixes": fix_log,
        "message": f"Fixed {fixed_count} transactions across {len(fix_log)} dates"
    }


@api_router.get("/debug/item-closing/{item_name}")
async def debug_item_closing(item_name: str, as_of_date: str = None, current_user: dict = Depends(get_current_user)):
    """Debug endpoint: shows full breakdown of closing stock calculation for an item."""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin/Manager only")

    # Find item in master
    master_item = await db.master_items.find_one({'item_name': item_name}, {'_id': 0})
    if not master_item:
        raise HTTPException(status_code=404, detail=f"Item '{item_name}' not found in master items")

    stamp = master_item.get('stamp', 'Unassigned')

    # Opening stock
    opening_docs = await db.opening_stock.find({'item_name': item_name}, {'_id': 0}).to_list(None)
    opening_gr = sum(d.get('gr_wt', 0) for d in opening_docs)

    # Find all names that map to this item
    mappings = await db.item_mappings.find({'master_name': item_name}, {'_id': 0}).to_list(None)
    all_names = [item_name] + [m['transaction_name'] for m in mappings]

    # Transactions
    query = {'item_name': {'$in': all_names}}
    if as_of_date:
        query['date'] = {'$lte': as_of_date + ' 23:59:59'}

    txns = await db.transactions.find(query, {'_id': 0}).to_list(None)

    from collections import defaultdict
    by_date_type = defaultdict(lambda: defaultdict(float))
    total_in = 0
    total_out = 0
    for t in txns:
        gr = t.get('gr_wt', 0)
        by_date_type[t['date']][t['type']] += gr
        if t['type'] in ['purchase', 'purchase_return', 'receive']:
            total_in += gr
        else:
            total_out += gr

    # Polythene
    poly_query = {'item_name': {'$in': all_names}}
    if as_of_date:
        poly_query['date'] = {'$lte': as_of_date + ' 23:59:59'}
    polythene = await db.polythene_adjustments.find(poly_query, {'_id': 0}).to_list(None)
    poly_total = 0
    for p in polythene:
        pw = p['poly_weight'] * 1000  # kg to grams
        if p['operation'] == 'add':
            poly_total += pw
        else:
            poly_total -= pw

    closing = opening_gr + total_in - total_out + poly_total

    daily_breakdown = []
    for d in sorted(by_date_type.keys()):
        day_data = {'date': d}
        for tp, val in by_date_type[d].items():
            day_data[tp] = round(val / 1000, 3)
        daily_breakdown.append(day_data)

    return {
        'item_name': item_name,
        'stamp': stamp,
        'as_of_date': as_of_date or 'all dates',
        'all_transaction_names': all_names,
        'opening_gr_wt_kg': round(opening_gr / 1000, 3),
        'total_inflow_kg': round(total_in / 1000, 3),
        'total_outflow_kg': round(total_out / 1000, 3),
        'polythene_adjustment_kg': round(poly_total / 1000, 3),
        'closing_gr_wt_kg': round(closing / 1000, 3),
        'transaction_count': len(txns),
        'daily_breakdown': daily_breakdown,
        'polythene_entries': [{
            'date': p.get('date', '?'),
            'operation': p['operation'],
            'weight_kg': p['poly_weight']
        } for p in polythene]
    }



@api_router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    total_transactions = await db.transactions.count_documents({})
    total_purchases = await db.transactions.count_documents({"type": "purchase"})
    total_sales = await db.transactions.count_documents({"type": "sale"})
    total_opening_stock = await db.opening_stock.count_documents({})
    
    # Get unique parties
    all_parties = await db.transactions.distinct("party_name")
    total_parties = len([p for p in all_parties if p])
    
    # Get transaction date range
    date_range = {"from_date": None, "to_date": None}
    if total_transactions > 0:
        pipeline = [{"$group": {"_id": None, "min_date": {"$min": "$date"}, "max_date": {"$max": "$date"}}}]
        async for doc in db.transactions.aggregate(pipeline):
            date_range["from_date"] = doc.get("min_date")
            date_range["to_date"] = doc.get("max_date")
    
    # Get unique items count
    all_items = await db.transactions.distinct("item_name")
    total_items = len([i for i in all_items if i])
    
    return {
        "total_transactions": total_transactions,
        "total_purchases": total_purchases,
        "total_sales": total_sales,
        "total_opening_stock": total_opening_stock,
        "total_parties": total_parties,
        "total_items": total_items,
        "date_range": date_range
    }


@api_router.get("/stats/transaction-summary")
async def get_transaction_summary(current_user: dict = Depends(get_current_user)):
    """Get detailed transaction summary with weight totals per type — useful for reconciliation."""
    pipeline = [
        {'$group': {
            '_id': '$type',
            'count': {'$sum': 1},
            'total_gr_wt': {'$sum': '$gr_wt'},
            'total_net_wt': {'$sum': '$net_wt'},
        }},
        {'$sort': {'_id': 1}}
    ]
    results = {}
    async for doc in db.transactions.aggregate(pipeline):
        results[doc['_id']] = {
            'count': doc['count'],
            'gr_wt_kg': round(doc['total_gr_wt'] / 1000, 3),
            'net_wt_kg': round(doc['total_net_wt'] / 1000, 3),
        }

    # Calculate summary totals
    sale_gr = results.get('sale', {}).get('gr_wt_kg', 0)
    sale_ret_gr = results.get('sale_return', {}).get('gr_wt_kg', 0)
    purchase_gr = results.get('purchase', {}).get('gr_wt_kg', 0)
    purchase_ret_gr = results.get('purchase_return', {}).get('gr_wt_kg', 0)
    issue_gr = results.get('issue', {}).get('gr_wt_kg', 0)
    receive_gr = results.get('receive', {}).get('gr_wt_kg', 0)

    return {
        "by_type": results,
        "summary": {
            "net_sale_gr_wt_kg": round(sale_gr + sale_ret_gr, 3),
            "net_purchase_gr_wt_kg": round(purchase_gr + purchase_ret_gr, 3),
            "net_branch_transfer_gr_wt_kg": round(issue_gr - receive_gr, 3),
            "total_outflow_gr_wt_kg": round(sale_gr + sale_ret_gr + issue_gr, 3),
        },
        "dates": sorted(await db.transactions.distinct('date'))
    }

@api_router.delete("/transactions/all")
async def clear_all_transactions(current_user: dict = Depends(get_current_user)):
    """Clear all transactions only (preserves opening stock and master data)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.transactions.delete_many({})
    return {"success": True, "deleted_count": result.deleted_count}

@api_router.get("/item/{item_name}")
async def get_item_detail(item_name: str, current_user: dict = Depends(get_current_user)):
    """Get detailed information about a specific item"""
    
    # Get all transactions for this item (and mapped names)
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in all_mappings}
    reverse_map = defaultdict(list)
    for txn, master in mapping_dict.items():
        reverse_map[master].append(txn)
    
    # Collect all names that map to this item
    search_names = [item_name] + reverse_map.get(item_name, [])
    
    transactions = await db.transactions.find(
        {"item_name": {"$in": search_names}}, 
        {"_id": 0}
    ).sort("date", -1).to_list(None)
    
    # Calculate statistics — receives that carry rate data count as purchases (goods come in via branch receive)
    def _rcv_has_rate(t):
        return float(t.get('tunch', 0) or 0) > 0 or (t.get('fine', 0) or 0) > 0 or (t.get('labor', 0) or 0) > 0 or (t.get('total_amount', 0) or 0) > 0
    purchases = [t for t in transactions if t['type'] in ['purchase', 'purchase_return'] or (t['type'] == 'receive' and _rcv_has_rate(t))]
    sales = [t for t in transactions if t['type'] in ['sale', 'sale_return']]
    
    # Weighted average tunch
    abs_purchase_wt = sum(abs(t.get('net_wt', 0)) for t in purchases)
    abs_sale_wt = sum(abs(t.get('net_wt', 0)) for t in sales)
    avg_purchase_tunch = (sum(float(t.get('tunch', 0) or 0) * abs(t.get('net_wt', 0)) for t in purchases) / abs_purchase_wt) if abs_purchase_wt > 0 else 0
    avg_sale_tunch = (sum(float(t.get('tunch', 0) or 0) * abs(t.get('net_wt', 0)) for t in sales) / abs_sale_wt) if abs_sale_wt > 0 else 0
    
    # Weighted average labour per kg — labour charge is in total_amount, not labor field
    def _get_labour(t):
        """Get labour charge from transaction. Uses total_amount (actual labour Rs) not labor field."""
        return float(t.get('total_amount', 0) or t.get('labor', 0) or 0)
    
    avg_purchase_labour = (sum(_get_labour(t) for t in purchases) / (abs_purchase_wt / 1000)) if abs_purchase_wt > 0 else 0
    avg_sale_labour = (sum(_get_labour(t) for t in sales) / (abs_sale_wt / 1000)) if abs_sale_wt > 0 else 0
    
    # Get ACCURATE current stock from get_current_inventory() (matches Current Stock page)
    inv_response = await get_current_inventory_cached()
    current_stock_kg = 0
    current_gr_wt_kg = 0
    item_fine = 0
    item_labor = 0
    # Search in individual items (by_stamp)
    for stamp_items in inv_response.get('by_stamp', {}).values():
        for si in stamp_items:
            if si['item_name'] == item_name:
                current_stock_kg = round(si.get('net_wt', 0) / 1000, 3)
                current_gr_wt_kg = round(si.get('gr_wt', 0) / 1000, 3)
                item_fine = round(si.get('fine', 0) / 1000, 3)
                item_labor = si.get('labor', 0)
                break
    
    # Get purchase ledger info (group-aware, with estimated fallback from purchase history)
    ledger = await db.purchase_ledger.find_one({"item_name": item_name}, {"_id": 0})
    rate_source = 'ledger' if ledger else None
    if not ledger:
        _ig = await db.item_groups.find({}, {"_id": 0}).to_list(None)
        _merged = await fetch_ledger_with_fallback(db, _ig, all_mappings)
        _grp_l = build_group_ledger(_merged, _ig, all_mappings)
        _entry = _grp_l.get(item_name)
        if _entry:
            ledger = _entry
            rate_source = 'estimated' if _entry.get('fallback') else 'ledger'
    has_purchase_rate = ledger is not None
    purchase_tunch_ledger = ledger.get('purchase_tunch', 0) if ledger else 0
    labour_per_kg_ledger = ledger.get('labour_per_kg', 0) if ledger else 0
    
    # Get current stamp from master_items
    master = await db.master_items.find_one({"item_name": item_name}, {"_id": 0})
    current_stamp = master.get('stamp', 'Unassigned') if master else 'Unassigned'
    
    return {
        "item_name": item_name,
        "current_stamp": current_stamp,
        "current_stock_kg": current_stock_kg,
        "current_gr_wt_kg": current_gr_wt_kg,
        "fine_kg": item_fine,
        "labor_value": item_labor,
        "total_purchases": len(purchases),
        "total_sales": len(sales),
        "avg_purchase_tunch": round(avg_purchase_tunch, 2),
        "avg_sale_tunch": round(avg_sale_tunch, 2),
        "tunch_margin": round(avg_sale_tunch - avg_purchase_tunch, 2),
        "avg_purchase_labour": round(avg_purchase_labour, 2),
        "avg_sale_labour": round(avg_sale_labour, 2),
        "labour_margin": round(avg_sale_labour - avg_purchase_labour, 2),
        "has_purchase_rate": has_purchase_rate,
        "purchase_rate_source": rate_source,
        "purchase_tunch_ledger": purchase_tunch_ledger,
        "labour_per_kg_ledger": labour_per_kg_ledger,
        "recent_transactions": transactions[:20],
    }


@api_router.post("/item/{item_name}/set-purchase-rate")
async def set_purchase_rate(item_name: str, request: Dict, current_user: dict = Depends(get_current_user)):
    """Set or update purchase tunch and labour rate for an item in the purchase ledger.
    Used for items that have no purchase transactions but need fine/labour calculations."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    purchase_tunch = request.get('purchase_tunch')
    labour_per_kg = request.get('labour_per_kg')
    
    if purchase_tunch is None and labour_per_kg is None:
        raise HTTPException(status_code=400, detail="Provide purchase_tunch and/or labour_per_kg")
    
    update_fields = {'item_name': item_name, 'updated_at': datetime.now(timezone.utc).isoformat()}
    if purchase_tunch is not None:
        update_fields['purchase_tunch'] = float(purchase_tunch)
    if labour_per_kg is not None:
        update_fields['labour_per_kg'] = float(labour_per_kg)
    
    await db.purchase_ledger.update_one(
        {'item_name': item_name},
        {'$set': update_fields},
        upsert=True
    )
    
    _inv_cache.invalidate()
    return {'success': True, 'message': f'Purchase rate updated for {item_name}'}


@api_router.post("/item/{item_name}/assign-stamp")
async def assign_stamp_to_item(item_name: str, stamp: str = Query(...), current_user: dict = Depends(get_current_user)):
    """Assign stamp to all instances of an item"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Normalize stamp to consistent format "STAMP X" (ALL CAPS)
    import re
    if stamp and stamp.lower() != 'unassigned':
        match = re.search(r'(\d+)', stamp)
        if match:
            stamp = f'STAMP {match.group(1)}'
    
    # Update master_items (single source of truth) — upsert to create entry if missing
    result_master = await db.master_items.update_one(
        {"item_name": item_name},
        {"$set": {"stamp": stamp, "item_name": item_name}},
        upsert=True
    )
    
    # Update all transactions
    result1 = await db.transactions.update_many(
        {"item_name": item_name},
        {"$set": {"stamp": stamp}}
    )
    
    # Update opening stock
    result2 = await db.opening_stock.update_many(
        {"item_name": item_name},
        {"$set": {"stamp": stamp}}
    )
    
    _inv_cache.invalidate()
    await save_action('assign_stamp', f"Assigned stamp '{stamp}' to '{item_name}'")
    
    return {
        "success": True,
        "message": f"Stamp '{stamp}' assigned to '{item_name}'",
        "master_items_updated": 1 if result_master.modified_count or result_master.upserted_id else 0,
        "transactions_updated": result1.modified_count,
        "opening_stock_updated": result2.modified_count
    }

# ==================== ITEM CATEGORIZATION & BUFFER MANAGEMENT ====================

@api_router.post("/item-buffers/categorize")
async def categorize_items(current_user: dict = Depends(get_current_user)):
    """Rotation-based buffer calculation: 2.73-month stock cycle with seasonal lead times."""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    now = datetime.now(timezone.utc)
    season_key = get_current_season(now.month)
    season = SEASON_PROFILES[season_key]
    lead_time_days = season['lead_time_days']
    target_total_stock = season['target_total_stock_kg']

    # 1. Load mappings + groups for item resolution
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in all_mappings}
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    member_to_group = {}
    for g in groups:
        for member in g.get('members', []):
            member_to_group[member] = g['group_name']

    def resolve(name):
        master = mapping_dict.get(name, name)
        return member_to_group.get(master, master)

    # 2. Master items + current inventory
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_dict = {m['item_name']: m for m in master_items}
    inv_response = await get_current_inventory_cached()
    inv_dict = {item['item_name']: item for item in inv_response['inventory']}
    inv_dict.update({item['item_name']: item for item in inv_response.get('negative_items', [])})

    # 3. Aggregate monthly sales (current + historical)
    monthly_pipeline = [
        {"$match": {"type": {"$in": ["sale", "sale_return"]}}},
        {"$project": {"item_name": 1, "net_wt": 1, "month": {"$substr": ["$date", 5, 2]}}},
        {"$group": {"_id": {"item": "$item_name", "month": "$month"}, "total_wt": {"$sum": "$net_wt"}}},
    ]
    item_monthly = defaultdict(lambda: defaultdict(float))
    async for doc in db.transactions.aggregate(monthly_pipeline):
        item = resolve(doc['_id']['item'])
        try:
            m = int(doc['_id']['month'])
        except (ValueError, TypeError):
            continue
        item_monthly[item][m] += abs(doc['total_wt']) / 1000

    async for doc in db.historical_transactions.aggregate(monthly_pipeline):
        item = resolve(doc['_id']['item'])
        try:
            m = int(doc['_id']['month'])
        except (ValueError, TypeError):
            continue
        item_monthly[item][m] += abs(doc['total_wt']) / 1000

    years_with_data = await db.historical_transactions.distinct("historical_year")
    num_years = max(len(years_with_data), 1)

    # 4. Resolve stock per group/item
    group_stock = defaultdict(float)
    group_stamps = {}
    for inv_item in list(inv_response['inventory']) + list(inv_response.get('negative_items', [])):
        name = inv_item['item_name']
        gname = resolve(name)
        group_stock[gname] += inv_item.get('net_wt', 0) / 1000
        if gname not in group_stamps:
            group_stamps[gname] = inv_item.get('stamp', 'Unassigned')
    for name in master_dict:
        gname = resolve(name)
        if gname not in group_stamps:
            group_stamps[gname] = master_dict.get(name, {}).get('stamp', 'Unassigned')

    # 5. Calculate per-item velocities
    all_item_names = set(list(group_stock.keys()) + list(item_monthly.keys()))
    velocities = []
    for gname in all_item_names:
        month_data = item_monthly.get(gname, {})
        # Seasonal velocity: avg monthly sales during current season's months
        season_months = season['months']
        season_total = sum(month_data.get(m, 0) for m in season_months)
        season_velocity = (season_total / num_years) / max(len(season_months), 1)
        # Overall average velocity
        total_all = sum(month_data.values())
        overall_velocity = (total_all / num_years) / 12.0
        # Use higher of seasonal vs overall
        effective_velocity = max(season_velocity, overall_velocity)

        velocities.append({
            'item_name': gname,
            'stamp': group_stamps.get(gname, 'Unassigned'),
            'monthly_velocity_kg': effective_velocity,
            'season_velocity_kg': season_velocity,
            'overall_velocity_kg': overall_velocity,
            'total_sold_kg': total_all / num_years,
            'current_stock_kg': round(group_stock.get(gname, 0), 3),
        })

    # 6. Tier assignment (quartile-based)
    vel_values = [v['monthly_velocity_kg'] for v in velocities if v['monthly_velocity_kg'] > 0]
    if vel_values:
        sorted_vals = sorted(vel_values)
        n = len(sorted_vals)
        q25 = float(sorted_vals[max(0, int(n * 0.25) - 1)])
        q50 = float(sorted_vals[max(0, int(n * 0.50) - 1)])
        q75 = float(sorted_vals[max(0, int(n * 0.75) - 1)])
    else:
        q25 = q50 = q75 = 0

    # Total monthly velocity across all items (for share calculation)
    total_monthly_velocity = sum(v['monthly_velocity_kg'] for v in velocities)

    # 7. Build buffer docs using rotation model
    buffer_docs = []
    group_names_set = {g['group_name'] for g in groups}
    for v in velocities:
        vel = v['monthly_velocity_kg']
        if vel <= 0:
            tier, tier_num = 'dead', 4
        elif vel <= q25:
            tier, tier_num = 'slow', 3
        elif vel <= q50:
            tier, tier_num = 'medium', 2
        elif vel <= q75:
            tier, tier_num = 'fast', 1
        else:
            tier, tier_num = 'fastest', 0

        # --- Core rotation-based calculation ---
        # Minimum stock = 2.73 months of sales (full rotation cycle worth)
        minimum_stock = round(vel * ROTATION_CYCLE_MONTHS, 3)

        # Reorder buffer = stock consumed during order lead time
        daily_velocity = vel / 30.0
        reorder_buffer = round(daily_velocity * lead_time_days, 3)

        # Upper buffer (target) = item's proportional share of target total stock
        # This is the aspirational level to push sales
        if total_monthly_velocity > 0:
            item_share = vel / total_monthly_velocity
            upper_target = round(item_share * target_total_stock, 3)
        else:
            upper_target = minimum_stock

        # Upper target should be at least minimum_stock
        upper_target = max(upper_target, minimum_stock)

        current_stock_kg = v['current_stock_kg']

        # Status logic:
        # red = below reorder buffer (CRITICAL - will run out before order arrives)
        # yellow = below minimum stock (needs restocking soon)
        # green = at or above minimum stock
        if vel <= 0:
            status = 'green'  # dead items — no concern
        elif current_stock_kg < reorder_buffer:
            status = 'red'
        elif current_stock_kg < minimum_stock:
            status = 'yellow'
        else:
            status = 'green'

        # season_boost = ratio of seasonal velocity to overall velocity (>1 means seasonal demand is higher)
        season_boost = round(v['season_velocity_kg'] / v['overall_velocity_kg'], 2) if v['overall_velocity_kg'] > 0 else 1.0

        buffer_docs.append({
            'item_name': v['item_name'],
            'stamp': v['stamp'],
            'tier': tier, 'tier_num': tier_num,
            'monthly_velocity_kg': round(vel, 3),
            'season_velocity_kg': round(v['season_velocity_kg'], 3),
            'overall_velocity_kg': round(v['overall_velocity_kg'], 3),
            'season_boost': season_boost,
            'total_sold_kg': round(v['total_sold_kg'], 3),
            'minimum_stock_kg': minimum_stock,
            'reorder_buffer_kg': reorder_buffer,
            'upper_target_kg': upper_target,
            'lead_time_days': lead_time_days,
            'current_stock_kg': current_stock_kg,
            'status': status,
            'current_season': season_key,
            'season_label': season['label'],
            'is_group': v['item_name'] in group_names_set,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })

    # Save to DB
    new_names = {doc['item_name'] for doc in buffer_docs}
    await db.item_buffers.delete_many({'item_name': {'$nin': list(new_names)}})
    for doc in buffer_docs:
        await db.item_buffers.update_one(
            {'item_name': doc['item_name']},
            {'$set': doc},
            upsert=True
        )

    tier_counts = defaultdict(int)
    for d in buffer_docs:
        tier_counts[d['tier']] += 1

    total_current_stock = round(sum(v['current_stock_kg'] for v in velocities), 2)
    await save_action('categorize_items', f"Categorized {len(buffer_docs)} items | Season: {season_key} | Lead: {lead_time_days}d | Total stock: {total_current_stock} kg", user=current_user)

    return {
        "success": True,
        "total_items": len(buffer_docs),
        "tiers": dict(tier_counts),
        "thresholds": {"q25": round(q25, 3), "q50": round(q50, 3), "q75": round(q75, 3)},
        "current_season": season_key,
        "season_label": season['label'],
        "lead_time_days": lead_time_days,
        "target_total_stock_kg": target_total_stock,
        "total_current_stock_kg": total_current_stock,
        "rotation_months": ROTATION_CYCLE_MONTHS,
        "years_analyzed": num_years
    }

@api_router.get("/item-buffers")
async def get_item_buffers(
    stamp: Optional[str] = None,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all item buffer configurations with optional filters"""
    query = {}
    if stamp:
        query['stamp'] = stamp
    if tier:
        query['tier'] = tier
    if status:
        query['status'] = status
    
    items = await db.item_buffers.find(query, {"_id": 0}).sort("tier_num", 1).to_list(None)
    
    # Refresh current stock and status using INDIVIDUAL item data (not group totals)
    inv_response = await get_current_inventory_cached()
    # Build dict from by_stamp (individual level) for accurate per-item stock
    inv_dict = {}
    for stamp_items in inv_response.get('by_stamp', {}).values():
        for si in stamp_items:
            inv_dict[si['item_name']] = si
    # Also include group-level entries for items that are group leaders
    for item in inv_response.get('inventory', []) + inv_response.get('negative_items', []):
        if item['item_name'] not in inv_dict:
            inv_dict[item['item_name']] = item
    
    for item in items:
        inv_item = inv_dict.get(item['item_name'])
        current = round(inv_item['net_wt'] / 1000, 3) if inv_item else 0
        item['current_stock_kg'] = current
        min_stock = item.get('minimum_stock_kg', 0)
        reorder = item.get('reorder_buffer_kg', 0)
        vel = item.get('monthly_velocity_kg', 0)
        
        if vel <= 0:
            item['status'] = 'green'
        elif current < reorder:
            item['status'] = 'red'
        elif current < min_stock:
            item['status'] = 'yellow'
        else:
            item['status'] = 'green'
    
    return {"items": items, "total": len(items)}

@api_router.put("/item-buffers/{item_name}")
async def update_item_buffer(item_name: str, minimum_stock_kg: float = Query(...), current_user: dict = Depends(get_current_user)):
    """Update minimum stock for an item"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.item_buffers.update_one(
        {'item_name': item_name},
        {'$set': {'minimum_stock_kg': round(minimum_stock_kg, 3), 'updated_at': datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found in buffers")
    return {"success": True, "message": f"Minimum stock for '{item_name}' set to {minimum_stock_kg} kg"}

# ==================== ITEM GROUPS (merge similar items) ====================

@api_router.get("/item-groups")
async def get_item_groups(current_user: dict = Depends(get_current_user)):
    """Get all item groups with their members and mapped items"""
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    # Also get item mappings to show which items map to each member
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapping_by_master = defaultdict(list)
    for m in mappings:
        mapping_by_master[m['master_name']].append(m['transaction_name'])
    for g in groups:
        g['mapped_items'] = {}
        for member in g.get('members', []):
            g['mapped_items'][member] = mapping_by_master.get(member, [])
    return {"groups": groups}


@api_router.post("/item-groups")
async def save_item_group(group: ItemGroup, current_user: dict = Depends(get_current_user)):
    """Create or update an item group"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    if len(group.members) < 2:
        raise HTTPException(status_code=400, detail="Group needs at least 2 members")
    await db.item_groups.update_one(
        {'group_name': group.group_name},
        {'$set': {'group_name': group.group_name, 'members': group.members,
                  'updated_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"success": True, "message": f"Group '{group.group_name}' saved with {len(group.members)} members"}


@api_router.delete("/item-groups/{group_name}")
async def delete_item_group(group_name: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    await db.item_groups.delete_one({'group_name': group_name})
    return {"success": True}


@api_router.get("/item-groups/suggestions")
async def suggest_item_groups(current_user: dict = Depends(get_current_user)):
    """List all master items + auto-detected groups from mappings"""
    items = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    existing = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    grouped_items = set()
    for g in existing:
        grouped_items.update(g.get('members', []))

    # Auto-detect: master items that have mappings pointing to them
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_names = {i['item_name'] for i in items}
    mapping_by_master = defaultdict(list)
    for m in mappings:
        mapping_by_master[m['master_name']].append(m['transaction_name'])
    # Items that have transaction names mapping to them AND those names are also master items
    auto_suggestions = []
    for master, txn_names in mapping_by_master.items():
        related_masters = [t for t in txn_names if t in master_names and t != master]
        if related_masters:
            auto_suggestions.append({
                'leader': master,
                'members': [master] + related_masters
            })

    return {"items": items, "already_grouped": list(grouped_items), "auto_suggestions": auto_suggestions}


# ==================== STAMP DETAIL (click a stamp to see items + assign) ====================

@api_router.get("/stamps/{stamp_name}/detail")
async def get_stamp_detail(stamp_name: str, current_user: dict = Depends(get_current_user)):
    """Get all items in a stamp with stock info (per-stamp, not grouped)"""
    master_items = await db.master_items.find(
        {"stamp": stamp_name}, {"_id": 0}
    ).to_list(None)
    inv_response = await get_current_inventory_cached()
    
    # Use stamp_items (ungrouped, per-stamp) for correct per-stamp lookup
    inv_dict = {}
    for item in inv_response.get('stamp_items', inv_response.get('inventory', [])):
        inv_dict[item['item_name']] = item

    items_with_stock = []
    total_net_wt = 0
    for mi in master_items:
        inv = inv_dict.get(mi['item_name'])
        net_wt = round(inv['net_wt'] / 1000, 3) if inv else 0
        total_net_wt += net_wt
        items_with_stock.append({
            'item_name': mi['item_name'],
            'net_wt_kg': net_wt,
            'gr_wt_kg': round(inv['gr_wt'] / 1000, 3) if inv else 0,
        })
    items_with_stock.sort(key=lambda x: x['net_wt_kg'], reverse=True)

    assignment = await db.stamp_assignments.find_one({"stamp": stamp_name}, {"_id": 0})
    return {
        "stamp": stamp_name,
        "items": items_with_stock,
        "total_items": len(items_with_stock),
        "total_net_wt_kg": round(total_net_wt, 3),
        "assigned_user": assignment.get('assigned_user') if assignment else None
    }


# ==================== STAMP-USER ASSIGNMENT ====================

@api_router.get("/stamp-assignments")
async def get_stamp_assignments(current_user: dict = Depends(get_current_user)):
    """Get all stamp-to-user assignments"""
    assignments = await db.stamp_assignments.find({}, {"_id": 0}).to_list(None)
    return {"assignments": assignments}

@api_router.post("/stamp-assignments")
async def save_stamp_assignment(assignment: StampAssignment, current_user: dict = Depends(get_current_user)):
    """Assign a user to a stamp for notifications"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    await db.stamp_assignments.update_one(
        {'stamp': assignment.stamp},
        {'$set': {'stamp': assignment.stamp, 'assigned_user': assignment.assigned_user, 'updated_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"success": True, "message": f"User '{assignment.assigned_user}' assigned to '{assignment.stamp}'"}

@api_router.delete("/stamp-assignments/{stamp}")
async def delete_stamp_assignment(stamp: str, current_user: dict = Depends(get_current_user)):
    """Remove stamp assignment"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    await db.stamp_assignments.delete_one({'stamp': stamp})
    return {"success": True}

# ==================== ORDER MANAGEMENT ====================

@api_router.post("/orders/create")
async def create_order(order: OrderCreate, current_user: dict = Depends(get_current_user)):
    """Create a restock order"""
    # Get buffer info
    buffer_info = await db.item_buffers.find_one({'item_name': order.item_name}, {"_id": 0})
    
    order_doc = {
        'id': str(uuid.uuid4()),
        'item_name': order.item_name,
        'quantity_kg': round(order.quantity_kg, 3),
        'supplier': order.supplier,
        'notes': order.notes,
        'status': 'ordered',
        'ordered_by': current_user['username'],
        'ordered_at': datetime.now(timezone.utc).isoformat(),
        'received_at': None,
        'verified': False,
        'stamp': buffer_info.get('stamp', '') if buffer_info else '',
        'tier': buffer_info.get('tier', '') if buffer_info else ''
    }
    
    await db.orders.insert_one(order_doc)
    
    # Notify admin
    await db.notifications.insert_one({
        'id': str(uuid.uuid4()),
        'category': 'order',
        'type': 'order_placed',
        'message': f"Order placed: {order.quantity_kg} kg of '{order.item_name}' by {current_user['username']}",
        'item_name': order.item_name,
        'target_user': 'admin',
        'read': False,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "order_id": order_doc['id'], "message": "Order created"}

@api_router.get("/orders")
async def get_orders(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get all orders (admin/manager see all, others see only their own)"""
    query = {}
    if status:
        query['status'] = status
    if current_user['role'] not in ['admin', 'manager']:
        query['ordered_by'] = current_user['username']
    orders = await db.orders.find(query, {"_id": 0}).sort("ordered_at", -1).to_list(1000)
    return {"orders": orders}

@api_router.put("/orders/{order_id}/received")
async def mark_order_received(order_id: str, current_user: dict = Depends(get_current_user)):
    """Mark order as received (admin/manager only)"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    result = await db.orders.update_one(
        {'id': order_id},
        {'$set': {
            'status': 'received',
            'received_at': datetime.now(timezone.utc).isoformat(),
            'received_by': current_user['username'],
            'verified': True
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Notify admin that order was received
    order = await db.orders.find_one({'id': order_id}, {"_id": 0})
    if order:
        await db.notifications.insert_one({
            'id': str(uuid.uuid4()),
            'category': 'order',
            'type': 'order_received',
            'message': f"Order received: {order.get('quantity_kg')} kg of '{order.get('item_name')}' by {current_user['username']}",
            'item_name': order.get('item_name'),
            'target_user': 'admin',
            'read': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    return {"success": True, "message": "Order marked as received"}

@api_router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel/delete an order"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    result = await db.orders.delete_one({'id': order_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"success": True, "message": "Order cancelled"}

@api_router.get("/orders/overdue")
async def check_overdue_orders(current_user: dict = Depends(get_current_user)):
    """Check for orders that are overdue (admin/manager only)"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    overdue = await db.orders.find({
        'status': 'ordered',
        'ordered_at': {'$lt': cutoff}
    }, {"_id": 0}).to_list(None)
    
    # Generate notifications for overdue orders
    for order in overdue:
        if not order.get('overdue_notified'):
            days_ago = (datetime.now(timezone.utc) - datetime.fromisoformat(order['ordered_at'].replace('Z', '+00:00'))).days
            await db.notifications.insert_one({
                'id': str(uuid.uuid4()),
                'category': 'order',
                'type': 'order_overdue',
                'severity': 'warning',
                'message': f"OVERDUE: Order for {order.get('quantity_kg')} kg of '{order.get('item_name')}' placed {days_ago} days ago not received",
                'item_name': order.get('item_name'),
                'target_user': 'admin',
                'read': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            await db.orders.update_one({'id': order['id']}, {'$set': {'overdue_notified': True}})
    
    return {"overdue_orders": overdue, "count": len(overdue)}

# ==================== ENHANCED NOTIFICATIONS ====================

@api_router.get("/notifications/categorized")
async def get_categorized_notifications(current_user: dict = Depends(get_current_user)):
    """Get notifications organized by category"""
    username = current_user['username']
    role = current_user['role']
    query = {"$or": [
        {"target_user": username},
        {"target_user": role},
        {"target_user": "all"},
        {"for_role": role},
    ]}
    if role == 'admin':
        query["$or"].append({"target_user": "admin"})
        query["$or"].append({"for_role": "admin"})
    
    all_notifs = await db.notifications.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)
    
    categorized = {
        'stock': [n for n in all_notifs if n.get('category') == 'stock'],
        'order': [n for n in all_notifs if n.get('category') == 'order'],
        'stamp': [n for n in all_notifs if n.get('category') == 'stamp'],
        'polythene': [n for n in all_notifs if n.get('category') == 'polythene'],
        'general': [n for n in all_notifs if n.get('category', 'general') == 'general' or not n.get('category')]
    }
    
    unread = sum(1 for n in all_notifs if not n.get('read'))
    
    return {"notifications": categorized, "total_unread": unread}

@api_router.post("/notifications/check-stock-alerts")
async def check_stock_alerts(current_user: dict = Depends(get_current_user)):
    """Check all items and generate stock deficit/excess notifications"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    buffers = await db.item_buffers.find({}, {"_id": 0}).to_list(None)
    if not buffers:
        return {"success": True, "alerts_generated": 0, "message": "No buffer data. Run categorization first."}
    
    inv_response = await get_current_inventory_cached()
    inv_dict = {item['item_name']: item for item in inv_response['inventory']}
    inv_dict.update({item['item_name']: item for item in inv_response.get('negative_items', [])})
    
    # Get stamp assignments
    assignments = await db.stamp_assignments.find({}, {"_id": 0}).to_list(None)
    stamp_user = {a['stamp']: a['assigned_user'] for a in assignments}
    
    alerts = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for buf in buffers:
        inv_item = inv_dict.get(buf['item_name'])
        current = round(inv_item['net_wt'] / 1000, 3) if inv_item else 0
        min_stock = buf.get('minimum_stock_kg', 0)
        reorder = buf.get('reorder_buffer_kg', 0)
        upper = buf.get('upper_target_kg', 0)
        stamp = buf.get('stamp', '')
        
        target = stamp_user.get(stamp, 'admin')
        
        if min_stock > 0 and current < min_stock:
            deficit = round(min_stock - current, 3)
            severity = 'critical' if current < reorder else 'warning'
            
            # Notify assigned SEE
            await db.notifications.insert_one({
                'id': str(uuid.uuid4()),
                'category': 'stock',
                'type': 'stock_deficit',
                'severity': severity,
                'message': f"LOW STOCK: '{buf['item_name']}' at {current} kg (min: {min_stock} kg, deficit: {deficit} kg)",
                'item_name': buf['item_name'],
                'stamp': stamp,
                'current_stock': current,
                'minimum_stock': min_stock,
                'deficit': deficit,
                'order_range_min': round(deficit, 3),
                'order_range_max': round(upper - current, 3) if upper > current else round(deficit, 3),
                'target_user': target,
                'read': False,
                'timestamp': now
            })
            
            # If critical, also notify admin
            if severity == 'critical' and target != 'admin':
                await db.notifications.insert_one({
                    'id': str(uuid.uuid4()),
                    'category': 'stock',
                    'type': 'stock_deficit',
                    'severity': 'critical',
                    'message': f"CRITICAL: '{buf['item_name']}' at {current} kg (below buffer!)",
                    'item_name': buf['item_name'],
                    'stamp': stamp,
                    'target_user': 'admin',
                    'read': False,
                    'timestamp': now
                })
            
            alerts += 1
        
        elif upper > 0 and current > upper:
            excess = round(current - upper, 3)
            await db.notifications.insert_one({
                'id': str(uuid.uuid4()),
                'category': 'stock',
                'type': 'stock_excess',
                'severity': 'info',
                'message': f"EXCESS: '{buf['item_name']}' at {current} kg (upper: {upper} kg, excess: {excess} kg)",
                'item_name': buf['item_name'],
                'stamp': stamp,
                'target_user': target,
                'read': False,
                'timestamp': now
            })
            alerts += 1
    
    return {"success": True, "alerts_generated": alerts}

@api_router.get("/stock-alerts/auto")
async def auto_stock_alerts(current_user: dict = Depends(get_current_user)):
    """Lightweight auto-check: returns current stock alerts for the user without generating new notifications.
    Only regenerates alerts if last check was > 30 minutes ago."""
    
    username = current_user['username']
    role = current_user['role']
    
    # Check if we need to regenerate alerts (throttle to every 30 min)
    last_check = await db.system_state.find_one({'key': 'last_stock_alert_check'}, {'_id': 0})
    now = datetime.now(timezone.utc)
    should_regenerate = True
    
    if last_check and last_check.get('timestamp'):
        try:
            last_ts = datetime.fromisoformat(last_check['timestamp'])
            if (now - last_ts).total_seconds() < 1800:  # 30 minutes
                should_regenerate = False
        except:
            pass
    
    if should_regenerate:
        # Run the stock alert check
        buffers = await db.item_buffers.find({}, {"_id": 0}).to_list(None)
        if buffers:
            inv_response = await get_current_inventory_cached()
            inv_dict = {item['item_name']: item for item in inv_response['inventory']}
            inv_dict.update({item['item_name']: item for item in inv_response.get('negative_items', [])})
            
            assignments = await db.stamp_assignments.find({}, {"_id": 0}).to_list(None)
            stamp_user = {a['stamp']: a['assigned_user'] for a in assignments}
            
            # Clear old stock alerts (only stock category)
            await db.notifications.delete_many({'category': 'stock', 'type': {'$in': ['stock_deficit', 'stock_excess']}})
            
            now_str = now.isoformat()
            for buf in buffers:
                inv_item = inv_dict.get(buf['item_name'])
                current = round(inv_item['net_wt'] / 1000, 3) if inv_item else 0
                min_stock = buf.get('minimum_stock_kg', 0)
                reorder = buf.get('reorder_buffer_kg', 0)
                upper = buf.get('upper_target_kg', 0)
                stamp = buf.get('stamp', '')
                target = stamp_user.get(stamp, 'admin')
                
                if min_stock > 0 and current < min_stock:
                    deficit = round(min_stock - current, 3)
                    severity = 'critical' if current < reorder else 'warning'
                    
                    await db.notifications.insert_one({
                        'id': str(uuid.uuid4()), 'category': 'stock', 'type': 'stock_deficit',
                        'severity': severity,
                        'message': f"LOW STOCK: '{buf['item_name']}' at {current} kg (min: {min_stock} kg)",
                        'item_name': buf['item_name'], 'stamp': stamp,
                        'current_stock': current, 'minimum_stock': min_stock, 'deficit': deficit,
                        'order_range_min': round(deficit, 3),
                        'order_range_max': round(upper - current, 3) if upper > current else round(deficit, 3),
                        'target_user': target, 'read': False, 'timestamp': now_str
                    })
                    
                    if severity == 'critical' and target != 'admin':
                        await db.notifications.insert_one({
                            'id': str(uuid.uuid4()), 'category': 'stock', 'type': 'stock_deficit',
                            'severity': 'critical',
                            'message': f"CRITICAL: '{buf['item_name']}' at {current} kg (below buffer!)",
                            'item_name': buf['item_name'], 'stamp': stamp,
                            'target_user': 'admin', 'read': False, 'timestamp': now_str
                        })
            
            await db.system_state.update_one(
                {'key': 'last_stock_alert_check'},
                {'$set': {'key': 'last_stock_alert_check', 'timestamp': now.isoformat()}},
                upsert=True
            )
    
    # Return alerts relevant to this user
    query = {'category': 'stock', 'type': 'stock_deficit', 'read': False}
    if role != 'admin':
        query['target_user'] = username
    
    alerts = await db.notifications.find(query, {"_id": 0}).sort("severity", 1).to_list(None)
    
    return {"alerts": alerts, "count": len(alerts)}

# ==================== HISTORICAL PROFIT ANALYSIS (Aggregation-based, scales to 1M+ txns) ====================

@api_router.get("/analytics/historical-profit")
async def get_historical_profit(
    year: Optional[str] = None,
    view: str = "yearly",
    current_user: dict = Depends(get_current_user)
):
    """
    Profit analysis from historical_transactions using MongoDB aggregation.
    NEVER loads raw documents into Python — all heavy lifting done in MongoDB.
    Scales comfortably to 500k+ transactions per year.
    """
    match_filter = {}
    if year:
        match_filter["historical_year"] = year

    # 1. Load item mappings + groups for group-aware resolution
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    h_mapping_dict, h_member_to_leader, _ = build_group_maps(all_groups, all_mappings)
    def resolve(name):
        return resolve_to_leader(name, h_mapping_dict, h_member_to_leader)

    # 2. Purchase basis via aggregation (grouped by item_name)
    purchase_agg = await db.historical_transactions.aggregate([
        {"$match": {**match_filter, "type": "purchase", "net_wt": {"$gt": 0.001}}},
        {"$group": {
            "_id": "$item_name",
            "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
            "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"}, "gr_wt": {"$sum": "$gr_wt"}
        }}
    ]).to_list(None)

    # Merge into master items using mappings
    purchase_basis = {}
    for doc in purchase_agg:
        master = resolve(doc["_id"])
        if master not in purchase_basis:
            purchase_basis[master] = {"fine": 0.0, "net_wt": 0.0, "labor": 0.0}
        purchase_basis[master]["fine"] += doc["fine"] or 0
        purchase_basis[master]["net_wt"] += doc["net_wt"] or 0
        purchase_basis[master]["labor"] += (doc.get("total_amount") or doc.get("labor") or 0)
    del purchase_agg

    # Compute avg tunch and labor/g per master item
    for item, d in purchase_basis.items():
        nw = d["net_wt"]
        if nw > 0.001:
            d["avg_tunch"] = (d["fine"] / nw) * 100 if d["fine"] > 0 else 0
            d["labor_per_gram"] = d["labor"] / nw
        else:
            d["avg_tunch"] = 0
            d["labor_per_gram"] = 0

    # === VIEW: YEARLY ===
    if view == "yearly":
        sale_item_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "sale", "net_wt": {"$gt": 0.001}}},
            {"$group": {
                "_id": "$item_name",
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"},
                "count": {"$sum": 1}
            }}
        ]).to_list(None)

        silver_kg = 0.0; labor_inr = 0.0; total_wt = 0.0; matched = 0
        total_sale_val = 0.0; total_sale_recs = 0
        for doc in sale_item_agg:
            master = resolve(doc["_id"])
            basis = purchase_basis.get(master)
            nw = doc["net_wt"] or 0
            total_sale_val += doc.get("total_amount") or 0
            total_sale_recs += doc["count"]
            if not basis or nw < 0.001:
                continue
            s_tunch = (doc["fine"] / nw) * 100 if (doc["fine"] or 0) > 0 else 0
            s_lpg = (doc.get("total_amount") or doc.get("labor") or 0) / nw
            silver_kg += (s_tunch - basis["avg_tunch"]) * nw / 100 / 1000
            labor_inr += (s_lpg - basis["labor_per_gram"]) * nw
            total_wt += nw / 1000
            matched += doc["count"]

        # Purchase totals
        purch_stats = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "purchase"}},
            {"$group": {"_id": None, "total_amount": {"$sum": "$total_amount"}, "count": {"$sum": 1}}}
        ]).to_list(1)
        p_val = purch_stats[0]["total_amount"] if purch_stats else 0
        p_cnt = purch_stats[0]["count"] if purch_stats else 0

        return {
            "view": "yearly", "year": year,
            "silver_profit_kg": round(silver_kg, 3), "labor_profit_inr": round(labor_inr, 2),
            "total_sold_kg": round(total_wt, 3), "total_transactions": matched,
            "total_sales_value": round(total_sale_val, 2), "total_purchase_value": round(p_val, 2),
            "total_sale_records": total_sale_recs, "total_purchase_records": p_cnt,
        }

    # === VIEW: CUSTOMER ===
    if view == "customer":
        cust_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "sale", "net_wt": {"$gt": 0.001}}},
            {"$group": {
                "_id": {"party": "$party_name", "item": "$item_name"},
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"}, "count": {"$sum": 1}
            }}
        ]).to_list(None)

        cust_profit = defaultdict(lambda: {"silver": 0.0, "labor": 0.0, "wt": 0.0, "cnt": 0})
        for doc in cust_agg:
            party = doc["_id"]["party"] or "Unknown"
            master = resolve(doc["_id"]["item"])
            basis = purchase_basis.get(master)
            nw = doc["net_wt"] or 0
            if not basis or nw < 0.001:
                continue
            s_tunch = (doc["fine"] / nw) * 100 if (doc["fine"] or 0) > 0 else 0
            s_lpg = (doc.get("total_amount") or doc.get("labor") or 0) / nw
            cust_profit[party]["silver"] += (s_tunch - basis["avg_tunch"]) * nw / 100 / 1000
            cust_profit[party]["labor"] += (s_lpg - basis["labor_per_gram"]) * nw
            cust_profit[party]["wt"] += nw / 1000
            cust_profit[party]["cnt"] += doc["count"]

        rows = [{"name": k, "silver_profit_kg": round(v["silver"], 3),
                 "labor_profit_inr": round(v["labor"], 2),
                 "total_sold_kg": round(v["wt"], 3), "transactions": v["cnt"]}
                for k, v in cust_profit.items() if v["cnt"] > 0]
        rows.sort(key=lambda x: x["silver_profit_kg"], reverse=True)
        return {"view": "customer", "year": year, "data": rows, "total": len(rows)}

    # === VIEW: SUPPLIER ===
    if view == "supplier":
        # Purchase grouped by supplier + item (via aggregation)
        sup_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "purchase", "net_wt": {"$gt": 0.001}}},
            {"$group": {
                "_id": {"party": "$party_name", "item": "$item_name"},
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}
            }}
        ]).to_list(None)

        # Global sale averages per master item (via aggregation)
        sale_avg_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "sale", "net_wt": {"$gt": 0.001}}},
            {"$group": {
                "_id": "$item_name",
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"}
            }}
        ]).to_list(None)

        # Merge sale averages by master item
        item_sale_avg = {}
        sale_merged = defaultdict(lambda: {"fine": 0.0, "net_wt": 0.0, "labor": 0.0, "total_amount": 0.0})
        for doc in sale_avg_agg:
            master = resolve(doc["_id"])
            sale_merged[master]["fine"] += doc["fine"] or 0
            sale_merged[master]["net_wt"] += doc["net_wt"] or 0
            sale_merged[master]["labor"] += doc["labor"] or 0
            sale_merged[master]["total_amount"] += doc.get("total_amount") or 0
        for master, sa in sale_merged.items():
            snw = sa["net_wt"]
            if snw > 0.001:
                labour_total = sa.get("total_amount") or sa.get("labor") or 0
                item_sale_avg[master] = {
                    "avg_tunch": (sa["fine"] / snw) * 100 if sa["fine"] > 0 else 0,
                    "labor_per_gram": labour_total / snw,
                }

        # Calculate per-supplier profit
        sup_profit = defaultdict(lambda: {"silver": 0.0, "labor": 0.0, "wt": 0.0, "items": set()})
        for doc in sup_agg:
            supplier = doc["_id"]["party"] or "Unknown"
            master = resolve(doc["_id"]["item"])
            avg_sale = item_sale_avg.get(master)
            pw = doc["net_wt"] or 0
            if not avg_sale or pw < 0.001:
                continue
            p_tunch = (doc["fine"] / pw) * 100 if (doc["fine"] or 0) > 0 else 0
            p_lpg = (doc["labor"] or 0) / pw
            sup_profit[supplier]["silver"] += (avg_sale["avg_tunch"] - p_tunch) * pw / 100 / 1000
            sup_profit[supplier]["labor"] += (avg_sale["labor_per_gram"] - p_lpg) * pw
            sup_profit[supplier]["wt"] += pw / 1000
            sup_profit[supplier]["items"].add(master)

        rows = [{"name": k, "silver_profit_kg": round(v["silver"], 3),
                 "labor_profit_inr": round(v["labor"], 2),
                 "total_purchased_kg": round(v["wt"], 3), "items_count": len(v["items"])}
                for k, v in sup_profit.items() if len(v["items"]) > 0]
        rows.sort(key=lambda x: x["silver_profit_kg"], reverse=True)
        return {"view": "supplier", "year": year, "data": rows, "total": len(rows)}

    # === VIEW: ITEM ===
    if view == "item":
        item_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "sale", "net_wt": {"$gt": 0.001}}},
            {"$group": {
                "_id": "$item_name",
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"}, "count": {"$sum": 1}
            }}
        ]).to_list(None)

        # Merge by master item
        master_agg = defaultdict(lambda: {"fine": 0.0, "net_wt": 0.0, "labor": 0.0, "total_amount": 0.0, "count": 0})
        for doc in item_agg:
            master = resolve(doc["_id"])
            master_agg[master]["fine"] += doc["fine"] or 0
            master_agg[master]["net_wt"] += doc["net_wt"] or 0
            master_agg[master]["labor"] += doc["labor"] or 0
            master_agg[master]["total_amount"] += doc.get("total_amount") or 0
            master_agg[master]["count"] += doc["count"]

        rows = []
        for master, sa in master_agg.items():
            basis = purchase_basis.get(master)
            snw = sa["net_wt"]
            if not basis or snw < 0.001 or sa["count"] == 0:
                continue
            sell_tunch = (sa["fine"] / snw) * 100 if sa["fine"] > 0 else 0
            buy_tunch = basis["avg_tunch"]
            silver_kg = round((sell_tunch - buy_tunch) * snw / 100 / 1000, 3)
            s_lpg = (sa.get("total_amount") or sa.get("labor") or 0) / snw
            labor_inr = round((s_lpg - basis["labor_per_gram"]) * snw, 2)
            rows.append({"name": master, "silver_profit_kg": silver_kg, "labor_profit_inr": labor_inr,
                         "total_sold_kg": round(snw / 1000, 3), "transactions": sa["count"],
                         "avg_purchase_tunch": round(buy_tunch, 2), "avg_sale_tunch": round(sell_tunch, 2)})
        rows.sort(key=lambda x: x["silver_profit_kg"], reverse=True)
        return {"view": "item", "year": year, "data": rows, "total": len(rows)}

    # === VIEW: MONTH ===
    if view == "month":
        month_agg = await db.historical_transactions.aggregate([
            {"$match": {**match_filter, "type": "sale", "net_wt": {"$gt": 0.001}}},
            {"$addFields": {"month_key": {"$substr": ["$date", 0, 7]}}},
            {"$group": {
                "_id": {"month": "$month_key", "item": "$item_name"},
                "fine": {"$sum": "$fine"}, "net_wt": {"$sum": "$net_wt"},
                "labor": {"$sum": "$labor"}, "total_amount": {"$sum": "$total_amount"}, "count": {"$sum": 1}
            }}
        ]).to_list(None)

        month_profit = defaultdict(lambda: {"silver": 0.0, "labor": 0.0, "wt": 0.0, "cnt": 0})
        for doc in month_agg:
            mk = doc["_id"]["month"] or "Unknown"
            master = resolve(doc["_id"]["item"])
            basis = purchase_basis.get(master)
            nw = doc["net_wt"] or 0
            if not basis or nw < 0.001:
                month_profit[mk]["cnt"] += doc["count"]
                month_profit[mk]["wt"] += nw / 1000
                continue
            s_tunch = (doc["fine"] / nw) * 100 if (doc["fine"] or 0) > 0 else 0
            s_lpg = (doc.get("total_amount") or doc.get("labor") or 0) / nw
            month_profit[mk]["silver"] += (s_tunch - basis["avg_tunch"]) * nw / 100 / 1000
            month_profit[mk]["labor"] += (s_lpg - basis["labor_per_gram"]) * nw
            month_profit[mk]["wt"] += nw / 1000
            month_profit[mk]["cnt"] += doc["count"]

        MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        rows = []
        for mk, v in sorted(month_profit.items()):
            parts = mk.split("-")
            if len(parts) == 2:
                yr_short = parts[0][2:]  # "2025" → "25"
                mi = int(parts[1]) if parts[1].isdigit() else 0
                label = f"{MONTH_NAMES[mi]} {yr_short}" if 1 <= mi <= 12 else mk
            else:
                label = mk
            rows.append({"month": mk, "month_name": label,
                         "silver_profit_kg": round(v["silver"], 3),
                         "labor_profit_inr": round(v["labor"], 2),
                         "total_sold_kg": round(v["wt"], 3), "transactions": v["cnt"]})
        return {"view": "month", "year": year, "data": rows, "total": len(rows)}

    raise HTTPException(status_code=400, detail="Invalid view. Use: customer, supplier, item, month, yearly")


# ==================== DATA VISUALIZATION ====================

@api_router.get("/analytics/visualization")
async def get_visualization_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    trend_granularity: Optional[str] = "auto",
    current_user: dict = Depends(get_current_user)
):
    """Get aggregated data for charts and visualizations"""
    query = {}
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date + ' 23:59:59'}
    
    # Get buffer info for tier colors
    buffers = await db.item_buffers.find({}, {"_id": 0}).to_list(None)
    tier_map = {b['item_name']: b.get('tier', 'unknown') for b in buffers}
    
    # Load mappings + groups for resolving to leaders
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in all_mappings}
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    member_to_leader = {}
    for g in groups:
        for member in g.get('members', []):
            member_to_leader[member] = g['group_name']
    def _resolve(name):
        master = mapping_dict.get(name, name)
        return member_to_leader.get(master, master)

    # Single streamed pass fills all accumulators (memory stays flat)
    item_sales = defaultdict(lambda: {'net_wt': 0, 'amount': 0, 'count': 0})
    party_sales = defaultdict(lambda: {'net_wt': 0, 'amount': 0, 'count': 0})
    supplier_purchases = defaultdict(lambda: {'net_wt': 0, 'amount': 0, 'count': 0})
    all_sale_dates = set()
    monthly_sales = defaultdict(lambda: {'net_wt': 0, 'amount': 0})
    daily_sales = defaultdict(lambda: {'net_wt': 0, 'amount': 0})
    _vz_proj = {"_id": 0, "date": 1, "type": 1, "item_name": 1, "party_name": 1,
                "net_wt": 1, "total_amount": 1}
    async for t in db.transactions.find(query, _vz_proj):
        if t['type'] in ['sale', 'sale_return']:
            name = _resolve(t.get('item_name', ''))
            item_sales[name]['net_wt'] += t.get('net_wt', 0)
            item_sales[name]['amount'] += t.get('total_amount', 0)
            item_sales[name]['count'] += 1
            party = t.get('party_name', 'Unknown')
            party_sales[party]['net_wt'] += t.get('net_wt', 0)
            party_sales[party]['amount'] += t.get('total_amount', 0)
            party_sales[party]['count'] += 1
            if t.get('date'):
                date_str = t['date'][:10]
                month = t['date'][:7]
                all_sale_dates.add(date_str)
                monthly_sales[month]['net_wt'] += t.get('net_wt', 0)
                monthly_sales[month]['amount'] += t.get('total_amount', 0)
                daily_sales[date_str]['net_wt'] += t.get('net_wt', 0)
                daily_sales[date_str]['amount'] += t.get('total_amount', 0)
        elif t['type'] in ['purchase', 'purchase_return']:
            party = t.get('party_name', 'Unknown')
            supplier_purchases[party]['net_wt'] += t.get('net_wt', 0)
            supplier_purchases[party]['amount'] += t.get('total_amount', 0)
            supplier_purchases[party]['count'] += 1
    
    sales_by_item = sorted([
        {'item_name': k, 'net_wt_kg': round(v['net_wt']/1000, 3), 'amount': round(v['amount'], 2), 'count': v['count'], 'tier': tier_map.get(k, 'unknown')}
        for k, v in item_sales.items() if v['net_wt'] > 0
    ], key=lambda x: x['net_wt_kg'], reverse=True)[:30]
    
    sales_by_party = sorted([
        {'party_name': k, 'net_wt_kg': round(v['net_wt']/1000, 3), 'amount': round(v['amount'], 2), 'count': v['count']}
        for k, v in party_sales.items() if v['net_wt'] > 0
    ], key=lambda x: x['net_wt_kg'], reverse=True)[:20]
    
    purchases_by_supplier = sorted([
        {'party_name': k, 'net_wt_kg': round(v['net_wt']/1000, 3), 'amount': round(v['amount'], 2), 'count': v['count']}
        for k, v in supplier_purchases.items() if v['net_wt'] > 0
    ], key=lambda x: x['net_wt_kg'], reverse=True)[:20]
    
    # 4. Tier distribution
    tier_dist = defaultdict(lambda: {'count': 0, 'total_stock_kg': 0})
    for b in buffers:
        t = b.get('tier', 'unknown')
        tier_dist[t]['count'] += 1
        tier_dist[t]['total_stock_kg'] += b.get('current_stock_kg', 0)
    
    tier_distribution = [{'tier': k, 'count': v['count'], 'total_stock_kg': round(v['total_stock_kg'], 3)} for k, v in tier_dist.items()]
    
    # 5. Sales trend granularity (accumulators filled in the streamed pass above)
    use_daily = trend_granularity == 'daily'
    if trend_granularity == 'auto' and all_sale_dates:
        sorted_dates = sorted(all_sale_dates)
        try:
            from datetime import datetime as dt_cls
            first = dt_cls.strptime(sorted_dates[0], '%Y-%m-%d')
            last = dt_cls.strptime(sorted_dates[-1], '%Y-%m-%d')
            use_daily = (last - first).days <= 60
        except Exception:
            use_daily = len(all_sale_dates) <= 60
    
    if use_daily:
        sales_trend = sorted([
            {'label': k, 'net_wt_kg': round(v['net_wt']/1000, 3), 'amount': round(v['amount'], 2)}
            for k, v in daily_sales.items()
        ], key=lambda x: x['label'])
    else:
        sales_trend = sorted([
            {'label': k, 'net_wt_kg': round(v['net_wt']/1000, 3), 'amount': round(v['amount'], 2)}
            for k, v in monthly_sales.items()
        ], key=lambda x: x['label'])
    
    # 6. Stock health summary
    status_counts = {'red': 0, 'green': 0, 'yellow': 0}
    for b in buffers:
        s = b.get('status', 'green')
        if s in status_counts:
            status_counts[s] += 1
    
    return {
        "sales_by_item": sales_by_item,
        "sales_by_party": sales_by_party,
        "purchases_by_supplier": purchases_by_supplier,
        "tier_distribution": tier_distribution,
        "sales_trend": sales_trend,
        "trend_granularity": "daily" if use_daily else "monthly",
        "stock_health": status_counts
    }

# ==================== HISTORICAL DATA & SEASONAL ====================

# ---- Business Constants: Wholesale Silver Stock Rotation Model ----
ROTATION_CYCLE_MONTHS = 2.73  # Full stock rotation period

SEASON_PROFILES = {
    'peak': {
        'months': [10, 11, 12, 1, 4, 5],   # Diwali, weddings, Akshaya Tritiya, Sankranti
        'label': 'Peak Season (Festivals & Weddings)',
        'monthly_sales_benchmark_kg': 7000,  # 6500-8000 avg
        'target_total_stock_kg': 10500,
        'lead_time_days': 10,                # orders take longer in peak
    },
    'normal': {
        'months': [2, 3, 6],                # Transition months
        'label': 'Normal Season',
        'monthly_sales_benchmark_kg': 2500,
        'target_total_stock_kg': 8200,
        'lead_time_days': 7,
    },
    'off_season': {
        'months': [7, 8, 9],                # Monsoon / lean months
        'label': 'Off Season (Monsoon)',
        'monthly_sales_benchmark_kg': 1800,
        'target_total_stock_kg': 7500,
        'lead_time_days': 7,
    },
}

# Total stock thresholds (aggregate)
STOCK_FLOOR_KG = 7500   # Below this, sales decline
STOCK_NORMAL_KG = 8200   # Normal operating stock
STOCK_PEAK_KG = 10500    # Max effective stock (sales plateau beyond this)

def get_current_season(month=None):
    """Return the season profile key for a given month."""
    if month is None:
        month = datetime.now(timezone.utc).month
    for key, profile in SEASON_PROFILES.items():
        if month in profile['months']:
            return key
    return 'normal'  # fallback


@api_router.post("/historical/upload")
async def upload_historical_data(
    file_type: str,
    year: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload historical sales/purchase data for AI training (does NOT affect current stock)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    if file_type not in ['sale', 'purchase']:
        raise HTTPException(status_code=400, detail="file_type must be 'sale' or 'purchase'")
    
    content = await file.read()
    logger.info(f"[Historical Direct Upload] file_type={file_type}, year={year}, size={len(content)} bytes")
    
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(_parse_executor, parse_excel_file, content, file_type)
    del content  # Free memory
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found")
    
    batch_id = str(uuid.uuid4())
    
    # Store in historical_transactions collection (NOT transactions)
    for record in records:
        record['batch_id'] = batch_id
        record['historical_year'] = year
        record['is_historical'] = True

    hist_docs = _prepare_transactions(records, batch_id)
    await batch_insert(db.historical_transactions, hist_docs)
    
    # Verify insertion
    verify_count = await db.historical_transactions.count_documents({"batch_id": batch_id})
    logger.info(f"[Historical Direct Upload] Inserted and verified {verify_count} records for batch {batch_id}")
    
    await save_action('upload_historical', f"Uploaded {verify_count} historical {file_type} records for year {year}", user=current_user)
    
    return {
        "success": True,
        "count": verify_count,
        "year": year,
        "file_type": file_type,
        "batch_id": batch_id,
        "message": f"Uploaded {verify_count} historical {file_type} records for {year}"
    }


@api_router.get("/historical/summary")
async def get_historical_summary(current_user: dict = Depends(get_current_user)):
    """Get summary of uploaded historical data"""
    try:
        pipeline = [
            {"$match": {"historical_year": {"$ne": None, "$exists": True}}},
            {"$group": {
                "_id": {
                    "year": "$historical_year",
                    "type": {"$cond": [
                        {"$in": ["$type", ["sale", "sale_return"]]}, "sale", "purchase"
                    ]}
                },
                "count": {"$sum": 1},
                "total_net_wt": {"$sum": "$net_wt"}
            }},
            {"$sort": {"_id.year": 1, "_id.type": 1}}
        ]
        results = await db.historical_transactions.aggregate(pipeline).to_list(None)
        
        summary = {}
        for r in results:
            year = r['_id'].get('year')
            if not year:
                continue
            ttype = r['_id']['type']
            if year not in summary:
                summary[year] = {}
            total_wt = r.get('total_net_wt', 0) or 0
            summary[year][ttype] = {
                'count': r['count'],
                'total_kg': round(total_wt / 1000, 3)
            }
        
        return {"summary": summary, "years": sorted(summary.keys())}
    except Exception as e:
        # Fallback: direct count if aggregation fails
        logger.error(f"Historical summary aggregation failed: {e}")
        total = await db.historical_transactions.count_documents({})
        if total > 0:
            years = await db.historical_transactions.distinct("historical_year")
            years = [y for y in years if y]
            fallback = {}
            for yr in years:
                sale_c = await db.historical_transactions.count_documents({"historical_year": yr, "type": {"$in": ["sale", "sale_return"]}})
                purch_c = await db.historical_transactions.count_documents({"historical_year": yr, "type": {"$in": ["purchase", "purchase_return"]}})
                fallback[yr] = {}
                if sale_c:
                    fallback[yr]["sale"] = {"count": sale_c, "total_kg": 0}
                if purch_c:
                    fallback[yr]["purchase"] = {"count": purch_c, "total_kg": 0}
            return {"summary": fallback, "years": sorted(years)}
        return {"summary": {}, "years": []}


@api_router.delete("/historical/{year}")
async def delete_historical_year(year: str, current_user: dict = Depends(get_current_user)):
    """Delete historical data for a specific year"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.historical_transactions.delete_many({"historical_year": year})
    return {"success": True, "deleted_count": result.deleted_count}


@api_router.get("/historical/debug")
async def debug_historical(current_user: dict = Depends(get_current_user)):
    """Diagnostic endpoint — shows raw DB state for historical data"""
    total = await db.historical_transactions.count_documents({})
    with_year = await db.historical_transactions.count_documents({"historical_year": {"$exists": True, "$ne": None}})
    without_year = total - with_year
    years = await db.historical_transactions.distinct("historical_year")
    types = await db.historical_transactions.distinct("type")
    
    by_year_type = {}
    for yr in (years or []):
        if not yr:
            continue
        by_year_type[yr] = {}
        for t in (types or []):
            c = await db.historical_transactions.count_documents({"historical_year": yr, "type": t})
            if c > 0:
                by_year_type[yr][t] = c
    
    # Check upload sessions
    active_sessions = await db.upload_sessions.count_documents({})
    pending_chunks = await db.upload_chunks.count_documents({})
    
    return {
        "total_records": total,
        "with_historical_year": with_year,
        "without_historical_year": without_year,
        "years": [y for y in years if y],
        "types": types,
        "breakdown": by_year_type,
        "active_upload_sessions": active_sessions,
        "pending_chunks": pending_chunks,
    }



# NOTE: Old /ai/seasonal-analysis endpoint removed — replaced by deterministic
# ML-based seasonal analytics at /api/seasonal/* routes.

@api_router.post("/ai/update-buffers-seasonal")
async def update_buffers_with_seasonal(current_user: dict = Depends(get_current_user)):
    """Update item buffers incorporating seasonal demand patterns"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Get seasonal analysis data via aggregation (memory-efficient)
    monthly_item_sales = defaultdict(lambda: defaultdict(float))
    
    for coll in [db.transactions, db.historical_transactions]:
        pipeline = [
            {"$match": {"type": {"$in": ["sale", "sale_return"]}}},
            {"$project": {"item_name": 1, "net_wt": 1, "month": {"$substr": ["$date", 5, 2]}}},
            {"$group": {"_id": {"item": "$item_name", "month": "$month"}, "total_wt": {"$sum": "$net_wt"}}},
        ]
        async for doc in coll.aggregate(pipeline):
            item = doc['_id']['item']
            try:
                month = int(doc['_id']['month'])
            except (ValueError, TypeError):
                continue
            monthly_item_sales[item][month] += abs(doc['total_wt']) / 1000
    
    now = datetime.now()
    current_month = now.month
    upcoming_months = [(current_month + i - 1) % 12 + 1 for i in range(1, 3)]
    
    updated = 0
    for item, month_data in monthly_item_sales.items():
        total = sum(month_data.values())
        if total < 0.01:
            continue
        avg = total / max(len(month_data), 1)
        
        # Calculate seasonal boost for upcoming period
        upcoming_demand = sum(month_data.get(m, avg) for m in upcoming_months)
        expected = avg * len(upcoming_months)
        boost = upcoming_demand / expected if expected > 0 else 1.0
        boost = max(min(boost, 2.0), 0.5)  # Cap between 0.5x and 2x
        
        # Update buffer with seasonal adjustment
        existing = await db.item_buffers.find_one({'item_name': item}, {"_id": 0})
        if existing:
            base_min = existing.get('minimum_stock_kg', 0)
            base_reorder = existing.get('reorder_buffer_kg', 0)
            base_upper = existing.get('upper_target_kg', 0)
            
            await db.item_buffers.update_one(
                {'item_name': item},
                {'$set': {
                    'seasonal_boost': round(boost, 2),
                    'seasonal_min_stock_kg': round(base_min * boost, 3),
                    'seasonal_reorder_buffer_kg': round(base_reorder * boost, 3),
                    'seasonal_upper_target_kg': round(base_upper * boost, 3),
                    'seasonal_updated_at': now.isoformat()
                }}
            )
            updated += 1
    
    await save_action('seasonal_buffer_update', f"Updated {updated} items with seasonal adjustments", user=current_user)
    return {"success": True, "items_updated": updated}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
