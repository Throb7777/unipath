<p align="right">
  🌐 <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

# UniPATH

> Looking for Chinese? See [README.zh-CN.md](./README.zh-CN.md).

> UniPATH: Unified Phone Action Task Hub
>
> A local companion workflow for sending shared links from Android to a local Forwarding Service, then processing them with OpenClaw or another Processing Method.

## 📦 APK Download

Want to install UniPATH on Android first?

- Download the APK from the [latest GitHub Release](https://github.com/Throb7777/unipath/releases/latest)
- File name: `UniPATH-v1.0.0.apk`

If you want the Android setup steps first, see [Android/README.md](./Android/README.md).

## 🔄 Example Workflow

One common workflow looks like this:

1. You find a useful article in WeChat or Zhihu.
2. You share it to **UniPATH** on Android.
3. UniPATH sends the task to your local **Forwarding Service**.
4. The local service runs **OpenClaw** to fetch, read, organize, and save the task result.
5. You review the result from Android, the Relay Web UI, or the CLI.

Example flow:

```text
WeChat / Zhihu
  -> UniPATH Android app
  -> Local Forwarding Service
  -> OpenClaw
  -> Android / Web UI / CLI result review
```

This is one typical workflow, not the only one. UniPATH can also be used for other share-to-local processing tasks.

## 🌐 Connection Models

UniPATH keeps the same workflow in each case:

```text
Android app
  -> Forwarding Service
  -> Processing Method
  -> Result Summary
```

The only thing that changes is the address you enter in **Settings**.

- `Android Emulator`
  - Use `http://10.0.2.2:8080`
- `Local Network`
  - Use your computer's LAN IP, such as `http://192.168.1.23:8080`
- `Private Network`
  - Use your Tailscale or ZeroTier relay address, such as `http://100.101.102.103:8080`

If your phone and computer are on different networks, the recommended path is a private network address. This keeps the existing UniPATH flow unchanged and works for OpenClaw, shell-command, and future Processing Methods alike.

## 🌟 What This Project Is

This repository contains two parts that work together:

- [Android](./Android): the Android app that receives shared links and submits tasks
- [relay](./relay): the local Forwarding Service with CLI, Web UI, diagnostics, and task execution

Simple flow:

```text
Android app
  -> Forwarding Service
  -> Processing Method (OpenClaw / Command / Mock)
  -> Result Summary
  -> Android app + Web UI
```

This project is best treated as a local companion tool, not a standalone cloud service.

## ✅ Current Status

- Main success flow has been verified end to end
- Failure and cancellation flows have also been verified end to end
- Android UI, relay Web UI, and diagnostics are available in English and Simplified Chinese
- Best-tested environment:
  - Windows
  - Android Emulator
  - local OpenClaw

Current release position:

- `v1.0.0`

## 📁 Repository Layout

```text
.
├─ Android/   Android app
├─ relay/     Forwarding Service, CLI, Web UI, tests, docs
└─ docs/      Shared terminology and release-facing project notes
```

## 🚀 Fastest First Run

If you want the shortest path, follow these steps in order.

### Step 1. Start the Forwarding Service

Go to [relay/README.md](./relay/README.md) and follow:

1. Create a Python virtual environment
2. Install relay dependencies
3. Run `python -m relay init`
4. Run `python -m relay doctor`
5. Run `python -m relay start`
6. Open `http://127.0.0.1:8080/ui`

### Step 2. Open the Relay Web UI

In the Web UI:

1. Open **Settings**
2. Choose a **Processing Method**
3. If needed, click **Test Processing Method**
4. Click **Save**

### Step 3. Build and Run the Android App

Go to [Android/README.md](./Android/README.md) and follow:

1. Open the `Android/` folder in Android Studio
2. Let Gradle sync
3. Run the app on an emulator or device

### Step 4. Configure the Android App

In the Android app:

1. Open **Settings**
2. Enter the Forwarding Service URL
3. Tap **Test Connection**
4. Choose a **Processing Mode**
5. Tap **Save**

### Step 5. Run a Real Link Test

1. Open a supported article link on Android
2. Share it to this app
3. Check **Forward Status** on Android
4. Check **Tasks** or **Diagnostics** in the Relay Web UI

## 🧭 Which Guide Should I Read?

- Start here if you want the whole project:
  - [README.md](./README.md)
- Read this if you mainly care about the Forwarding Service:
  - [relay/README.md](./relay/README.md)
- Read this if you mainly care about the Android app:
  - [Android/README.md](./Android/README.md)
- Shared wording and button names:
  - [docs/terminology.md](./docs/terminology.md)

## 🔤 Main Terms Used in the Project

These terms are used consistently across Android, relay Web UI, and docs.

| English | 简体中文 |
| --- | --- |
| Forwarding Service | 转发服务 |
| Processing Method | 处理方式 |
| Processing Mode | 处理模式 |
| Current Configuration | 当前配置 |
| Recent Tasks | 近期任务 |
| Step Flow | 处理步骤 |
| Diagnostics | 诊断 |
| Test Connection | 测试连接 |
| Save | 保存 |
| Save and Test | 保存并测试 |
| Cancel Task | 中断任务 |

## 🧪 What Has Been Verified

Verified areas include:

- relay unit tests
- Android build
- Android -> Forwarding Service -> OpenClaw success flow
- Android -> Forwarding Service -> failed task flow
- Android -> Forwarding Service -> cancelled task flow

## 🖥️ Supported and Tested Environments

### Best-tested environment

- Windows
- Android Emulator
- local OpenClaw

### Also verified

- relay core on WSL Ubuntu
- relay core on Docker Linux

### Important note

The strongest end-to-end verification today is still:

- Windows + Android Emulator + local Forwarding Service + local OpenClaw

## ⚠️ Known Limits

- The Android app depends on a running Forwarding Service.
- OpenClaw depends on local command, browser, and gateway availability.
- Raw diagnostic snapshots may keep original English text for troubleshooting.
- Non-Windows relay environments are supported, but the strongest real end-to-end validation is currently on Windows.

## 📚 Extra Documentation

Relay docs:

- [relay/docs/quickstart.md](./relay/docs/quickstart.md)
- [relay/docs/executors.md](./relay/docs/executors.md)
- [relay/docs/android-setup.md](./relay/docs/android-setup.md)
- [relay/docs/troubleshooting.md](./relay/docs/troubleshooting.md)

## 🤝 Open Source Notes

Before contributing or redistributing:

- keep local files such as `relay/.env` and `Android/local.properties` out of version control
- do not commit relay runtime data, logs, or task files
- follow the shared wording in [docs/terminology.md](./docs/terminology.md)

## 📄 License

This project is licensed under the MIT License.

See [LICENSE](./LICENSE).
