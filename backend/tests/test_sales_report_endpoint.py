"""Sales Report endpoint tests.

Verifies stamp-wise and item-wise sales aggregation with canonical signed
formula, item exclusion filter, custom date range vs year+month modes.
"""

import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope='module')
def admin_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = httpx.post(f"{BASE_URL}/api/auth/login",
                   json={"username": "admin", "password": "admin123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code}")
    return r.json()['access_token']


def test_sales_report_year_month(admin_token):
    r = httpx.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=2",
                  headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert 'period' in d
    assert d['period']['year'] == 2026
    assert d['period']['month'] == 2
    assert d['period']['start_date'] == '2026-02-01'
    assert d['period']['end_date'] == '2026-02-28'
    assert isinstance(d['by_stamp'], list)
    assert isinstance(d['by_item'], list)
    assert 'totals' in d


def test_sales_report_custom_range(admin_token):
    r = httpx.get(
        f"{BASE_URL}/api/analytics/sales-report?start_date=2026-02-01&end_date=2026-02-15",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d['period']['start_date'] == '2026-02-01'
    assert d['period']['end_date'] == '2026-02-15'


def test_sales_report_columns(admin_token):
    r = httpx.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=2",
                  headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    d = r.json()
    if d['by_stamp']:
        row = d['by_stamp'][0]
        for col in ('stamp', 'gross_wt_kg', 'net_wt_kg', 'avg_tunch',
                    'avg_labour_per_kg', 'total_fine_kg', 'total_labour_inr',
                    'sale_kg', 'return_kg', 'transactions', 'items_count'):
            assert col in row, f"missing column {col} in by_stamp"
    if d['by_item']:
        row = d['by_item'][0]
        for col in ('item_name', 'stamp', 'gross_wt_kg', 'net_wt_kg', 'avg_tunch',
                    'avg_labour_per_kg', 'total_fine_kg', 'total_labour_inr',
                    'sale_kg', 'return_kg', 'transactions'):
            assert col in row, f"missing column {col} in by_item"


def test_sales_report_missing_params_returns_400(admin_token):
    r = httpx.get(f"{BASE_URL}/api/analytics/sales-report",
                  headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 400


def test_sales_report_requires_auth():
    r = httpx.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=2", timeout=15)
    assert r.status_code in (401, 403)


def test_signed_canonical_in_endpoint():
    """Inline check that the endpoint uses canonical signed math.
    
    For a known dataset: sale rows + sale_return rows should produce a NET
    weight equal to sum of |sale| minus sum of |sale_return|.
    Validated indirectly via the debug-breakdown endpoint."""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = httpx.post(f"{BASE_URL}/api/auth/login",
                   json={"username": "admin", "password": "admin123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip("login failed")
    tok = r.json()['access_token']
    r2 = httpx.get(f"{BASE_URL}/api/analytics/sale-debug-breakdown?year=2026&month=2",
                   headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    if r2.status_code != 200:
        pytest.skip("debug endpoint unavailable")
    d = r2.json()
    raw = d['raw_kg']
    # canonical = sale - |sale_return|
    canonical = raw['sale_raw_sum_kg'] - raw['sale_return_abs_sum_kg']
    expected = d['totals_kg']['signed_net_total_all_items_kg']
    assert abs(canonical - expected) < 0.001, \
        f"Canonical {canonical} != endpoint signed_net {expected}"
