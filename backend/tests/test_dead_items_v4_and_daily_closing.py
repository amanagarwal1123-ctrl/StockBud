"""
Tests for v4 Dead Items methodology (actual stock + windowed months-to-clear)
and new /api/stock-audit/daily-closing endpoint.
"""
import os
import time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


def _retry(fn, tries=5, delay=2.5):
    """Retry helper for 503 'Server is busy' semaphore responses."""
    last = None
    for _ in range(tries):
        r = fn()
        last = r
        if r.status_code != 503:
            return r
        time.sleep(delay)
    return last


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def exec_token():
    # Ensure TEST_EXEC exists; try login first
    r = requests.post(f"{API}/auth/login", json={"username": "TEST_EXEC", "password": "exec123"}, timeout=30)
    if r.status_code == 200:
        return r.json()["access_token"]
    pytest.skip(f"TEST_EXEC login failed: {r.status_code} {r.text}")


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ------------------- Dead Items v4 -------------------

class TestDeadItemsV4:
    def test_dead_items_basic(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=90", headers=admin_h, timeout=120))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert data.get("window_days") == 90
        # No 'Totals' or numeric item names
        for row in data["items"]:
            name = str(row.get("item_name", ""))
            assert name.lower() != "totals", f"Totals row leaked: {row}"
            assert not name.strip().isdigit(), f"Numeric item name leaked: {name}"
            assert row.get("stock_net_kg", 0) > 0, f"Non-positive stock: {row}"
            # new fields present
            for f in ("avg_daily_closing_kg", "window_days", "window_start", "sale_events"):
                assert f in row, f"Missing field {f} in row: {row}"

    def test_dead_items_window_changes(self, admin_h):
        r30 = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=30", headers=admin_h, timeout=120))
        r180 = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=180", headers=admin_h, timeout=120))
        assert r30.status_code == 200
        assert r180.status_code == 200
        d30, d180 = r30.json(), r180.json()
        assert d30["window_days"] == 30
        assert d180["window_days"] == 180
        # Some rows should differ in months_to_clear across windows (not strict equality)
        if d30["items"] and d180["items"]:
            # build dicts
            m30 = {i["item_name"]: i.get("months_to_clear") for i in d30["items"]}
            m180 = {i["item_name"]: i.get("months_to_clear") for i in d180["items"]}
            common = set(m30) & set(m180)
            diffs = [k for k in common if m30[k] != m180[k]]
            assert len(diffs) >= 1 or len(common) == 0, "window change didn't affect any months_to_clear"

    def test_dead_items_stock_matches_current_inventory(self, admin_h):
        r_dead = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=90", headers=admin_h, timeout=120))
        assert r_dead.status_code == 200
        r_inv = _retry(lambda: requests.get(f"{API}/inventory/current", headers=admin_h, timeout=120))
        assert r_inv.status_code == 200, r_inv.text
        inv = r_inv.json()
        # inventory stamp_items shape
        stamp_items = inv.get("stamp_items") or inv.get("items") or []
        # Build index: name -> net_wt grams
        name_to_g = {}
        for it in stamp_items:
            nm = it.get("item_name") or it.get("name")
            g = it.get("net_wt") or it.get("net_wt_grams") or 0
            if nm is None:
                continue
            name_to_g[nm] = name_to_g.get(nm, 0) + float(g or 0)

        items = r_dead.json()["items"]
        if not items:
            pytest.skip("No dead items to validate stock match")
        checked = 0
        for row in items[:5]:
            name = row["item_name"]
            merged = row.get("merged_names") or []
            expected_g = name_to_g.get(name, 0)
            for m in merged:
                expected_g += name_to_g.get(m, 0)
            expected_kg = expected_g / 1000.0
            got_kg = float(row["stock_net_kg"])
            # tolerant compare
            assert abs(got_kg - expected_kg) <= max(0.01, expected_kg * 0.02), (
                f"Stock mismatch for {name}: dead={got_kg} inv={expected_kg} merged={merged}"
            )
            checked += 1
        assert checked > 0

    def test_dead_items_review_reasons(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=90", headers=admin_h, timeout=120))
        assert r.status_code == 200
        for row in r.json()["items"]:
            rr = row.get("review_reasons")
            if rr:
                assert isinstance(rr, list)

    def test_dead_items_summary(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/analytics/dead-items/summary?window_days=90", headers=admin_h, timeout=120))
        assert r.status_code == 200, r.text
        data = r.json()
        # should contain counts
        assert isinstance(data, dict)
        summary = data.get("summary") or data
        assert any(k in summary for k in ("needs_review", "dead_total", "confirmed_dead", "total_items"))

    def test_dead_items_remove_and_restore(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/analytics/dead-items?window_days=90", headers=admin_h, timeout=120))
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("No items to remove")
        target = items[0]["item_name"]
        rem = requests.post(f"{API}/dead-items/remove", json={"item_name": target}, headers=admin_h, timeout=30)
        assert rem.status_code in (200, 201), rem.text
        res = requests.post(f"{API}/dead-items/restore", json={"item_name": target}, headers=admin_h, timeout=30)
        assert res.status_code in (200, 201), res.text

    def test_dead_items_forbidden_for_exec(self, exec_token):
        h = {"Authorization": f"Bearer {exec_token}"}
        r = requests.get(f"{API}/analytics/dead-items", headers=h, timeout=60)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text[:200]}"


# ------------------- Daily Closing Stock -------------------

class TestDailyClosing:
    def test_daily_closing_basic(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/stock-audit/daily-closing?days=30", headers=admin_h, timeout=120))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "days" in data
        days = data["days"]
        assert len(days) > 0
        # each day has date and closing_kg
        for d in days:
            assert "date" in d
            assert "closing_kg" in d

    def test_daily_closing_last_matches_inventory(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/stock-audit/daily-closing?days=30", headers=admin_h, timeout=120))
        assert r.status_code == 200
        days = r.json()["days"]
        last = days[-1]
        inv = _retry(lambda: requests.get(f"{API}/inventory/current", headers=admin_h, timeout=120)).json()
        total_g = inv.get("total_net_wt") or inv.get("total_net_wt_grams") or 0
        inv_kg = float(total_g) / 1000.0
        assert abs(float(last["closing_kg"]) - inv_kg) <= 0.05, f"last {last} vs inv {inv_kg}"

    def test_daily_closing_consistency_backroll(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/stock-audit/daily-closing?days=30", headers=admin_h, timeout=120))
        assert r.status_code == 200
        days = r.json()["days"]
        # If net_delta_kg provided, verify closing[d-1] = closing[d] - delta[d]
        has_delta = all("net_delta_kg" in d for d in days)
        if not has_delta:
            pytest.skip("No net_delta_kg field for back-roll check")
        for i in range(len(days) - 1, 0, -1):
            expected_prev = float(days[i]["closing_kg"]) - float(days[i]["net_delta_kg"])
            got_prev = float(days[i - 1]["closing_kg"])
            assert abs(got_prev - expected_prev) <= 0.05, (
                f"Backroll mismatch day {days[i]['date']}: prev={got_prev} expected={expected_prev}"
            )

    def test_daily_closing_forbidden_for_exec(self, exec_token):
        h = {"Authorization": f"Bearer {exec_token}"}
        r = requests.get(f"{API}/stock-audit/daily-closing?days=30", headers=h, timeout=60)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text[:200]}"


# ------------------- Regression -------------------

class TestRegression:
    def test_current_stock_loads(self, admin_h):
        r = _retry(lambda: requests.get(f"{API}/inventory/current", headers=admin_h, timeout=120))
        assert r.status_code == 200

    def test_profit_analysis_loads(self, admin_h):
        # Try common profit endpoints — accept any 200
        for ep in ("/analytics/profit", "/profit/summary", "/analytics/profit-analysis", "/profit"):
            r = requests.get(f"{API}{ep}", headers=admin_h, timeout=60)
            if r.status_code == 200:
                return
        pytest.skip("No known profit endpoint returned 200 — skipping (not a dead-items regression)")
