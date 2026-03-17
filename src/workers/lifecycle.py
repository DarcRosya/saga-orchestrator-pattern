from typing import Any

import httpx

from core.database import async_session_factory, engine
from core.logging import setup_logging


async def startup(ctx: dict[str, Any]) -> None:
    setup_logging()
    ctx["http_client"] = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,
    )

    ctx["session_factory"] = async_session_factory


async def shutdown(ctx: dict[str, Any]) -> None:
    if ctx["http_client"]:
        await ctx["http_client"].aclose()

    await engine.dispose()
