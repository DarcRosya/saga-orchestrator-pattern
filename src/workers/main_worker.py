from core.settings import settings
from workers.lifecycle import shutdown, startup
from workers.saga_tasks.billing import process_billing


class SagaWorkerSettings:
    redis_settings = settings.redis.arq_settings

    functions = [process_billing]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 15
