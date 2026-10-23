# Full Stack Developer Coding Assessment — Variant PDP

A single, structured repository for the Aeris Health full-stack coding
assessment. It contains three standalone algorithm tasks (A, B, C) and a
full-stack Variant Product Detail Page (app) with a FastAPI backend and a
React + TypeScript (Vite) frontend.

---

## Repository layout

```
A/            Task A — single-SKU inventory reservation ledger (Python)
B/            Task B — fulfilment split optimiser (Python, DP)
CI/           Task C Xero integration review (answers.md) + one-command runner
app/
  backend/    FastAPI + SQLite API for the Variant PDP
  frontend/   Vite + React + TypeScript PDP
README.md
```

---

## Requirements

- Python 3.11+ (developed and tested on 3.14)
- Node.js 20+ / npm (developed and tested on 22 / 10)

No other global tooling is required; each part manages its own virtual
environment / node_modules and `.gitignore` excludes generated artifacts.

---

## Task A — Inventory Reservation Ledger

A command processor for a single-SKU inventory ledger with reservation state
(`on_hand`, `total_reserved`, and processed `event_id`s).

```bash
cd A
python3 -m unittest discover -s tests -v   # 16 tests
./run.sh < input.txt                        # read commands from a file
```

Commands: `RESERVE|RELEASE|SHIP event_id order_id qty` and
`RESET event_id qty`. Output is one `OK|REJECTED|DUPLICATE on_hand total_reserved`
line per command, followed by open reservations per `order_id`. `event_id` is
idempotent (replays return `DUPLICATE` without mutating state).

Design decisions (all visible in `A/solution.py`):
- `Ledger` holds `on_hand`, `reserved_by_order`, and `processed` (a set of
  event ids). A `REJECTED` business action is still recorded as processed, so a
  re-sent invalid event is reported as `DUPLICATE`, not re-evaluated.
- `RESERVE` only succeeds when `available = on_hand - total_reserved >= qty`;
  `SHIP` decrements both `on_hand` and the order's reservation.
- Malformed/unknown commands are rejected with **no partial state change**.
- `RESET` resets `on_hand` (assumed to be a stock count) while keeping existing
  reservations intact.
- Complexity: O(1) per command.

## Task B — Fulfilment Split Optimiser

Allocate exactly `Q` units across `W` warehouses optimising (in order):
① fewest warehouses used, ② lowest total cost `Σ(fixed + qty·unit)`,
③ lexicographically smallest allocation sorted by `warehouse_id`.

```bash
cd B
python3 -m unittest discover -s tests -v   # 7 tests
./run.sh < input.txt
```

Approach — dynamic programming, no subset brute-force and no external solver:
- `dp[q]` stores the best `(warehouses_used, total_cost, allocation)` triple for
  producing exactly `q` units. Because the comparison is the Python tuple
  ordering of `(warehouses, cost, allocation)`, the three-level objective is
  implemented directly.
- Warehouses are consumed 0/1 (each at most once) by iterating `q` in reverse.
- The allocation is kept sorted by `warehouse_id`, so its lexicographic order
  matches the spec.
- Complexity: `O(W · Q · avg_stock)` time, `O(Q · W)` space — handles the
  largest case `W=20, Q=2000`.
- Zero-stock warehouses are skipped; if `Σ stock < Q` the answer is `-1`.

## Task C — Xero Integration Review

See [`CI/answers.md`](CI/answers.md): a concise production answer to C1–C6
(connection verification, failure diagnosis, incremental sync, rate limits,
data integrity, observability & security) with references to the official Xero
developer documentation.

## One-command verification

```bash
./CI/run_all.sh
```

Runs Task A and Task B unit tests, and (when dependencies are installed) the
backend and frontend test suites.

---

## App — Variant PDP

A product detail page with two option dimensions (colour × size), ≥6 SKUs
including an unavailable combination and an out-of-stock SKU.

### Backend (FastAPI + SQLite)

```bash
cd app/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests -q          # 7 tests
.venv/bin/uvicorn main:app --reload          # http://localhost:8000
```

Endpoints:
- `GET /api/products/{id}` — product, option dimensions, SKUs, unavailable combos
- `POST /api/cart/items` — add `{sku_id, quantity, idempotency_key?}`
- `GET /api/cart` — cart + total item count

Server-side guarantees:
- SKU existence, quantity and current stock are validated server-side; the
  client's price/stock is never trusted (the client only sends `sku_id` +
  `quantity`).
- **Idempotency**: `add-to-cart` accepts an `idempotency_key`; a repeated key
  returns the existing result and never adds twice.
- **Structured errors**: `product_not_found` / `sku_not_found` /
  `insufficient_stock` / `internal_error` with a stable `error_code`.
- **Overselling**: a process-wide lock plus a SQLite `BEGIN IMMEDIATE`
  transaction makes the check-and-decrement atomic, so two concurrent requests
  for the final unit cannot both succeed — one gets `409 insufficient_stock`.
  This is covered by a dedicated race test.

### Frontend (Vite + React + TypeScript)

```bash
cd app/frontend
npm install
npm test                    # vitest (variant resolution + component tests)
npm run dev                 # http://localhost:5173 (proxies /api to :8000)
npm run build               # type-check + production build
```

Behaviour:
- Shows image, name, description, selected price, stock status and cart count.
- Renders both option dimensions; unavailable combinations (no SKU) and
  out-of-stock SKUs are disabled or clearly flagged.
- Selection resolves the concrete SKU immediately (pure `domain/variant.ts`).
- Quantity is clamped to `1..available stock`.
- Add-to-cart shows progress, prevents duplicate submissions (a `pending` guard
  plus disabling the button), and reports success/failure with accessible
  `role="status"` / `role="alert"` feedback.
- Responsive: single column below 900px, two columns on 1280px.

---

## Design decisions worth explaining in review

- **Task A**: idempotency by `event_id` with rejected-actions-also-processed;
  RESET semantics.
- **Task B**: DP state `(warehouses, cost, allocation)` and why the tuple
  ordering encodes the priority; 0/1 reverse iteration.
- **App overselling**: the lock + `BEGIN IMMEDIATE` transaction approach and its
  race-test.
- **App idempotency**: server-side key table so replays are no-ops.

## Known limitations

- Task A/B official examples could not be read reliably from the view-only PDF
  (OCR noise), so tests use self-consistent examples built from the stated
  rules.
- The cart lives in memory and is shared per backend process (no user
  auth/session — out of scope per the assessment).
- Single-product, single-image PDP; the frontend is not SSR.
- `httpx` with Starlette's test client emits a deprecation warning in newer
  FastAPI (non-blocking).

## AI assistance disclosure

This solution was developed with assistance from an AI coding agent. AI was
used for: scaffolding the repository, drafting the initial algorithm
implementations and tests, and generating the app's frontend/backend skeleton
and README. Every design decision (Task A state machine, Task B DP and
tie-breaking, the app's overselling and idempotency mechanisms, frontend
layering) was reviewed, validated by tests, and is explainable — I understand
and can walk through or modify each part on request. No confidential or
customer data is included.
