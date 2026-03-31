from src.core.settings import settings
from workers.lifecycle import shutdown, startup
from workers.saga_tasks.billing import process_billing
from workers.saga_tasks.compensation import compensation
from workers.saga_tasks.inventory import process_inventory
from workers.saga_tasks.logistics import process_logistic


class SagaWorkerSettings:
    redis_settings = settings.redis.arq_settings
    queue_name = "saga:tasks"

    functions = [compensation, process_billing, process_inventory, process_logistic]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 15
    job_timeout = 60
