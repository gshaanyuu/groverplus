# Grove+ Seller Portal — PRD

## Original problem statement
Seller should be able to login and perform the following actions:
- Stock update
- Customer detail update
- Customer order — select a customer and place order on his behalf
- Customer should be listed under a society

## Architecture
- Backend: FastAPI + Motor (async MongoDB). All routes /api-prefixed. Auth dep `get_current_seller` reads session token from cookie or Authorization header.
- Frontend: React 19 + react-router-dom v7 + axios (withCredentials=true). Two routes: `/` (Login) and `/dashboard` (workspace). Hash `#session_id=` is intercepted at router level for AuthCallback.
- Auth: Emergent-managed Google OAuth (session token stored in httpOnly cookie, 7-day expiry, also mirrored in `user_sessions` collection).

## User personas
- Local seller / kirana operator managing multiple gated societies.

## Core requirements (static)
- Google Sign-In for the seller.
- Manage products (name, category, price, stock ≥ 0, availability).
- Manage customers (name, phone, address, society ∈ fixed list of 5 societies).
- Filter customers by society.
- Place order on behalf of a customer (select customer + add products + Place Order).
- View order history + update status (Pending → Out for Delivery → Delivered).

## What's been implemented
- 2026-02-14 — Migrated auth from mocked OTP to Emergent-managed Google OAuth (`/api/auth/session`, `/api/auth/me`, `/api/auth/logout`). All product/customer/order routes now require authentication.
- 2026-02-14 — React key warnings and `<span>` inside `<option>` cleaned up in app source.
- Earlier — Product CRUD with inline +/- stepper (negative stock 422), customer CRUD tied to fixed society list, order placement with stock decrement + status pipeline.

## Backlog (prioritised)
- P1 — Split `App.js` (currently ~470 lines) into `pages/Login.jsx`, `pages/Dashboard.jsx`, `components/Inventory.jsx`, etc.
- P1 — Atomic order placement: use `find_one_and_update({id, stock: {$gte: qty}}, {$inc: {stock: -qty}})` to avoid overselling under concurrency.
- P1 — Body model for `PATCH /orders/{id}/status` instead of query-string.
- P2 — Delivery SMS alerts (Twilio) — blocked earlier on real API keys; can be revisited when keys are provided.
- P2 — Low-stock badge / restock alerts on Overview.
- P2 — Search + sort on Orders + date range filter.
- P2 — CSV export for orders.
