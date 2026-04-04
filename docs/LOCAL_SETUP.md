# Local Development & Infrastructure Guide

This guide explains how to set up the project locally, manage environment variables, and understand the mock services.

## Environment Variables

Before starting the project, you need to configure your environment variables. Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

### Configuration (`src/core/settings.py`)

The application uses Pydantic Settings to validate environment variables. Key parameters include:
- **`DB__USER` / `DB__PASS` / `DB__NAME`**: Database credentials.
- **`REDIS__R_HOST` / `REDIS__R_PORT`**: Redis connection for caching and ARQ worker queues.
- **`AUTH__SECRET_KEY`**: JWT encryption key.
- **`DEBUG_MODE`**: Enables detailed logging and FastAPI debug features.

## Local Launch (Docker Compose)

The project includes a comprehensive `docker-compose.yml` to spin up the entire ecosystem, including the database, cache, workers, and mock microservices.

### Starting the Application

To build and start all containers:
```bash
docker-compose up -d --build
```

This will spin up:
1. `database` (PostgreSQL)
2. `redis` (Redis)
3. `migrator` (Runs Alembic migrations and exits)
4. `api` (FastAPI backend on port 8000)
5. `scheduler-worker` & `saga-worker` (ARQ background tasks)
6. `nginx` (Reverse proxy on port 80)
7. `mock-services` (Port 8080)
8. `redisinsight` (Redis GUI on port 5540)

*Note: During the FastAPI application startup (`api` service), an automated seeding process runs (`src/core/seed.py`), which populates the database with initial records (like `goods`), so you don't have to create them manually to start testing orders. It handles duplicates securely by skipping population if the table is not empty.*

### Admins Monitoring (RedisInsight)

RedisInsight is deployed with the main environment and allows an admin to visually inspect Redis databases. This is used for monitoring ARQ queues, troubleshooting stuck sagas, and managing background tasks.

1. Open your browser and navigate to `http://localhost:5540`
2. Follow the initialization steps and Add a Redis Database.
3. Configure the connection using the host `redis` and default port `6379`.

### Running Tests

A separate `docker-compose.test.yml` is provided for running integration and unit tests using an isolated `test-database` running entirely in `tmpfs` (RAM) for speed.

To up test dependencies:
```bash
docker-compose -f docker-compose.test.yml up -d
```

## Mock Environment (`mock_env`)

Since this is a simulated distributed transaction (Saga Orchestrator), actual external microservices (Billing, Inventory, Logistics) are not present. Instead, a lightweight mock service is included (`mock_env/Dockerfile`).

The `mock-services` container emulates these subdomains and provides endpoints like:
- `POST /billing/{order_id}`
- `POST /billing/{order_id}/refund` 
- `POST /inventory/{order_id}`
- `POST /inventory/{order_id}/release` 

Workers (`src/workers/saga_tasks/`) communicate with this container via HTTP to simulate realistic network boundaries and failures.