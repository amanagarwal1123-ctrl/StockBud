"""Tests for year-comparison parties endpoint (>1000 cap removal)."""
import os
from pathlib import Path
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_year_comparison_parties_customer_no_cap(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/parties",
                     params={"party_type": "customer"}, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # Data can be list or dict with 'parties'
    parties = data if isinstance(data, list) else data.get("parties", data.get("names", []))
    assert isinstance(parties, list)
    assert len(parties) > 1000, f"Expected >1000 customers, got {len(parties)}"
    print(f"Customer parties count: {len(parties)}")
    # Verify late-alphabet names present
    joined = "\n".join(parties)
    assert "YCTEST CUSTOMER 1199" in joined, "YCTEST CUSTOMER 1199 missing"
    assert any("ZIL SILVER" in p for p in parties), "ZIL SILVER expected"


def test_year_comparison_parties_supplier_no_cap(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/parties",
                     params={"party_type": "supplier"}, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    parties = data if isinstance(data, list) else data.get("parties", data.get("names", []))
    assert len(parties) > 1000, f"Expected >1000 suppliers, got {len(parties)}"
    print(f"Supplier parties count: {len(parties)}")
    assert "YCTEST SUPPLIER 1099" in parties or any("YCTEST SUPPLIER 1099" == p for p in parties)
    assert any("ZEENAT" in p for p in parties), "ZEENAT SILVER CHAMMACH expected"


def test_year_comparison_party_detail(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/party-detail",
                     params={"party": "YCTEST CUSTOMER 0005", "party_type": "customer"},
                     headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # Expect monthly series keyed structure
    assert isinstance(data, dict)
    # Must contain at least one of the expected keys
    keys_str = str(data.keys())
    assert any(k in data for k in ("kg", "value", "silver_profit_kg", "labor_profit_inr", "series", "monthly")), \
        f"Unexpected structure: {keys_str}"


def test_monthly_profit_regression(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/monthly-profit",
                     params={"year": 2026, "month": 0}, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # Check no duplicate item names
    items = data.get("items") if isinstance(data, dict) else None
    if items and isinstance(items, list):
        names = [i.get("item_name") or i.get("name") for i in items if isinstance(i, dict)]
        names = [n for n in names if n]
        assert len(names) == len(set(names)), "Duplicate item names present"
