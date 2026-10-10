"""Dead Items v2 audit corrections — focused offline regression fixtures.

Runs the REAL server functions (_compute_dead_items / _dead_split /
_dead_summary / _dead_items_data) against an ISOLATED scratch Mongo database
(dead_items_v3_fixtures). No production/preview collections are touched.

Fixtures mirror the audit's exact failure reproductions:
  F1  purchase 0 kg Jan 1 then 10 kg Jan 20       -> anchor must be Jan 20
  F2  p1 / s2 / p5 on successive days             -> negative intermediate balance flagged
  F3  ten-day-old unsold item                     -> provisional, NOT in confirmed totals
  F4  live purchase Jan 1 + historical sale Jan20 -> merged, NOT flagged ambiguous
  F4B same type+day both sources, distinct refnos -> NOT flagged
  F4C same type+day, blank historical identity    -> flagged ambiguous (review)
  F5  ALIAS->LEADER mapping with raw ' alias '    -> one consolidated row, 8 kg
  F6  sale 1 kg Jan 10 + sale 0 kg Jan 30         -> last sale Jan 10, 1 sale event
  F6B sale 0 kg before first purchase             -> no pre-purchase movement flag
  F7  49.6 g stock                                -> must NOT round up to 0.05 kg eligibility
  F7B no-anchor item with 0.010 kg                -> stays visible in review
  F8  blank-date row                              -> ignored, valid history kept
  F9  new item fully returned                     -> provisional, NOT confirmed
  F10 ordinary slow item                          -> months-to-clear formula unchanged
  F11 unmapped case/whitespace variants           -> merged into one row
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import server  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

AS_OF = '2026-02-28'
SCRATCH_DB = 'dead_items_v3_fixtures'


def _t(item, typ, day, g, refno=None, party=None):
    return {'id': str(uuid.uuid4()), 'item_name': item, 'type': typ,
            'date': f'{day} 10:00:00' if day else day, 'net_wt': g,
            'refno': refno, 'party_name': party}


MAIN = [
    _t('DIV3-ZERO-ANCHOR', 'purchase', '2026-01-01', 0),
    _t('DIV3-ZERO-ANCHOR', 'purchase', '2026-01-20', 10000),

    _t('DIV3-NEG-INTER', 'purchase', '2026-01-01', 1000),
    _t('DIV3-NEG-INTER', 'sale', '2026-01-02', 2000),
    _t('DIV3-NEG-INTER', 'purchase', '2026-01-03', 5000),

    _t('DIV3-NEW-UNSOLD', 'purchase', '2026-02-19', 10000),

    _t('DIV3-CROSS-SRC', 'purchase', '2026-01-01', 10000, refno='L1', party='PA'),

    _t('DIV3-DUP-DISTINCT', 'purchase', '2026-01-05', 5000, refno='R1', party='P1'),

    _t('DIV3-DUP-BLANK', 'purchase', '2026-01-05', 5000, refno='R9', party='P9'),

    _t(' div3 alias ', 'purchase', '2026-01-01', 10000),
    _t('DIV3-LEADER', 'sale', '2026-01-10', 2000),

    _t('DIV3-ZERO-SALE', 'purchase', '2026-01-01', 10000),
    _t('DIV3-ZERO-SALE', 'sale', '2026-01-10', 1000),
    _t('DIV3-ZERO-SALE', 'sale', '2026-01-30', 0),

    _t('DIV3-ZERO-PRE', 'sale', '2026-01-01', 0),
    _t('DIV3-ZERO-PRE', 'purchase', '2026-01-05', 10000),

    _t('DIV3-ROUND', 'purchase', '2026-01-01', 1000),
    _t('DIV3-ROUND', 'sale', '2026-01-10', 950.4),

    _t('DIV3-REVIEW-TINY', 'sale_return', '2026-01-01', 10),

    _t('DIV3-BAD-DATE', 'purchase', '', 500),

    _t('DIV3-RETURNED-NEW', 'purchase', '2026-02-19', 5000),
    _t('DIV3-RETURNED-NEW', 'sale', '2026-02-20', 1000),
    _t('DIV3-RETURNED-NEW', 'sale_return', '2026-02-21', 1000),

    _t('DIV3-NORMAL-DEAD', 'purchase', '2025-10-01', 30000),
    _t('DIV3-NORMAL-DEAD', 'sale', '2025-11-10', 1500),
    _t('DIV3-NORMAL-DEAD', 'sale', '2026-01-15', 1500),

    _t('DiV3 Mixed Item', 'purchase', '2026-01-01', 5000),
    _t('DIV3  MIXED ITEM ', 'sale', '2026-01-15', 1000),

    # T1 baseline item: opening 10 kg + p5 - s4 + sr1 = 12 kg; pre-2024 row must be ignored
    _t('DIV4-BASE', 'purchase', '2023-06-01', 7000),
    _t('DIV4-BASE', 'purchase', '2024-02-01', 5000),
    _t('DIV4-BASE', 'sale', '2024-03-01', 4000),
    _t('DIV4-BASE', 'sale_return', '2024-04-01', 1000),
    # T1b negative consolidated baseline stays in review (not forced to zero)
    _t('DIV4-NEG-BASE', 'purchase', '2024-05-01', 1000),
    # T2 ten-day-old item: p10 s8 -> stock 2, avg monthly 24.352, score ~0.082, provisional
    _t('DIV4-TENDAY', 'purchase', '2026-02-19', 10000),
    _t('DIV4-TENDAY', 'sale', '2026-02-20', 8000),
    # T3 purchase duplicated across both collections (same line identity+weight), sale once
    _t('DIV4-DEDUP', 'purchase', '2026-01-05', 20000, refno='D1', party='PD'),
    _t('DIV4-DEDUP', 'sale', '2026-01-10', 5000),
    # T3b separate legitimate historical movement preserved
    _t('DIV4-HIST-KEEP', 'sale', '2026-01-20', 1000),
]

HIST = [
    _t('DIV3-CROSS-SRC', 'sale', '2026-01-20', 2000, refno='H1', party='PB'),
    _t('DIV3-DUP-DISTINCT', 'purchase', '2026-01-05', 7000, refno='R2', party='P2'),
    _t('DIV3-DUP-BLANK', 'purchase', '2026-01-05', 5000),
    _t('DIV4-DEDUP', 'purchase', '2026-01-05', 20000, refno='D1', party='PD'),
    _t('DIV4-HIST-KEEP', 'purchase', '2026-01-03', 3000, refno='K1', party='PK'),
]

MAPPINGS = [{'transaction_name': 'DIV3 ALIAS', 'master_name': 'DIV3-LEADER'}]

# SIGNED grams, whitespace variant exercises normalized baseline consolidation
TEST_BASELINE = [
    {'item_name': ' div4-base ', 'net_wt': 10000.0},
    {'item_name': 'DIV4-NEG-BASE', 'net_wt': -2000.0},
]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope='module')
def results():
    async def _run():
        client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        tdb = client[SCRATCH_DB]
        for c in ('transactions', 'historical_transactions', 'item_mappings',
                  'item_groups', 'master_items', 'dead_item_removals'):
            await tdb[c].delete_many({})
        await tdb.transactions.insert_many([dict(d) for d in MAIN])
        await tdb.historical_transactions.insert_many([dict(d) for d in HIST])
        await tdb.item_mappings.insert_many([dict(m) for m in MAPPINGS])
        orig = server.db
        orig_bl = server._load_dead_baseline
        server.db = tdb
        server._load_dead_baseline = lambda: TEST_BASELINE
        try:
            server._dead_cache.invalidate()
            data = await server._compute_dead_items(AS_OF)
            items, review, removed = server._dead_split(data, {})
            summary = server._dead_summary(items, review)
            server._dead_cache.invalidate()
            ddata, _di, _dr, _drm, coverage = await server._dead_items_data(None)
        finally:
            server.db = orig
            server._load_dead_baseline = orig_bl
            server._dead_cache.invalidate()
        client.close()
        return {'data': data, 'items': items, 'review': review,
                'summary': summary, 'default_as_of': ddata['as_of'],
                'coverage': coverage}
    return run(_run())


def _row(rows, name):
    key = server._dead_norm(name)
    for r in rows:
        if server._dead_norm(r['item_name']) == key:
            return r
    return None


def _all(results):
    return results['items'] + results['review']


def test_f1_zero_weight_purchase_does_not_anchor(results):
    r = _row(_all(results), 'DIV3-ZERO-ANCHOR')
    assert r is not None
    assert r['first_purchase'] == '2026-01-20'
    assert r['observed_days'] == 40
    assert r['review_reasons'] == []


def test_f2_negative_intermediate_balance_flagged(results):
    r = _row(results['review'], 'DIV3-NEG-INTER')
    assert r is not None, 'p1/s2/p5 item must land in history review'
    assert 'negative_intermediate_stock' in r['review_reasons']
    assert abs(r['stock_net_kg'] - 4.0) < 1e-9
    assert _row(results['items'], 'DIV3-NEG-INTER') is None


def test_f3_new_unsold_is_provisional_not_confirmed(results):
    r = _row(results['items'], 'DIV3-NEW-UNSOLD')
    assert r is not None
    assert r['provisional'] is True and r['status'] == 'never_sold'
    assert r['observed_days'] == 10


def test_f4_cross_source_distinct_events_not_ambiguous(results):
    r = _row(results['items'], 'DIV3-CROSS-SRC')
    assert r is not None, 'must NOT be in review (distinct type/day events)'
    assert r['review_reasons'] == []
    assert abs(r['stock_net_kg'] - 8.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 2.0) < 1e-9
    assert r['status'] == 'ok'


def test_f4b_same_day_distinct_identities_not_flagged(results):
    r = _row(results['items'], 'DIV3-DUP-DISTINCT')
    assert r is not None
    assert r['review_reasons'] == []
    assert abs(r['stock_net_kg'] - 12.0) < 1e-9


def test_f4c_same_day_blank_identity_flagged(results):
    r = _row(results['review'], 'DIV3-DUP-BLANK')
    assert r is not None
    assert 'ambiguous_source_overlap' in r['review_reasons']


def test_f5_alias_case_whitespace_merges(results):
    r = _row(results['items'], 'DIV3-LEADER')
    assert r is not None
    assert abs(r['stock_net_kg'] - 8.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 2.0) < 1e-9
    assert _row(_all(results), 'DIV3 ALIAS') is None, 'alias must not be a separate row'
    assert r['review_reasons'] == []


def test_f6_zero_weight_sale_not_an_event(results):
    r = _row(results['items'], 'DIV3-ZERO-SALE')
    assert r is not None
    assert r['last_sale_date'] == '2026-01-10'
    assert r['status'] == 'ok'
    assert abs(r['total_net_sales_kg'] - 1.0) < 1e-9


def test_f6b_zero_sale_before_purchase_no_flag(results):
    r = _row(results['items'], 'DIV3-ZERO-PRE')
    assert r is not None
    assert r['first_purchase'] == '2026-01-05'
    assert r['review_reasons'] == []


def test_f7_unrounded_near_zero_not_eligible(results):
    assert _row(results['items'], 'DIV3-ROUND') is None, '0.0496 kg must not qualify for 0.05 cutoff'
    assert _row(results['review'], 'DIV3-ROUND') is None


def test_f7b_tiny_review_row_stays_visible(results):
    r = _row(results['review'], 'DIV3-REVIEW-TINY')
    assert r is not None, '0.010 kg no-anchor row must stay in review'
    assert 'no_purchase_anchor' in r['review_reasons']


def test_f8_blank_date_ignored_history_kept(results):
    assert results['data']['history_start'] == '2023-06-01'
    assert _row(_all(results), 'DIV3-BAD-DATE') is None


def test_f9_fully_returned_new_item_provisional(results):
    r = _row(results['items'], 'DIV3-RETURNED-NEW')
    assert r is not None
    assert r['status'] == 'no_positive_net_sales' and r['provisional'] is True


def test_f10_months_to_clear_formula_unchanged(results):
    r = _row(results['items'], 'DIV3-NORMAL-DEAD')
    assert r is not None
    days = (datetime(2026, 2, 28) - datetime(2025, 10, 1)).days + 1
    months = days / 30.44
    expected = 27000.0 / (3000.0 / months)
    assert r['observed_days'] == days
    assert abs(r['months_to_clear'] - expected) < 1e-9
    assert r['provisional'] is False and r['status'] == 'ok'


def test_f11_unmapped_case_variants_merge(results):
    r = _row(results['items'], 'DIV3 MIXED ITEM')
    assert r is not None
    assert abs(r['stock_net_kg'] - 4.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 1.0) < 1e-9


def test_summary_partitions_provisional_first(results):
    s = results['summary']
    # provisional: NEW-UNSOLD + RETURNED-NEW (TENDAY scores 0.082 < 3 -> healthy)
    assert s['provisional_dead'] == 2
    # no_net (non-provisional never-sold): ZERO-ANCHOR, DUP-DISTINCT, ZERO-PRE
    assert s['no_net_sales'] == 3
    # confirmed (score >= 3): CROSS-SRC, LEADER, ZERO-SALE, NORMAL-DEAD, MIXED,
    # DIV4-BASE, DIV4-DEDUP, DIV4-HIST-KEEP
    assert s['confirmed_dead'] == 8
    assert s['dead_total'] == 11, 'provisional items must not inflate dead_total'
    # review: NEG-INTER, DUP-BLANK, REVIEW-TINY, DIV4-NEG-BASE
    assert s['needs_review'] == 4


def test_default_as_of_uses_coverage_cutoff(results):
    # Last valid transaction in scratch data is 2026-02-21 (F9 sale_return)
    assert results['default_as_of'] == '2026-02-21'
    cov = results['coverage']
    assert cov['cutoff'] == '2026-02-21'
    assert cov['verified'] is False
    assert cov['source'] == 'last_transaction_fallback'
    assert cov['explicit_as_of'] is False


# --- Codex round-2 fixtures: baseline opening + source reconciliation ---

def test_t1_baseline_opening_and_window(results):
    r = _row(results['items'], 'DIV4-BASE')
    assert r is not None
    # opening 10 + p5 - s4 + sr1 = 12; pre-2024 purchase (7 kg) must NOT be counted
    assert abs(r['stock_net_kg'] - 12.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 3.0) < 1e-9
    assert abs(r['opening_kg'] - 10.0) < 1e-9
    assert r['window_start'] == '2024-01-01'
    assert r['window_basis'] == 'baseline_2023'
    days = (datetime(2026, 2, 28) - datetime(2024, 1, 1)).days + 1
    assert r['observed_days'] == days
    assert r['review_reasons'] == []
    assert abs(r['movements']['purchases_kg'] - 5.0) < 1e-9
    assert abs(r['movements']['sales_kg'] - 4.0) < 1e-9
    assert abs(r['movements']['sale_returns_kg'] - 1.0) < 1e-9


def test_t1b_negative_baseline_stays_in_review(results):
    r = _row(results['review'], 'DIV4-NEG-BASE')
    assert r is not None, 'negative consolidated baseline must be Needs History Review'
    assert 'negative_baseline' in r['review_reasons']
    assert r['months_to_clear'] is None, 'review rows expose no usable score'
    assert abs(r['opening_kg'] - (-2.0)) < 1e-9
    assert abs(r['stock_net_kg'] - (-1.0)) < 1e-9


def test_t2_ten_day_item_provisional_with_score(results):
    r = _row(results['items'], 'DIV4-TENDAY')
    assert r is not None
    assert abs(r['stock_net_kg'] - 2.0) < 1e-9
    assert r['observed_days'] == 10 and r['provisional'] is True
    assert abs(r['avg_monthly_sale_kg'] - 24.352) < 0.001
    assert abs(r['months_to_clear'] - 0.082) < 0.001


def test_t3_confirmed_duplicate_counted_once(results):
    r = _row(results['items'], 'DIV4-DEDUP')
    assert r is not None, 'confirmed duplicate must be reconciled, not flagged to review'
    # purchase 20 duplicated across both collections -> once; sale 5 once
    assert abs(r['stock_net_kg'] - 15.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 5.0) < 1e-9
    assert r['review_reasons'] == []


def test_t3b_legitimate_historical_movement_preserved(results):
    r = _row(results['items'], 'DIV4-HIST-KEEP')
    assert r is not None
    assert abs(r['stock_net_kg'] - 2.0) < 1e-9
    assert abs(r['total_net_sales_kg'] - 1.0) < 1e-9
    assert r['first_purchase'] == '2026-01-03'
    assert r['review_reasons'] == []


def test_review_rows_have_no_usable_score(results):
    for r in results['review']:
        assert r['months_to_clear'] is None, f"{r['item_name']} review row leaked a score"
