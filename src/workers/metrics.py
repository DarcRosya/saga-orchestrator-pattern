import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus

SAGA_EXECUTION_TOTAL = Counter(
    "saga_execution_total",
    "Total count of saga executions by final status.",
    ["status"],
)

SAGA_STATUS = SAGA_EXECUTION_TOTAL

SAGA_MANUAL_STUCK_CURRENT = Gauge(
    "saga_manual_intervention_required_current",
    "Current number of sagas in MANUAL_INTERVENTION_REQUIRED state",
)

SAGA_STEP_EXECUTION_TOTAL = Counter(
    "saga_step_execution_total",
    "Total count of saga step executions by step and status.",
    ["step", "status"],
)

SAGA_STEP_DURATION_SECONDS = Histogram(
    "saga_step_duration_seconds",
    "Saga step duration in seconds.",
    ["step"],
)


@contextmanager
def observe_step_duration(step: str) -> Iterator[None]:
    started_at = time.perf_counter()
    try:
        yield
    finally:
        SAGA_STEP_DURATION_SECONDS.labels(step=step).observe(time.perf_counter() - started_at)


def record_step_status(step: str, status: SagaStepStatus) -> None:
    SAGA_STEP_EXECUTION_TOTAL.labels(step=step, status=status.value.lower()).inc()


def record_final_status_transition(
    previous_status: OrderGlobalStatus,
    current_status: OrderGlobalStatus,
) -> None:
    if previous_status == current_status:
        return

    if current_status == OrderGlobalStatus.COMPLETED:
        SAGA_EXECUTION_TOTAL.labels(status="success").inc()
    elif current_status == OrderGlobalStatus.CANCELLED:
        SAGA_EXECUTION_TOTAL.labels(status="compensated").inc()
    elif current_status == OrderGlobalStatus.MANUAL_INTERVENTION_REQUIRED:
        SAGA_EXECUTION_TOTAL.labels(status="stuck").inc()
