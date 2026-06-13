"""Regression test: daily profit must sum to the monthly total.

Reproduces the production bug "sum of daywise profit != total profit shown".

Root cause: the daily-profit endpoint recomputed the purchase tunch (cost basis) from
EACH DAY's purchases, while the monthly total (header) uses a per-item MONTH-level cost
basis. A per-day cost basis is non-additive, so the daily values could not sum to the
monthly total. The fix (`compute_daily_profits`) holds the per-item cost basis constant
across the month, making the daily values additive.

These tests assert the invariant directly against `_compute_item_profits` — the exact
function that feeds the monthly_summaries the header reads from.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.profit_helpers import compute_daily_profits, compute_date_profit_detail
from services.monthly_summary_service import _compute_item_profits
from services.group_utils import build_group_maps, build_group_ledger

def _txn(date, ttype, item, net_wt_g, tunch, amount):
    return {"date": date, "type": ttype, "item_name": item,
            "net_wt": net_wt_g, "tunch": tunch, "total_amount": amount, "labor": amount,
            "fine": net_wt_g * tunch / 100, "party_name": "P"}


LEDGER = [{
    "item_name": "RING", "purchase_tunch": 54.0, "labour_per_kg": 240.0,
    "total_purchased_kg": 18.0, "total_fine_kg": 9.72, "total_labour": 4320.0,
}]


def _monthly_total(transactions, master_stamps):
    mapping_dict, member_to_leader, _ = build_group_maps([], [])
    grp_ledger = build_group_ledger(LEDGER, [], [])
    results = _compute_item_profits(transactions, master_stamps, mapping_dict, member_to_leader, grp_ledger)
    silver = sum(r["silver_profit_kg"] for r in results.values())
    labor = sum(r["labor_profit_inr"] for r in results.values())
    return silver, labor


def _daily_total(transactions, master_stamps, year, month):
    daily = compute_daily_profits(transactions, LEDGER, [], [], master_stamps, year, month)
    silver = sum(d["silver_profit_kg"] for d in daily)
    labor = sum(d["labor_profit_inr"] for d in daily)
    return silver, labor, daily


MASTER = {"RING": "STAMP 1"}


def test_daily_silver_sums_to_monthly_no_returns():
    """Multi-day purchases at different tunches + a sale day with NO purchase.
    The OLD per-day cost basis dropped the no-purchase day entirely; the fix includes it."""
    txns = [
        _txn("2026-06-01", "purchase", "RING", 10000, 50, 2000),
        _txn("2026-06-01", "sale",     "RING", 5000, 70, 5000),
        _txn("2026-06-02", "sale",     "RING", 4000, 72, 4000),  # no purchase this day
        _txn("2026-06-03", "purchase", "RING", 8000, 60, 2400),
        _txn("2026-06-03", "sale",     "RING", 6000, 75, 6000),
    ]
    m_silver, m_labor = _monthly_total(txns, MASTER)
    d_silver, d_labor, _ = _daily_total(txns, MASTER, 2026, 6)

    assert abs(d_silver - m_silver) < 0.005, f"silver daily {d_silver} != monthly {m_silver}"
    assert abs(d_labor - m_labor) < 1.0, f"labour daily {d_labor} != monthly {m_labor}"


def test_old_per_day_costbasis_would_diverge():
    """Documents the bug: a per-day cost basis (purchase tunch from that day only,
    skipping no-purchase sale days) does NOT sum to the monthly total."""
    txns = [
        _txn("2026-06-01", "purchase", "RING", 10000, 50, 0),
        _txn("2026-06-01", "sale",     "RING", 5000, 70, 5000),
        _txn("2026-06-02", "sale",     "RING", 4000, 72, 4000),
        _txn("2026-06-03", "purchase", "RING", 8000, 60, 0),
        _txn("2026-06-03", "sale",     "RING", 6000, 75, 6000),
    ]
    # OLD logic: per-day avg purchase tunch, skip days with no purchase & no ledger
    old_day1 = (70 - 50) * 5000 / 100 / 1000   # 1.0
    old_day2 = 0.0                              # dropped (no purchase / ledger)
    old_day3 = (75 - 60) * 6000 / 100 / 1000   # 0.9
    old_sum = old_day1 + old_day2 + old_day3    # 1.9
    m_silver, _ = _monthly_total(txns, MASTER)  # ~2.713
    assert abs(old_sum - m_silver) > 0.1, "expected the OLD per-day method to diverge"

    # NEW method must match the monthly total
    d_silver, _, _ = _daily_total(txns, MASTER, 2026, 6)
    assert abs(d_silver - m_silver) < 0.005


def test_daily_sums_to_monthly_with_returns():
    """With sale returns present, daily must still closely track the monthly total."""
    txns = [
        _txn("2026-06-01", "purchase", "RING", 20000, 55, 4000),
        _txn("2026-06-01", "sale",     "RING", 8000, 71, 8000),
        _txn("2026-06-05", "sale",     "RING", 5000, 73, 5000),
        _txn("2026-06-05", "sale_return", "RING", 1000, 71, 1000),
        _txn("2026-06-09", "sale",     "RING", 6000, 76, 6000),
    ]
    m_silver, m_labor = _monthly_total(txns, MASTER)
    d_silver, d_labor, _ = _daily_total(txns, MASTER, 2026, 6)
    # Per-entry summation is exact even with returns (no averaging residual)
    assert abs(d_silver - m_silver) < 0.005, f"silver daily {d_silver} != monthly {m_silver}"
    assert abs(d_labor - m_labor) < 1.0, f"labour daily {d_labor} != monthly {m_labor}"


def test_excluded_items_skipped_in_daily():
    """Excluded items contribute nothing to daily profit (parity with monthly)."""
    txns = [
        _txn("2026-06-01", "purchase", "EMERALD MURTI", 1000, 50, 100),
        _txn("2026-06-01", "sale",     "EMERALD MURTI", 500, 90, 50000),
    ]
    d_silver, d_labor, _ = _daily_total(txns, {"EMERALD MURTI": "STAMP 1"}, 2026, 6)
    assert d_silver == 0
    assert d_labor == 0


def test_drilldown_items_sum_to_daily_total():
    """The per-date drilldown (top_items) must use the same cost basis as the daily total,
    so the sum of its item silver/labour equals that day's daily-profit value."""
    txns = [
        _txn("2026-06-01", "purchase", "RING", 10000, 50, 2000),
        _txn("2026-06-01", "sale",     "RING", 5000, 70, 5000),
        _txn("2026-06-02", "sale",     "RING", 4000, 72, 4000),
        _txn("2026-06-03", "purchase", "RING", 8000, 60, 2400),
        _txn("2026-06-03", "sale",     "RING", 6000, 75, 6000),
    ]
    _, _, daily = _daily_total(txns, MASTER, 2026, 6)
    by_date = {d["date"]: d for d in daily}
    for date in ("2026-06-01", "2026-06-02", "2026-06-03"):
        detail = compute_date_profit_detail(txns, date, LEDGER, [], [], MASTER)
        items_silver = round(sum(i["silver_profit_kg"] for i in detail["top_items"]), 3)
        items_labor = round(sum(i["labor_profit_inr"] for i in detail["top_items"]), 2)
        assert abs(items_silver - by_date[date]["silver_profit_kg"]) < 0.005, \
            f"{date}: drilldown silver {items_silver} != daily {by_date[date]['silver_profit_kg']}"
        assert abs(items_labor - by_date[date]["labor_profit_inr"]) < 1.0, \
            f"{date}: drilldown labour {items_labor} != daily {by_date[date]['labor_profit_inr']}"
