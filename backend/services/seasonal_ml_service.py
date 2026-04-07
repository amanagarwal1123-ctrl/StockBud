"""Deterministic ML-based Seasonal Analysis Service.

Implements segmented demand forecasting, PMS (Profit-Margin Score) ranking,
procurement planning, dead-stock detection, and seasonality extraction.

Non-negotiable: existing profit logic is READ-ONLY — silver MCX is demand-side only."""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Item family extraction
# ---------------------------------------------------------------------------
_FAMILY_PATTERNS = [
    (r"\bRING\b", "RING"), (r"\bCHAIN\b", "CHAIN"), (r"\bPAYAL\b", "PAYAL"),
    (r"\bBICHHIYA\b", "BICHHIYA"), (r"\bCOIN\b", "COIN"), (r"\bKADA\b", "KADA"),
    (r"\bBARTAN\b", "BARTAN"), (r"\bMURTI\b", "MURTI"), (r"\bPUJA\b", "PUJA"),
    (r"\bPENDANT\b", "PENDANT"), (r"\bBANGLE\b", "BANGLE"), (r"\bBRACELET\b", "BRACELET"),
    (r"\bNECKLACE\b", "NECKLACE"), (r"\bEARRING\b", "EARRING"), (r"\bATTHA\b", "ATTHA"),
    (r"\bGHUNGHRU\b", "GHUNGHRU"), (r"\bMANGALSUTRA\b", "MANGALSUTRA"),
    (r"\bTIKKA\b", "TIKKA"), (r"\bCHAPLA\b", "CHAPLA"),
]

def extract_item_family(item_name: str) -> str:
    upper = item_name.upper()
    for pat, family in _FAMILY_PATTERNS:
        if re.search(pat, upper):
            return family
    return "OTHER"

# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------
SEGMENT_DENSE = "dense_daily"
SEGMENT_MEDIUM = "medium_daily"
SEGMENT_WEEKLY = "weekly_sparse"
SEGMENT_COLD = "cold_start"

def segment_series(active_days: int, n_lines: int) -> str:
    if active_days >= 180 and n_lines >= 500:
        return SEGMENT_DENSE
    if active_days >= 60 and n_lines >= 100:
        return SEGMENT_MEDIUM
    if active_days >= 20:
        return SEGMENT_WEEKLY
    return SEGMENT_COLD

# ---------------------------------------------------------------------------
# Robust scaling
# ---------------------------------------------------------------------------
def robust_scale(arr: np.ndarray, clip_iqr_mult: float = 3.0) -> np.ndarray:
    """Median/IQR based scaling with clipping."""
    if len(arr) == 0:
        return arr
    med = np.nanmedian(arr)
    q1, q3 = np.nanpercentile(arr, [25, 75])
    iqr = q3 - q1
    if iqr < 1e-9:
        iqr = np.nanstd(arr)
    if iqr < 1e-9:
        return np.zeros_like(arr)
    scaled = (arr - med) / iqr
    scaled = np.clip(scaled, -clip_iqr_mult, clip_iqr_mult)
    return scaled

# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------
class SeasonalMLService:
    """Orchestrates the full ML seasonal analysis pipeline."""

    def __init__(self, db):
        self.db = db
        self._cache: Optional[dict] = None
        self._cache_ts: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 hour

    @property
    def _cache_valid(self) -> bool:
        return (
            self._cache is not None
            and self._cache_ts is not None
            and (datetime.now(timezone.utc) - self._cache_ts).total_seconds() < self._cache_ttl
        )

    async def get_results(self, force: bool = False) -> dict:
        if self._cache_valid and not force:
            return self._cache
        results = await self._compute()
        self._cache = results
        self._cache_ts = datetime.now(timezone.utc)
        return results

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------
    async def _compute(self) -> dict:
        logger.info("SeasonalML: starting full computation")

        # 1. Load data (current + historical sales AND purchases)
        sales_df, purchases_df, inventory, coverage_dates = await self._load_data()
        if sales_df.empty:
            return self._empty_results("No sales transactions found")

        # 2. Segment items (coverage-aware)
        segments = self._segment_items(sales_df)

        # 3. Build daily demand panel
        demand_panel = self._build_demand_panel(sales_df)

        # 4. Compute margins using the SHARED profit engine (group-aware)
        margins = await self._compute_margins_shared()

        # 5. Silver MCX features (optional)
        silver_features = await self._get_silver_features()

        # 6. Forecast demand (coverage-aware)
        forecasts = self._forecast_demand(demand_panel, segments, silver_features, coverage_dates)

        # 7. Compute PMS
        pms = self._compute_pms(forecasts, margins)

        # 8. Seasonality patterns
        seasonality = self._extract_seasonality(sales_df)

        # 9. Procurement planner
        procurement = self._plan_procurement(pms, forecasts, inventory, purchases_df)

        # 10. Supplier view
        supplier_view = self._build_supplier_view(purchases_df, pms, forecasts)

        # 11. Dead stock
        dead_stock = self._detect_dead_stock(demand_panel, pms, inventory)

        result = {
            "status": "ready",
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_items": len(segments),
            "segments_summary": self._segments_summary(segments),
            "pms_final": pms["final"],
            "pms_silver": pms["silver"],
            "pms_labour": pms["labour"],
            "demand_forecast": forecasts,
            "seasonality": seasonality,
            "procurement": procurement,
            "supplier_view": supplier_view,
            "dead_stock": dead_stock,
        }
        logger.info("SeasonalML: computation complete — %d items", len(segments))
        return result

    # ------------------------------------------------------------------
    # Data loading (current + historical sales AND purchases)
    # ------------------------------------------------------------------
    async def _load_data(self):
        proj = {"_id": 0, "date": 1, "item_name": 1, "stamp": 1, "gr_wt": 1,
                "net_wt": 1, "tunch": 1, "total_amount": 1, "labor": 1,
                "type": 1, "party_name": 1, "tag_no": 1}

        # Sales: current + historical
        sale_types = ["sale", "sale_return"]
        sales_cur = await self.db.transactions.find(
            {"type": {"$in": sale_types}}, proj).to_list(None)
        sales_hist = await self.db.historical_transactions.find(
            {"type": {"$in": sale_types}}, proj).to_list(None)
        all_sales = sales_cur + sales_hist
        sales_df = pd.DataFrame(all_sales) if all_sales else pd.DataFrame()
        if not sales_df.empty:
            sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")
            sales_df = sales_df.dropna(subset=["date"])
            for c in ["gr_wt", "net_wt", "tunch", "total_amount", "labor"]:
                if c in sales_df.columns:
                    sales_df[c] = pd.to_numeric(sales_df[c], errors="coerce").fillna(0)
            sales_df["item_family"] = sales_df["item_name"].apply(extract_item_family)

        # Purchases: current + historical
        purch_types = ["purchase", "purchase_return"]
        purch_cur = await self.db.transactions.find(
            {"type": {"$in": purch_types}}, proj).to_list(None)
        purch_hist = await self.db.historical_transactions.find(
            {"type": {"$in": purch_types}}, proj).to_list(None)
        all_purchases = purch_cur + purch_hist
        purchases_df = pd.DataFrame(all_purchases) if all_purchases else pd.DataFrame()
        if not purchases_df.empty:
            purchases_df["date"] = pd.to_datetime(purchases_df["date"], errors="coerce")
            for c in ["gr_wt", "net_wt", "tunch", "total_amount", "labor"]:
                if c in purchases_df.columns:
                    purchases_df[c] = pd.to_numeric(purchases_df[c], errors="coerce").fillna(0)

        # Current inventory
        from services.stock_service import get_current_inventory
        inv_resp = await get_current_inventory()
        inv = {}
        for item in inv_resp.get("inventory", []) + inv_resp.get("negative_items", []):
            inv[item["item_name"]] = item.get("net_wt", 0) / 1000  # kg

        # Build coverage dates: the set of dates where we actually have data
        # (distinguishes real zero-demand from upload gaps)
        coverage_dates = set()
        if not sales_df.empty:
            coverage_dates.update(sales_df["date"].dt.date)
        if not purchases_df.empty:
            coverage_dates.update(purchases_df["date"].dt.date)

        return sales_df, purchases_df, inv, coverage_dates

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------
    def _segment_items(self, sales_df: pd.DataFrame) -> dict:
        segs = {}
        for (item, stamp), grp in sales_df.groupby(["item_name", "stamp"]):
            active_days = grp["date"].dt.date.nunique()
            n_lines = len(grp)
            seg = segment_series(active_days, n_lines)
            segs[(item, stamp)] = {
                "segment": seg,
                "active_days": active_days,
                "n_lines": n_lines,
                "item_family": grp["item_family"].iloc[0] if "item_family" in grp.columns else "OTHER",
            }
        return segs

    def _segments_summary(self, segments: dict) -> dict:
        counts = defaultdict(int)
        for v in segments.values():
            counts[v["segment"]] += 1
        return dict(counts)

    # ------------------------------------------------------------------
    # Daily demand panel
    # ------------------------------------------------------------------
    def _build_demand_panel(self, sales_df: pd.DataFrame) -> pd.DataFrame:
        if sales_df.empty:
            return pd.DataFrame()
        df = sales_df.copy()
        # sign: sale positive, sale_return negative
        df["signed_gr_wt"] = df.apply(
            lambda r: -abs(r["gr_wt"]) if r["type"] == "sale_return" else abs(r["gr_wt"]), axis=1
        )
        daily = (
            df.groupby(["item_name", "stamp", pd.Grouper(key="date", freq="D")])
            .agg(demand_gr_wt=("signed_gr_wt", "sum"), n_txns=("signed_gr_wt", "count"))
            .reset_index()
        )
        daily["demand_gr_wt"] = daily["demand_gr_wt"].clip(lower=0)
        daily["item_family"] = daily["item_name"].apply(extract_item_family)
        return daily

    # ------------------------------------------------------------------
    # Margin computation via SHARED profit engine (group-aware)
    # ------------------------------------------------------------------
    async def _compute_margins_shared(self) -> dict:
        """Compute per-item silver and labour margins using the same
        group-aware logic as /analytics/profit.  Returns dict keyed
        by BOTH leader name AND all member/mapped names so that PMS
        lookups work regardless of whether fc["item_name"] is the raw
        transaction name, the master name, or the group leader."""
        from services.profit_helpers import compute_item_margins
        from services.group_utils import build_group_maps

        # Load the same raw data the profit endpoint uses
        all_txns = await self.db.transactions.find(
            {}, {"_id": 0, "item_name": 1, "type": 1, "net_wt": 1,
                 "tunch": 1, "total_amount": 1, "labor": 1}
        ).to_list(None)
        ledger_items = await self.db.purchase_ledger.find({}, {"_id": 0}).to_list(None)
        groups = await self.db.item_groups.find({}, {"_id": 0}).to_list(1000)
        mappings = await self.db.item_mappings.find({}, {"_id": 0}).to_list(None)

        item_margins = compute_item_margins(all_txns, ledger_items, groups, mappings)

        # Build reverse lookups: raw/member name → leader
        mapping_dict, member_to_leader, group_members = build_group_maps(groups, mappings)

        # Convert to dict keyed by leader for PMS lookup
        margins = {}
        for m in item_margins:
            entry = {
                "silver_margin_per_gram": m["silver_margin_per_gram"],
                "labour_margin_per_gram": m["labour_margin_per_gram"],
                "total_sold_grams": m["net_wt_sold_kg"] * 1000,
                "purchase_tunch": m["avg_purchase_tunch"],
                "has_ledger": True,
            }
            leader = m["item_name"]
            margins[leader] = entry

            # Also register all group members under the same margin entry
            for member in group_members.get(leader, []):
                if member != leader:
                    margins[member] = entry

        # Register transaction-name → master-name aliases
        # so raw sales names resolve to their leader's margin
        for txn_name, master_name in mapping_dict.items():
            leader = member_to_leader.get(master_name, master_name)
            if leader in margins and txn_name not in margins:
                margins[txn_name] = margins[leader]
            elif master_name in margins and txn_name not in margins:
                margins[txn_name] = margins[master_name]

        return margins

    # ------------------------------------------------------------------
    # Silver features (non-blocking)
    # ------------------------------------------------------------------
    async def _get_silver_features(self) -> dict:
        try:
            from services.silver_price_service import fetch_silver_prices, compute_silver_features
            prices = await fetch_silver_prices()
            return compute_silver_features(prices)
        except Exception as e:
            logger.warning("Silver features unavailable: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Demand forecasting
    # ------------------------------------------------------------------
    def _forecast_demand(self, demand_panel: pd.DataFrame, segments: dict,
                         silver_features: dict, coverage_dates: set) -> list[dict]:
        if demand_panel.empty:
            return []

        today = pd.Timestamp.now().normalize()
        results = []

        all_keys = list(segments.keys())
        for key in all_keys:
            item, stamp = key
            seg_info = segments[key]
            seg = seg_info["segment"]
            subset = demand_panel[(demand_panel["item_name"] == item) & (demand_panel["stamp"] == stamp)].copy()
            if subset.empty:
                results.append(self._cold_start_forecast(item, stamp, seg_info, demand_panel))
                continue

            subset = subset.set_index("date").sort_index()

            # Coverage-aware reindex: only fill zeros on COVERED dates,
            # leave uncovered dates as NaN so they are excluded from training
            min_d, max_d = subset.index.min(), max(subset.index.max(), today)
            idx = pd.date_range(min_d, max_d, freq="D")
            series = subset["demand_gr_wt"].reindex(idx)
            # Mark covered dates as 0 (true zero demand), leave others NaN
            for d in idx:
                if d.date() in coverage_dates and pd.isna(series.loc[d]):
                    series.loc[d] = 0.0
            # Uncovered dates remain NaN → masked from features/targets

            # Compute coverage ratio for confidence adjustment
            covered_count = series.notna().sum()
            total_count = len(series)
            coverage_ratio = covered_count / max(total_count, 1)

            if seg == SEGMENT_COLD:
                results.append(self._cold_start_forecast(item, stamp, seg_info, demand_panel))
                continue

            # For feature engineering, fill NaN with 0 only in feature columns
            # (the model sees covered-zero as real zero; uncovered rows are dropped from training)
            feat_df = self._build_features(series, seg_info["item_family"], demand_panel, silver_features)
            if feat_df.empty or len(feat_df.dropna(subset=["demand"])) < 14:
                results.append(self._cold_start_forecast(item, stamp, seg_info, demand_panel))
                continue

            if seg == SEGMENT_WEEKLY:
                fc = self._forecast_weekly(feat_df, series, item, stamp, seg_info)
            else:
                fc = self._forecast_daily(feat_df, series, item, stamp, seg_info, seg)

            # Adjust confidence based on coverage
            if coverage_ratio < 0.3:
                fc["confidence"] = "very_low"
            elif coverage_ratio < 0.6 and fc["confidence"] == "high":
                fc["confidence"] = "medium"

            results.append(fc)

        return results

    def _build_features(self, series: pd.Series, family: str,
                        demand_panel: pd.DataFrame, silver_features: dict) -> pd.DataFrame:
        df = pd.DataFrame({"demand": series})
        # Calendar
        df["weekday"] = df.index.weekday
        df["week"] = df.index.isocalendar().week.astype(int)
        df["month"] = df.index.month
        df["quarter"] = df.index.quarter
        df["month_start"] = (df.index.day <= 5).astype(int)
        df["month_end"] = (df.index.day >= 25).astype(int)

        # Demand lags
        for lag in [1, 2, 3, 7, 14, 21, 28]:
            df[f"lag_{lag}"] = df["demand"].shift(lag)

        # Rolling stats
        for w in [7, 14, 28, 56]:
            df[f"roll_mean_{w}"] = df["demand"].shift(1).rolling(w, min_periods=1).mean()
            df[f"roll_sum_{w}"] = df["demand"].shift(1).rolling(w, min_periods=1).sum()

        # Non-zero sale days
        nz = (df["demand"] > 0).astype(float)
        df["nz_days_28"] = nz.shift(1).rolling(28, min_periods=1).sum()

        # Days since last sale
        last_sale = nz.shift(1).cumsum()
        df["days_since_sale"] = df.groupby(last_sale).cumcount()

        # Item family average demand (overall)
        family_mask = demand_panel["item_family"] == family
        if family_mask.any():
            fam_daily = demand_panel.loc[family_mask].groupby("date")["demand_gr_wt"].mean()
            df["family_avg"] = df.index.map(fam_daily).fillna(0)
        else:
            df["family_avg"] = 0

        # Silver features
        if silver_features:
            for col in ["silver_close", "silver_1d_return", "silver_7d_return",
                        "silver_30d_return", "silver_7d_vol", "silver_30d_vol"]:
                df[col] = df.index.map(
                    lambda d: (silver_features.get(d.strftime("%Y-%m-%d")) or {}).get(col)
                )
            df[list(silver_features.get(next(iter(silver_features), ""), {}).keys())] = (
                df[list(silver_features.get(next(iter(silver_features), ""), {}).keys())].ffill()
            )

        return df

    def _forecast_daily(self, feat_df: pd.DataFrame, series: pd.Series,
                        item: str, stamp: str, seg_info: dict, seg: str) -> dict:
        """Train LightGBM on daily data, predict 14 & 30 day forward demand."""
        df = feat_df.copy()

        # Create targets: forward rolling sum
        df["target_14"] = series.rolling(14).sum().shift(-14)
        df["target_30"] = series.rolling(30).sum().shift(-30)

        feature_cols = [c for c in df.columns if c not in
                        ["demand", "target_14", "target_30"]]

        # Drop rows with NaN targets (training set)
        train = df.dropna(subset=["target_14"]).copy()
        if len(train) < 10:
            return self._cold_start_forecast(item, stamp, seg_info, pd.DataFrame())

        X_train = train[feature_cols].fillna(0)
        # Predict on the latest row (today)
        X_latest = df[feature_cols].iloc[-1:].fillna(0)

        fc14, fc30, conf = 0, 0, "low"
        try:
            import lightgbm as lgb
            params = {"objective": "regression", "verbosity": -1, "n_estimators": 100,
                      "max_depth": 6, "learning_rate": 0.1, "subsample": 0.8,
                      "colsample_bytree": 0.8, "min_child_samples": 5}
            # 14-day model
            m14 = lgb.LGBMRegressor(**params)
            m14.fit(X_train, train["target_14"])
            fc14 = max(float(m14.predict(X_latest)[0]), 0)

            # 30-day model
            train30 = df.dropna(subset=["target_30"]).copy()
            if len(train30) >= 10:
                m30 = lgb.LGBMRegressor(**params)
                m30.fit(train30[feature_cols].fillna(0), train30["target_30"])
                fc30 = max(float(m30.predict(X_latest)[0]), 0)
            else:
                fc30 = fc14 * (30 / 14)

            conf = "high" if seg == SEGMENT_DENSE else "medium"
        except Exception as e:
            logger.warning("LightGBM failed for %s/%s: %s — using fallback", item, stamp, e)
            recent = series.tail(28).mean() if len(series) >= 28 else series.mean()
            fc14 = recent * 14
            fc30 = recent * 30
            conf = "low"

        # Shrink toward priors for medium segment
        if seg == SEGMENT_MEDIUM:
            fc14, fc30 = self._shrink_toward_prior(fc14, fc30, series, seg_info)
            conf = "medium"

        return {
            "item_name": item, "stamp": stamp,
            "segment": seg_info["segment"], "item_family": seg_info["item_family"],
            "forecast_14d": round(fc14, 1), "forecast_30d": round(fc30, 1),
            "confidence": conf,
            "active_days": seg_info["active_days"], "n_lines": seg_info["n_lines"],
        }

    def _forecast_weekly(self, feat_df: pd.DataFrame, series: pd.Series,
                         item: str, stamp: str, seg_info: dict) -> dict:
        """Weekly aggregation for sparse items. NaN (uncovered) dates excluded."""
        weekly = series.dropna().resample("W").sum()
        avg_weekly = weekly.tail(8).mean() if len(weekly) >= 8 else weekly.mean()
        fc14 = avg_weekly * 2
        fc30 = avg_weekly * (30 / 7)
        return {
            "item_name": item, "stamp": stamp,
            "segment": SEGMENT_WEEKLY, "item_family": seg_info["item_family"],
            "forecast_14d": round(max(fc14, 0), 1),
            "forecast_30d": round(max(fc30, 0), 1),
            "confidence": "low",
            "active_days": seg_info["active_days"], "n_lines": seg_info["n_lines"],
        }

    def _cold_start_forecast(self, item: str, stamp: str, seg_info: dict,
                             demand_panel: pd.DataFrame) -> dict:
        """Backoff priors for cold-start items."""
        fc14, fc30 = 0, 0
        family = seg_info.get("item_family", "OTHER")
        if not demand_panel.empty:
            fam_mask = demand_panel["item_family"] == family
            if fam_mask.any():
                fam_daily = demand_panel.loc[fam_mask, "demand_gr_wt"].mean()
                fc14 = fam_daily * 14
                fc30 = fam_daily * 30
            else:
                overall_daily = demand_panel["demand_gr_wt"].mean()
                fc14 = overall_daily * 14
                fc30 = overall_daily * 30
        return {
            "item_name": item, "stamp": stamp,
            "segment": SEGMENT_COLD, "item_family": family,
            "forecast_14d": round(max(fc14, 0), 1),
            "forecast_30d": round(max(fc30, 0), 1),
            "confidence": "very_low",
            "active_days": seg_info.get("active_days", 0),
            "n_lines": seg_info.get("n_lines", 0),
        }

    def _shrink_toward_prior(self, fc14, fc30, series, seg_info):
        """Shrink medium-segment forecast toward item-level prior."""
        prior_daily = series.tail(56).mean() if len(series) >= 56 else series.mean()
        prior_14 = prior_daily * 14
        prior_30 = prior_daily * 30
        w = 0.6  # weight on model, 0.4 on prior
        return w * fc14 + (1 - w) * prior_14, w * fc30 + (1 - w) * prior_30

    # ------------------------------------------------------------------
    # PMS computation
    # ------------------------------------------------------------------
    def _compute_pms(self, forecasts: list[dict], margins: dict) -> dict:
        if not forecasts:
            return {"final": [], "silver": [], "labour": []}

        # Collect margin arrays for robust scaling
        # Margins are keyed by item leader name (from shared profit engine)
        silver_arr, labour_arr = [], []
        for fc in forecasts:
            m = margins.get(fc["item_name"], {})
            silver_arr.append(m.get("silver_margin_per_gram", 0))
            labour_arr.append(m.get("labour_margin_per_gram", 0))

        silver_scores = robust_scale(np.array(silver_arr, dtype=float))
        labour_scores = robust_scale(np.array(labour_arr, dtype=float))

        final_list, silver_list, labour_list = [], [], []
        for i, fc in enumerate(forecasts):
            m = margins.get(fc["item_name"], {})
            s_score = float(silver_scores[i])
            l_score = float(labour_scores[i])
            vol_30 = fc["forecast_30d"]

            pms_silver = vol_30 * s_score
            pms_labour = vol_30 * l_score
            balanced = 0.5 * (s_score + l_score) + 0.5 * min(s_score, l_score)
            pms_final = vol_30 * balanced

            base = {
                "item_name": fc["item_name"], "stamp": fc["stamp"],
                "item_family": fc.get("item_family", "OTHER"),
                "segment": fc["segment"], "confidence": fc["confidence"],
                "forecast_14d": fc["forecast_14d"], "forecast_30d": fc["forecast_30d"],
                "silver_margin_per_gram": round(m.get("silver_margin_per_gram", 0), 4),
                "labour_margin_per_gram": round(m.get("labour_margin_per_gram", 0), 4),
                "silver_score": round(s_score, 3),
                "labour_score": round(l_score, 3),
                "has_ledger": m.get("has_ledger", False),
            }
            final_list.append({**base, "pms": round(pms_final, 2), "balanced_score": round(balanced, 3)})
            silver_list.append({**base, "pms": round(pms_silver, 2)})
            labour_list.append({**base, "pms": round(pms_labour, 2)})

        final_list.sort(key=lambda x: x["pms"], reverse=True)
        silver_list.sort(key=lambda x: x["pms"], reverse=True)
        labour_list.sort(key=lambda x: x["pms"], reverse=True)
        return {"final": final_list, "silver": silver_list, "labour": labour_list}

    # ------------------------------------------------------------------
    # Seasonality extraction
    # ------------------------------------------------------------------
    def _extract_seasonality(self, sales_df: pd.DataFrame) -> list[dict]:
        if sales_df.empty:
            return []
        df = sales_df.copy()
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        monthly = (
            df.groupby(["item_name", "stamp", "year", "month"])
            .agg(sold_gr_wt=("gr_wt", "sum"), n_txns=("gr_wt", "count"))
            .reset_index()
        )
        # Compute avg by month across years
        avg_month = (
            monthly.groupby(["item_name", "stamp", "month"])
            .agg(avg_demand=("sold_gr_wt", "mean"))
            .reset_index()
        )
        results = []
        for (item, stamp), grp in avg_month.groupby(["item_name", "stamp"]):
            profile = {}
            overall_avg = grp["avg_demand"].mean()
            for _, row in grp.iterrows():
                m = int(row["month"])
                profile[m] = {
                    "avg_demand": round(float(row["avg_demand"]), 1),
                    "index": round(float(row["avg_demand"]) / overall_avg, 2) if overall_avg > 0 else 0,
                }
            peak_months = [m for m, v in profile.items() if v["index"] > 1.2]
            results.append({
                "item_name": item, "stamp": stamp,
                "monthly_profile": profile,
                "peak_months": peak_months,
                "overall_avg_monthly": round(overall_avg, 1),
                "item_family": extract_item_family(item),
            })
        results.sort(key=lambda x: x["overall_avg_monthly"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Procurement planner
    # ------------------------------------------------------------------
    def _plan_procurement(self, pms: dict, forecasts: list[dict],
                          inventory: dict, purchases_df: pd.DataFrame) -> list[dict]:
        today = pd.Timestamp.now().normalize()
        # Purchase recency per item
        purchase_recency = {}
        if not purchases_df.empty and "date" in purchases_df.columns:
            for item, grp in purchases_df.groupby("item_name"):
                last_purchase = grp["date"].max()
                purchase_recency[item] = (today - last_purchase).days

        # Map forecasts by key
        fc_map = {(f["item_name"], f["stamp"]): f for f in forecasts}
        pms_map = {(p["item_name"], p["stamp"]): p for p in pms.get("final", [])}

        plans = []
        for key, p in pms_map.items():
            item, stamp = key
            fc = fc_map.get(key, {})
            current_stock = inventory.get(item, 0) * 1000  # grams
            fc_14 = fc.get("forecast_14d", 0)
            fc_30 = fc.get("forecast_30d", 0)
            pms_val = p.get("pms", 0)
            s_score = p.get("silver_score", 0)
            l_score = p.get("labour_score", 0)
            days_since_purchase = purchase_recency.get(item, 999)

            # Stock coverage days
            daily_demand = fc_30 / 30 if fc_30 > 0 else 0
            coverage_days = current_stock / daily_demand if daily_demand > 0 else 999

            # Determine reason code
            reason = self._get_reason_code(pms_val, s_score, l_score, coverage_days,
                                           daily_demand, fc_30)

            # Suggested quantity: enough for 30 days minus current stock
            deficit = max(fc_30 - current_stock, 0)

            plans.append({
                "item_name": item, "stamp": stamp,
                "item_family": p.get("item_family", "OTHER"),
                "pms_final": pms_val,
                "silver_score": s_score, "labour_score": l_score,
                "forecast_14d": fc_14, "forecast_30d": fc_30,
                "current_stock_g": round(current_stock, 1),
                "coverage_days": round(coverage_days, 0),
                "days_since_purchase": days_since_purchase,
                "suggested_qty_g": round(deficit, 1),
                "reason_code": reason,
                "confidence": fc.get("confidence", "low"),
                "action": "buy" if deficit > 0 and pms_val > 0 else "hold",
            })

        plans.sort(key=lambda x: x["pms_final"], reverse=True)
        return plans

    def _get_reason_code(self, pms, s_score, l_score, coverage_days, daily_demand, fc_30):
        if pms <= 0 or daily_demand <= 0:
            return "hold_procurement"
        if s_score > 0.3 and l_score > 0.3:
            return "high_pms_balanced_margin"
        if l_score > 0.5 and s_score < 0:
            return "high_labour_but_silver_weak"
        if s_score > 0.5 and l_score < 0:
            return "high_silver_but_labour_weak"
        if coverage_days < 7 and fc_30 > 0:
            return "seasonal_peak_prebuild"
        if daily_demand < 1 and pms < 0:
            return "slow_mover_low_pms"
        return "moderate_demand"

    # ------------------------------------------------------------------
    # Supplier view
    # ------------------------------------------------------------------
    def _build_supplier_view(self, purchases_df: pd.DataFrame,
                             pms: dict, forecasts: list[dict]) -> list[dict]:
        if purchases_df.empty:
            return []
        today = pd.Timestamp.now().normalize()
        pms_map = {(p["item_name"], p["stamp"]): p for p in pms.get("final", [])}

        supplier_data = defaultdict(lambda: {
            "items": set(), "total_volume_g": 0, "n_purchases": 0,
            "last_purchase": None, "stamps": set(),
        })
        for _, row in purchases_df.iterrows():
            supplier = row.get("party_name", "Unknown")
            item = row.get("item_name", "")
            stamp = row.get("stamp", "")
            supplier_data[supplier]["items"].add(item)
            supplier_data[supplier]["stamps"].add(stamp)
            supplier_data[supplier]["total_volume_g"] += abs(row.get("gr_wt", 0))
            supplier_data[supplier]["n_purchases"] += 1
            d = row.get("date")
            if d is not None:
                if supplier_data[supplier]["last_purchase"] is None or d > supplier_data[supplier]["last_purchase"]:
                    supplier_data[supplier]["last_purchase"] = d

        results = []
        for supplier, data in supplier_data.items():
            last_p = data["last_purchase"]
            days_since = (today - last_p).days if last_p is not None else 999
            # Average PMS of items this supplier provides
            item_pms_vals = [pms_map.get((item, s), {}).get("pms", 0)
                            for item in data["items"] for s in data["stamps"]
                            if (item, s) in pms_map]
            avg_pms = np.mean(item_pms_vals) if item_pms_vals else 0
            results.append({
                "supplier": supplier,
                "n_items": len(data["items"]),
                "n_purchases": data["n_purchases"],
                "total_volume_kg": round(data["total_volume_g"] / 1000, 3),
                "days_since_last_purchase": days_since,
                "avg_item_pms": round(float(avg_pms), 2),
                "items": sorted(list(data["items"]))[:20],
            })
        results.sort(key=lambda x: x["avg_item_pms"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Dead stock detection
    # ------------------------------------------------------------------
    def _detect_dead_stock(self, demand_panel: pd.DataFrame, pms: dict,
                           inventory: dict) -> list[dict]:
        today = pd.Timestamp.now().normalize()
        pms_map = {(p["item_name"], p["stamp"]): p for p in pms.get("final", [])}
        results = []

        if demand_panel.empty:
            return results

        for (item, stamp), grp in demand_panel.groupby(["item_name", "stamp"]):
            last_sale = grp["date"].max()
            days_since = (today - last_sale).days
            total_demand = grp["demand_gr_wt"].sum()
            active_days = grp["date"].dt.date.nunique()
            daily_velocity = total_demand / max(active_days, 1)
            current_stock_g = inventory.get(item, 0) * 1000
            p = pms_map.get((item, stamp), {})
            pms_val = p.get("pms", 0)

            is_dead = days_since > 60 and daily_velocity < 5
            is_slow = daily_velocity < 10 and pms_val < 0

            if is_dead or is_slow:
                results.append({
                    "item_name": item, "stamp": stamp,
                    "item_family": extract_item_family(item),
                    "days_since_last_sale": days_since,
                    "daily_velocity_g": round(daily_velocity, 2),
                    "pms_final": pms_val,
                    "current_stock_g": round(current_stock_g, 1),
                    "classification": "dead_stock" if is_dead else "slow_mover",
                    "recommendation": "do_not_restock" if is_dead else "reduce_procurement",
                })

        results.sort(key=lambda x: x["days_since_last_sale"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Empty result helper
    # ------------------------------------------------------------------
    def _empty_results(self, msg: str) -> dict:
        return {
            "status": "no_data", "message": msg, "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_items": 0, "segments_summary": {},
            "pms_final": [], "pms_silver": [], "pms_labour": [],
            "demand_forecast": [], "seasonality": [], "procurement": [],
            "supplier_view": [], "dead_stock": [],
        }
