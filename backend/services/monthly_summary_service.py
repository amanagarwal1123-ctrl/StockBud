"""
Pre-computed Monthly Summary Service
Computes and stores monthly aggregates for instant retrieval.
Triggered on data upload or manual recompute.

Freshness model
---------------
Every recompute writes a `_meta` document per year containing
(txn_count, max_created_at, computed_at). On every read, callers can use
``ensure_year_summary_fresh(db, year)`` which compares the stored fingerprint
to the current state of `transactions` for that year and recomputes only if
they diverge. This guarantees Dashboard / Profit Analysis never serve stale
totals after a new upload, even if the background task lost in flight.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from services.group_utils import build_group_maps, build_group_ledger, resolve_to_leader
from services.profit_helpers import ledger_cost_basis, aggregate_sale_profit, fetch_ledger_with_fallback


EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]

# Bump this whenever the profit/summary computation logic changes so that pre-computed
# summaries from an older logic version are treated as stale and auto-recomputed on the
# next read (no manual "recompute" needed after a deploy).
# v2: cumulative-ledger cost basis + per-entry (atom-by-atom) silver/labour profit.
PROFIT_LOGIC_VERSION = 6

logger = logging.getLogger(__name__)


async def recompute_monthly_summaries(db, year: int = None):
    """Recompute all monthly summaries for a given year (or all years if None)."""
    
    if year is None:
        # Get all distinct years from transactions
        all_dates = await db.transactions.distinct('date')
        years = set()
        for d in all_dates:
            if d and len(d) >= 4:
                try:
                    years.add(int(d[:4]))
                except ValueError:
                    pass
        if not years:
            return {"recomputed": 0, "years": []}
    else:
        years = {year}
    
    total_docs = 0
    for yr in sorted(years):
        total_docs += await _compute_year(db, yr)
    
    return {"recomputed": total_docs, "years": sorted(years)}


async def _get_year_fingerprint(db, year: int):
    """Return (txn_count, max_created_at) for a year's transactions.

    Used to detect whether the monthly summaries are stale relative to the
    current state of the `transactions` collection. Both fields together
    catch inserts, deletes, and replacements done by re-uploads.
    """
    start = f"{year}-01-01"
    end = f"{year}-12-31 23:59:59"
    count = await db.transactions.count_documents({'date': {'$gte': start, '$lte': end}})
    max_created = None
    if count > 0:
        cursor = db.transactions.aggregate([
            {'$match': {'date': {'$gte': start, '$lte': end}}},
            {'$group': {'_id': None, 'max_created': {'$max': '$created_at'}}}
        ])
        async for doc in cursor:
            max_created = doc.get('max_created')
            break
    return count, max_created


async def get_year_meta(db, year: int):
    """Return the stored _meta doc for a year (or None)."""
    return await db.monthly_summaries.find_one(
        {"year": year, "summary_type": "_meta"},
        {"_id": 0}
    )


async def is_year_summary_stale(db, year: int):
    """True if the year's pre-computed summaries diverge from live transactions."""
    meta = await get_year_meta(db, year)
    if not meta:
        return True
    # Logic version bump -> existing summaries were computed with old math -> stale.
    if meta.get('logic_version') != PROFIT_LOGIC_VERSION:
        return True
    current_count, current_max_created = await _get_year_fingerprint(db, year)
    if meta.get('txn_count') != current_count:
        return True
    if (meta.get('max_created_at') or '') != (current_max_created or ''):
        return True
    return False


async def ensure_year_summary_fresh(db, year: int):
    """Recompute the year if stale; otherwise no-op. Returns status dict."""
    stale = await is_year_summary_stale(db, year)
    if not stale:
        meta = await get_year_meta(db, year)
        return {
            "recomputed": False,
            "last_computed_at": (meta or {}).get('computed_at'),
            "txn_count": (meta or {}).get('txn_count', 0),
        }
    try:
        await _compute_year(db, year)
        meta = await get_year_meta(db, year)
        return {
            "recomputed": True,
            "last_computed_at": (meta or {}).get('computed_at'),
            "txn_count": (meta or {}).get('txn_count', 0),
        }
    except Exception as e:
        logger.error(f"[monthly_summaries] ensure_year_summary_fresh({year}) failed: {e}", exc_info=True)
        meta = await get_year_meta(db, year)
        return {
            "recomputed": False,
            "error": str(e),
            "last_computed_at": (meta or {}).get('computed_at'),
            "txn_count": (meta or {}).get('txn_count', 0),
        }


async def _compute_year(db, year: int):
    """Compute all summaries for a single year."""
    
    # Projection keeps memory bounded; transactions are fetched month-by-month below
    _tx_proj = {"_id": 0, "date": 1, "item_name": 1, "type": 1, "net_wt": 1, "gr_wt": 1,
                "fine": 1, "tunch": 1, "labor": 1, "total_amount": 1, "party_name": 1}

    # Load mappings and groups
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    master_items = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    master_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in master_items}
    
    p_mapping_dict, p_member_to_leader, _ = build_group_maps(all_groups, mappings)
    
    # Load purchase ledger for cost basis (+ estimated fallback from purchase history)
    all_ledger = await fetch_ledger_with_fallback(db, all_groups, mappings, use_cache=False)
    grp_ledger = build_group_ledger(all_ledger, all_groups, mappings)
    
    def _resolve(name):
        return resolve_to_leader(name, p_mapping_dict, p_member_to_leader)
    
    docs_written = 0
    
    # Delete existing summaries for this year
    await db.monthly_summaries.delete_many({"year": year})
    
    # Compute item profit summaries per month (fetched per month to keep memory flat)
    for month in range(1, 13):
        m_start = f"{year}-{month:02d}-01"
        m_end = f"{year}-{month:02d}-31 23:59:59"
        txns = await db.transactions.find(
            {'date': {'$gte': m_start, '$lte': m_end}}, _tx_proj
        ).to_list(None)
        item_profits = _compute_item_profits(txns, master_stamps, p_mapping_dict, p_member_to_leader, grp_ledger)
        party_data = _compute_party_data(txns)
        cust_profits = _compute_customer_profit_month(txns, grp_ledger, p_mapping_dict, p_member_to_leader)
        supp_profits = _compute_supplier_profit_month(txns, p_mapping_dict, p_member_to_leader)
        item_sales = _compute_item_sales_month(txns, p_mapping_dict, p_member_to_leader)
        
        summaries = []
        
        # Item profit documents
        for item_name, data in item_profits.items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "item_profit",
                "name": item_name,
                "silver_profit_kg": round(data['silver_profit_kg'], 3),
                "labor_profit_inr": round(data['labor_profit_inr'], 2),
                "avg_purchase_tunch": round(data['avg_purchase_tunch'], 2),
                "avg_sale_tunch": round(data['avg_sale_tunch'], 2),
                "net_wt_sold_kg": round(data['net_wt_sold_kg'], 3),
                "total_sales_value": round(data.get('total_sales_value', 0), 2),
                "cost_source": data.get('cost_source', 'ledger'),
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Party customer documents
        for party_name, data in party_data['customers'].items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "party_customer",
                "name": party_name,
                "total_net_wt": round(data['total_net_wt'], 3),
                "total_fine_wt": round(data['total_fine_wt'], 3),
                "total_gr_wt": round(data['total_gr_wt'], 3),
                "total_sales_value": round(data['total_sales_value'], 2),
                "transaction_count": data['transaction_count'],
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Party supplier documents
        for party_name, data in party_data['suppliers'].items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "party_supplier",
                "name": party_name,
                "total_net_wt": round(data['total_net_wt'], 3),
                "total_fine_wt": round(data['total_fine_wt'], 3),
                "total_gr_wt": round(data['total_gr_wt'], 3),
                "total_purchases_value": round(data['total_purchases_value'], 2),
                "transaction_count": data['transaction_count'],
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        for party_name, data in cust_profits.items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "party_customer_profit",
                "name": party_name,
                "silver_profit_kg": round(data['silver'], 3),
                "labor_profit_inr": round(data['labour'], 2),
                "sold_kg": round(data['sold_kg'], 3),
                "transaction_count": data['n'],
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        for item_name, data in item_sales.items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "item_sales",
                "name": item_name,
                "sold_kg": round(data['sold_kg'], 3),
                "sales_value": round(data['sales_value'], 2),
                "transaction_count": data['n'],
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        for party_name, data in supp_profits.items():
            summaries.append({
                "year": year,
                "month": month,
                "summary_type": "party_supplier_profit",
                "name": party_name,
                "silver_profit_kg": round(data['silver'], 3),
                "labor_profit_inr": round(data['labor'], 2),
                "purchased_kg": round(data['purchased_kg'], 3),
                "items_count": data['items'],
                "computed_at": datetime.now(timezone.utc).isoformat()
            })
        
        if summaries:
            await db.monthly_summaries.insert_many(summaries)
            docs_written += len(summaries)
    
    # Write fingerprint meta so freshness checks can detect future drift.
    txn_count, max_created = await _get_year_fingerprint(db, year)
    await db.monthly_summaries.insert_one({
        "year": year,
        "summary_type": "_meta",
        "txn_count": txn_count,
        "max_created_at": max_created,
        "logic_version": PROFIT_LOGIC_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    docs_written += 1
    
    return docs_written


def _compute_item_sales_month(transactions, mapping_dict, member_to_leader):
    """Per-item sold qty/value for one month (all items, stamp-independent, group-aware)."""
    EXCLUDED = {"SILVER ORNAMENTS"}
    res = defaultdict(lambda: {'sold_kg': 0.0, 'sales_value': 0.0, 'n': 0})
    for t in transactions:
        if t['type'] not in ('sale', 'sale_return'):
            continue
        raw = t.get('item_name', '') or ''
        if not raw or raw in EXCLUDED or raw.isdigit():
            continue
        leader = resolve_to_leader(raw, mapping_dict, member_to_leader)
        sign = -1 if t['type'] == 'sale_return' else 1
        res[leader]['sold_kg'] += sign * abs(t.get('net_wt', 0) or 0) / 1000
        res[leader]['sales_value'] += sign * abs(t.get('total_amount', 0) or 0)
        res[leader]['n'] += 1
    return res


def _compute_customer_profit_month(transactions, grp_ledger, mapping_dict, member_to_leader):
    """Per-customer profit for one month (mirrors /analytics/customer-profit math)."""
    res = defaultdict(lambda: {'silver': 0.0, 'labour': 0.0, 'sold_kg': 0.0, 'n': 0})
    for txn in transactions:
        if txn['type'] not in ('sale', 'sale_return'):
            continue
        customer = txn.get('party_name', 'Unknown')
        if not customer:
            continue
        raw_item_name = txn.get('item_name', '')
        leader_name = resolve_to_leader(raw_item_name, mapping_dict, member_to_leader)
        txn_tunch = float(txn.get('tunch', 0) or 0)
        txn_net_wt = txn.get('net_wt', 0)
        txn_total = txn.get('total_amount', 0) or txn.get('labor', 0)
        ledger_item = grp_ledger.get(leader_name) or grp_ledger.get(raw_item_name)
        if ledger_item is None:
            continue  # no cumulative cost basis -> skip (prevents zero-cost inflation)
        purchase_tunch = ledger_item.get('purchase_tunch', 0)
        purchase_cost_per_gram = ledger_item.get('labour_per_kg', 0) / 1000
        if txn['type'] == 'sale_return':
            abs_wt = abs(txn_net_wt)
            abs_total = abs(txn_total)
            silver_profit_kg = (purchase_tunch - txn_tunch) * abs_wt / 100 / 1000
            labour_profit = (purchase_cost_per_gram * abs_wt) - abs_total
            res[customer]['sold_kg'] -= abs_wt / 1000
        else:
            silver_profit_kg = (txn_tunch - purchase_tunch) * txn_net_wt / 100 / 1000
            labour_profit = txn_total - (purchase_cost_per_gram * txn_net_wt)
            res[customer]['sold_kg'] += txn_net_wt / 1000
        res[customer]['silver'] += silver_profit_kg
        res[customer]['labour'] += labour_profit
        res[customer]['n'] += 1
    return res


def _compute_supplier_profit_month(transactions, mapping_dict, member_to_leader):
    """Per-supplier profit for one month (mirrors /analytics/supplier-profit math)."""
    purch_agg = defaultdict(lambda: {'wt': 0.0, 'abs_wt': 0.0, 'tunch_wt': 0.0, 'labour': 0.0, 'n': 0})
    sale_agg = defaultdict(lambda: {'wt': 0.0, 'abs_wt': 0.0, 'tunch_wt': 0.0, 'labour': 0.0, 'n': 0})
    for trans in transactions:
        item_name = resolve_to_leader(trans.get('item_name', ''), mapping_dict, member_to_leader)
        net = trans.get('net_wt', 0) or 0
        a = abs(net)
        tv = abs(trans.get('total_amount', 0) or trans.get('labor', 0) or 0)
        tn = float(trans.get('tunch', 0) or 0)
        if trans['type'] in ('purchase', 'purchase_return'):
            supplier = trans.get('party_name', 'Unknown')
            if not supplier:
                continue
            p = purch_agg[(supplier, item_name)]
            p['wt'] += net; p['abs_wt'] += a; p['tunch_wt'] += tn * a; p['labour'] += tv; p['n'] += 1
        elif trans['type'] in ('sale', 'sale_return'):
            sagg = sale_agg[item_name]
            sagg['wt'] += net; sagg['abs_wt'] += a; sagg['tunch_wt'] += tn * a; sagg['labour'] += tv; sagg['n'] += 1

    res = defaultdict(lambda: {'silver': 0.0, 'labor': 0.0, 'purchased_kg': 0.0, 'items': 0})
    for (supplier, item_name), p in purch_agg.items():
        sagg = sale_agg.get(item_name)
        if not sagg or sagg['n'] == 0 or p['n'] == 0:
            continue
        st = res[supplier]
        st['items'] += 1
        purchase_wt = p['wt']
        if abs(purchase_wt) < 0.001 or abs(sagg['wt']) < 0.001:
            continue
        avg_p_tunch = p['tunch_wt'] / p['abs_wt'] if p['abs_wt'] else 0
        avg_s_tunch = sagg['tunch_wt'] / sagg['abs_wt'] if sagg['abs_wt'] else 0
        p_lpg = p['labour'] / p['abs_wt'] if p['abs_wt'] else 0
        s_lpg = sagg['labour'] / sagg['abs_wt'] if sagg['abs_wt'] else 0
        st['silver'] += (avg_s_tunch - avg_p_tunch) * purchase_wt / 100 / 1000
        st['labor'] += (s_lpg - p_lpg) * purchase_wt
        st['purchased_kg'] += purchase_wt / 1000
    return {k: v for k, v in res.items() if v['purchased_kg'] > 0}


def _compute_item_profits(transactions, master_stamps, mapping_dict, member_to_leader, grp_ledger):
    """Compute item profit metrics from a list of transactions (single month)."""
    
    def _resolve(name):
        return resolve_to_leader(name, mapping_dict, member_to_leader)
    
    # Filter transactions
    filtered = []
    for t in transactions:
        leader = _resolve(t['item_name'])
        if leader in EXCLUDED_ITEMS:
            continue
        stamp = master_stamps.get(leader, master_stamps.get(mapping_dict.get(t['item_name'], t['item_name']), 'Unassigned'))
        if not stamp or stamp == 'Unassigned':
            continue
        filtered.append(t)
    
    # Group by leader item — canonicalize signs so SR always carries negative
    # net_wt/total_amount/labor regardless of how DB stored them.
    item_txns = defaultdict(lambda: {'purchases': [], 'sales': []})
    for t in filtered:
        item_name = _resolve(t['item_name'])
        sign = -1 if t['type'] in ('sale_return', 'purchase_return') else 1
        trans_data = {
            'net_wt': abs(t.get('net_wt', 0) or 0) * sign,
            'tunch': float(t.get('tunch', 0) or 0),
            'labor': abs(t.get('labor', 0) or 0) * sign,
            'total_amount': abs(t.get('total_amount', 0) or 0) * sign
        }
        if t['type'] in ['purchase', 'purchase_return']:
            item_txns[item_name]['purchases'].append(trans_data)
        elif t['type'] in ['sale', 'sale_return']:
            item_txns[item_name]['sales'].append(trans_data)
    
    results = {}
    for item_name, data in item_txns.items():
        sales = data['sales']
        if not sales:
            continue

        # Cost basis = long-run CUMULATIVE ledger (goods sold now were purchased earlier).
        cb = ledger_cost_basis(grp_ledger, item_name)
        if cb is None:
            continue  # no long-run cost basis -> skip (effectively unassigned)
        cost_tunch, cost_lpg = cb

        # Per-ENTRY silver/labour profit (atom-by-atom) so day/month/year reconcile exactly.
        silver_profit_kg, labor_profit_inr, total_sale_wt, avg_sale_tunch = aggregate_sale_profit(
            sales, cost_tunch, cost_lpg)
        if abs(total_sale_wt) < 0.001:
            continue

        # Net sales value = sales - returns (returns carry negative total_amount)
        total_sales_value = sum(s.get('total_amount', 0) for s in sales)

        results[item_name] = {
            'silver_profit_kg': silver_profit_kg,
            'labor_profit_inr': labor_profit_inr,
            'avg_purchase_tunch': cost_tunch,
            'avg_sale_tunch': avg_sale_tunch,
            'net_wt_sold_kg': total_sale_wt / 1000,
            'total_sales_value': total_sales_value,
            'cost_source': 'estimated' if (grp_ledger.get(item_name) or {}).get('fallback') else 'ledger'
        }

    return results


def _compute_party_data(transactions):
    """Compute party-level aggregates from a list of transactions."""
    
    customers = defaultdict(lambda: {
        'total_net_wt': 0.0, 'total_fine_wt': 0.0, 'total_gr_wt': 0.0,
        'total_sales_value': 0.0, 'transaction_count': 0
    })
    suppliers = defaultdict(lambda: {
        'total_net_wt': 0.0, 'total_fine_wt': 0.0, 'total_gr_wt': 0.0,
        'total_purchases_value': 0.0, 'transaction_count': 0
    })
    
    for t in transactions:
        party = t.get('party_name', '')
        if not party:
            continue
        
        # Canonicalize sign: returns always contribute negatively regardless of
        # whether DB stored them as signed or unsigned.
        is_return = t['type'] in ('sale_return', 'purchase_return')
        sign = -1 if is_return else 1
        net_wt = abs(t.get('net_wt', 0) or 0) * sign
        fine_wt = abs(t.get('fine', 0) or 0) * sign
        gr_wt = abs(t.get('gr_wt', 0) or 0) * sign
        amount = abs(t.get('total_amount', 0) or 0) * sign
        
        if t['type'] in ['sale', 'sale_return']:
            customers[party]['total_net_wt'] += net_wt
            customers[party]['total_fine_wt'] += fine_wt
            customers[party]['total_gr_wt'] += gr_wt
            customers[party]['total_sales_value'] += amount
            customers[party]['transaction_count'] += 1
        elif t['type'] in ['purchase', 'purchase_return']:
            suppliers[party]['total_net_wt'] += net_wt
            suppliers[party]['total_fine_wt'] += fine_wt
            suppliers[party]['total_gr_wt'] += gr_wt
            suppliers[party]['total_purchases_value'] += amount
            suppliers[party]['transaction_count'] += 1
    
    return {'customers': dict(customers), 'suppliers': dict(suppliers)}
