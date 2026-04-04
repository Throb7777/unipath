## Relay Core

Relay core is the stable, executor-agnostic part of the local companion service.

It is responsible for:

- receiving normalized Android submissions
- validating source, mode, and URL shape
- persisting task state and timeline
- scheduling background execution
- exposing task status and cancellation through the HTTP API

Relay core is **not** responsible for:

- building executor-specific commands
- understanding executor-specific stderr/stdout semantics
- managing OpenClaw agent/session details directly
- deciding how a given CLI fetches or parses article content

Those responsibilities belong to executor adapters.

### Stable task contract

Android submits a structured task:

- `mode`
- `source`
- `rawText`
- `rawUrl`
- `normalizedUrl`
- `clientSubmissionId`
- `clientAppVersion`

Relay core stores the submission as a `TaskRecord` and schedules it for the configured executor.

### Stable API surface

The Android-facing API remains:

- `GET /api/health`
- `GET /api/client-config`
- `POST /api/share-submissions`
- `GET /api/share-submissions/{taskId}`
- `POST /api/share-submissions/{taskId}/cancel`

These endpoints should remain stable even when executor implementations change.
