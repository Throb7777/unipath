# Troubleshooting

## `OpenClaw command could not be resolved`

Meaning:

- relay cannot find the configured OpenClaw command

What to do:

1. Open Web UI Settings
2. Check the OpenClaw command field
3. Run:

```bash
python -m relay doctor
```

If you do not want to use OpenClaw, switch to `shell_command`.

## `manual_verification_required`

Meaning:

- WeChat returned a verification page instead of article content

What to do:

1. Open the managed browser profile used by OpenClaw
2. Complete the manual verification once
3. Retry the task

## `profile_revalidation_required`

Meaning:

- a previously verified managed browser profile needs verification again

What to do:

1. Re-open the article in the managed browser
2. Re-complete verification
3. Retry the task

## `wechat_parameter_error`

Meaning:

- the shared link itself does not resolve to a valid article page

What to do:

1. Re-share the original article URL
2. Avoid shortened or truncated links when possible

## `executor_session_locked`

Meaning:

- the selected OpenClaw lane is currently busy

What to do:

1. Wait for the current task to finish
2. Retry later
3. Consider a separate relay-only OpenClaw agent if you also use `main` interactively

Relay already retries and defers this internally before surfacing it.

## `executor_network_error`

Meaning:

- provider/network communication failed during execution

What to do:

1. Check network access
2. Retry the task
3. Use `python -m relay doctor`
4. Inspect the task detail page and task artifacts

## Web UI does not open

Check:

- `WEB_UI_ENABLED=true`
- relay is started
- correct host/port

Use:

```bash
python -m relay ui
```

## Need to inspect one task quickly

Use:

```bash
python -m relay tasks show <taskId>
```

Or open:

```text
/ui/tasks/<taskId>
```

Artifacts such as `prompt.txt`, `stdout.txt`, `stderr.txt`, and `result.txt` are listed there when present.
