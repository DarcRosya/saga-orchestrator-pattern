from typing import Any

import httpx
import structlog

from core.settings import settings

logger = structlog.get_logger("saga.alerts")


async def send_critical_alert(order_id: str, reason: str, context: dict[str, Any]) -> None:
    if not settings.slack.WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured, skipping alert.")
        return

    payload = {
        "attachments": [
            {
                "color": "#FF0000",
                "title": f"🚨 CRITICAL SAGA FAILURE: Order {order_id}",
                "text": f"*{reason}*\n\n*Context:*\n```\n{context}\n```",
                "fallback": f"Saga Failure for Order {order_id}",
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.slack.WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logger.info("Slack alert sent successfully", order_id=order_id)
    except Exception as e:
        logger.error("Failed to send Slack alert", exc_info=e)
