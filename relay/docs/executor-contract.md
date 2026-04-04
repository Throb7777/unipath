## Executor Contract

Executors are adapters that turn a relay task into concrete work.

Relay core calls executors through a small, stable contract:

- `descriptor()`
- `health()`
- `supports_mode(mode)`
- `supported_mode_ids()`
- `lane_key_for_task(task)`
- `execute(task_id)`
- `cancel_task(task_id)`

### Responsibilities

An executor is responsible for:

- converting a relay task into its own input format
- running the underlying command, process, or HTTP call
- writing task artifacts such as prompts or command lines
- classifying executor-specific failures
- exposing executor-specific health information
- advertising stable capabilities through `descriptor()`, including:
  - cancellation support
  - browser-prefetch support
  - structured-result support
  - realtime-timeline support
  - supported relay mode ids

### Current executors

- `openclaw`: default adapter with managed browser and article extraction
- `mock`: deterministic fake executor for regression tests
- `shell_command`: generic command-template executor for non-OpenClaw users

### Cancellation semantics

Executors should treat cancellation as a first-class outcome:

- relay core may set task status to `cancelling`
- executor should stop active child processes as soon as practical
- executor should avoid overwriting a cancellation request with a generic failure
