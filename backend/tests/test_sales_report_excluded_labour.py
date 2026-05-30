"""
Regression test: /api/analytics/sales-report response must surface the
LABOUR amount of EXCLUDED_ITEMS so users can explain the Tally-vs-App gap.

The bug we are guarding against: the previous response only reported
``excluded_items_kg`` and ``excluded_rows`` (weight only). Items like
EMERALD MURTI, FRAME NEW, NAJARIA, COURIER carry tiny weight but
significant labour Rs — hiding that labour silently caused a ~₹50L
Tally-vs-App discrepancy that was impossible to attribute.
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
    assert r.status_code == 200, r.text
    return r.json().get('access_token') or r.json().get('token')


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_sales_report_exposes_excluded_labour_amount():
    token = _login()
    r = httpx.get(
        f"{BASE_URL}/api/analytics/sales-report?year=2026&month=0",
        headers=_auth(token), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()

    # New fields that must be present
    for key in ('excluded_items_kg', 'excluded_items_amount_inr',
                'excluded_items_fine_kg', 'excluded_rows',
                'excluded_items_breakdown'):
        assert key in data, f"missing {key} — UI cannot diagnose Tally gap"

    # Breakdown shape
    if data['excluded_rows'] > 0:
        assert isinstance(data['excluded_items_breakdown'], list)
        assert len(data['excluded_items_breakdown']) > 0
        first = data['excluded_items_breakdown'][0]
        for k in ('item_name', 'net_kg', 'amount_inr', 'fine_kg', 'rows'):
            assert k in first

        # Sum of per-item amounts equals the headline excluded amount
        total = sum(it['amount_inr'] for it in data['excluded_items_breakdown'])
        assert abs(total - data['excluded_items_amount_inr']) < 0.01, \
            f"breakdown sum {total} != headline {data['excluded_items_amount_inr']}"

        # Sorted desc by amount
        amounts = [it['amount_inr'] for it in data['excluded_items_breakdown']]
        assert amounts == sorted(amounts, reverse=True)
