import asyncio
import os

import aiofiles
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/logs", tags=["Log"])


async def streaming(run_id: str):
    file_path = f"logs/{run_id}.log"
    if not os.path.exists(file_path):
        return
    async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
        while True:
            line = await f.readline()
            if line:
                yield f"{line}\n"
            else:
                await asyncio.sleep(2.5)


@router.get("/{run_id}")
async def log_realtime(run_id: str):
    return StreamingResponse(streaming(run_id), media_type="text/event-stream")
