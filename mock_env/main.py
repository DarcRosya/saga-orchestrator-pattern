import asyncio
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, status
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

app = FastAPI(title="Advanced Mock External Services for Saga Orchestration")

Instrumentator().instrument(app).expose(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# In-memory database for state storage.
# Essential for Idempotency (e.g., when a worker retries a request after a 500 network error).
db: dict[str, dict[uuid.UUID, Any]] = {"billing": {}, "inventory": {}, "logistics": {}}


class ResponseModel(BaseModel):
    status: str
    message: str
    timestamp: str
    latency_ms: float
    idempotent_replay: bool = False


def get_realistic_latency() -> float:
    """
    Generates realistic network latency using a Log-Normal distribution.
    Most requests are fast, but occasional "long tail" latencies occur.
    """
    latency = random.lognormvariate(-1.5, 0.8)
    return min(latency, 8.0)  # Cap maximum latency at 8 seconds


async def process_service_call(
    service: str,
    order_id: uuid.UUID,
    action: str,
    success_rate: float,
    is_compensation: bool = False,
) -> dict[str, Any]:
    """Core logic to simulate the behavior of a real, unstable microservice."""

    start_time = time.perf_counter()

    # 1. State check and Idempotency
    service_db = db[service]
    state_record = service_db.get(order_id)

    # If this action was already performed (e.g., retry after client-side timeout)
    if state_record and state_record.get("last_action") == action:
        logger.info(f"[{service.upper()}] Idempotent replay for order {order_id} ({action})")
        return {
            "status": "success",
            "message": f"{action.capitalize()} already processed for order {order_id}",
            "idempotent_replay": True,
            "latency_ms": 5.0,  # Cached responses are typically very fast
        }

    # 2. Simulate response delay
    delay = get_realistic_latency()

    # 3. Simulate failures
    chance = random.random()
    if chance > success_rate:
        # Randomly select an error type typical for production environments
        error_types = [
            "timeout",
            "server_error",
            "bad_request",
            "service_unavailable",
            "rate_limit",
        ]
        weights = [0.3, 0.25, 0.1, 0.2, 0.15]
        error_type = random.choices(error_types, weights=weights)[0]

        if error_type == "timeout":
            # Real timeouts hang before dropping the connection
            await asyncio.sleep(min(delay + 4.0, 6.0))
            logger.error(f"[{service.upper()}] Timeout executing {action} for order {order_id}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Upstream Service Timeout"
            )

        elif error_type == "rate_limit":
            # 429 error occurs almost instantly
            await asyncio.sleep(0.05)
            logger.warning(
                f"[{service.upper()}] Rate Limited executing {action} for order {order_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate Limit Exceeded"
            )

        elif error_type == "server_error":
            await asyncio.sleep(delay)
            logger.error(
                f"[{service.upper()}] Internal Server Error executing {action} for order {order_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Service Error"
            )

        elif error_type == "service_unavailable":
            await asyncio.sleep(0.1)  # Fail-fast
            logger.error(
                f"[{service.upper()}] Service Unavailable executing {action} for order {order_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service Unavailable (Overloaded)",
            )

        else:
            await asyncio.sleep(delay)
            logger.warning(
                f"[{service.upper()}] Bad Request / Invalid State executing {action} for order {order_id}"  # noqa: E501
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Request Payload or Business Rule Failure",
            )

    # 4. Successful execution - record state
    await asyncio.sleep(delay)

    service_db[order_id] = {
        "status": "compensated" if is_compensation else "processed",
        "last_action": action,
        "updated_at": datetime.now(UTC).isoformat(),
    }

    end_time = time.perf_counter()
    latency_ms = round((end_time - start_time) * 1000, 2)

    logger.info(
        f"[{service.upper()}] Successfully completed {action} for order {order_id} in {latency_ms}ms"  # noqa: E501
    )

    return {
        "status": "success",
        "message": f"Successfully performed {action} on {service} for order {order_id}",
        "idempotent_replay": False,
        "latency_ms": latency_ms,
    }


def format_response(result: dict[str, Any]) -> ResponseModel:
    return ResponseModel(
        status=result["status"],
        message=result["message"],
        idempotent_replay=result.get("idempotent_replay", False),
        latency_ms=result.get("latency_ms", 0.0),
        timestamp=datetime.now(UTC).isoformat(),
    )


# --- BILLING ---
@app.post("/billing/{order_id}", response_model=ResponseModel, tags=["mock_env"])
async def process_billing(order_id: uuid.UUID):
    result = await process_service_call("billing", order_id, "charge", success_rate=0.88)
    return format_response(result)


@app.post("/billing/{order_id}/refund", response_model=ResponseModel, tags=["mock_env"])
async def refund_billing(order_id: uuid.UUID):
    result = await process_service_call(
        "billing", order_id, "refund", success_rate=0.98, is_compensation=True
    )
    return format_response(result)


# --- INVENTORY ---
@app.post("/inventory/{order_id}", response_model=ResponseModel, tags=["mock_env"])
async def reserve_inventory(order_id: uuid.UUID):
    result = await process_service_call("inventory", order_id, "reserve", success_rate=0.84)
    return format_response(result)


@app.post("/inventory/{order_id}/release", response_model=ResponseModel, tags=["mock_env"])
async def release_inventory(order_id: uuid.UUID):
    result = await process_service_call(
        "inventory", order_id, "release", success_rate=0.98, is_compensation=True
    )
    return format_response(result)


# --- LOGISTICS ---
@app.post("/logistics/{order_id}", response_model=ResponseModel, tags=["mock_env"])
async def arrange_logistics(order_id: uuid.UUID):
    # Logistics in a real-world environment is often the most unstable
    result = await process_service_call("logistics", order_id, "arrange", success_rate=0.79)
    return format_response(result)


@app.post("/logistics/{order_id}/cancel", response_model=ResponseModel, tags=["mock_env"])
async def cancel_logistics(order_id: uuid.UUID):
    result = await process_service_call(
        "logistics", order_id, "cancel", success_rate=0.95, is_compensation=True
    )
    return format_response(result)
