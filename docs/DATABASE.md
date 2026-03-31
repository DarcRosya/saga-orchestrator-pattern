# Database & Migrations

This document explains the schema of the application database and the migration lifecycle.

## Main Tables & Schema

The core domain relies on PostgreSQL as its primary data store. The database models are defined in `src/db/models/`.

### 1. `orders` (Source: `src/db/models/order.py`)
The central entity for the SAGA orchestration.
- **Primary Key**: `id` (UUID).
- **Foreign Keys**: `buyer_id` (Users), `good_id` (Goods).
- **Fields of note**:
  - `idempotency_key` (Unique String): Prevents duplicate orders.
  - `global_status` (Enum: PROCESSING, COMPLETED, CANCELLED, COMPENSATING, MANUAL_INTERVENTION_REQUIRED).
  - Component sync statuses: `billing_status`, `inventory_status`, `logistics_status` (Enum: PENDING, SUCCESS, FAILED, COMPENSATED, SKIPPED, CANCELLED).
- **Relationships**: 1-to-1 with `order_shipping_details`, 1-to-many with `saga_logs`.

### 2. `order_shipping_details` (Source: `src/db/models/order_shipping_detail.py`)
Stores PII (Personally Identifiable Information) and delivery context for the order.
- **Primary/Foreign Key**: `order_id` (UUID). This enforces a strict 1-to-1 relationship at the database level.
- **Fields**: `guest_email`, `guest_phone`, `region`, `city`, `delivery_service`, `postal_address`.

### 3. `saga_logs` (Source: `src/db/models/saga_log.py`)
Audit trail for transitions in the Saga workflow.
- **Primary Key**: `id` (UUID).
- **Foreign Key**: `order_id` -> `orders.id`.
- **Fields**: `action`, `status`, `error_details` (for capturing stack traces or external API errors). 

---

## Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    GOODS ||--o{ ORDERS : contains
    ORDERS ||--|| ORDER_SHIPPING_DETAILS : has
    ORDERS ||--o{ SAGA_LOGS : tracks_steps

    ORDERS {
        uuid id PK
        int buyer_id FK
        int good_id FK
        string idempotency_key
        string global_status
        string billing_status
        string inventory_status
        string logistics_status
    }

    ORDER_SHIPPING_DETAILS {
        uuid order_id PK "FK referencing ORDERS"
        string guest_email
        string guest_phone
        string region
        string delivery_service
    }

    SAGA_LOGS {
        uuid id PK
        uuid order_id FK
        string action
        string status
        text error_details
    }
```

## Migrations (Alembic)

Database schema evolution is managed by Alembic (`src/db/migrations/`). Revisions live in `src/db/migrations/versions/`.

When running in docker (via `docker-compose.yml`), a dedicated `migrator` service runs `poetry run alembic upgrade head` on startup before the API and Workers spin up. 

**Common Commands (run locally via poetry):**
- **Generate new migration**: `alembic revision --autogenerate -m "description"`
- **Apply migrations**: `alembic upgrade head`
- **Rollback 1 step**: `alembic downgrade -1`