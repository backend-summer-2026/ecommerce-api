# Postman Collection for Ecommerce API

This directory contains the master Postman collection used for end-to-end testing of business logic across all modules of the Ecommerce backend.

---

## Master Collection File

- **File**: [`ecommerce_api_collection.json`](file:///postman/ecommerce_api_collection.json)
- **Format**: Postman Collection Schema v2.1.0

---

## Rule for Developers & `agy` Agent

> [!IMPORTANT]
> **Mandatory Endpoint Synchronization**:
> Whenever an endpoint is created, updated (paths, parameters, request body, headers), or removed, this collection **MUST be updated immediately**.
> No feature or endpoint modification is complete without corresponding updates in this collection.
> For the complete rule specification, see [.agents/rules/postman-workflow.md](file:///.agents/rules/postman-workflow.md).

---

## Collection Structure

The collection is organized into the following domain folders:
1. `1. Authentication & Users` — Registration, OTP verification, JWT login, token refresh, user profile
2. `2. Products & Categories` — Category browsing, product listing, search, filtering, and product details
3. `3. Cart & Items` — Cart management, item additions, quantity updates, removals
4. `4. Orders & Checkout` — Cart checkout, order placement, order history, order details
5. `5. Reviews & Ratings` — Product reviews and ratings
6. `6. Dashboard & Admin APIs` — Administrative analytics and metrics

---

## Environment & Collection Variables

The collection uses built-in collection variables so requests can be chained without manual token copying:
- `base_url`: Defaults to `http://127.0.0.1:8000`
- `access_token`: Automatically captured by test scripts upon successful login or OTP verification
- `refresh_token`: Automatically captured by test scripts upon successful login or OTP verification
- `user_id`: Captured upon login / user profile
- `order_id`: Captured upon checkout / order creation

---

## How to Import into Postman

1. Open Postman.
2. Click **Import** (top left).
3. Drag and drop `postman/ecommerce_api_collection.json` or choose the file.
4. Set the `base_url` variable if your Django server runs on a different host/port.
