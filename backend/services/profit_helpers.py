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

    # Group by leader
    item_txns = defaultdict(lambda: {"purchases": [], "sales": []})
    for t in filtered:
        leader = _resolve(t["item_name"])
        td = {
            "net_wt": t.get("net_wt", 0),
            "tunch": float(t.get("tunch", 0) or 0),
            "labor": t.get("labor", 0),
            "total_amount": t.get("total_amount", 0),
        }
        if t["type"] in ("purchase", "purchase_return"):
            item_txns[leader]["purchases"].append(td)
        elif t["type"] == "sale":
            item_txns[leader]["sales"].append(td)
        elif t["type"] == "sale_return":
            item_txns[leader]["purchases"].append(td)

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
        total_sale_wt = sum(s["net_wt"] for s in sales)
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

        # Labour profit (INR)
        total_sale_labour = sum(
            abs(s.get("total_amount", 0) or s.get("labor", 0)) for s in sales
        )
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
