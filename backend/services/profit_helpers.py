"""Shared profit-computation helpers.

Both /analytics/profit and the Seasonal Analysis PMS pipeline
call through this module so the silver and labour margin logic
is defined exactly once.
"""

import time
from collections import defaultdict
from services.group_utils import build_group_maps, resolve_to_leader, build_group_ledger


EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]


def ledger_cost_basis(grp_ledger: dict, leader: str, raw_name: str | None = None):
    """Long-run CUMULATIVE cost basis from the PURCHASE_CUMUL ledger.

    Goods sold in any period were purchased earlier, so the cost side must be a long-run
    average, NOT the period's own purchases. The PURCHASE_CUMUL ledger holds each item's
    cumulative purchase totals, giving a stable weighted-average purchase tunch & labour/kg
    that is identical across every period (day/month/year) → profit is consistent & additive.

    Returns (purchase_tunch_pct, purchase_labour_per_gram) or None when the item has no
    ledger entry (such items are skipped from profit — effectively unassigned).
    """
    le = grp_ledger.get(leader)
    if le is None and raw_name is not None:
        le = grp_ledger.get(raw_name)
    if not le:
        return None
    return (le.get("purchase_tunch", 0) or 0), ((le.get("labour_per_kg", 0) or 0) / 1000)


_fallback_cache = {"ts": 0.0, "stats": None}
_FALLBACK_TTL = 60  # seconds


def invalidate_fallback_cache():
    _fallback_cache["stats"] = None


async def fetch_fallback_purchase_stats(db, use_cache: bool = True) -> dict:
    """Signed per-item purchase totals from ALL purchase/purchase_return transactions
    (regular + historical) PLUS branch 'receive' rows that carry rate data (goods often
    come in via branch receive instead of purchase). Used to ESTIMATE a cost basis for
    items that have no PURCHASE_CUMUL ledger entry instead of skipping them from profit.
    Returns raw_item_name -> {wt_g, fine_g, labour}."""
    if use_cache and _fallback_cache["stats"] is not None and time.time() - _fallback_cache["ts"] < _FALLBACK_TTL:
        return _fallback_cache["stats"]
    _abs_wt = {"$abs": {"$ifNull": ["$net_wt", 0]}}
    _tunch = {"$convert": {"input": "$tunch", "to": "double", "onError": 0, "onNull": 0}}
    pipeline = [
        {"$match": {"type": {"$in": ["purchase", "purchase_return", "receive"]}}},
        {"$addFields": {"_has_rate": {"$or": [
            {"$gt": [{"$abs": {"$ifNull": ["$fine", 0]}}, 0]},
            {"$gt": [_tunch, 0]},
            {"$gt": [{"$abs": {"$ifNull": ["$labor", 0]}}, 0]},
            {"$gt": [{"$abs": {"$ifNull": ["$total_amount", 0]}}, 0]},
        ]}}},
        # receive rows without any rate data would dilute the average toward zero — drop them
        {"$match": {"$or": [{"type": {"$in": ["purchase", "purchase_return"]}}, {"_has_rate": True}]}},
        {"$group": {
            "_id": {"item": "$item_name", "type": "$type"},
            "wt": {"$sum": _abs_wt},
            "fine": {"$sum": {"$cond": [
                {"$gt": [{"$abs": {"$ifNull": ["$fine", 0]}}, 0]},
                {"$abs": {"$ifNull": ["$fine", 0]}},
                {"$divide": [{"$multiply": [_abs_wt, _tunch]}, 100]},
            ]}},
            "labour": {"$sum": {"$cond": [
                {"$gt": [{"$abs": {"$ifNull": ["$labor", 0]}}, 0]},
                {"$abs": {"$ifNull": ["$labor", 0]}},
                {"$abs": {"$ifNull": ["$total_amount", 0]}},
            ]}},
        }},
    ]
    stats: dict = {}
    for coll in (db.transactions, db.historical_transactions):
        async for d in coll.aggregate(pipeline):
            item = (d["_id"].get("item") or "").strip()
            if not item or item.isdigit():
                continue
            sign = -1 if d["_id"]["type"] == "purchase_return" else 1
            s = stats.setdefault(item, {"wt_g": 0.0, "fine_g": 0.0, "labour": 0.0})
            s["wt_g"] += sign * (d["wt"] or 0)
            s["fine_g"] += sign * (d["fine"] or 0)
            s["labour"] += sign * (d["labour"] or 0)
    _fallback_cache["stats"] = stats
    _fallback_cache["ts"] = time.time()
    return stats


def merge_fallback_entries(ledger_items: list[dict], fallback_stats: dict,
                           groups: list[dict], mappings: list[dict]) -> list[dict]:
    """Return ledger_items + synthetic ``fallback: True`` entries for items whose group
    leader has NO real ledger coverage but does have purchase transaction history.
    Real ledger entries always win — fallback never alters an existing group's basis."""
    mapping_dict, member_to_leader, _ = build_group_maps(groups, mappings)
    real_grp = build_group_ledger(ledger_items, groups, mappings)
    agg: dict = {}
    for raw, st in fallback_stats.items():
        leader = resolve_to_leader(raw, mapping_dict, member_to_leader)
        if leader in real_grp or raw in real_grp:
            continue
        a = agg.setdefault(leader, {"wt_g": 0.0, "fine_g": 0.0, "labour": 0.0})
        a["wt_g"] += st["wt_g"]
        a["fine_g"] += st["fine_g"]
        a["labour"] += st["labour"]
    out = list(ledger_items)
    for leader, a in agg.items():
        if a["wt_g"] < 1:  # need at least 1g of net purchase history
            continue
        out.append({
            "item_name": leader,
            "purchase_tunch": a["fine_g"] / a["wt_g"] * 100,
            "labour_per_kg": a["labour"] / (a["wt_g"] / 1000.0),
            "total_purchased_kg": a["wt_g"] / 1000.0,
            "total_fine_kg": a["fine_g"] / 1000.0,
            "total_labour": a["labour"],
            "fallback": True,
        })
    return out


async def fetch_ledger_with_fallback(db, groups: list[dict], mappings: list[dict],
                                     use_cache: bool = True) -> list[dict]:
    """purchase_ledger entries + estimated entries for no-ledger items (from their own
    purchase history). Drop-in replacement for ``db.purchase_ledger.find().to_list()``."""
    ledger = await db.purchase_ledger.find({}, {"_id": 0}).to_list(None)
    stats = await fetch_fallback_purchase_stats(db, use_cache=use_cache)
    return merge_fallback_entries(ledger, stats, groups, mappings)


def aggregate_sale_profit(sales: list[dict], cost_tunch: float, cost_lpg: float):
    """Sum PER-ENTRY silver (kg) & labour (INR) profit for a bag of sale rows of one item.

    Each sale entry's margin uses its OWN actual sale tunch/labour against the long-run cost
    basis — never a period-blended sale rate. Because profit is computed atom-by-atom (per
    transaction) and summed, day/month/year totals always reconcile exactly, and a past day's
    profit never changes when later sales arrive.

      silver(entry) = (sale_tunch - cost_tunch) * net_wt_signed / 100 / 1000   (kg)
      labour(entry) = sale_total_signed - cost_lpg * net_wt_signed             (INR)

    ``net_wt_signed`` is negative for sale_returns, which correctly reverses that sale's profit
    (matches the proven /analytics/customer-profit logic). Returns
    (silver_kg, labour_inr, signed_net_wt_g, avg_sale_tunch).
    """
    silver = 0.0
    labour = 0.0
    signed_wt = 0.0
    abs_wt = 0.0
    st_weighted = 0.0
    for s in sales:
        w = s.get("net_wt", 0) or 0  # signed (SR negative)
        st = float(s.get("tunch", 0) or 0)
        amt = abs(s.get("total_amount", 0) or 0) or abs(s.get("labor", 0) or 0)
        amt_signed = -amt if w < 0 else amt
        silver += (st - cost_tunch) * w / 100 / 1000
        labour += amt_signed - cost_lpg * w
        signed_wt += w
        abs_wt += abs(w)
        st_weighted += st * abs(w)
    avg_st = st_weighted / abs_wt if abs_wt > 0.0001 else 0.0
    return silver, labour, signed_wt, avg_st


def compute_item_margins(transactions: list[dict], ledger_items: list[dict],
                         groups: list[dict], mappings: list[dict],
                         master_stamps: dict | None = None) -> list[dict]:
    """Compute silver and labour margin per item using the canonical per-entry profit logic.

    This is the SINGLE source of truth shared by /analytics/profit and the Seasonal Analysis
    PMS pipeline. Cost basis = cumulative PURCHASE_CUMUL ledger (long-run); sale side = each
    sale entry's actual tunch/labour. Items without a ledger cost basis are skipped.

    Returns list of dicts: item_name, silver_profit_kg, labor_profit_inr, avg_purchase_tunch,
    avg_sale_tunch, net_wt_sold_kg, silver_margin_per_gram, labour_margin_per_gram.
    """
    mapping_dict, member_to_leader, _ = build_group_maps(groups, mappings)
    grp_ledger = build_group_ledger(ledger_items, groups, mappings)

    def _resolve(name):
        return resolve_to_leader(name, mapping_dict, member_to_leader)

    # Group SALE rows by leader (signed); skip excluded / unassigned
    item_sales = defaultdict(list)
    for t in transactions:
        if t["type"] not in ("sale", "sale_return"):
            continue
        leader = _resolve(t["item_name"])
        if leader in EXCLUDED_ITEMS:
            continue
        if master_stamps is not None:
            s = master_stamps.get(leader, master_stamps.get(
                mapping_dict.get(t["item_name"], t["item_name"]), "Unassigned"))
            if not s or s == "Unassigned":
                continue
        sign = -1 if t["type"] == "sale_return" else 1
        item_sales[leader].append({
            "net_wt": abs(t.get("net_wt", 0) or 0) * sign,
            "tunch": float(t.get("tunch", 0) or 0),
            "labor": abs(t.get("labor", 0) or 0) * sign,
            "total_amount": abs(t.get("total_amount", 0) or 0) * sign,
        })

    results = []
    for item_name, sales in item_sales.items():
        cb = ledger_cost_basis(grp_ledger, item_name)
        if cb is None:
            continue  # no long-run cost basis -> skip (effectively unassigned)
        cost_tunch, cost_lpg = cb
        silver_kg, labour_inr, signed_wt, avg_st = aggregate_sale_profit(sales, cost_tunch, cost_lpg)
        if abs(signed_wt) < 0.001:
            continue
        results.append({
            "item_name": item_name,
            "silver_profit_kg": round(silver_kg, 3),
            "labor_profit_inr": round(labour_inr, 2),
            "avg_purchase_tunch": round(cost_tunch, 2),
            "avg_sale_tunch": round(avg_st, 2),
            "net_wt_sold_kg": round(signed_wt / 1000, 3),
            "silver_margin_per_gram": (silver_kg * 1000) / max(abs(signed_wt), 1),
            "labour_margin_per_gram": labour_inr / max(abs(signed_wt), 1),
        })

    return results


def _build_month_context(transactions: list[dict], ledger_items: list[dict],
                         groups: list[dict], mappings: list[dict], master_stamps: dict):
    """Build the shared per-item MONTH-level cost basis + helpers used by both the daily
    profit totals and the per-date drilldown, so every profit view uses one consistent
    cost basis (purchase tunch + purchase labour/kg held constant per item across the month).

    Returns (resolve_fn, included_fn, cost_basis_fn) where cost_basis_fn(leader) -> tuple
    (avg_purchase_tunch, purchase_labour_per_gram) or None.
    """
    mapping_dict, member_to_leader, _ = build_group_maps(groups, mappings)
    grp_ledger = build_group_ledger(ledger_items, groups, mappings)

    def _resolve(name):
        return resolve_to_leader(name, mapping_dict, member_to_leader)

    def _included(leader, raw):
        if leader in EXCLUDED_ITEMS:
            return False
        s = master_stamps.get(leader, master_stamps.get(mapping_dict.get(raw, raw), "Unassigned"))
        return bool(s) and s != "Unassigned"

    cost_cache: dict = {}

    def _cost_basis(leader):
        """Long-run CUMULATIVE cost basis from the ledger (constant across all periods).
        Returns (purchase_tunch, purchase_labour_per_gram) or None to skip the item."""
        if leader in cost_cache:
            return cost_cache[leader]
        cost_cache[leader] = ledger_cost_basis(grp_ledger, leader)
        return cost_cache[leader]

    return _resolve, _included, _cost_basis


def _sale_silver_labour(sales: list[dict], cost_tunch: float, cost_lpg: float):
    """Per-ENTRY silver (kg) + labour (INR) profit for a bag of sale rows of ONE item.
    ``sales`` rows already carry signed weight/amount (SR negative)."""
    silver, labour, signed_wt, _ = aggregate_sale_profit(sales, cost_tunch, cost_lpg)
    return silver, labour, signed_wt


def _signed_sale_row(t: dict) -> dict:
    sign = -1 if t["type"] == "sale_return" else 1
    return {
        "net_wt": abs(t.get("net_wt", 0) or 0) * sign,
        "tunch": float(t.get("tunch", 0) or 0),
        "labor": abs(t.get("labor", 0) or 0) * sign,
        "total_amount": abs(t.get("total_amount", 0) or 0) * sign,
    }


def compute_daily_profits(transactions: list[dict], ledger_items: list[dict],
                          groups: list[dict], mappings: list[dict],
                          master_stamps: dict, year: int, month: int) -> list[dict]:
    """Daily silver / labour profit for each day of a month.

    Each day's profit is the SUM of that day's individual sale entries' profit, where every
    sale entry's margin = (its actual sale tunch/labour) − (the item's long-run CUMULATIVE
    ledger cost basis). Because the cost basis is constant across all periods and profit is
    summed atom-by-atom (per sale entry), the daily values are perfectly additive — the sum
    of daily profit equals the monthly total, which equals the yearly total.

    (The earlier implementation recomputed the purchase tunch from each day's/month's own
    purchases, which is non-additive AND conceptually wrong — goods sold today were bought
    earlier, so the cost must be the long-run cumulative purchase rate.)
    """
    import calendar
    _resolve, _included, _cost_basis = _build_month_context(
        transactions, ledger_items, groups, mappings, master_stamps)

    daily_sales = defaultdict(lambda: defaultdict(list))
    daily_sale_count = defaultdict(int)
    for t in transactions:
        if t.get("type") not in ("sale", "sale_return"):
            continue
        d = (t.get("date", "") or "")[:10]
        if not d:
            continue
        leader = _resolve(t["item_name"])
        if not _included(leader, t["item_name"]):
            continue
        daily_sales[d][leader].append(_signed_sale_row(t))
        if t["type"] == "sale":
            daily_sale_count[d] += 1

    last_day = calendar.monthrange(year, month)[1]
    daily = []
    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        items_today = daily_sales.get(date_str)
        if not items_today:
            daily.append({"date": date_str, "silver_profit_kg": 0, "labor_profit_inr": 0, "sale_count": 0})
            continue
        day_silver = 0.0
        day_labor = 0.0
        for leader, sales in items_today.items():
            cb = _cost_basis(leader)
            if cb is None:
                continue
            silver, labour, _ = _sale_silver_labour(sales, cb[0], cb[1])
            day_silver += silver
            day_labor += labour
        daily.append({
            "date": date_str,
            "silver_profit_kg": round(day_silver, 3),
            "labor_profit_inr": round(day_labor, 2),
            "sale_count": daily_sale_count.get(date_str, 0),
        })
    return daily


def compute_date_profit_detail(month_transactions: list[dict], date: str,
                               ledger_items: list[dict], groups: list[dict],
                               mappings: list[dict], master_stamps: dict,
                               top_n: int = 20) -> dict:
    """Top items & customers profit for a single ``date`` (YYYY-MM-DD).

    Uses the same long-run cumulative-ledger cost basis + per-entry profit as
    `compute_daily_profits`, so per-item silver profits on drilldown stay consistent with the
    day's total. ``month_transactions`` are all transactions for the date's month.
    """
    _resolve, _included, _cost_basis = _build_month_context(
        month_transactions, ledger_items, groups, mappings, master_stamps)

    item_sales = defaultdict(list)
    customer_items = defaultdict(lambda: defaultdict(list))
    for t in month_transactions:
        if (t.get("date", "") or "")[:10] != date:
            continue
        if t.get("type") not in ("sale", "sale_return"):
            continue
        leader = _resolve(t["item_name"])
        if not _included(leader, t["item_name"]):
            continue
        row = _signed_sale_row(t)
        item_sales[leader].append(row)
        party = t.get("party_name") or "Unknown"
        customer_items[party][leader].append(row)

    item_profits = []
    for leader, sales in item_sales.items():
        cb = _cost_basis(leader)
        if cb is None:
            continue
        silver, labour, day_sw = _sale_silver_labour(sales, cb[0], cb[1])
        item_profits.append({
            "item_name": leader,
            "silver_profit_kg": round(silver, 3),
            "labor_profit_inr": round(labour, 2),
            "net_wt_sold_kg": round(day_sw / 1000, 3),
        })
    item_profits.sort(key=lambda x: x["silver_profit_kg"], reverse=True)

    customer_profits = []
    for party, items in customer_items.items():
        c_silver = 0.0
        c_labor = 0.0
        for leader, sales in items.items():
            cb = _cost_basis(leader)
            if cb is None:
                continue
            silver, labour, _ = _sale_silver_labour(sales, cb[0], cb[1])
            c_silver += silver
            c_labor += labour
        if abs(c_silver) > 0.0001 or abs(c_labor) > 0.01:
            customer_profits.append({
                "party_name": party,
                "silver_profit_kg": round(c_silver, 3),
                "labor_profit_inr": round(c_labor, 2),
            })
    customer_profits.sort(key=lambda x: x["silver_profit_kg"], reverse=True)

    return {"date": date, "top_items": item_profits[:top_n], "top_customers": customer_profits[:top_n]}
