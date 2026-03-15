from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.models.order import Order


class DuplicateOrderError(Exception):
    """Raised when an order with the same idempotency_key already exists."""

    def __init__(self, existing_order: Order) -> None:
        self.existing_order = existing_order
        super().__init__("Order with this idempotency key already exists.")
