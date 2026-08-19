"""Purchase List daily snapshot computation.

For a given date D:
- Daily CLOSING stock per item from baseline_start..D (engine sign rules:
  purchase/purchase_return/receive ADD, sale/sale_return/issue SUBTRACT),
  opening seeded from inventory as-of baseline_start - 1.
- Variable baseline = max closing stock in the window; fixed = admin value.
- order_qty = baseline - closing(D); only rows with order_qty > 0 are kept.
- Fine/labour of order qty from the cumulative purchase-ledger cost basis.
- Profit per kg (silver g/kg, labour INR/kg) from the last 60 days of sales
  vs the same long-run cost basis (canonical per-entry margin math).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from services.group_utils import build_group_maps, build_group_ledger, resolve_to_leader
from services.profit_helpers import EXCLUDED_ITEMS, ledger_cost_basis, fetch_ledger_with_fallback

ADD_TYPES = ("purchase", "purchase_return", "receive")
SUB_TYPES = ("sale", "sale_return", "issue")


async def _get_opening_cached(db, prev_day, inventory_fn, resolve, excluded):
    """DB-cached opening stock per leader (grams) as of end of prev_day.
    The as-of inventory is the heaviest part of the snapshot compute; caching it
    in Mongo makes recomputes (fingerprint change / baseline edits) fast."""
    txn_cnt = await db.transactions.count_documents({'date': {'$lte': prev_day + ' 23:59:59'}})
    anchor_cnt = await db.inventory_baselines.count_documents({})
    fp = f"{txn_cnt}:{anchor_cnt}"
    doc = await db.purchase_opening_cache.find_one({'date': prev_day}, {"_id": 0})
    if doc and doc.get('fingerprint') == fp:
        return defaultdict(float, {e['item']: e['g'] for e in doc.get('entries', [])})
    inv = await inventory_fn(as_of_date=prev_day)
    opening = defaultdict(float)
    for si in inv.get('stamp_items', []):
        raw = si.get('item_name', '') or ''
        if not raw or raw.isdigit():
            continue
        leader = resolve(raw)
        if leader in excluded:
            continue
        opening[leader] += si.get('net_wt', 0) or 0
    await db.purchase_opening_cache.update_one(
        {'date': prev_day},
        {'$set': {'date': prev_day, 'fingerprint': fp,
                  'entries': [{'item': k, 'g': v} for k, v in opening.items()],
                  'computed_at': datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return opening


async def compute_purchase_snapshot(db, date_s: str, baseline_start: str,
                                    item_states: dict, inventory_fn) -> list[dict]:
    sd_dt = datetime.strptime(baseline_start, '%Y-%m-%d')
    ed_dt = datetime.strptime(date_s, '%Y-%m-%d')
    sale_start = (ed_dt - timedelta(days=60)).strftime('%Y-%m-%d')
    win_start = min(baseline_start, sale_start)

    all_groups = await db.item_groups.find({}, {"_id": 0}).to_list(None)
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    map_dict, m2l, _ = build_group_maps(all_groups, mappings)
    ledger_items = await fetch_ledger_with_fallback(db, all_groups, mappings)
    grp_ledger = build_group_ledger(ledger_items, all_groups, mappings)
    excluded = set(EXCLUDED_ITEMS)

    def _resolve(n):
        return resolve_to_leader(n, map_dict, m2l)

    prev_day = (sd_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    opening = await _get_opening_cached(db, prev_day, inventory_fn, _resolve, excluded)

    daily_delta = defaultdict(lambda: defaultdict(float))  # leader -> date -> grams
    sale_agg = defaultdict(lambda: {'silver_kg': 0.0, 'labour': 0.0, 'wt_g': 0.0})
    async for t in db.transactions.find(
            {'date': {'$gte': win_start, '$lte': date_s + ' 23:59:59'},
             'type': {'$in': list(ADD_TYPES + SUB_TYPES)}},
            {"_id": 0, "date": 1, "type": 1, "item_name": 1, "net_wt": 1,
             "tunch": 1, "labor": 1, "total_amount": 1}):
        raw = t.get('item_name', '') or ''
        if not raw or raw.isdigit():
            continue
        leader = _resolve(raw)
        if leader in excluded:
            continue
        d = (t.get('date') or '')[:10]
        if not d:
            continue
        w = t.get('net_wt', 0) or 0
        ttype = t['type']
        if baseline_start <= d <= date_s:
            daily_delta[leader][d] += w if ttype in ADD_TYPES else -w
        if ttype in ('sale', 'sale_return') and sale_start <= d <= date_s:
            cb = ledger_cost_basis(grp_ledger, leader, raw)
            if cb is not None:
                cost_tunch, cost_lpg = cb
                sign = -1 if ttype == 'sale_return' else 1
                sw = abs(w) * sign
                st = float(t.get('tunch', 0) or 0)
                amt = abs(t.get('total_amount', 0) or 0) or abs(t.get('labor', 0) or 0)
                a = sale_agg[leader]
                a['silver_kg'] += (st - cost_tunch) * sw / 100 / 1000
                a['labour'] += (amt * sign) - cost_lpg * sw
                a['wt_g'] += sw

    n_days = (ed_dt - sd_dt).days
    date_list = [(sd_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(n_days + 1)]

    rows = []
    for leader in set(opening) | set(daily_delta):
        running = opening.get(leader, 0.0)
        deltas = daily_delta.get(leader, {})
        max_closing = None
        for ds in date_list:
            running += deltas.get(ds, 0.0)
            if max_closing is None or running > max_closing:
                max_closing = running
        closing_g = running
        variable_baseline_g = max_closing if max_closing is not None else closing_g

        st_doc = item_states.get(leader) or {}
        if st_doc.get('baseline_mode') == 'fixed' and st_doc.get('fixed_baseline_kg') is not None:
            baseline_g = float(st_doc['fixed_baseline_kg']) * 1000.0
        else:
            baseline_g = variable_baseline_g
        order_g = baseline_g - closing_g
        if order_g <= 0.5:
            continue

        cb = ledger_cost_basis(grp_ledger, leader)
        p_tunch = cb[0] if cb else 0.0
        lpg = cb[1] if cb else 0.0  # INR per gram
        order_kg = order_g / 1000.0
        a = sale_agg.get(leader)
        if a and abs(a['wt_g']) > 1:
            ps = a['silver_kg'] * 1000.0 / abs(a['wt_g']) * 1000.0  # g fine silver / kg sold
            pl = a['labour'] / abs(a['wt_g']) * 1000.0              # INR / kg sold
        else:
            ps = None
            pl = None
        rows.append({
            'item_name': leader,
            'order_qty_kg': round(order_kg, 3),
            'current_stock_kg': round(closing_g / 1000.0, 3),
            'baseline_kg': round(baseline_g / 1000.0, 3),
            'variable_baseline_kg': round(variable_baseline_g / 1000.0, 3),
            'fine_kg': round(order_kg * p_tunch / 100.0, 3),
            'labour_inr': round(order_kg * lpg * 1000.0, 0),
            'purchase_tunch': round(p_tunch, 2),
            'labour_per_kg': round(lpg * 1000.0, 2),
            'profit_silver_per_kg': round(ps, 1) if ps is not None else None,
            'profit_labour_per_kg': round(pl, 0) if pl is not None else None,
        })
    rows.sort(key=lambda r: (r['profit_silver_per_kg'] is None, -(r['profit_silver_per_kg'] or 0)))
    return rows
