<p align="right">
  🌐 <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

# UniPATH Android

> Looking for Chinese? See [README.zh-CN.md](./README.zh-CN.md).

> The Android app for UniPATH. It receives shared links, submits them to the local Forwarding Service, and shows task status back to the user.

## 🌟 What This App Does

The app is designed for this flow:

1. You share a link from another Android app
2. This app receives the shared text
3. The app sends the task to the local Forwarding Service
4. The Forwarding Service runs the selected Processing Method
5. The app shows **Forward Status**, **Recent Tasks**, and the final **Result Summary**

## ✅ Main Screens

These names match the UI:

- `Home`
- `Settings`
- `Forward Status`
- `Full Flow`

Important buttons:

- `Test Connection`
- `Save`
- `Cancel Task`
- `Copy Result`
- `View Full Flow`

## 📦 What You Need

### Required

- Android Studio
- Android SDK
- a running Forwarding Service

### Optional but recommended

- Android Emulator
- local OpenClaw environment, if you want real processing

## 🚀 Build and Run, Step by Step

### Step 1. Open the Android project

Open the `Android/` folder in Android Studio.

### Step 2. Let Android Studio sync Gradle

Wait until:

- Gradle sync completes
- SDK components are resolved

### Step 3. Check `local.properties`

Android Studio usually creates this automatically.

This file should point to your local Android SDK.

Important:

- keep `local.properties` local
- do not commit it to version control

### Step 4. Run the app

Choose one:

- Android Emulator
- physical Android device

Then click **Run** in Android Studio.

## 🔧 First-Time Setup in the App

After the app opens, do this in order.

### Step 1. Open `Settings`

In the app, tap **Settings**.

### Step 2. Enter the Forwarding Service URL

Fill in the Forwarding Service base URL.

Common values:

- Android Emulator to Windows host:
  - `http://10.0.2.2:8080`
- physical phone to local computer:
  - `http://<your-lan-ip>:8080`
- physical phone to a computer on another network:
  - `http://<your-tailscale-or-zerotier-ip>:8080`

### Step 3. Tap `Test Connection`

This checks:

- whether the Forwarding Service can be reached
- whether the list of Processing Modes can be fetched

### Step 4. Choose a `Processing Mode`

After the connection test succeeds, choose a Processing Mode.

### Step 5. Tap `Save`

This stores the settings locally in the app.

## 🌐 Use UniPATH on Different Networks

If your phone and computer are not on the same Wi-Fi, keep the same UniPATH flow and switch only the relay address.

Recommended approach:

1. Install Tailscale on the computer that runs relay
2. Install Tailscale on the Android phone
3. Sign in to the same Tailscale account on both devices
4. Make sure relay is listening on `0.0.0.0:8080`
5. Copy the computer's Tailscale address
6. In UniPATH **Settings**, choose **Private Network**
7. Enter `http://<your-tailscale-ip>:8080`
8. Tap **Test Connection**
9. Choose a **Processing Mode**
10. Tap **Save**

Notes:

- `0.0.0.0` is only a bind address for relay. Do not type it into the Android app.
- `localhost` and `127.0.0.1` only work on the same device.
- The same private-network setup also works for ZeroTier or another equivalent private network tool.

## 📱 How to Run a Real Test

### Step 1. Open a supported article link

For example, a WeChat article link.

### Step 2. Share the link to this app

Use Android system share, then select this app.

### Step 3. Confirm the submission

The app will show:

- source
- normalized link
- current Processing Mode

Then tap **Submit**.

### Step 4. Watch `Forward Status`

You can then check:

- current state
- Result Summary
- Step Flow
- Follow-up Advice

### Step 5. Open `Full Flow` if needed

Use **View Full Flow** when you want the complete step history.

## UI Automation Helper

For the Windows emulator workflow in this repository, you can also run:

```powershell
./scripts/run_android_ui_e2e.ps1
```

This helper will:

- start a temporary mock relay
- install the debug APK
- inject relay test settings into the app
- launch the Android share flow
- submit a test link
- verify that the relay task completes

## 🧭 What Each Screen Is For

### `Home`

Use it to:

- see current Forwarding Service settings
- see `Recent Tasks`
- reopen a task quickly

### `Settings`

Use it to:

- change the Forwarding Service URL
- tap `Test Connection`
- choose a Processing Mode
- change the app language
- tap `Save`

### `Forward Status`

Use it to:

- see the current state
- read the Result Summary
- read Follow-up Advice
- copy the diagnostic summary
- cancel a task with `Cancel Task`

### `Full Flow`

Use it to:

- inspect the full Step Flow
- understand where a task stopped or failed

## 🧪 Build Outputs

If you want a local debug APK, build from Android Studio or run:

```bash
./gradlew assembleDebug
```

Windows:

```powershell
.\gradlew.bat assembleDebug
```

## ⚠️ Important Notes

- This app depends on a running Forwarding Service.
- The app alone does not perform article processing.
- Real article processing depends on the selected Processing Method in Relay.

## 🧩 Consistent Terms

This project uses these terms consistently:

| English | 简体中文 |
| --- | --- |
| Forwarding Service | 转发服务 |
| Processing Method | 处理方式 |
| Processing Mode | 处理模式 |
| Recent Tasks | 近期任务 |
| Step Flow | 处理步骤 |
| Diagnostics | 诊断 |

See also:

- [../docs/terminology.md](../docs/terminology.md)

## 📄 License

This project is licensed under the MIT License.
