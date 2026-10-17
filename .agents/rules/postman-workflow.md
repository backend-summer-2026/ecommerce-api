# Postman Collection Maintenance Rules

## Overview

This document defines the mandatory rules for maintaining and updating the primary Postman Collection for the `ecommerce` API. To enable continuous end-to-end testing of business logic, the master Postman collection in `postman/` must always mirror the latest state of all backend endpoints.

---

## 1. Mandatory Synchronization Rule

- **Trigger for Updates**: Whenever an API endpoint is:
  - **Created** (new route, view, or action)
  - **Updated** (changed URL path, HTTP method, query parameters, request payload schema, or response structure)
  - **Removed / Deprecated**
  
  The agent **MUST immediately update the master Postman collection file**:
  `postman/ecommerce_api_collection.json`

- **No Stale Endpoints**: Code changes to endpoints (views, serializers, URLs) are NOT considered complete until the corresponding request(s) in the Postman collection are added or updated.

---

## 2. Collection Location & Format

- **File Path**: `postman/ecommerce_api_collection.json`
- **Schema**: Postman Collection Schema v2.1.0 (`https://schema.getpostman.com/json/collection/v2.1.0/collection.json`)
- **JSON Validity**: The file must always remain strictly valid JSON.

---

## 3. Structural Standards

The collection must be organized by domain/app folders:
- `1. Authentication & Users` (Register, Request OTP, Verify OTP, Login, Refresh Token, Profile, Logout)
- `2. Products & Categories` (List Products, Filter, Search, Product Details, Category List)
- `3. Cart & Items` (Get Cart, Add Item, Update Item Quantity, Remove Item, Clear Cart)
- `4. Orders & Checkout` (Create Order, Order Details, List Orders, Order Payment/Status)
- `5. Reviews & Ratings` (List Reviews, Add Review, Update Review)
- `6. Dashboard / Admin APIs` (Admin Analytics, Inventory Management)

---

## 4. Request Specifications for Business Logic Testing

Each Postman request must include:
1. **Dynamic Base URL**: Use the variable `{{base_url}}` (e.g. `http://127.0.0.1:8000`) for all hostnames.
2. **Proper Headers**:
   - `Content-Type: application/json` for requests with bodies.
   - `Authorization: Bearer {{access_token}}` for all protected/authenticated endpoints.
3. **Realistic Sample Request Payloads**:
   - Provide concrete, valid JSON data in `raw` body mode reflecting realistic business test cases (e.g., real email addresses, phone numbers, valid SKU, valid quantities).
4. **Chaining Scripts (Tests / Pre-request)**:
   - For authentication endpoints (e.g. Login, Token Verify, Token Refresh), include Postman test scripts to automatically save tokens into collection variables:
     ```javascript
     if (pm.response.code === 200) {
         var data = pm.response.json();
         if (data.access) {
             pm.collectionVariables.set("access_token", data.access);
         }
         if (data.refresh) {
             pm.collectionVariables.set("refresh_token", data.refresh);
         }
     }
     ```
5. **Clear Naming & Description**: Every request must have an informative name (e.g., `POST /api/v1/auth/verify-otp/ - Verify OTP and Issue Tokens`) and brief description explaining its business logic role.

---

## 5. Checklist Integration

In accordance with [.agents/rules/planning-workflow.md](file:///.agents/rules/planning-workflow.md), when planning any API-related feature or modification:
- The execution checklist must explicitly include a step:
  `- [ ] Step X: Update master Postman collection in postman/ecommerce_api_collection.json with new/updated endpoints`
- This step must be executed and marked `- [x]` before the feature is finalized.
