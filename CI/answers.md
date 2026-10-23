# Task C — Xero Integration Review

> Multi-tenant service synchronising invoices between an internal order system
> and Xero. Sync runs in background workers. Tokens, tenant IDs and sync cursors
> are stored per connected organisation.

Answers are concise, written from a production-operations point of view:
observable checks, failure handling and safe production behaviour.

---

## C1 — Connection verification

Smallest sequence of calls and checks that proves OAuth and tenant selection are
working **before** reading invoices, and what each result proves:

1. **Introspect the access token / refresh on demand**
   `POST https://identity.xero.com/connect/token` with the stored refresh token.
   - A valid response proves the stored credentials are still refreshable and
     the grant is live. A `invalid_grant` proves the refresh token is revoked or
     expired and the tenant needs re-onboarding.

2. **List connections**
   `GET https://api.xero.com/connections` (or the identity connection resource)
   with `Authorization: Bearer <access_token>`.
   - 200 + a body containing a connection whose `tenantId` matches our stored
     tenant ID proves the token is valid and this organisation is still
     connected to the app. An empty list or a missing tenant proves the app was
     disconnected from that organisation.

3. **Tenant-scoped round-trip with the smallest read**
   `GET https://api.xero.com/api.xro/2.0/Organisation` with
   `Xero-tenant-id: <tenantId>`.
   - 200 proves (a) the tenant ID is correct for this token, (b) the app is
     authorized to read basic organisation data for this tenant, and (c) the
     tenant header is being applied. 403/404 here narrows the failure to tenant
     selection rather than token validity.

4. **Invoice-scope smoke check (optional but recommended before a batch)**
   `GET https://api.xero.com/api.xro/2.0/Invoices?page=1` once.
   - Proves the specific `accounting.transactions` scope is granted and usable.
     This is the exact surface we will hit during sync, so it catches a
     scope-grant problem before any write.

Order matters: each step isolates a different layer (credentials → connection →
tenant → data scope), so a failure tells you *which* layer to fix.

---

## C2 — Failure diagnosis (401 / 403 / 404)

The connection call succeeds but `Invoices` returns 401, 403 or 404 in different
environments. Diagnostic decision tree:

```
Invoices request failed (401 | 403 | 404)
│
├─ 401 Unauthorized
│   ├─ Token expired / invalid (expires_in passed, clock skew)?
│   │   └─ YES → refresh access token and retry once with a fresh token.
│   │         If refresh fails (invalid_grant) → tenant needs re-auth.
│   ├─ Access token missing / malformed `Authorization` header?
│   │   └─ YES → fix how the token is attached to the request.
│   └─ Still 401 after refresh → scope not granted for this grant?
│       └─ Check `scopes` on the stored grant; user must re-consent.
│
├─ 403 Forbidden
│   ├─ Scope missing (e.g. only `accounting.transactions.read`, no write)?
│   │   └─ Compare granted scopes vs required scope; trigger re-consent.
│   ├─ App not authorized for this tenant (organisation-level)?
│   │   └─ Verify connection list still contains tenantId; re-link if dropped.
│   └─ Tenant trial/plan restrictions?
│       └─ Check tenant subscription status in Organisation response.
│
└─ 404 Not Found
    ├─ Tenant header (`Xero-tenant-id`) wrong / absent?
    │   └─ Confirm the header uses the tenantId from /connections for THIS env.
    ├─ Tenant ID belongs to a different environment (dev vs prod data)?
    │   └─ Check environment config: base URL + tenant pairing is per-env.
    ├─ Resource genuinely not present (e.g. invoice id unknown)?
    │   └─ This is a data-level 404, handled by the sync, not a bug in auth.
    └─ Base URL / environment configuration wrong?
        └─ Verify the API host matches the environment the tenant was created in.
```

Key principle: treat each status as a *different layer* (token/scope/permission/
tenant/environment) and keep the diagnosis branching by the HTTP semantics, not
by guessing.

---

## C3 — Incremental synchronisation

Resilient invoice sync for a large organisation:

- **Pagination**: use Xero `page` for full scans and read `Invoices` with
  `page=1..N`, stopping when a page returns fewer items than the page size. Use
  an `If-Modified-Since` header to fetch only records changed since the last
  run (Xero honours it for many list endpoints), which bounds each run to the
  delta rather than the whole ledger.
- **Change window / modified-since**: persist the `If-Modified-Since` timestamp
  *after* a run succeeds, not before, so a crash never loses a window. Prefer a
  slightly older "low watermark" (e.g. start of the last hour) to absorb late
  updates and clock skew.
- **Cursor persistence**: store the cursor/checkpoint (timestamp + last seen
  invoice id) per tenant in the same durable store as the tokens. Write it in
  the same transaction as the upsert of the processed invoices so cursor and
  data never diverge.
- **Duplicates**: make the write side idempotent. Store the Xero `InvoiceID`
  as the unique key in our order-invoice mapping; on re-read, an invoice we
  already mapped is ignored (upsert). Do not rely on "the invoice was modified"
  to re-create it.
- **Partial failure**: process in pages/batches; record per-batch completion.
  On a batch failure, retry just that batch (the checkpoint is the last fully
  completed batch). Keep a retry queue for failed items with a bounded backoff.
- **Safe replay**: because the sync is idempotent and the checkpoint is written
  atomically with processed items, replaying from the last checkpoint is safe —
  re-reading a page that was already processed simply yields no-op upserts.
  Never delete-and-reinsert on replay.

---

## C4 — Rate limits (HTTP 429)

When a worker receives `429 Too Many Requests`:

- **Response headers**: honour the headers Xero returns (e.g.
  `Rate-Limit-*`/`Retry-After`-style values where provided) and respect the
  documented per-tenant rate limit. Back off for at least the suggested delay.
- **Backoff + jitter**: use exponential backoff (base interval growing
  multiplicatively, capped, e.g. `min(2^n * base, max)` plus a random jitter
  `[0, jitter]`). Jitter prevents a fleet of workers from resyncing in lockstep
  and hammering the API in waves.
- **Concurrency limits**: cap per-tenant and global concurrent requests (a
  semaphore sized to the documented limits). Do not spawn unbounded workers for
  the same tenant.
- **Retry budgets**: give each job/item a small, explicit retry budget (e.g.
  max 3 retries) and stop retrying after the budget is exhausted — move the item
  to a DLQ/alert rather than retrying forever.
- **Job scheduling**: schedule sync jobs with spacing so a tenant is never hit
  by overlapping runs; backfill/retry jobs are queued behind the main poll.
- **Errors that should NOT be retried**: `4xx` errors that indicate a permanent
  condition — `401` (token must be refreshed first, not blindly retried),
  `403` (missing permission, needs re-consent), `404` (resource genuinely
  absent), and any validation `4xx`. Also do not retry an item whose retry
  budget is spent. Only transient errors (429, 5xx, network timeouts) are
  eligible for backoff-retry.

---

## C5 — Data integrity (duplicate invoices & lost responses)

- **Prevent duplicate invoices**: make invoice creation idempotent on the Xero
  side. Send a stable, unique external reference with every create — e.g. set
  the invoice `LineItems`/`Reference` (or an external-link/idempotency key) to
  the internal order id, and before creating, query for an existing invoice with
  that reference. If found, treat the create as already-done (reuse it) instead
  of creating a second one. This converts "create after a timeout retry" into a
  look-up-then-create.
- **Reconcile "request succeeded but response was lost"**: when the request
  times out, we do not know whether Xero created the invoice. Before retrying a
  create, look up by the stable reference. If Xero returns an invoice with that
  reference, the original create did succeed — reconcile by mapping that
  existing invoice to the order (and never creating a duplicate). If no invoice
  exists, retry the create. This "query-by-idempotency-key before retry" closes
  the lost-response gap.
- **Audit trail**: keep a durable `order → invoice` mapping table with status
  transitions and a reconciliation job that periodically detects orders mapped
  to multiple invoices and alerts.

---

## C6 — Observability and security

- **Logs** (structured, with a correlation id):
  - per sync-run start/finish, per-batch progress, per-item outcome
    (created/updated/skipped/error),
  - retry events with attempt number and backoff delay,
  - auth/connection lifecycle events (refresh, connect, disconnect).
- **Metrics**:
  - sync duration, records processed, duplicates skipped,
  - API error rate by status class (429/5xx/4xx), retry rate, retry-budget
    exhaustion count,
  - per-tenant lag (time since last successful sync).
- **Alerts**:
  - retry-budget exhaustion (a tenant stuck failing),
  - sustained 4xx (scope/permission broke),
  - 429 rate-limit saturation,
  - per-tenant lag above a threshold (sync not keeping up).
- **Correlation identifiers**: a `correlation_id` (and a `tenant_id`,
  `order_id`) propagated from the internal order through the job and included in
  every request header and log/metric label, so a failure can be traced across
  worker, Xero and DB.
- **Never log**: access/refresh tokens, client secrets, `Xero-tenant-id` is fine
  but do not log raw token bodies or the full OAuth `id_token`/`refresh_token`,
  real customer personal data beyond what is necessary, or full payment/bank
  detail.
- **Secrets storage & rotation**:
  - store tokens and client secrets in a vault/secret manager, never in the
    repo or plaintext config;
  - encrypt tokens at rest; store the Xero `refresh_token` per tenant with
    short-lived access tokens derived at use time;
  - rotate refresh tokens on re-auth, and support forced re-consent/rotation
    when a security incident occurs or a grant is revoked; keep the client
    secret versioned so old secrets can be retired.

---

## REFERENCE

Assumptions: Xero OAuth 2.0 authorisation code flow; Accounting API v2.0
(`api.xro/2.0`); `accounting.transactions` scope for invoices; the standard
Xero .NET/Node SDK version is not used for these calls — the review assumes
direct REST against the official API.

- Xero OAuth 2.0 auth flow — https://developer.xero.com/documentation/guides/oauth2/auth-flow/
- Scopes for the Accounting API — https://developer.xero.com/documentation/guides/how-to-guides/oauth2/scopes/
- Connecting your app to Xero / connections — https://developer.xero.com/documentation/guides/how-to-guides/connect-your-app-to-xero/
- Accounting API overview — https://developer.xero.com/documentation/api/accounting/overview
- Invoices endpoint — https://developer.xero.com/documentation/api/accounting/invoices
- Synchronisation / If-Modified-Since guidance — https://developer.xero.com/documentation/guides/how-to-guides/synchronisation/
- API rate limits — https://developer.xero.com/documentation/guides/oauth2/limits/
