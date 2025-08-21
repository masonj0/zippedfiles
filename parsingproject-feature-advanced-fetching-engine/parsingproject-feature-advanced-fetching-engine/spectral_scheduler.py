# spectral_scheduler.py
from __future__ import annotations
import asyncio, random
from typing import Callable, Awaitable, List, Dict

from config import SpectralScheduler as SPEC

async def run_bursts(task: Callable[[], Awaitable[None]]):
    if not SPEC.get("enabled"):
        await task()
        return
    period = SPEC.get("burst_period_sec", 900)
    concurrency = SPEC.get("burst_concurrency", 3)
    while True:
        # quick burst
        await asyncio.gather(*(task() for _ in range(concurrency)))
        await asyncio.sleep(period + random.uniform(0, 30))
