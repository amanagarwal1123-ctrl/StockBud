"""Regression tests for signed sale/sale_return canonicalization.

User-specified tests (verbatim):
1. sale net_wt +1469.741 kg and sale_return net_wt -24.447 kg  => 1445.294 kg
2. sale net_wt +1469.741 kg and sale_return net_wt +24.447 kg  => 1445.294 kg
3. /api/analytics/monthly-profit total_net_wt_sold == 1445.294 kg
4. Profit calculations subtract returns from sold volume and labour/value.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.profit_helpers import compute_item_margins
from services.monthly_summary_service import _compute_item_profits, _compute_party_data


KG = 1000  # grams per kg


def test_signed_negative_sr_yields_1445():
    """DB stores SR with negative net_wt (Excel sign preserved)."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 1469.741 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': 1469.741 * KG},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': -24.447 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': -24.447 * KG},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 2000 * KG, 'tunch': '50',
         'labor': 0, 'total_amount': 0},
    ]
    result = compute_item_margins(transactions, [], [], [])
    assert len(result) == 1
    # 1469.741 - 24.447 = 1445.294
    assert result[0]['net_wt_sold_kg'] == 1445.294, f"expected 1445.294, got {result[0]['net_wt_sold_kg']}"


def test_signed_positive_sr_also_yields_1445():
    """DB stores SR with positive net_wt (sign stripped)."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 1469.741 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': 1469.741 * KG},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': +24.447 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': +24.447 * KG},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 2000 * KG, 'tunch': '50',
         'labor': 0, 'total_amount': 0},
    ]
    result = compute_item_margins(transactions, [], [], [])
    assert len(result) == 1
    assert result[0]['net_wt_sold_kg'] == 1445.294, f"expected 1445.294, got {result[0]['net_wt_sold_kg']}"


def test_monthly_summary_negative_sr():
    """monthly_summary_service: SR with negative net_wt → net sales = 1445.294."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 1469.741 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 5000},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': -24.447 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': -100},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 2000 * KG, 'tunch': '50',
         'labor': 0, 'total_amount': 3000},
    ]
    master_stamps = {'X': 'JB-1'}
    result = _compute_item_profits(transactions, master_stamps, {}, {}, {})
    assert 'X' in result
    assert result['X']['net_wt_sold_kg'] == 1445.294
    # total_sales_value = 5000 - 100 = 4900
    assert result['X']['total_sales_value'] == 4900.0


def test_monthly_summary_positive_sr():
    """monthly_summary_service: SR with positive net_wt (unsigned) → net sales = 1445.294."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 1469.741 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 5000},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': +24.447 * KG, 'tunch': '55',
         'labor': 0, 'total_amount': 100},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 2000 * KG, 'tunch': '50',
         'labor': 0, 'total_amount': 3000},
    ]
    master_stamps = {'X': 'JB-1'}
    result = _compute_item_profits(transactions, master_stamps, {}, {}, {})
    assert result['X']['net_wt_sold_kg'] == 1445.294
    # Even with +100 SR total_amount in DB, signed should be -100 → 5000 - 100 = 4900
    assert result['X']['total_sales_value'] == 4900.0


def test_party_data_signed_negative_sr():
    """Party customer totals: SR with negative net_wt → net sales weight correct."""
    transactions = [
        {'type': 'sale', 'party_name': 'A', 'net_wt': 100.0, 'fine': 91.0,
         'gr_wt': 100.0, 'total_amount': 5000, 'item_name': 'X'},
        {'type': 'sale_return', 'party_name': 'A', 'net_wt': -30.0, 'fine': -27.3,
         'gr_wt': -30.0, 'total_amount': -1500, 'item_name': 'X'},
    ]
    result = _compute_party_data(transactions)
    assert round(result['customers']['A']['total_net_wt'], 3) == 70.0
    assert round(result['customers']['A']['total_sales_value'], 2) == 3500.0


def test_party_data_signed_positive_sr():
    """Party customer totals: SR with POSITIVE net_wt → still subtracts correctly."""
    transactions = [
        {'type': 'sale', 'party_name': 'A', 'net_wt': 100.0, 'fine': 91.0,
         'gr_wt': 100.0, 'total_amount': 5000, 'item_name': 'X'},
        {'type': 'sale_return', 'party_name': 'A', 'net_wt': +30.0, 'fine': +27.3,
         'gr_wt': +30.0, 'total_amount': +1500, 'item_name': 'X'},
    ]
    result = _compute_party_data(transactions)
    assert round(result['customers']['A']['total_net_wt'], 3) == 70.0
    assert round(result['customers']['A']['total_sales_value'], 2) == 3500.0


def test_profit_calc_subtracts_return_from_volume():
    """Silver profit should be computed on NET sale volume (sale - return)."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 1000.0, 'tunch': '91',
         'labor': 0, 'total_amount': 0, 'gr_wt': 1000.0},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': -100.0, 'tunch': '91',
         'labor': 0, 'total_amount': 0, 'gr_wt': -100.0},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 2000.0, 'tunch': '89',
         'labor': 0, 'total_amount': 0},
    ]
    result = compute_item_margins(transactions, [], [], [])
    # Net vol = 900g. silver = (91-89) * 900 / 100 / 1000 = 0.018 kg
    assert result[0]['net_wt_sold_kg'] == 0.9
    assert result[0]['silver_profit_kg'] == 0.018


def test_no_double_negation():
    """Confirm: SR with negative net_wt doesn't get flipped back to positive."""
    transactions = [
        {'type': 'sale', 'item_name': 'X', 'net_wt': 100.0, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': 100.0},
        {'type': 'sale_return', 'item_name': 'X', 'net_wt': -20.0, 'tunch': '55',
         'labor': 0, 'total_amount': 0, 'gr_wt': -20.0},
        {'type': 'purchase', 'item_name': 'X', 'net_wt': 500.0, 'tunch': '50',
         'labor': 0, 'total_amount': 0},
    ]
    result = compute_item_margins(transactions, [], [], [])
    # Correct net = 100 - 20 = 80g = 0.08 kg.
    # Double-negated (buggy) would be 100 + 20 = 120g = 0.12 kg.
    assert result[0]['net_wt_sold_kg'] == 0.08
    assert result[0]['net_wt_sold_kg'] != 0.12  # explicit guard against bug regression


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in dict(globals()).items() if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    if failed:
        raise SystemExit(f"{failed} test(s) failed")
    print(f"\nAll {len(tests)} signed-sale-return tests passed.")
