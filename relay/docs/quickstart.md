# Quick Start

This is the fastest way to get relay running as a local companion service.

There are two equivalent entry styles:

- from the parent directory that contains `relay/`: `python -m relay <command>`
- from inside `relay/`: `python run.py <command>`

For backward compatibility, `python run.py` without extra arguments still starts the service.

## 1. Prepare the environment

From the `relay/` directory:

```bash
pip install -r requirements.txt
```

If you want to run the relay test suite locally:

```bash
pip install -r requirements-dev.txt
```

Optional:

```bash
copy .env.example .env
```

Use `.env` only for bootstrap settings such as:

- `HOST`
- `PORT`
- `WORKSPACE_DIR`
- `WEB_UI_ENABLED`
- `WEB_UI_LOCAL_ONLY`

## 2. Initialize relay

```bash
python -m relay init
```

This creates:

- `runtime/`
- `runtime/data/config.json`
- runtime database and log directories

## 3. Run diagnostics

```bash
python -m relay doctor
```

This checks:

- runtime directory access
- database availability
- Web UI exposure
- configured executor health
- individual executor readiness

Use JSON output if needed:

```bash
python -m relay doctor --json
```

## 4. Start relay

```bash
python -m relay start
```

Useful output:

- local API base URL
- local Web UI URL
- Android emulator URL (`10.0.2.2`)

## 5. Open Web UI

Open:

```text
http://127.0.0.1:8080/ui
```

Use the Web UI to:

- select the executor
- edit OpenClaw or shell-command runtime settings
- test the selected executor without saving
- inspect tasks and diagnostics

## 6. Connect Android

For the Android emulator:

```text
http://10.0.2.2:8080
```

For a physical phone:

```text
http://<your-lan-ip>:8080
```

## Common commands

```bash
python -m relay status
python -m relay config show
python -m relay tasks list
python -m relay tasks show <taskId>
python -m relay tasks cancel <taskId>
python -m relay ui
```

## Run tests

```bash
python -m unittest discover -s tests -v
```
