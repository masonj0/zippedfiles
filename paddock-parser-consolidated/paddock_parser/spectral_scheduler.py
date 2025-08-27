# spectral_scheduler.py
from __future__ import annotations
import asyncio
import random
from typing import Callable, Awaitable

from .config_manager import config_manager


async def run_bursts(task: Callable[[], Awaitable[None]]):
    config = config_manager.get_config()
    scheduler_config = config.get("SPECTRAL_SCHEDULER", {})

    if not scheduler_config.get("enabled"):
        await task()
        return

    period = scheduler_config.get("burst_period_sec", 900)
    concurrency = scheduler_config.get("burst_concurrency", 3)

    while True:
        # quick burst
        await asyncio.gather(*(task() for _ in range(concurrency)))
        await asyncio.sleep(period + random.uniform(0, 30))
