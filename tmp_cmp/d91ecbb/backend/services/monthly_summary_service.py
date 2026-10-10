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


EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]

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
    
    start = f"{year}-01-01"
    end = f"{year}-12-31 23:59:59"
    
    # Load all transactions for this year
    transactions = await db.transactions.find(
        {'date': {'$gte': start, '$lte': end}},
        {"_id": 0}
    ).to_list(None)
    
    # Load mappings and groups
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)
    master_items = await db.master_items.find({}, {"_id": 0, "item_name": 1, "stamp": 1}).to_list(None)
    master_stamps = {m['item_name']: m.get('stamp', 'Unassigned') for m in master_items}
    
    p_mapping_dict, p_member_to_leader, _ = build_group_maps(all_groups, mappings)
    
    # Load purchase ledger for cost basis
    all_ledger = await db.purchase_ledger.find({}, {"_id": 0}).to_list(None)
    grp_ledger = build_group_ledger(all_ledger, all_groups, mappings)
    
    def _resolve(name):
        return resolve_to_leader(name, p_mapping_dict, p_member_to_leader)
    
    # Group transactions by month
    monthly_txns = defaultdict(list)  # month -> [transactions]
    for t in transactions:
        d = t.get('date', '')
        if not d or len(d) < 7:
            continue
        try:
            month = int(d[5:7])
        except ValueError:
            continue
        monthly_txns[month].append(t)
    
    docs_written = 0
    
    # Delete existing summaries for this year
    await db.monthly_summaries.delete_many({"year": year})
    
    # Compute item profit summaries per month
    for month in range(1, 13):
        txns = monthly_txns.get(month, [])
        item_profits = _compute_item_profits(txns, master_stamps, p_mapping_dict, p_member_to_leader, grp_ledger)
        party_data = _compute_party_data(txns)
        
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
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    docs_written += 1
    
    return docs_written


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
        purchases = data['purchases']
        sales = data['sales']
        
        if not sales:
            continue
        
        if not purchases:
            ledger_item = grp_ledger.get(item_name)
            if ledger_item:
                purchases = [{
                    'net_wt': ledger_item.get('total_purchased_kg', 0) * 1000,
                    'tunch': ledger_item.get('purchase_tunch', 0),
                    'labor': ledger_item.get('total_labour', 0),
                    'total_amount': ledger_item.get('total_labour', 0)
                }]
            else:
                continue
        
        total_purchase_wt = sum(p['net_wt'] for p in purchases)
        total_sale_wt = sum(s['net_wt'] for s in sales)
        
        if abs(total_purchase_wt) < 0.001 or abs(total_sale_wt) < 0.001:
            continue
        
        avg_purchase_tunch = sum(p['tunch'] * abs(p['net_wt']) for p in purchases) / sum(abs(p['net_wt']) for p in purchases) if purchases else 0
        avg_sale_tunch = sum(s['tunch'] * abs(s['net_wt']) for s in sales) / sum(abs(s['net_wt']) for s in sales) if sales else 0
        
        silver_profit_grams = (avg_sale_tunch - avg_purchase_tunch) * total_sale_wt / 100
        silver_profit_kg = silver_profit_grams / 1000
        
        total_sale_labour = 0
        for s in sales:
            amt = abs(s.get('total_amount', 0) or s.get('labor', 0))
            if s.get('net_wt', 0) < 0:
                total_sale_labour -= amt
            else:
                total_sale_labour += amt
        
        ledger_item = grp_ledger.get(item_name)
        if ledger_item and ledger_item.get('labour_per_kg', 0) > 0:
            purchase_labour_per_gram = ledger_item['labour_per_kg'] / 1000
        elif purchases and sum(abs(p['net_wt']) for p in purchases) > 0:
            purchase_labour_per_gram = sum(abs(p.get('total_amount', 0) or p.get('labor', 0)) for p in purchases) / sum(abs(p['net_wt']) for p in purchases)
        else:
            purchase_labour_per_gram = 0
        
        labor_profit_inr = total_sale_labour - (purchase_labour_per_gram * abs(total_sale_wt))
        # Net sales value = sales - returns (returns now have negative total_amount)
        total_sales_value = sum(s.get('total_amount', 0) for s in sales)
        
        results[item_name] = {
            'silver_profit_kg': silver_profit_kg,
            'labor_profit_inr': labor_profit_inr,
            'avg_purchase_tunch': avg_purchase_tunch,
            'avg_sale_tunch': avg_sale_tunch,
            'net_wt_sold_kg': total_sale_wt / 1000,
            'total_sales_value': total_sales_value
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
