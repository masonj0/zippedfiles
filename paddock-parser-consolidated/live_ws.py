# live_ws.py
import asyncio
import json
import websockets
from typing import List, Dict, Any


async def ws_collect(
    uri: str, subscribe_msg: Dict[str, Any] | None = None, duration_sec: int = 30
) -> List[str]:
    msgs = []
    async with websockets.connect(uri, max_size=2**22) as ws:
        if subscribe_msg:
            await ws.send(json.dumps(subscribe_msg))
        end = asyncio.get_event_loop().time() + duration_sec
        while asyncio.get_event_loop().time() < end:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                msgs.append(msg)
            except asyncio.TimeoutError:
                break
    return msgs
