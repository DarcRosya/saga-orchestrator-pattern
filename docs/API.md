# 1. API Documentation

## [POST] /orders/

**Description:** Creates one or multiple orders. When creating an order, a Saga Orchestrator is initialized in the background to handle the distributed transaction. Supports bulk creation by passing an array of order objects.

**Authorization:** Can be called with or without authentication (`OptionalCurrentUser`).

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:**
JSON object or an array of objects for bulk order creation with the following structure:
```json
{
  "good_id": 1, // required, integer
  "idempotency_key": "uuid", // required, uuid
  "payment_type": "string", // required, enum (e.g., PAYMENT_METHOD)
  "quantity": 1, // required, integer (minimum 1)
  "order_details": { // required, shipping details object
    "guest_email": "string", // required, email (max 255 chars)
    "guest_phone": "string", // required, string (max 20 chars)
    "region": "string", // required, string (max 100 chars)
    "city": "string", // required, string (max 100 chars)
    "delivery_service": "string", // required, string (max 50 chars)
    "postal_address": "string" // required, string
  }
}
```
*Note: You can pass a `[ {...}, {...} ]` array of the above structure to create multiple orders simultaneously.*

**Responses:**

*   **201 Created**: Successful creation of the order(s).
    ```json
    {
      "id": "uuid",
      "global_status": "string (enum)"
    }
    ```
    *(Or an array of the above object if multiple were passed).*
*   **200 OK**: Returned in case of a duplicate via idempotent creation (`DuplicateOrderError`) returning the existing order.
*   **422 Unprocessable Entity**: Validation error for request body structure.

---

## [POST] /auth/register

**Description:** Register a new user in the system.

**Authorization:** None.

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:**
```json
{
  "username": "string", // required, string (3 to 20 chars)
  "password": "string", // required, string (min 8 chars)
  "email": "string" // optional, string
}
```

**Responses:**

*   **201 Created**: Successfully registered user and access tokens generated.
    ```json
    {
      "access_token": "string",
      "refresh_token": "string",
      "token_type": "bearer"
    }
    ```
*   **422 Unprocessable Entity**: Validation error.

---

## [POST] /auth/login

**Description:** Authenticate a user and receive JWT tokens.

**Authorization:** None.

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:**
```json
{
  "username": "string", // required, string
  "password": "string" // required, string
}
```

**Responses:**

*   **200 OK**: Successful login.
    ```json
    {
      "access_token": "string",
      "refresh_token": "string",
      "token_type": "bearer"
    }
    ```
*   **401 Unauthorized**: Invalid credentials.
*   **422 Unprocessable Entity**: Validation error.

---

## [POST] /auth/refresh

**Description:** Get an access token using a refresh token.

**Authorization:** None.

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:**
```json
{
  "refresh_token": "string" // required, string
}
```

**Responses:**

*   **200 OK**: New tokens generated successfully.
    ```json
    {
      "access_token": "string",
      "refresh_token": "string",
      "token_type": "bearer"
    }
    ```
*   **401 Unauthorized**: Invalid or expired refresh token.

---

## [POST] /auth/logout

**Description:** Logout user by invalidating the given refresh token.

**Authorization:** None.

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:**
```json
{
  "refresh_token": "string" // required, string
}
```

**Responses:**

*   **204 No Content**: Successful logout.

---

## [GET] /auth/me

**Description:** Get the profile of the currently authenticated user.

**Authorization:** Required (JWT Bearer Token).

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| None | - | - | - |

**Request Body:** None

**Responses:**

*   **200 OK**: User details.
    ```json
    {
      "id": 1,
      "username": "string",
      "email": "string",
      "role": "string (UserPrivileges)",
      "created_at": "datetime"
    }
    ```
*   **401 Unauthorized**: Missing or invalid token.

---

## [PATCH] /admin/orders/{order_id}/force-cancel

**Description:** Admin strictly forces an order to be cancelled if it requires manual intervention (`MANUAL_INTERVENTION_REQUIRED`).

**Authorization:** Required (JWT Bearer Token with Admin role).

**Query/Path Parameters:**
| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| **`order_id`** | uuid | Yes | The ID of the stuck order. |

**Request Body:** None

**Responses:**

*   **200 OK**: Order was forcefully cancelled successfully.
    ```json
    {
      "message": "Order <uuid> forcefully cancelled by admin <user_id>",
      "order_id": "uuid",
      "status": "CANCELLED"
    }
    ```
*   **400 Bad Request**: Order is not in `MANUAL_INTERVENTION_REQUIRED` state.
*   **401 Unauthorized**: Missing or invalid token.
*   **403 Forbidden**: User token provided but without Administrator privileges.
*   **404 Not Found**: Order with provided ID does not exist.

---
