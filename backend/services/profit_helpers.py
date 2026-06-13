"""Shared profit-computation helpers.

Both /analytics/profit and the Seasonal Analysis PMS pipeline
call through this module so the silver and labour margin logic
is defined exactly once.
"""

from collections import defaultdict
from services.group_utils import build_group_maps, resolve_to_leader, build_group_ledger


EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]


def compute_item_margins(transactions: list[dict], ledger_items: list[dict],
                         groups: list[dict], mappings: list[dict],
                         master_stamps: dict | None = None) -> list[dict]:
    """Compute silver and labour margin per item using the real group-aware
    profit logic.

    This is the SINGLE source of truth shared by /analytics/profit
    and the Seasonal Analysis PMS pipeline.

    Parameters
    ----------
    transactions : sale + sale_return rows (dicts with item_name, tunch, net_wt, total_amount, labor, type)
    ledger_items : raw purchase_ledger docs
    groups       : item_groups docs
    mappings     : item_mappings docs
    master_stamps: optional {item_name: stamp} for exclusion (skip Unassigned)

    Returns
    -------
    list of dicts, each with:
      item_name, silver_profit_kg, labor_profit_inr, avg_purchase_tunch,
      avg_sale_tunch, net_wt_sold_kg, stamp (if master_stamps supplied)
    """
    mapping_dict, member_to_leader, _ = build_group_maps(groups, mappings)
    grp_ledger = build_group_ledger(ledger_items, groups, mappings)

    def _resolve(name):
        return resolve_to_leader(name, mapping_dict, member_to_leader)

    # Optionally filter out excluded / unassigned items
    filtered = []
    for t in transactions:
        leader = _resolve(t["item_name"])
        if leader in EXCLUDED_ITEMS:
            continue
        if master_stamps is not None:
            s = master_stamps.get(leader, master_stamps.get(
                mapping_dict.get(t["item_name"], t["item_name"]), "Unassigned"))
            if not s or s == "Unassigned":
                continue
        filtered.append(t)

    # Group by leader — canonicalize signs so SR rows always carry negative
    # weight/amount/labor regardless of how DB stored them (signed or unsigned).
    item_txns = defaultdict(lambda: {"purchases": [], "sales": []})
    for t in filtered:
        leader = _resolve(t["item_name"])
        sign = -1 if t["type"] in ("sale_return", "purchase_return") else 1
        td = {
            "net_wt": abs(t.get("net_wt", 0) or 0) * sign,
            "tunch": float(t.get("tunch", 0) or 0),
            "labor": abs(t.get("labor", 0) or 0) * sign,
            "total_amount": abs(t.get("total_amount", 0) or 0) * sign,
        }
        if t["type"] in ("purchase", "purchase_return"):
            item_txns[leader]["purchases"].append(td)
        elif t["type"] in ("sale", "sale_return"):
            item_txns[leader]["sales"].append(td)

    results = []
    for item_name, data in item_txns.items():
        purchases = data["purchases"]
        sales = data["sales"]
        if not sales:
            continue

        # Cost-basis fallback from group ledger (same as /analytics/profit)
        if not purchases:
            le = grp_ledger.get(item_name)
            if le:
                purchases = [{
                    "net_wt": le.get("total_purchased_kg", 0) * 1000,
                    "tunch": le.get("purchase_tunch", 0),
                    "labor": le.get("total_labour", 0),
                    "total_amount": le.get("total_labour", 0),
                }]
            else:
                continue

        total_purchase_wt = sum(p["net_wt"] for p in purchases)
        total_sale_wt = sum(s["net_wt"] for s in sales)  # sale_returns reduce via negative net_wt
        if abs(total_purchase_wt) < 0.001 or abs(total_sale_wt) < 0.001:
            continue

        avg_purchase_tunch = (
            sum(p["tunch"] * abs(p["net_wt"]) for p in purchases)
            / sum(abs(p["net_wt"]) for p in purchases)
        ) if purchases else 0
        avg_sale_tunch = (
            sum(s["tunch"] * abs(s["net_wt"]) for s in sales)
            / sum(abs(s["net_wt"]) for s in sales)
        ) if sales else 0

        # Silver profit (kg)
        silver_profit_g = (avg_sale_tunch - avg_purchase_tunch) * total_sale_wt / 100
        silver_profit_kg = silver_profit_g / 1000

        # Labour profit (INR) — returns (negative net_wt) reduce labour income
        total_sale_labour = 0
        for s in sales:
            amt = abs(s.get("total_amount", 0) or s.get("labor", 0))
            if s.get("net_wt", 0) < 0:  # sale_return
                total_sale_labour -= amt
            else:
                total_sale_labour += amt
        le = grp_ledger.get(item_name)
        if le and le.get("labour_per_kg", 0) > 0:
            purchase_labour_per_gram = le["labour_per_kg"] / 1000
        elif purchases and sum(abs(p["net_wt"]) for p in purchases) > 0:
            purchase_labour_per_gram = (
                sum(abs(p.get("total_amount", 0) or p.get("labor", 0)) for p in purchases)
                / sum(abs(p["net_wt"]) for p in purchases)
            )
        else:
            purchase_labour_per_gram = 0
        labor_profit_inr = total_sale_labour - (purchase_labour_per_gram * abs(total_sale_wt))

        results.append({
            "item_name": item_name,
            "silver_profit_kg": round(silver_profit_kg, 3),
            "labor_profit_inr": round(labor_profit_inr, 2),
            "avg_purchase_tunch": round(avg_purchase_tunch, 2),
            "avg_sale_tunch": round(avg_sale_tunch, 2),
            "net_wt_sold_kg": round(total_sale_wt / 1000, 3),
            # Per-gram components for PMS
            "silver_margin_per_gram": silver_profit_g / max(abs(total_sale_wt), 1),
            "labour_margin_per_gram": labor_profit_inr / max(abs(total_sale_wt), 1),
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

    month_purchases = defaultdict(list)
    for t in transactions:
        if t.get("type") not in ("purchase", "purchase_return"):
            continue
        leader = _resolve(t["item_name"])
        if not _included(leader, t["item_name"]):
            continue
        sign = -1 if t["type"] == "purchase_return" else 1
        month_purchases[leader].append({
            "net_wt": abs(t.get("net_wt", 0) or 0) * sign,
            "tunch": float(t.get("tunch", 0) or 0),
            "labor": abs(t.get("labor", 0) or 0) * sign,
            "total_amount": abs(t.get("total_amount", 0) or 0) * sign,
        })

    cost_cache: dict = {}

    def _cost_basis(leader):
        if leader in cost_cache:
            return cost_cache[leader]
        purchases = month_purchases.get(leader, [])
        if not purchases:
            le = grp_ledger.get(leader)
            if le:
                purchases = [{
                    "net_wt": le.get("total_purchased_kg", 0) * 1000,
                    "tunch": le.get("purchase_tunch", 0),
                    "labor": le.get("total_labour", 0),
                    "total_amount": le.get("total_labour", 0),
                }]
            else:
                cost_cache[leader] = None
                return None
        tot_abs = sum(abs(p["net_wt"]) for p in purchases)
        if tot_abs < 0.001:
            cost_cache[leader] = None
            return None
        avg_pt = sum(p["tunch"] * abs(p["net_wt"]) for p in purchases) / tot_abs
        le = grp_ledger.get(leader)
        if le and le.get("labour_per_kg", 0) > 0:
            plpg = le["labour_per_kg"] / 1000
        else:
            plpg = sum(abs(p.get("total_amount", 0) or p.get("labor", 0)) for p in purchases) / tot_abs
        cost_cache[leader] = (avg_pt, plpg)
        return cost_cache[leader]

    return _resolve, _included, _cost_basis


def _sale_silver_labour(sales: list[dict], avg_pt: float, plpg: float):
    """Silver (kg) + labour (INR) profit for a bag of sale rows of ONE item, given a fixed
    cost basis. ``sales`` rows already carry signed weight/amount (SR negative)."""
    day_sw = sum(s["net_wt"] for s in sales)
    tot_abs_sw = sum(abs(s["net_wt"]) for s in sales)
    if tot_abs_sw < 0.001:
        return 0.0, 0.0, day_sw
    day_avg_st = sum(s["tunch"] * abs(s["net_wt"]) for s in sales) / tot_abs_sw
    silver = (day_avg_st - avg_pt) * day_sw / 100 / 1000
    sale_labour = 0.0
    for s in sales:
        amt = abs(s.get("total_amount", 0) or s.get("labor", 0))
        sale_labour += -amt if s["net_wt"] < 0 else amt
    labour = sale_labour - (plpg * abs(day_sw))
    return silver, labour, day_sw


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

    CRITICAL: silver & labour profit per day use a per-item **month-level** cost basis
    (avg purchase tunch + purchase labour/kg) — exactly the same cost basis the monthly
    summary (`_compute_item_profits`) uses. Because the purchase tunch is held CONSTANT
    per item across every day, the daily values are additive: the sum of daily silver
    profit equals the monthly total shown in the header.

    The earlier implementation recomputed the purchase tunch from *each day's* purchases
    (and fell back to the ledger only on no-purchase days). That is non-additive — the
    per-day cost basis drifts from the month-level one — so daily sums diverged from the
    monthly total (the reported "sum of daywise profit != total profit" bug).
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

    Uses the SAME month-level cost basis as `compute_daily_profits`, so the per-item silver
    profits shown on drilldown stay consistent with the day's total in the daily breakdown.
    ``month_transactions`` are all transactions for the date's month (needed for cost basis).
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
