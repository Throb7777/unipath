# Executors

Relay core is executor-agnostic. It schedules tasks, persists state, exposes status APIs, and delegates actual work to the configured executor.

## Supported executors

### `openclaw`

Default executor.

Best when you want:

- article-body prefetch through the managed browser
- OpenClaw agent execution
- richer task timelines
- WeChat-specific handling

Typical runtime settings:

- command
- target mode
- local embedded mode
- agent id / session id / recipient
- browser profile
- timeout and retry settings

This executor is the richest default path, but relay itself is not tied to it.

### `shell_command`

Generic fallback executor.

Best when you want:

- to run a custom local script or CLI
- to avoid OpenClaw entirely
- to prototype a new backend quickly

The configured template is treated as trusted local configuration.

Available placeholders:

- `{task_id}`
- `{mode}`
- `{source}`
- `{raw_text}`
- `{raw_url}`
- `{normalized_url}`
- `{client_submission_id}`
- `{client_app_version}`

Example:

```text
python my_script.py --url "{normalized_url}"
```

### `mock`

Lightweight testing executor.

Best when you want:

- to verify Android -> relay -> status UI flow
- to test without external dependencies

## Configuration ownership

Bootstrap config:

- chooses where relay runs
- `.env` / environment variables

Runtime config:

- chooses which executor relay uses
- edited through Web UI
- stored in `runtime/data/config.json`

## Executor testing

Use the Web UI Settings page and click `Test executor`.

This validates the current form values without saving them.

CLI health check:

```bash
python -m relay doctor
```

## Future executor model

The relay architecture is designed so more executors can be added later without changing the Android API surface. New executors should follow the contract documented in:

- `docs/executor-contract.md`
