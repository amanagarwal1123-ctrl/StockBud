"""Seasonal Analytics API routes.

Exposes endpoints for the deterministic ML-based Seasonal Analysis module:
PMS Final/Silver/Labour, Demand Forecast, Seasonality, Procurement Planner,
Supplier View, and Dead Stock."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from database import db
from auth import get_current_user
from services.seasonal_ml_service import SeasonalMLService

router = APIRouter(prefix="/seasonal", tags=["seasonal-analytics"])

_service: Optional[SeasonalMLService] = None


def _get_service() -> SeasonalMLService:
    global _service
    if _service is None:
        _service = SeasonalMLService(db)
    return _service


@router.get("/status")
async def seasonal_status(current_user: dict = Depends(get_current_user)):
    """Check if seasonal analysis data is cached and ready."""
    svc = _get_service()
    return {
        "cached": svc._cache_valid,
        "computed_at": svc._cache_ts.isoformat() if svc._cache_ts else None,
    }


@router.post("/compute")
async def seasonal_compute(
    force: bool = Query(False, description="Force recompute even if cache is fresh"),
    current_user: dict = Depends(get_current_user),
):
    """Trigger full seasonal ML computation. Results are cached for 1 hour."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results(force=force)
    return {
        "status": results.get("status"),
        "computed_at": results.get("computed_at"),
        "total_items": results.get("total_items"),
        "segments_summary": results.get("segments_summary"),
    }


@router.get("/pms-final")
async def get_pms_final(current_user: dict = Depends(get_current_user)):
    """PMS Final rankings — items ranked by balanced PMS score."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("pms_final", []), "computed_at": results.get("computed_at")}


@router.get("/pms-silver")
async def get_pms_silver(current_user: dict = Depends(get_current_user)):
    """PMS Silver rankings — items ranked by silver-margin PMS."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("pms_silver", []), "computed_at": results.get("computed_at")}


@router.get("/pms-labour")
async def get_pms_labour(current_user: dict = Depends(get_current_user)):
    """PMS Labour rankings — items ranked by labour-margin PMS."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("pms_labour", []), "computed_at": results.get("computed_at")}


@router.get("/demand-forecast")
async def get_demand_forecast(current_user: dict = Depends(get_current_user)):
    """14-day and 30-day demand forecasts per item+stamp."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("demand_forecast", []), "computed_at": results.get("computed_at")}


@router.get("/seasonality")
async def get_seasonality(current_user: dict = Depends(get_current_user)):
    """Month-over-month and year-over-year seasonal patterns."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("seasonality", []), "computed_at": results.get("computed_at")}


@router.get("/procurement")
async def get_procurement(current_user: dict = Depends(get_current_user)):
    """Bi-weekly & monthly procurement recommendations."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("procurement", []), "computed_at": results.get("computed_at")}


@router.get("/supplier-view")
async def get_supplier_view(current_user: dict = Depends(get_current_user)):
    """Supplier-wise recommendations by item and stamp."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("supplier_view", []), "computed_at": results.get("computed_at")}


@router.get("/dead-stock")
async def get_dead_stock(current_user: dict = Depends(get_current_user)):
    """Dead stock / slow mover detection."""
    if current_user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    results = await svc.get_results()
    return {"items": results.get("dead_stock", []), "computed_at": results.get("computed_at")}
