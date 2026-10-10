"""Purchase List daily snapshot computation.

Correctness contract: the 'current stock' of every row equals the Current Stock
page exactly — it is read from the same inventory engine (get_current_inventory)
as-of the snapshot date, which applies item-mapping normalization (stripped
names) and per-item physical-stock baseline anchors.

The baseline (peak) series is reconstructed from baseline_start..D using the
cached engine opening at baseline_start-1 plus in-window transaction deltas
(anchor-aware: txns on/before an item's baseline cutoff are skipped, same rule
as the engine), then uniformly aligned so the series ends at the engine value.

- Interchangeable items (item_groups) are combined under their leader; each row
  carries a per-member breakdown (engine stock + net sold in the profit window).
- Variable baseline = max closing in the window; fixed = admin value.
- order_qty = baseline - closing(D); only rows with order_qty > 0 are kept.
- Profit: silver in TUNCH points and labour in INR/kg from the last 60 days of
  sales vs the group ledger cost basis (weight-averaged across members).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from services.group_utils import build_group_maps, build_group_ledger
from services.profit_helpers import EXCLUDED_ITEMS, ledger_cost_basis, fetch_ledger_with_fallback
from services.stock_service import get_opening_effective_date

ADD_TYPES = ("purchase", "purchase_return", "receive")
SUB_TYPES = ("sale", "sale_return", "issue")


def _flatten_map(map_dict):
    """Resolve chained mappings (A -> B -> C) to their final master, cycle-safe."""
    flat = {}
    for k in map_dict:
        seen = set()
        cur = k
        while cur in map_dict and cur not in seen:
            seen.add(cur)
            cur = map_dict[cur]
        flat[k] = cur
    return flat


async def _get_opening_cached(db, prev_day, inventory_fn, map_dict):
    """DB-cached opening stock per MEMBER (stripped, alias-resolved master name,
    grams) as of end of prev_day, straight from the inventory engine."""
    txn_cnt = await db.transactions.count_documents({'date': {'$lte': prev_day + ' 23:59:59'}})
    anchor_cnt = await db.inventory_baselines.count_documents({})
    fp = f"v4:{txn_cnt}:{anchor_cnt}:m{len(map_dict)}"
    doc = await db.purchase_opening_cache.find_one({'date': prev_day}, {"_id": 0})
    if doc and doc.get('fingerprint') == fp:
        return defaultdict(float, {e['item']: e['g'] for e in doc.get('entries', [])})
    inv = await inventory_fn(as_of_date=prev_day)
    opening = defaultdict(float)
    for si in inv.get('stamp_items', []):
        raw = (si.get('item_name') or '').strip()
        if not raw or raw.isdigit():
            continue
        opening[raw] += si.get('net_wt', 0) or 0
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
    flat_map = _flatten_map(map_dict)
    ledger_items = await fetch_ledger_with_fallback(db, all_groups, mappings)
    grp_ledger = build_group_ledger(ledger_items, all_groups, mappings)
    excluded = set(EXCLUDED_ITEMS)

    def _leader_of(mem):
        """Member (engine display name) -> transitive master -> group leader."""
        t = flat_map.get(mem, mem)
        return m2l.get(t, t)

    # Per-item baseline anchor cutoffs (same rule as the inventory engine)
    oed = await get_opening_effective_date()
    cutoffs = {}
    async for b in db.inventory_baselines.find(
            {'baseline_date': {'$lte': date_s}},
            {"_id": 0, "item_name": 1, "baseline_date": 1}):
        if oed and b['baseline_date'] < oed:
            continue
        master = b['item_name'].strip()
        master = flat_map.get(map_dict.get(master, master), map_dict.get(master, master))
        k = master.strip().lower()
        if k not in cutoffs or b['baseline_date'] > cutoffs[k]:
            cutoffs[k] = b['baseline_date']

    prev_day = (sd_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    opening_mem = await _get_opening_cached(db, prev_day, inventory_fn, map_dict)
    leader_open = defaultdict(float)
    for mem, g in opening_mem.items():
        leader = _leader_of(mem)
        if leader in excluded:
            continue
        leader_open[leader] += g

    # Current stock straight from the engine (matches the Current Stock page)
    inv_now = await inventory_fn(as_of_date=date_s)
    leader_direct = defaultdict(float)
    member_direct = defaultdict(lambda: defaultdict(float))
    for si in inv_now.get('stamp_items', []):
        raw = (si.get('item_name') or '').strip()
        if not raw or raw.isdigit():
            continue
        leader = _leader_of(raw)
        if leader in excluded:
            continue
        g = si.get('net_wt', 0) or 0
        leader_direct[leader] += g
        member_direct[leader][raw] += g

    daily_delta = defaultdict(lambda: defaultdict(float))    # leader -> date -> grams
    member_sold = defaultdict(lambda: defaultdict(float))    # leader -> member -> grams sold (net)
    sale_agg = defaultdict(lambda: {'silver_kg': 0.0, 'labour': 0.0, 'wt_g': 0.0})
    async for t in db.transactions.find(
            {'date': {'$gte': win_start, '$lte': date_s + ' 23:59:59'},
             'type': {'$in': list(ADD_TYPES + SUB_TYPES)}},
            {"_id": 0, "date": 1, "type": 1, "item_name": 1, "net_wt": 1,
             "tunch": 1, "labor": 1, "total_amount": 1}):
        raw = (t.get('item_name') or '').strip()
        if not raw or raw.isdigit():
            continue
        mem = map_dict.get(raw, raw)          # engine-equivalent display name (one hop)
        leader = _leader_of(mem)              # transitive master + group leader
        if leader in excluded:
            continue
        d = (t.get('date') or '')[:10]
        if not d:
            continue
        w = t.get('net_wt', 0) or 0
        ttype = t['type']
        if baseline_start <= d <= date_s:
            cut = cutoffs.get(flat_map.get(mem, mem).lower(), oed)
            if not (cut and d <= cut):
                daily_delta[leader][d] += w if ttype in ADD_TYPES else -w
        if ttype in ('sale', 'sale_return') and sale_start <= d <= date_s:
            cb = ledger_cost_basis(grp_ledger, leader, raw)
            sign = -1 if ttype == 'sale_return' else 1
            sw = abs(w) * sign
            member_sold[leader][mem] += sw
            if cb is not None:
                cost_tunch, cost_lpg = cb
                st = float(t.get('tunch', 0) or 0)
                amt = abs(t.get('total_amount', 0) or 0) or abs(t.get('labor', 0) or 0)
                a = sale_agg[leader]
                a['silver_kg'] += (st - cost_tunch) * sw / 100 / 1000
                a['labour'] += (amt * sign) - cost_lpg * sw
                a['wt_g'] += sw

    n_days = (ed_dt - sd_dt).days
    date_list = [(sd_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(n_days + 1)]

    rows = []
    for leader in set(leader_direct) | set(daily_delta) | set(leader_open):
        running = leader_open.get(leader, 0.0)
        deltas = daily_delta.get(leader, {})
        max_closing = None
        for ds in date_list:
            running += deltas.get(ds, 0.0)
            if max_closing is None or running > max_closing:
                max_closing = running
        closing_g = leader_direct.get(leader, 0.0)       # engine truth
        adjust = closing_g - running                     # align series to engine
        variable_baseline_g = max((max_closing if max_closing is not None else running) + adjust, closing_g)

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
            fine_frac = a['silver_kg'] * 1000.0 / abs(a['wt_g'])   # g fine / g sold
            ps_tunch = fine_frac * 100.0
            ps = fine_frac * 1000.0
            pl = a['labour'] / abs(a['wt_g']) * 1000.0
        else:
            ps_tunch = None
            ps = None
            pl = None

        mem_names = set(member_direct.get(leader, {})) | set(member_sold.get(leader, {}))
        members = []
        for mem in mem_names:
            members.append({'name': mem,
                            'current_stock_kg': round(member_direct.get(leader, {}).get(mem, 0.0) / 1000.0, 3),
                            'sold_60d_kg': round(member_sold.get(leader, {}).get(mem, 0.0) / 1000.0, 3)})
        members.sort(key=lambda m: -m['current_stock_kg'])

        rows.append({
            'item_name': leader,
            'members': members,
            'order_qty_kg': round(order_kg, 3),
            'current_stock_kg': round(closing_g / 1000.0, 3),
            'baseline_kg': round(baseline_g / 1000.0, 3),
            'variable_baseline_kg': round(variable_baseline_g / 1000.0, 3),
            'fine_kg': round(order_kg * p_tunch / 100.0, 3),
            'labour_inr': round(order_kg * lpg * 1000.0, 0),
            'purchase_tunch': round(p_tunch, 2),
            'labour_per_kg': round(lpg * 1000.0, 2),
            'profit_silver_tunch': round(ps_tunch, 2) if ps_tunch is not None else None,
            'profit_silver_per_kg': round(ps, 1) if ps is not None else None,
            'profit_labour_per_kg': round(pl, 0) if pl is not None else None,
        })
    rows.sort(key=lambda r: (r['profit_silver_tunch'] is None, -(r['profit_silver_tunch'] or 0)))
    return rows
