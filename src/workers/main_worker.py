from core.settings import settings
from workers.lifecycle import shutdown, startup
from workers.saga_tasks.billing import process_billing
from workers.saga_tasks.inventory import process_inventory
from workers.saga_tasks.logistics import process_logistic


class SagaWorkerSettings:
    redis_settings = settings.redis.arq_settings

    functions = [process_billing, process_inventory, process_logistic]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 15
