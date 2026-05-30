"""
End-to-end tests for the /api/analytics/sales-reconciliation endpoint and
the new freshness/refresh APIs (summary-status, recompute-summaries with
last_computed_at, dashboard-year-summary with freshness fields).
"""
import os
import pytest
import httpx


BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def _login():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = httpx.post(f"{BASE_URL}/api/auth/login",
                   json={"username": "admin", "password": "admin123"},
                   timeout=15)
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json().get('access_token') or r.json().get('token')


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_summary_status_returns_freshness_fields():
    token = _login()
    r = httpx.get(f"{BASE_URL}/api/analytics/summary-status?year=2026",
                  headers=_auth(token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ('year', 'is_stale', 'last_computed_at', 'stored_txn_count',
                'live_txn_count'):
        assert key in data, f"missing {key}"
    assert data['year'] == 2026
    assert isinstance(data['is_stale'], bool)


def test_recompute_summaries_returns_last_computed_at():
    token = _login()
    r = httpx.post(f"{BASE_URL}/api/analytics/recompute-summaries",
                   headers=_auth(token), json={"year": 2026}, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['success'] is True
    assert 'last_computed_at' in data
    assert 'txn_count' in data
    # After recompute, the year should no longer be stale
    r2 = httpx.get(f"{BASE_URL}/api/analytics/summary-status?year=2026",
                   headers=_auth(token), timeout=15)
    assert r2.json()['is_stale'] is False


def test_dashboard_year_summary_includes_freshness():
    token = _login()
    r = httpx.get(f"{BASE_URL}/api/analytics/dashboard-year-summary?year=2026",
                  headers=_auth(token), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'last_computed_at' in data
    assert 'was_recomputed' in data


def test_monthly_profit_includes_freshness():
    token = _login()
    r = httpx.get(f"{BASE_URL}/api/analytics/monthly-profit?year=2026&month=0",
                  headers=_auth(token), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'last_computed_at' in data
    assert 'was_recomputed' in data


def test_sales_reconciliation_returns_per_item_rows():
    token = _login()
    r = httpx.get(
        f"{BASE_URL}/api/analytics/sales-reconciliation"
        "?start_date=2026-01-01&end_date=2026-12-31",
        headers=_auth(token), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # Schema sanity
    assert 'items' in data
    assert 'grand_totals_all_items' in data
    assert 'excluded_items_totals' in data
    assert 'unassigned_stamp_totals' in data
    assert 'visible_net_after_returns_kg' in data
    for key in ('sale_net_kg', 'ret_net_kg', 'net_after_returns_kg',
                'net_amount'):
        assert key in data['grand_totals_all_items']

    # Math integrity: visible = grand - excluded - unassigned (within rounding)
    grand = data['grand_totals_all_items']['net_after_returns_kg']
    excluded = data['excluded_items_totals']['net_after_returns_kg']
    unassigned = data['unassigned_stamp_totals']['net_after_returns_kg']
    visible = data['visible_net_after_returns_kg']
    diff = abs((grand - excluded - unassigned) - visible)
    assert diff < 0.01, f"visible math mismatch: {diff} kg"

    # Per-item row schema
    if data['items']:
        row = data['items'][0]
        for key in ('raw_item_name', 'leader', 'stamp', 'is_excluded',
                    'is_unassigned', 'sale_net_kg', 'ret_net_kg',
                    'net_after_returns_kg', 'net_amount', 'sale_rows',
                    'ret_rows'):
            assert key in row, f"missing item key {key}"


def test_sales_reconciliation_requires_auth():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    r = httpx.get(
        f"{BASE_URL}/api/analytics/sales-reconciliation"
        "?start_date=2026-01-01&end_date=2026-12-31",
        timeout=15)
    assert r.status_code in (401, 403)


def test_sales_reconciliation_requires_admin():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    # Login as a non-admin role if available; otherwise skip
    r = httpx.post(f"{BASE_URL}/api/auth/login",
                   json={"username": "TEST_EXEC", "password": "exec123"},
                   timeout=15)
    if r.status_code != 200:
        pytest.skip("Executive user not seeded")
    tok = r.json().get('access_token') or r.json().get('token')
    r2 = httpx.get(
        f"{BASE_URL}/api/analytics/sales-reconciliation"
        "?start_date=2026-01-01&end_date=2026-12-31",
        headers=_auth(tok), timeout=15)
    assert r2.status_code == 403
