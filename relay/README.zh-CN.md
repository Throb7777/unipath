# UniPATH 转发服务

> 这是 UniPATH 配套使用的本地转发服务。它负责接收任务、调用处理方式、保存任务状态，并提供 Web UI 与诊断能力。

## 🌟 Relay 是做什么的

Relay 是整条链路中间的本地服务：

```text
Android 应用
  -> 转发服务
  -> 处理方式
  -> 结果摘要
  -> 回到 Android 应用和 Web UI
```

Relay 提供：

- 本地 HTTP API
- 本地 Web UI
- CLI 命令
- 诊断与冒烟测试
- 任务存储和状态跟踪

## ✅ 已包含的能力

- 任务接收
- 任务状态和中断
- Web UI 页面：
  - `概览`
  - `设置`
  - `任务`
  - `诊断`
- CLI 命令：
  - `init`
  - `doctor`
  - `smoke`
  - `start`
  - `status`
  - `tasks`
- 处理方式：
  - `openclaw`
  - `shell_command`
  - `mock`

## 📦 运行前准备

### 必需

- Python 3.10+
- 一个终端

### 建议准备

- OpenClaw，如果你要跑真实文章处理
- Android 应用，如果你要跑完整移动端链路

## 🚀 第一次运行，按步骤来

这一节按第一次上手来写。

### 第 1 步：在项目根目录打开终端

项目根目录应该包含：

- `Android/`
- `relay/`
- `docs/`

### 第 2 步：创建虚拟环境

Windows PowerShell：

```powershell
cd /你的仓库路径/relay
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS 或 Linux：

```bash
cd /path/to/share-paper/relay
python3 -m venv .venv
source .venv/bin/activate
```

### 第 3 步：安装依赖

```bash
pip install -r requirements.txt
```

如果你也要跑 relay 测试：

```bash
pip install -r requirements-dev.txt
```

### 第 4 步：初始化本地运行目录

在包含 `relay/` 目录的上一级目录执行：

```bash
python -m relay init
```

这一步会创建本地运行目录和默认配置文件。

### 第 5 步：先做一次本地诊断

```bash
python -m relay doctor
```

你会看到类似这些结果：

- `ready`
- `warning`
- `blocked`

如果当前处理方式还没准备好，下一步去 Web UI 里继续配置。

### 第 6 步：启动 Relay

```bash
python -m relay start
```

启动后，Relay 会打印：

- API 地址
- Web UI 地址
- 当前处理方式
- 当前处理模式
- 配置文件路径

### 第 7 步：打开 Web UI

浏览器打开：

```text
http://127.0.0.1:8080/ui
```

### 第 8 步：在 Web UI 中完成设置

在 Web UI 中：

1. 打开 **设置**
2. 选择一种**处理方式**
3. 如果需要，点击 **测试处理方式**
4. 点击 **保存**

### 第 9 步：跑一次冒烟测试

CLI：

```bash
python -m relay smoke mock
```

另外两条也很常用：

```bash
python -m relay smoke shell
python -m relay smoke openclaw
```

## 🧭 Web UI 页面说明

### `概览`

这个页面适合：

- 确认 Relay 是否在运行
- 查看当前处理方式
- 查看当前处理模式
- 快速跳转到 **设置**、**任务**、**诊断**

### `设置`

这个页面适合：

- 切换**处理方式**
- 切换**默认模式**
- 使用 **测试处理方式** 检查当前配置
- 使用 **保存** 或 **保存并测试** 应用变更

### `任务`

这个页面适合：

- 查看近期任务
- 筛选任务
- 打开任务详情
- 用 **中断任务** 停掉一条任务

### `诊断`

这个页面适合：

- 检查当前处理方式是否就绪
- 查看环境检查结果
- 查看环境诊断摘要
- 判断下一步应该做什么

## 🧪 CLI 命令

推荐入口：

```bash
python -m relay <command>
```

可用命令：

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

大多数命令也支持 `--json`。

## ⚙️ 配置模型

Relay 使用两层配置。

### 1. 启动配置

来源：

- `.env`
- 进程环境变量

用途：

- host
- port
- 工作目录
- Web UI 暴露方式

### 2. 当前配置

来源：

- `runtime/data/config.json`

用途：

- 当前处理方式
- 默认模式
- 各处理方式自己的参数

## 🧩 处理方式说明

### `openclaw`

适合：

- 真实文章处理
- 浏览器辅助抓取
- 真实结果提取

### `shell_command`

适合：

- 接入受信任的本地脚本
- 简单命令链路
- 轻量自定义集成

### `mock`

适合：

- 冒烟测试
- UI 测试
- 不跑真实处理工具时验证整条链路

## 📂 运行时文件

Relay 会把本地运行文件放在 `runtime/` 下。

重要位置：

- `runtime/data/config.json`
- `runtime/data/relay.sqlite3`
- `runtime/logs/relay.log`
- `runtime/tasks/<taskId>/`

## 🖥️ Android 如何连接 Relay

Android 应用只需要填写 Relay 的基础地址。

例如：

- Android 模拟器连接 Windows 主机：
  - `http://10.0.2.2:8080`
- Android 真机连接局域网内电脑：
  - `http://<你的局域网 IP>:8080`

## ✅ 验证

运行 relay 测试：

```bash
python -m unittest discover -s tests -v
```

## ⚠️ 已知限制

- OpenClaw 依赖本地命令、浏览器和 gateway 环境。
- 当前最强的真实端到端验证仍然集中在 Windows 环境。
- 为了方便排查，原始诊断信息可能保留英文原文。

## 📚 进一步阅读

- [docs/quickstart.md](./docs/quickstart.md)
- [docs/executors.md](./docs/executors.md)
- [docs/android-setup.md](./docs/android-setup.md)
- [docs/troubleshooting.md](./docs/troubleshooting.md)
- [docs/relay-core.md](./docs/relay-core.md)
- [docs/executor-contract.md](./docs/executor-contract.md)
- [docs/mode-definition.md](./docs/mode-definition.md)

## 📄 许可证

本项目使用 MIT License。
