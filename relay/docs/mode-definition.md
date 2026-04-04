## Mode Definition

Modes are relay-level task modes, not executor-specific prompt presets.

Examples:

- `paper_harvest_v1`
- `paper_harvest_relaxed_v1`
- `link_only_v1`

Relay core owns the mode registry and exposes it to Android through `client-config`.

Executors implement modes. This means:

- Android chooses a relay mode
- relay validates that the current executor supports that mode
- the executor decides how to fulfill that mode internally

This keeps Android independent from OpenClaw-specific command or prompt semantics.

Modes can also advertise relay-level metadata that stays independent from any one executor, such as:

- `category`
- `outputKind`
- `requiresNormalizedUrl`
- `requiresArticleBodyFetch`
- `supportsBrowserPrefetch`
- `preferredExecutors`

This metadata is owned by relay core. Executors can use it to choose execution paths, but clients should still treat the mode registry itself as the source of truth.
