"""Silver price service — fetches spot silver prices from free APIs.
Used only as exogenous demand-side features, NOT for profit calculation."""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_silver_cache: dict = {"prices": [], "fetched_at": None}
CACHE_TTL_HOURS = 6


async def fetch_silver_prices(days: int = 90) -> list[dict]:
    """Fetch recent silver spot prices. Returns list of {date, close} dicts.
    Non-blocking: returns empty list on failure so seasonal analysis still works."""
    global _silver_cache
    if (
        _silver_cache["fetched_at"]
        and (datetime.utcnow() - _silver_cache["fetched_at"]).total_seconds() < CACHE_TTL_HOURS * 3600
        and _silver_cache["prices"]
    ):
        return _silver_cache["prices"]

    prices = await _try_metals_live()
    if not prices:
        prices = await _try_goldapi()
    if not prices:
        logger.warning("All silver price APIs failed — continuing without silver MCX features")
        return []

    _silver_cache["prices"] = prices
    _silver_cache["fetched_at"] = datetime.utcnow()
    return prices


async def _try_metals_live() -> list[dict]:
    """metals.live — free, no key required."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.metals.live/v1/spot/silver")
            resp.raise_for_status()
            data = resp.json()
            # Returns list of [timestamp_ms, price_usd]
            prices = []
            for entry in data:
                if isinstance(entry, list) and len(entry) >= 2:
                    ts = entry[0] / 1000
                    dt = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                    prices.append({"date": dt, "close": float(entry[1])})
                elif isinstance(entry, dict):
                    prices.append({
                        "date": datetime.utcfromtimestamp(entry.get("timestamp", 0) / 1000).strftime("%Y-%m-%d"),
                        "close": float(entry.get("price", 0)),
                    })
            if prices:
                logger.info(f"metals.live: fetched {len(prices)} silver prices")
            return prices
    except Exception as e:
        logger.debug(f"metals.live failed: {e}")
        return []


async def _try_goldapi() -> list[dict]:
    """Fallback: try gold-api or similar free endpoints."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.metals.live/v1/spot")
            resp.raise_for_status()
            data = resp.json()
            for metal in data:
                if isinstance(metal, dict) and metal.get("metal", "").lower() == "silver":
                    return [{"date": datetime.utcnow().strftime("%Y-%m-%d"), "close": float(metal["price"])}]
            return []
    except Exception as e:
        logger.debug(f"goldapi fallback failed: {e}")
        return []


def compute_silver_features(prices: list[dict]) -> dict:
    """Compute silver MCX features from price history.
    Returns dict keyed by date with feature values."""
    if not prices:
        return {}

    import pandas as pd
    df = pd.DataFrame(prices)
    if df.empty or "close" not in df.columns:
        return {}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    df["close"] = df["close"].astype(float)

    df["silver_1d_return"] = df["close"].pct_change(1)
    df["silver_7d_return"] = df["close"].pct_change(7)
    df["silver_30d_return"] = df["close"].pct_change(30)
    df["silver_7d_vol"] = df["close"].pct_change().rolling(7).std()
    df["silver_30d_vol"] = df["close"].pct_change().rolling(30).std()
    df["silver_close"] = df["close"]

    features = {}
    for _, row in df.iterrows():
        d = row["date"].strftime("%Y-%m-%d")
        features[d] = {
            "silver_close": row.get("silver_close"),
            "silver_1d_return": row.get("silver_1d_return"),
            "silver_7d_return": row.get("silver_7d_return"),
            "silver_30d_return": row.get("silver_30d_return"),
            "silver_7d_vol": row.get("silver_7d_vol"),
            "silver_30d_vol": row.get("silver_30d_vol"),
        }
    return features
