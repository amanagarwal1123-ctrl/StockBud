"""Iteration 52: heavy-analytics request queue (semaphore) + sales-report cache."""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))
import server  # noqa: E402


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_gate_allows_two_concurrent():
    async def _t():
        gate = asyncio.Semaphore(2)
        orig = server._heavy_gate
        server._heavy_gate = gate
        try:
            await server._acquire_heavy()
            await server._acquire_heavy()
            assert gate.locked()
            gate.release()
            gate.release()
        finally:
            server._heavy_gate = orig
    run(_t())


def test_gate_returns_503_when_saturated():
    async def _t():
        orig_gate, orig_wait = server._heavy_gate, server._HEAVY_WAIT_SECONDS
        gate = asyncio.Semaphore(2)
        server._heavy_gate, server._HEAVY_WAIT_SECONDS = gate, 0.2
        try:
            await gate.acquire()
            await gate.acquire()
            with pytest.raises(HTTPException) as exc:
                await server._acquire_heavy()
            assert exc.value.status_code == 503
            assert "busy" in exc.value.detail.lower()
        finally:
            server._heavy_gate, server._HEAVY_WAIT_SECONDS = orig_gate, orig_wait
    run(_t())


def test_queued_request_proceeds_when_slot_frees():
    async def _t():
        orig_gate, orig_wait = server._heavy_gate, server._HEAVY_WAIT_SECONDS
        gate = asyncio.Semaphore(1)
        server._heavy_gate, server._HEAVY_WAIT_SECONDS = gate, 5
        try:
            await gate.acquire()

            async def waiter():
                await server._acquire_heavy()
                return "ran"

            task = asyncio.ensure_future(waiter())
            await asyncio.sleep(0.05)
            assert not task.done()  # queued, not failed
            gate.release()
            assert await asyncio.wait_for(task, timeout=2) == "ran"
        finally:
            server._heavy_gate, server._HEAVY_WAIT_SECONDS = orig_gate, orig_wait
    run(_t())


def test_heavy_queue_slot_dependency_releases():
    async def _t():
        orig_gate = server._heavy_gate
        gate = asyncio.Semaphore(1)
        server._heavy_gate = gate
        try:
            agen = server.heavy_queue_slot()
            await agen.__anext__()
            assert gate.locked()
            with pytest.raises(StopAsyncIteration):
                await agen.__anext__()
            assert not gate.locked()
        finally:
            server._heavy_gate = orig_gate
    run(_t())


def test_inv_cache_invalidation_clears_report_cache():
    server._report_cache.set("sales-report:2025-01-01:2025-12-31", {"x": 1})
    assert server._report_cache.get("sales-report:2025-01-01:2025-12-31") is not None
    server._inv_cache.invalidate()
    assert server._report_cache.get("sales-report:2025-01-01:2025-12-31") is None
