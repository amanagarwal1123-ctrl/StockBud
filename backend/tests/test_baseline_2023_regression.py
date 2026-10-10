"""Regression tests for STOCK 31-12-2023 baseline swap (iteration 59)."""
import os
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if 'REACT_APP_BACKEND_URL' in os.environ else None
if not BASE:
    # Fallback: read frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE = line.split('=', 1)[1].strip().rstrip('/')


@pytest.fixture(scope='module')
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={'username': 'admin', 'password': 'admin123'}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()['access_token']


@pytest.fixture(scope='module')
def hdr(token):
    return {'Authorization': f'Bearer {token}'}


# --- Mongo baseline collection shape ---
def test_baseline_mongo_shape():
    c = MongoClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    assert db.stock_sale_baseline.count_documents({}) == 894
    meta = db.stock_sale_baseline_meta.find_one({'key': 'meta'})
    assert meta is not None
    assert meta['baseline_date'] == '2023-12-31'
    assert meta['items'] == 894


# --- Sales report 2025 full year: RH-60 BICCHIYA anchored to baseline ---
def test_sales_report_2025_rh60_bicchiya(hdr):
    r = requests.get(f"{BASE}/api/analytics/sales-report",
                     params={'year': 2025, 'month': 0}, headers=hdr, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data.get('by_item') or data.get('items') or []
    row = next((x for x in rows if x.get('item_name') == 'RH-60 BICCHIYA'), None)
    assert row is not None, "RH-60 BICCHIYA missing"
    assert abs(row['avg_stock_kg'] - 888.466) < 0.01, row
    assert abs(row['stock_sale_ratio'] - 213) < 2, row


# --- Sales report pre-baseline period: null ratios, no error ---
def test_sales_report_pre_baseline_period(hdr):
    r = requests.get(f"{BASE}/api/analytics/sales-report",
                     params={'start_date': '2023-01-01', 'end_date': '2023-12-31'},
                     headers=hdr, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data.get('by_item') or data.get('items') or []
    # all stock_sale_ratio must be null (period entirely before baseline date)
    non_null = [x for x in rows if x.get('stock_sale_ratio') is not None]
    assert non_null == [], f"Expected all null ratios, got {len(non_null)} non-null, sample: {non_null[:3]}"


# --- Dead items endpoint ---
def test_dead_items(hdr):
    r = requests.get(f"{BASE}/api/analytics/dead-items", headers=hdr, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['baseline_date'] == '2023-12-31'
    assert abs(data['months_span'] - 33.3) < 0.5, data['months_span']
    rows = data.get('items') or data.get('rows') or []
    assert len(rows) == 85, f"Expected 85 rows, got {len(rows)}"
    # verify ratio formula
    for row in rows[:20]:
        avg = row['avg_monthly_sale_kg']
        if avg and avg > 0:
            expected = row['stock_net_kg'] / avg
            assert row.get('stock_sale_ratio') is not None
            # avg is rounded to 3 decimals; allow 2% relative tolerance
            assert abs(row['stock_sale_ratio'] - expected) / max(expected, 1) < 0.02, row


# --- Unmapped list includes baseline-only names ---
def test_unmapped_includes_baseline_only(hdr):
    r = requests.get(f"{BASE}/api/mappings/unmapped", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    unmapped = data.get('unmapped_items') or []
    names = {u if isinstance(u, str) else u.get('item_name') for u in unmapped}
    assert '.CHAIN -058' in names, "'.CHAIN -058' missing from unmapped"
    assert '84-46-001' in names, "'84-46-001' missing from unmapped"
    assert len(unmapped) > 500, f"Expected ~751, got {len(unmapped)}"
