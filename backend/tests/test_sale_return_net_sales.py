"""Regression tests: sale_return must SUBTRACT from net sales (not add).

User reported: "the code added sale and sale return and showed the total when
indeed it should have subtracted the sale return from sale to show net sales,
and likewise calculate the profit."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.profit_helpers import compute_item_margins
from services.monthly_summary_service import _compute_item_profits, _compute_party_data


def test_profit_helpers_subtracts_sale_return_from_net_wt():
    """100g sale + 30g return at same tunch => net 70g sold, not 130g."""
    transactions = [
        {'type': 'sale', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '91',
         'labor': 0, 'total_amount': 9100, 'gr_wt': 100.0},
        {'type': 'sale_return', 'item_name': 'ITEM_X', 'net_wt': 30.0, 'tunch': '91',
         'labor': 0, 'total_amount': 2730, 'gr_wt': 30.0},
        {'type': 'purchase', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '89',
         'labor': 0, 'total_amount': 8900},
    ]
    result = compute_item_margins(transactions, [], [], [])
    assert len(result) == 1
    r = result[0]
    assert r['net_wt_sold_kg'] == 0.07, f"expected 0.07 kg net (100g - 30g), got {r['net_wt_sold_kg']}"


def test_profit_helpers_subtracts_sale_return_from_silver_profit():
    """Silver profit must use NET sale weight (sale - return)."""
    transactions = [
        {'type': 'sale', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '91',
         'labor': 0, 'total_amount': 9100, 'gr_wt': 100.0},
        {'type': 'sale_return', 'item_name': 'ITEM_X', 'net_wt': 30.0, 'tunch': '91',
         'labor': 0, 'total_amount': 2730, 'gr_wt': 30.0},
        {'type': 'purchase', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '89',
         'labor': 0, 'total_amount': 8900},
    ]
    result = compute_item_margins(transactions, [], [], [])
    r = result[0]
    # (sale tunch 91 - purchase tunch 89) * 70g / 100 / 1000 = 0.0014 kg
    expected = round(0.0014, 3)
    assert r['silver_profit_kg'] == expected, f"expected {expected}, got {r['silver_profit_kg']}"


def test_monthly_summary_subtracts_sale_return_from_total_sales_value():
    """Total Sales Value = sale total - sale_return total."""
    transactions = [
        {'type': 'sale', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '91',
         'labor': 50, 'total_amount': 5000},
        {'type': 'sale_return', 'item_name': 'ITEM_X', 'net_wt': 30.0, 'tunch': '91',
         'labor': 15, 'total_amount': 1500},
        {'type': 'purchase', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '89',
         'labor': 30, 'total_amount': 3000},
    ]
    master_stamps = {'ITEM_X': 'JB-1'}
    result = _compute_item_profits(transactions, master_stamps, {}, {}, {})
    assert 'ITEM_X' in result
    v = result['ITEM_X']
    assert v['net_wt_sold_kg'] == 0.07
    assert v['total_sales_value'] == 3500.0, f"expected 3500 (5000-1500), got {v['total_sales_value']}"


def test_party_data_subtracts_sale_return():
    """Customer's net_wt and sales_value should reflect (sale - sale_return)."""
    transactions = [
        {'type': 'sale', 'party_name': 'CUST A', 'net_wt': 100.0, 'fine': 91.0,
         'gr_wt': 100.0, 'total_amount': 5000, 'item_name': 'X'},
        {'type': 'sale_return', 'party_name': 'CUST A', 'net_wt': 30.0, 'fine': 27.3,
         'gr_wt': 30.0, 'total_amount': 1500, 'item_name': 'X'},
    ]
    result = _compute_party_data(transactions)
    cust = result['customers'].get('CUST A')
    assert cust is not None
    assert round(cust['total_net_wt'], 3) == 70.0
    assert round(cust['total_sales_value'], 2) == 3500.0


def test_no_returns_unchanged():
    """If no sale_return, behavior unchanged from pure sale handling."""
    transactions = [
        {'type': 'sale', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '91',
         'labor': 0, 'total_amount': 9100, 'gr_wt': 100.0},
        {'type': 'purchase', 'item_name': 'ITEM_X', 'net_wt': 100.0, 'tunch': '89',
         'labor': 0, 'total_amount': 8900},
    ]
    result = compute_item_margins(transactions, [], [], [])
    assert result[0]['net_wt_sold_kg'] == 0.1


if __name__ == '__main__':
    test_profit_helpers_subtracts_sale_return_from_net_wt()
    test_profit_helpers_subtracts_sale_return_from_silver_profit()
    test_monthly_summary_subtracts_sale_return_from_total_sales_value()
    test_party_data_subtracts_sale_return()
    test_no_returns_unchanged()
    print("All sale_return regression tests passed.")
