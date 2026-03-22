import time

import structlog
import ulid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger("api.middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(ulid.ULID())

        # Bind request_id to the context for all subsequent logs in this request
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            response = await call_next(request)

            process_time = time.perf_counter() - start_time

            logger.info(
                "request_finished",
                status_code=response.status_code,
                duration=process_time,
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            process_time = time.perf_counter() - start_time
            logger.exception("request_failed", duration=process_time, error=str(exc))
            raise
