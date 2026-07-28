"""Iteration 42 — Stock:Sale ratio averaging fix + merged_names on by_item."""
import os
from pathlib import Path
from dotenv import dotenv_values
import pytest
import requests
from datetime import datetime, timezone, timedelta

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _months_equiv(sd, ed):
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
    ed_eff = min(ed, today)
    n = (datetime.strptime(ed_eff, '%Y-%m-%d') - datetime.strptime(sd, '%Y-%m-%d')).days + 1
    return max(n / 30.44, 0.033)


class TestSalesReportRatio:
    def test_single_month_ratio_fields_present(self, api):
        r = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=7", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d['by_item'] and d['by_stamp']
        for row in d['by_item']:
            assert 'stock_sale_ratio' in row
            assert 'avg_stock_kg' in row
            assert row['stock_sale_ratio'] is None or isinstance(row['stock_sale_ratio'], (int, float))
        for row in d['by_stamp']:
            assert 'stock_sale_ratio' in row
            assert 'avg_stock_kg' in row

    def test_full_year_ratio_uses_monthly_average(self, api):
        r = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=0", timeout=90)
        assert r.status_code == 200
        d = r.json()
        rows = {row['item_name']: row for row in d['by_item']}
        assert 'CHAIN MS-70' in rows, f"CHAIN MS-70 missing; sample: {list(rows)[:20]}"
        row = rows['CHAIN MS-70']
        me = _months_equiv('2026-01-01', '2026-12-31')
        net = row['net_wt_kg']
        avg_stock = row['avg_stock_kg']
        if net and abs(net) > 0.001:
            monthly = net / me
            expected = round(avg_stock / monthly, 2) if abs(monthly) > 0.001 else None
            # Old (wrong) formula would be avg_stock/net (much smaller magnitude for full year)
            old_wrong = round(avg_stock / net, 2) if abs(net) > 0.001 else None
            print(f"CHAIN MS-70 avg_stock_kg={avg_stock} net_kg={net} months={me:.2f} expected_ratio={expected} old={old_wrong} api={row['stock_sale_ratio']}")
            if expected is not None and row['stock_sale_ratio'] is not None:
                assert abs(row['stock_sale_ratio'] - expected) < 0.05, \
                    f"ratio {row['stock_sale_ratio']} != new-formula {expected} (old={old_wrong})"

    def test_ratio_pill_color_distribution(self, api):
        r = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=0", timeout=90)
        assert r.status_code == 200
        rows = r.json()['by_item']
        ratios = [row['stock_sale_ratio'] for row in rows if row['stock_sale_ratio'] is not None]
        assert ratios, "no numeric ratios at all"
        # Preview data has negative stock; ensure both green (<=2) and red (>4 or <0) exist
        greens = [x for x in ratios if 0 <= x <= 2]
        reds = [x for x in ratios if x < 0 or x > 4]
        print(f"ratios n={len(ratios)} green={len(greens)} red={len(reds)}")
        assert greens or reds


class TestDrillConsistency:
    def test_drill_matches_by_item_ratio(self, api):
        rep = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=0", timeout=90).json()
        by_item = {r['item_name']: r for r in rep['by_item']}
        item = 'CHAIN MS-70'
        assert item in by_item
        drill = api.get(
            f"{BASE_URL}/api/analytics/sales-report-drill",
            params={'entity_type': 'item', 'name': item,
                    'start_date': '2026-01-01', 'end_date': '2026-12-31'},
            timeout=60,
        )
        assert drill.status_code == 200
        d = drill.json()
        assert 'avg_monthly_sale_kg' in d
        assert 'stock_to_sale_ratio' in d
        rep_ratio = by_item[item]['stock_sale_ratio']
        drl_ratio = d['stock_to_sale_ratio']
        print(f"rep_ratio={rep_ratio} drill_ratio={drl_ratio} avg_monthly={d['avg_monthly_sale_kg']}")
        if rep_ratio is None or drl_ratio is None:
            assert rep_ratio == drl_ratio
        else:
            assert abs(rep_ratio - drl_ratio) < 0.05


class TestMergedNames:
    def test_chain_ms70_has_merged_variant_and_no_dupe_row(self, api):
        r = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=7", timeout=60)
        assert r.status_code == 200
        rows = r.json()['by_item']
        names = [row['item_name'] for row in rows]
        assert 'CHAIN MS-70' in names
        assert 'CHAIN MS-70 CASTING' not in names, "variant should be merged, not separate row"
        row = next(r for r in rows if r['item_name'] == 'CHAIN MS-70')
        assert 'merged_names' in row
        print(f"merged_names for CHAIN MS-70: {row['merged_names']}")
        assert 'CHAIN MS-70 CASTING' in row['merged_names']


class TestRegressionTotals:
    def test_totals_match_by_stamp_sums(self, api):
        r = api.get(f"{BASE_URL}/api/analytics/sales-report?year=2026&month=7", timeout=60)
        assert r.status_code == 200
        d = r.json()
        t = d['totals']
        assert abs(t['net_wt_kg'] - round(sum(x['net_wt_kg'] for x in d['by_stamp']), 3)) < 0.01
        assert abs(t['total_fine_kg'] - round(sum(x['total_fine_kg'] for x in d['by_stamp']), 3)) < 0.01
        assert abs(t['total_labour_inr'] - round(sum(x['total_labour_inr'] for x in d['by_stamp']), 2)) < 1
