# UniPATH Forwarding Service

> The local Forwarding Service used by UniPATH. It receives tasks, runs a Processing Method, stores task status, and provides a Web UI and diagnostics.

## 🌟 What Relay Does

Relay is the local service in the middle of the workflow:

```text
Android app
  -> Forwarding Service
  -> Processing Method
  -> Result Summary
  -> Android app + Web UI
```

Relay provides:

- a local HTTP API
- a local Web UI
- a CLI
- diagnostics and smoke tests
- task storage and status tracking

## ✅ What Is Already Included

- Task intake
- Task status and cancellation
- Web UI pages:
  - `Overview`
  - `Settings`
  - `Tasks`
  - `Diagnostics`
- CLI commands:
  - `init`
  - `doctor`
  - `smoke`
  - `start`
  - `status`
  - `tasks`
- Processing Methods:
  - `openclaw`
  - `shell_command`
  - `mock`

## 📦 Requirements

### Required

- Python 3.10+
- a terminal

### Optional but recommended

- OpenClaw, if you want real article processing
- Android app, if you want the full mobile workflow

## 🚀 First Run, Step by Step

This section is written for a first-time user.

### Step 1. Open a terminal in the project root

The project root is the folder that contains:

- `Android/`
- `relay/`
- `docs/`

### Step 2. Create a virtual environment

Windows PowerShell:

```powershell
cd /path/to/your/repo/relay
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
cd /path/to/share-paper/relay
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3. Install dependencies

```bash
pip install -r requirements.txt
```

If you also want to run relay tests:

```bash
pip install -r requirements-dev.txt
```

### Step 4. Create the local runtime files

From the parent directory that contains the `relay/` folder:

```bash
python -m relay init
```

This creates the local runtime layout and the default configuration file.

### Step 5. Run a local readiness check

```bash
python -m relay doctor
```

Look for one of these summaries:

- `ready`
- `warning`
- `blocked`

If the selected Processing Method is not ready yet, open the Web UI in the next step and finish the setup there.

### Step 6. Start Relay

```bash
python -m relay start
```

After startup, Relay prints:

- API address
- Web UI address
- current Processing Method
- current Processing Mode
- configuration file path

### Step 7. Open the Web UI

Open:

```text
http://127.0.0.1:8080/ui
```

### Step 8. Configure Relay in the Web UI

In the Web UI:

1. Open **Settings**
2. Choose a **Processing Method**
3. If needed, click **Test Processing Method**
4. Click **Save**

### Step 9. Run a smoke test

CLI:

```bash
python -m relay smoke mock
```

Other useful smoke commands:

```bash
python -m relay smoke shell
python -m relay smoke openclaw
```

## 🧭 Web UI Pages

### `Overview`

Use this page to:

- confirm Relay is running
- see the current Processing Method
- see the current Processing Mode
- jump to **Settings**, **Tasks**, or **Diagnostics**

### `Settings`

Use this page to:

- change the **Processing Method**
- change the **Default Mode**
- use **Test Processing Method**
- use **Save** or **Save and Test**

### `Tasks`

Use this page to:

- view Recent Tasks
- filter tasks
- open task details
- cancel a task with **Cancel Task**

### `Diagnostics`

Use this page to:

- check whether the current Processing Method is ready
- see environment checks
- read the environment diagnostic summary
- understand the next recommended action

## 🧪 CLI Commands

Preferred entrypoint:

```bash
python -m relay <command>
```

Available commands:

- `python -m relay init`
- `python -m relay doctor`
- `python -m relay doctor --short`
- `python -m relay smoke mock`
- `python -m relay smoke shell`
- `python -m relay smoke openclaw`
- `python -m relay start`
- `python -m relay status`
- `python -m relay config show`
- `python -m relay config path`
- `python -m relay tasks list`
- `python -m relay tasks show <taskId>`
- `python -m relay tasks cancel <taskId>`
- `python -m relay ui`

Most commands also support `--json`.

## ⚙️ Configuration Model

Relay uses two layers of configuration.

### 1. Bootstrap configuration

Source:

- `.env`
- process environment

Used for:

- host
- port
- workspace directory
- Web UI exposure

### 2. Current Configuration

Source:

- `runtime/data/config.json`

Used for:

- selected Processing Method
- Default Mode
- method-specific settings

## 🧩 Processing Methods

### `openclaw`

Use this when you want:

- real article processing
- browser-assisted fetching
- real result extraction

### `shell_command`

Use this when you want:

- a trusted local script
- a simple command-based pipeline
- a lightweight integration path

### `mock`

Use this when you want:

- a smoke test
- a UI test
- a full workflow test without real processing

## 📂 Runtime Files

Relay stores local runtime files under `runtime/`.

Important locations:

- `runtime/data/config.json`
- `runtime/data/relay.sqlite3`
- `runtime/logs/relay.log`
- `runtime/tasks/<taskId>/`

## 🖥️ Android Connection

For the Android app, use only the Relay base URL.

Examples:

- Android Emulator to Windows host:
  - `http://10.0.2.2:8080`
- physical phone to a local machine:
  - `http://<your-lan-ip>:8080`

## ✅ Verification

Run relay tests:

```bash
python -m unittest discover -s tests -v
```

## ⚠️ Known Limits

- OpenClaw depends on local command, browser, and gateway readiness.
- The strongest real end-to-end verification today is on Windows.
- Raw diagnostics may keep original English text for troubleshooting.

## 📚 Extra Docs

- [docs/quickstart.md](./docs/quickstart.md)
- [docs/executors.md](./docs/executors.md)
- [docs/android-setup.md](./docs/android-setup.md)
- [docs/troubleshooting.md](./docs/troubleshooting.md)
- [docs/relay-core.md](./docs/relay-core.md)
- [docs/executor-contract.md](./docs/executor-contract.md)
- [docs/mode-definition.md](./docs/mode-definition.md)

## 📄 License

This project is licensed under the MIT License.
