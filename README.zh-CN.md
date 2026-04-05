<p align="right">
  🌐 <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

# UniPATH

> 查看英文版：[README.md](./README.md)

> UniPATH: Unified Phone Action Task Hub
>
> 一个本地协同方案：把 Android 上分享的链接交给本机的转发服务，再由 OpenClaw 或其他处理方式继续处理。

## 🌟 这是什么项目

这个仓库包含两个会一起工作的部分：

- [Android](./Android)：接收分享链接并提交任务的 Android 应用
- [relay](./relay)：本地转发服务，提供 CLI、Web UI、诊断和任务执行能力

整体流程很简单：

```text
Android 应用
  -> 转发服务
  -> 处理方式（OpenClaw / 命令处理方式 / 模拟处理方式）
  -> 结果摘要
  -> 回到 Android 应用和 Web UI
```

这个项目更适合被理解为“本地 companion 工具”，而不是一个独立云服务。

## ✅ 当前状态

- 主成功链路已经完成真实端到端验证
- 失败和中断分支也已经完成真实端到端验证
- Android 界面、relay Web UI、诊断信息都支持英文和简体中文
- 当前验证最充分的环境：
  - Windows
  - Android 模拟器
  - 本地 OpenClaw

当前版本定位：

- `v1.0.0`

## 📁 仓库结构

```text
.
├─ Android/   Android 应用
├─ relay/     转发服务、CLI、Web UI、测试、文档
└─ docs/      共享术语表和发布相关说明
```

## 🚀 最短上手路径

如果你想最快跑起来，请按下面顺序操作。

### 第 1 步：启动转发服务

进入 [relay/README.zh-CN.md](./relay/README.zh-CN.md)，按步骤完成：

1. 创建 Python 虚拟环境
2. 安装 relay 依赖
3. 运行 `python -m relay init`
4. 运行 `python -m relay doctor`
5. 运行 `python -m relay start`
6. 打开 `http://127.0.0.1:8080/ui`

### 第 2 步：打开 Relay Web UI

在 Web UI 中：

1. 打开 **设置**
2. 选择一种**处理方式**
3. 如果需要，点击 **测试处理方式**
4. 点击 **保存**

### 第 3 步：构建并运行 Android 应用

进入 [Android/README.zh-CN.md](./Android/README.zh-CN.md)，按步骤完成：

1. 用 Android Studio 打开 `Android/` 目录
2. 等待 Gradle 同步完成
3. 在模拟器或真机上运行应用

### 第 4 步：配置 Android 应用

在 Android 应用中：

1. 打开 **设置**
2. 填写转发服务地址
3. 点击 **测试连接**
4. 选择一个**处理模式**
5. 点击 **保存**

### 第 5 步：跑一次真实链接测试

1. 在 Android 上打开一篇支持的文章链接
2. 通过系统分享发送到本应用
3. 在 Android 里查看 **转发状态**
4. 在 Relay Web UI 里查看 **任务** 或 **诊断**

## 🧭 先看哪份文档

- 想了解整个项目：
  - [README.zh-CN.md](./README.zh-CN.md)
- 想重点使用转发服务：
  - [relay/README.zh-CN.md](./relay/README.zh-CN.md)
- 想重点使用 Android 应用：
  - [Android/README.zh-CN.md](./Android/README.zh-CN.md)
- 想核对统一术语和按钮名称：
  - [docs/terminology.md](./docs/terminology.md)

## 🔤 项目统一术语

下面这些词会尽量在 Android、relay Web UI 和文档里保持一致。

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

## 🧪 已验证内容

已验证的范围包括：

- relay 单元测试
- Android 构建
- Android -> 转发服务 -> OpenClaw 成功链路
- Android -> 转发服务 -> 失败链路
- Android -> 转发服务 -> 中断链路

## 🖥️ 支持与验证环境

### 当前验证最充分的环境

- Windows
- Android 模拟器
- 本地 OpenClaw

### 另外已验证

- WSL Ubuntu 下的 relay 核心
- Docker Linux 下的 relay 核心

### 重要说明

当前最强的完整端到端验证仍然是：

- Windows + Android 模拟器 + 本地转发服务 + 本地 OpenClaw

## ⚠️ 已知限制

- Android 应用不能单独工作，必须配合正在运行的转发服务。
- OpenClaw 依赖本地命令、浏览器和 gateway 环境。
- 为了便于排查问题，原始诊断快照里可能保留英文原文。
- 非 Windows 环境下 relay 核心已验证，但最完整的真实端到端链路主要在 Windows 环境验证。

## 📚 进一步阅读

Relay 相关文档：

- [relay/docs/quickstart.md](./relay/docs/quickstart.md)
- [relay/docs/executors.md](./relay/docs/executors.md)
- [relay/docs/android-setup.md](./relay/docs/android-setup.md)
- [relay/docs/troubleshooting.md](./relay/docs/troubleshooting.md)

## 🤝 开源使用说明

贡献或分发前，请注意：

- 不要把 `relay/.env`、`Android/local.properties` 这类本地文件提交到版本控制
- 不要把 relay 的运行数据、日志和任务文件提交到仓库
- 用户界面和文档中的术语尽量跟 [docs/terminology.md](./docs/terminology.md) 保持一致

## 📄 许可证

本项目使用 MIT License。

详见 [LICENSE](./LICENSE)。
