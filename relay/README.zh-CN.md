<p align="right">
  🌐 <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

# UniPATH 转发服务

> 查看英文版：[README.md](./README.md)

UniPATH 转发服务是整个本地工作流里的任务中枢。它负责：

- 接收 Android 端提交的分享任务
- 调用处理方式执行任务
- 保存任务状态和结果
- 提供 Web UI、CLI 和诊断能力

---

## 这项服务做什么

整体链路如下：

```text
Android App
  -> 转发服务
  -> 处理方式（OpenClaw / 命令处理方式 / 模拟处理方式）
  -> 结果摘要
  -> 回到 Android App 和 Web UI
```

它更像一个本地 companion 服务，而不是一个公共云服务。

---

## 第一次运行

### 1. 进入 relay 目录

```powershell
cd relay
```

### 2. 创建虚拟环境

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

如果你还要跑测试：

```bash
pip install -r requirements-dev.txt
```

### 4. 初始化运行目录

```bash
python -m relay init
```

### 5. 先做一次诊断

```bash
python -m relay doctor
```

### 6. 启动服务

```bash
python -m relay start
```

启动后默认地址通常是：

- API / Web UI：`http://127.0.0.1:8080`

---

## Web UI

启动后可以打开：

```text
http://127.0.0.1:8080/ui
```

常用页面：

- `概览`
- `设置`
- `任务`
- `诊断`

---

## 连接方式

UniPATH 转发服务现在支持 3 类常见连接方式。

### 1. Android 模拟器

Android 模拟器访问电脑上的 relay 时，填：

```text
http://10.0.2.2:8080
```

### 2. 同一局域网

如果手机和电脑在同一个 Wi‑Fi 下，手机里填：

```text
http://<你的电脑局域网 IP>:8080
```

例如：

```text
http://192.168.1.23:8080
```

### 3. 不同网络 / 私网访问

如果手机和电脑不在同一个普通局域网，推荐使用：

- Tailscale
- ZeroTier

此时手机里填电脑的私网地址，例如：

```text
http://100.101.102.103:8080
```

### 重要说明

- `0.0.0.0:8080` 只是 relay 的监听方式，不是手机里要填写的访问地址。
- 如果你要让其他设备访问 relay，服务端应监听在 `0.0.0.0` 或其他可达网卡地址上。
- 真机异网访问时，建议同时配置 `AUTH_TOKEN`。

---

## 私网 relay（Tailscale / ZeroTier）

如果你想在异网下继续使用现有流程：

```text
Android App -> relay -> executor
```

最推荐的是把 relay 作为一个“私有远程入口”来访问。

### 步骤

1. 在电脑上安装 Tailscale 或 ZeroTier
2. 在手机上安装同一个私网工具
3. 用同一个账号或同一私网网络登录
4. 确认电脑拿到了一个私网地址
5. 让 relay 监听 `0.0.0.0:8080`
6. 在 Android 设置里填写：
   - `http://<私网地址>:8080`
7. 点击 `Test Connection`

### 安全建议

- 私网或公网访问时，建议开启 `AUTH_TOKEN`
- 不建议把无认证的 relay 直接暴露到公网

---

## Settings 页面

在 Web UI 的 `设置` 页里，你可以：

- 选择默认模式
- 选择处理方式
- 测试处理方式
- 配置 OpenClaw 参数
- 配置命令处理方式
- 新建和测试自定义模式

---

## 自定义模式

现在第一版已经支持在 `设置` 页直接创建轻量自定义模式。

### 当前范围

- 自定义模式当前通过 `shell_command` 执行
- 每个自定义模式都可以保存自己的：
  - 名称
  - 描述
  - 命令模板
  - 超时秒数

### 适合做什么

- 保存文章
- 调自己的本地脚本
- 把链接送给别的 CLI 工具

### 测试方式

在同一页面里可以直接填写：

- 测试 URL
- 测试来源
- 测试文本

然后点击 `测试模式`，页面会返回：

- 状态
- 结果摘要
- 渲染后的命令预览

---

## CLI 常用命令

```bash
python -m relay init
python -m relay doctor
python -m relay doctor --short
python -m relay smoke mock
python -m relay smoke shell
python -m relay smoke openclaw
python -m relay start
python -m relay status
python -m relay config show
python -m relay config path
python -m relay tasks list
python -m relay tasks show <taskId>
python -m relay tasks cancel <taskId>
```

---

## 冒烟测试

### mock

```bash
python -m relay smoke mock
```

### shell

```bash
python -m relay smoke shell
```

### openclaw

```bash
python -m relay smoke openclaw
```

---

## 诊断页

诊断页会告诉你：

- 当前处理方式是否可用
- relay 是否只监听在本机
- 私网 / 远程访问是否准备好
- 是否已经配置认证
- 建议下一步怎么做

---

## 当前定位

当前版本更适合：

- 本地优先
- 自己掌控数据和执行环境
- Android 负责采集与提交
- relay 负责调度和执行

如果你想异网使用，优先推荐：

1. Tailscale / ZeroTier
2. 再考虑公网反代或 tunnel

