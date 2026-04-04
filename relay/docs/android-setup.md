# Android Setup

Relay is a local companion service. Android only needs the relay base URL.

## Android emulator

When relay runs on the same machine as the emulator, use:

```text
http://10.0.2.2:8080
```

If you changed the relay port, replace `8080`.

## Physical phone

When relay runs on your local machine and the phone is on the same network, use:

```text
http://<your-lan-ip>:8080
```

Examples:

```text
http://192.168.1.12:8080
http://10.0.0.15:8080
```

## Verify relay first

Before testing Android, run:

```bash
python -m relay doctor
python -m relay start
```

Then check Web UI:

```text
http://127.0.0.1:8080/ui
```

## Android flow

1. Open relay Web UI
2. Confirm executor and default mode
3. Open Android app settings
4. Enter relay base URL
5. Test connection
6. Select mode
7. Save
8. Share a link into the app

## Useful relay checks while Android is running

```bash
python -m relay status
python -m relay tasks list
python -m relay tasks show <taskId>
```

## If Android says connection failed

Check:

1. relay is running
2. correct host for emulator vs phone
3. port matches the relay bootstrap port
4. local firewall is not blocking access
5. `/ui` and `/api/health` are reachable locally
