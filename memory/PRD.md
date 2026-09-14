# Grove Seller Portal PRD
## Original problem statement
Seller should be able to login and perform stock update, customer detail update, customer order placement on behalf of a selected customer, and list customers under a society.
## Architecture decisions
React dashboard with FastAPI REST API and MongoDB collections for products, customers, and orders. Phone OTP is a simulated MVP flow using demo code 123456; no SMS provider is connected.
## User personas
Local society seller managing grocery inventory and placing orders for residents.
## Core requirements
Phone OTP login; product creation and stock/price/availability; customer CRUD fields; fixed society grouping; customer order builder; order status/history.
## Implemented (2026-06-24)
Attractive responsive Grove seller workspace, seeded demo data, overview, inventory, inline stock stepper editing (minus, editable quantity, plus) with persistence and nonnegative API validation, inventory editing (price, stock, availability), customer directory with full society filtering and editing, order creation with stock limits, order history, delivery status updates, hydration loading state, and API endpoints.
## Prioritized backlog
P0: Real SMS OTP provider and persistent seller sessions. P1: Analytics exports and delivery notifications. P2: Multi-seller roles and advanced reporting.
## Next tasks
Connect an SMS provider when production credentials are available, then add delivery notifications and seller roles.