# RCA — 2026-10-06 Profit Analysis drop (~28 kg → 20.307 kg silver)

**App:** stock-tracker-722  **DB:** stock-tracker-722-test_database  **Mode:** READ-ONLY (no writes performed)

## Summary
The drop is explained by **production DATA that changed today (2026-10-10)**, not code. The repo was proven innocent and that holds: no deploy/build/manifest issue is involved. Two data changes landed between the "yesterday" (28 kg) and "today" (20.307 kg) observations.

## Confirmed data changes (evidence)

### 1. The entire 2026-10-06 sales dataset was wholesale-REPLACED today at 10:20
- All **1,683** live `transactions` rows dated `2026-10-06`, type `sale`, carry `batch_id = 22ab6df4-610b-4b12-8426-798d69182ad0`, `upload_date = 2026-10-10T10:20`.
- `replaced_records` holds the prior version as backup: `batch_id 22ab6df4` parts 0 & 1, `replaced_at = 2026-10-10T10:20:20`. The backed-up (previous) rows carry original `batch_id 602443e6` / `upload_date 2026-10-08T17:34` and span dates incl. 2026-10-03 and 2026-10-07 — i.e. this replacement overwrote the earlier multi-day upload that the "yesterday 28 kg" figure was computed from.
- **This is the direct change to the 2026-10-06 sale rows themselves.**

### 2. 350 new purchase / purchase_return rows added in the last 48h → fallback cost basis shifted
- `transactions` with type in {purchase, purchase_return} and `upload_date` ^2026-10-(08|09|10): **count = 350**.
- The fallback cost basis is computed from ALL purchase rows for items missing from `purchase_ledger`; adding 350 purchase rows raises the long-run purchase tunch for affected items, which **lowers** (sale_tunch − purchase_tunch) and therefore profit.
- Related: replacement batches `7d7731fd` and `602443e6` at 10:19–10:34 overwrote 2026-10-03 purchase/sale data (backups confirm date 2026-10-03, type purchase).

### 3. Minor: one new item_mapping today
- `item_mappings`: 1 doc created `2026-10-10T10:22:30` — `COIN MINA PCS RATE` → `COIN MINA 100-98T`. Re-routes that item's sales to a different leader's cost basis. Small, localized effect.

## Ruled OUT
- **purchase_ledger re-upload:** NOT re-uploaded. 395 docs; newest `_id` prefix `6979faac` = January 2026. Ledger cost basis unchanged.
- **master_items stamp exclusion:** 342 docs, **0** with missing/empty/`Unassigned` stamp. (master_items was rebuilt today ~16:00, all `_id` prefix `6aca…`, but with zero exclusions now, exclusions could only have decreased — which would RAISE profit, not lower it.) Not the cause of a drop.
- **The 6,909,255 g corrupted row (item '4937.0', batch 0c8ffa1e):** sits in `quarantined_transactions`, type `issue`, date `2026-10-10` (not 10-06), quarantined by admin2 at 16:47. `issue` rows do not affect profit. Confirmed not the cause. It is the only quarantined row.
- No purely-numeric item_name rows exist among 2026-10-06 transactions.

## Most likely driver
The 2026-10-06 profit fell primarily because the day's **sales rows were re-uploaded/replaced at 10:20 today** (batch 22ab6df4) AND the **fallback cost basis rose** from 350 purchase rows added in the last 48h. Both push 2026-10-06 profit down relative to yesterday's computed 28 kg.

## Limitation / what was not fully quantified
The provided DB tool cannot aggregate, and the backup rows live inside large nested `records[]` arrays that cannot be summed/filtered server-side. So exact Σ(net_wt) for old-vs-new 2026-10-06 sales was NOT numerically computed — the replacement and cost-basis shift are proven structurally, but the precise kg attribution per driver is inferred, not summed. To close this, compare old (replaced_records/22ab6df4) vs live (transactions, date 2026-10-06, batch 22ab6df4) sale-row count and Σ(net_wt), and recompute fallback tunch for the top-weight items among the 350 new purchases.

## Recommended fix path (NO production writes; do NOT redeploy)
- A redeploy will NOT fix this — cause is data, code is unchanged and the app is healthy.
- If yesterday's 28 kg was correct, restore/validate the 2026-10-06 sales (the backup in replaced_records/22ab6df4 is the prior version) and review whether the 350 new purchase rows (and the COIN MINA mapping) are legitimate, via the app's DB Manager / data-restore flow.
