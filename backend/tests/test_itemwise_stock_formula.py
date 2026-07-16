"""Item-wise current stock formula regression tests.

Verifies:
    stock = opening + purchase + purchase_return(signed) + receive
            - sale - sale_return(signed) - issue

Tally exports returns with NEGATIVE weights; the engine ADDs
purchase_return and SUBTRACTs sale_return, so the sign naturally flips
returns the right way (net gain for a sale_return, net loss for a
purchase_return).

Uses direct-DB inserts to isolate the stock engine from the parser.
Item names are prefixed 'QQTEST ' for easy cleanup, use 2025 dates
only (real data is 2026-01..03), and always sleeps 31s before reading
/api/inventory/current because that endpoint caches for 30s.
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get('BACKEND_URL', 'http://localhost:8001').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')
KG = 1000.0
ADMIN = {'username': 'admin', 'password': 'admin123'}


# -------------------- fixtures --------------------
@pytest.fixture(scope='module')
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope='module')
def auth_headers():
    r = requests.post(f'{BASE}/api/auth/login', json=ADMIN, timeout=15)
    assert r.status_code == 200, f'admin login failed: {r.status_code} {r.text}'
    return {'Authorization': f'Bearer {r.json()["access_token"]}'}


# -------------------- helpers --------------------
def _txn(item, ttype, date, net_kg, gr_kg=None, batch_id='QQTEST-BATCH'):
    return {
        'type': ttype, 'date': date, 'refno': 'T1', 'party_name': 'P',
        'item_name': item, 'stamp': 'STAMP 70', 'tag_no': '',
        'gr_wt': (gr_kg if gr_kg is not None else net_kg) * KG,
        'net_wt': net_kg * KG, 'fine': 0.0, 'labor': 0.0, 'labor_on': None,
        'dia_wt': 0.0, 'stn_wt': 0.0, 'tunch': '75', 'rate': 0.0,
        'total_pc': 1, 'total_amount': 0.0, 'batch_id': batch_id,
        'upload_date': '2026-07-17T00:00:00',
    }


def _cleanup(db, names):
    db.transactions.delete_many({'item_name': {'$in': names}})
    db.opening_stock.delete_many({'item_name': {'$in': names}})
    db.inventory_baselines.delete_many({'item_name': {'$in': names}})


def _get_item_stock(headers, name, wait_cache=True):
    if wait_cache:
        time.sleep(31)  # inventory endpoint caches for 30 seconds
    r = requests.get(f'{BASE}/api/inventory/current', headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    inv = r.json()
    for lst in (inv.get('inventory', []), inv.get('negative_items', [])):
        for it in lst:
            if it['item_name'] == name:
                return round(it['net_wt'] / KG, 3)
            for m in it.get('members', []):
                if m['item_name'] == name:
                    return round(m['net_wt'] / KG, 3)
    for stamp_items in inv.get('by_stamp', {}).values():
        for si in stamp_items:
            if si['item_name'] == name:
                return round(si['net_wt'] / KG, 3)
    return None


# -------------------- tests --------------------
class TestItemwiseStockFormula:
    """Direct-DB stock formula verification"""

    def test_formula_full_txn_mix(self, db, auth_headers):
        """opening 100 + purchase 30 + purchase_return(-5) + receive 10
           - sale 20 - sale_return(-3) - issue 7 == 111 kg"""
        item = 'QQTEST FORMULA'
        _cleanup(db, [item])
        db.opening_stock.insert_one({
            'item_name': item, 'stamp': 'STAMP 70', 'unit': '', 'pc': 1,
            'gr_wt': 100 * KG, 'net_wt': 100 * KG, 'fine': 0.0,
            'labor_wt': 0.0, 'labor_rs': 0.0, 'rate': 0.0, 'total': 0.0,
        })
        db.transactions.insert_many([
            _txn(item, 'purchase',        '2025-02-01',  30),
            _txn(item, 'purchase_return', '2025-02-02',  -5),
            _txn(item, 'sale',            '2025-02-03',  20),
            _txn(item, 'sale_return',     '2025-02-04',  -3),
            _txn(item, 'receive',         '2025-02-05',  10),
            _txn(item, 'issue',           '2025-02-06',   7),
        ])
        try:
            expected = 100 + 30 - 5 + 10 - 20 + 3 - 7  # 111
            net = _get_item_stock(auth_headers, item)
            assert net == expected, f'expected {expected}kg, got {net}kg'
        finally:
            _cleanup(db, [item])

    def test_old_vs_new_parser_equivalence(self, db, auth_headers):
        """Same file: OLD parser (continuation lines date='' + default type)
        vs NEW parser (inherited date+type) -> identical stock."""
        old, new = 'QQTEST OLDSTYLE', 'QQTEST NEWSTYLE'
        _cleanup(db, [old, new])
        db.transactions.insert_many([
            _txn(old, 'purchase',        '2025-02-01', 30),
            _txn(old, 'purchase',        '',           12),  # ghost continuation
            _txn(old, 'purchase_return', '2025-02-02', -5),
            _txn(old, 'sale',            '2025-02-03', 20),
            _txn(old, 'sale',            '',            6),  # ghost continuation
            _txn(old, 'sale_return',     '2025-02-04', -3),
            _txn(old, 'issue',           '2025-02-05',  7),
            _txn(old, 'receive',         '2025-02-06', 10),
        ])
        db.transactions.insert_many([
            _txn(new, 'purchase',        '2025-02-01', 30),
            _txn(new, 'purchase',        '2025-02-01', 12),  # inherited
            _txn(new, 'purchase_return', '2025-02-02', -5),
            _txn(new, 'sale',            '2025-02-03', 20),
            _txn(new, 'sale',            '2025-02-03',  6),  # inherited
            _txn(new, 'sale_return',     '2025-02-04', -3),
            _txn(new, 'issue',           '2025-02-05',  7),
            _txn(new, 'receive',         '2025-02-06', 10),
        ])
        try:
            expected = 30 + 12 - 5 + 10 - 20 - 6 + 3 - 7  # 17
            time.sleep(31)  # single cache-flush covers both reads
            old_net = _get_item_stock(auth_headers, old, wait_cache=False)
            new_net = _get_item_stock(auth_headers, new, wait_cache=False)
            assert old_net == expected, f'old={old_net}'
            assert new_net == expected, f'new={new_net}'
            assert old_net == new_net
        finally:
            _cleanup(db, [old, new])

    def test_baseline_skips_pre_and_no_date_rows(self, db, auth_headers):
        """Baseline 50kg on 2025-03-01. Sales before/no-date are skipped;
        only the 4kg post-baseline sale counts -> 46kg."""
        item = 'QQTEST BASELINE'
        _cleanup(db, [item])
        db.inventory_baselines.insert_one({
            'item_key': item.lower(), 'item_name': item, 'stamp': 'STAMP 70',
            'gr_wt': 50 * KG, 'net_wt': 50 * KG, 'baseline_date': '2025-03-01',
        })
        db.transactions.insert_many([
            _txn(item, 'sale', '2025-02-10', 5),  # before baseline -> skipped
            _txn(item, 'sale', '2025-03-10', 4),  # after -> counts
            _txn(item, 'sale', '',           2),  # no-date ghost -> skipped
        ])
        try:
            net = _get_item_stock(auth_headers, item)
            assert net == 46, f'expected 46kg, got {net}kg'
        finally:
            _cleanup(db, [item])


class TestRegressionEnvironment:
    """Cleanup + baseline totals + admin login still work"""

    def test_admin_login_and_baseline_txn_count(self, db, auth_headers):
        # ensure no QQTEST leftovers from earlier runs
        _cleanup(db, ['QQTEST FORMULA', 'QQTEST OLDSTYLE',
                      'QQTEST NEWSTYLE', 'QQTEST BASELINE', 'QQTEST E2E'])
        db.transactions.delete_many({'batch_id': 'QQTEST-BATCH'})

        r = requests.get(f'{BASE}/api/stats', headers=auth_headers, timeout=30)
        assert r.status_code == 200
        total = r.json().get('total_transactions')
        assert total == 11767, f'expected 11767 baseline txns, got {total}'
