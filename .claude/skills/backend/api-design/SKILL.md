---
name: api-design
description: Designs and implements HTTP/REST APIs — endpoints, request/response shapes, status codes, errors, pagination, auth, versioning, and OpenAPI specs. Use whenever the user is building, adding, reviewing, or fixing a backend endpoint, route, controller, or API contract, in any language or framework, even if they don't say "API design" (e.g. "add a route for X", "my backend needs to return Y", "write the spec for this service").
---

# API Design

Design the contract first, then implement it in whatever framework the project already uses. Consistency across endpoints matters more than any single "perfect" choice, so match existing conventions in the codebase before applying the defaults below.

## Step 1: Gather context (before writing anything)

1. Look for existing routes, controllers, or an OpenAPI file. If found, adopt their casing, error shape, pagination style, and versioning. Only deviate if the existing pattern is broken; say so explicitly.
2. Identify: the resources (nouns), who calls the API (browser app, mobile app, other services), and the auth model.
3. If the framework is unknown and there is no code, ask which one. Do not pick one silently.

## Step 2: Apply these defaults (unless the project already does otherwise)

**URLs**
- Plural nouns for collections: `/users`, `/users/{id}`. No verbs in paths (`/createUser` is wrong).
- Nest at most one level: `/users/{id}/runs` is fine; `/users/{id}/runs/{runId}/points/{pointId}` should become `/runs/{runId}/points`.
- Non-CRUD actions are a sub-resource with POST: `POST /orders/{id}/cancel`.
- Prefix with a major version: `/v1/...`. Bump only for breaking changes.

**Methods and status codes**

| Method | Use | Success code |
|---|---|---|
| GET | read, no side effects | 200 |
| POST | create / action | 201 + `Location` header (create), 200 or 202 (action) |
| PUT | full replace | 200 |
| PATCH | partial update | 200 |
| DELETE | remove | 204, no body |

Error codes: 400 malformed/invalid input, 401 not authenticated, 403 authenticated but not allowed, 404 not found (also use for resources the caller may not know exist), 409 conflict (duplicate, version mismatch), 422 validation failure if the project distinguishes it from 400, 429 rate limited, 500 server bug. Never return 200 with an error in the body.

**Payloads**
- One casing everywhere (default `camelCase` for JSON consumed by JS clients, otherwise match the project).
- IDs as strings. Timestamps as ISO 8601 UTC strings (`2026-10-16T18:30:00Z`). Money as integer minor units plus currency code.
- Return the created/updated resource from POST/PUT/PATCH so clients don't need a second request.
- Never expose internal fields (password hashes, internal flags, raw DB errors).

**Errors** — use one shape for every error (RFC 9457 problem details style):
```json
{ "type": "validation_error", "title": "Invalid request", "status": 400,
  "detail": "distance must be positive", "errors": [{ "field": "distance", "message": "must be > 0" }] }
```

**Lists**
- Always paginate collections. Default to cursor pagination: `?limit=20&cursor=abc`, response `{ "data": [...], "nextCursor": "..." | null }`. Use offset only for small, admin-style lists.
- Cap `limit` (default 20, max 100). A `limit` above the max is clamped to the max, not rejected; a non-numeric or negative `limit` is a 400.
- Filters and sorting as query params: `?status=active&sort=-createdAt`.

**Safety and reliability**
- Validate every input at the boundary with a schema library the project uses (zod, pydantic, etc.). Reject unknown fields on write endpoints.
- Require auth by default; mark public endpoints explicitly.
- Check authorization per resource (does this user own this run?), not just "is logged in".
- POST endpoints that create money movements, orders, or other must-not-duplicate records accept an `Idempotency-Key` header.
- Add rate limiting on auth and expensive endpoints.

## Step 3: Produce output

For a new API or a set of endpoints, deliver in this order:
1. **Endpoint table**: method, path, purpose, auth, success code.
2. **Request/response examples** for each endpoint (one success, one error).
3. **OpenAPI 3.1 spec** (`openapi.yaml`) when designing 3+ endpoints or when the user asks.
4. **Implementation** in the project's framework: routes, validation schemas, handlers, and error middleware producing the error shape above.
5. **Short note** listing any decisions that deviate from these defaults and why.

For a single new endpoint in an existing API, skip the table and spec unless one already exists (then update it).

## Step 4: Check before finishing

- [ ] Every endpoint has an explicit auth decision.
- [ ] Every list endpoint is paginated with a capped limit.
- [ ] Every error path returns the shared error shape with the right status code.
- [ ] Every write endpoint validates input.
- [ ] No internal fields leak in responses.
- [ ] Naming, casing, and versioning match the rest of the API.
