## Open Questions addressed

### 1) What happens if a disbursement webhook never arrives? How long do you wait before escalating?

- Use a configurable timeout window. In this implementation, `webhook_timeout_seconds` is set to `120` seconds in `config.yaml`.
- If no webhook arrives within the timeout while application is `disbursement_queued`, escalate to `flagged_for_review`.
- In production, run timeout checks via a scheduler/worker so escalation is automatic even without incoming webhook traffic.

### 2) If scoring weights changed, would existing approved applications need re-evaluation?

- Do not necessarily re-score already finalized applications by default, keep the decision consistency and audit integrity.
- Apply new weights to new applications only, and store score snapshots and version for traceability.
- If policy requires re-checks, run a controlled re-evaluation job and flag only impacted cases for manual review.

### 3) How would you extend support for multiple document types (tax returns, offer letters)?

- Add a `documents` domain model in DB with fields like `document_type`, `verification_status`, `source`, and extracted normalized values.
- Move income verification to a different layer depends on document type (for example, payslip  vs tax return document layers).
- Keep the verification output API, so scoring engine consumes one consistent structure regardless of document source.

### 4) What would change to handle 10,000 applications/day?

- Replace SQLite with Postgres and add indexed queries plus migration tooling.
- Decouple heavy workflows flows (webhooks, timeout checks, retries, audits) using a queue or worker architecture.
- Add observability and operational safeguards: metrics, structured logs, retry policies, idempotency keys, and horizontal API scaling.