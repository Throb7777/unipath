# Terminology

This file defines the primary display terms for the project. Use these terms in the Android app, relay Web UI, and end-user guides.

## Style Guide

- Prefer user-facing wording over internal engineering wording.
- Keep text simple, calm, and easy to understand.
- Avoid slang.
- Avoid over-technical phrasing in user-facing UI.
- Use one primary term for one concept.
- Do not translate internal IDs such as `taskId`, `mode id`, `executor id`, or file paths.

## Core Terms

| Internal | English | 简体中文 | Notes |
| --- | --- | --- | --- |
| relay | Forwarding Service | 转发服务 | Main user-facing name for relay. |
| task | Task | 任务 | |
| task_id | Task ID | 任务编号 | |
| recent_tasks | Recent Tasks | 近期任务 | Prefer this over “最近任务” for a steadier tone. |
| timeline | Step Flow | 处理步骤 | Prefer this over the technical word “timeline”. |
| result_summary | Result Summary | 结果摘要 | |
| artifacts | Task Files | 任务文件 | Prefer this over the technical word “artifacts”. |
| runtime_config | Current Configuration | 当前配置 | Prefer this over “runtime config” in normal UI. |
| config_file | Configuration File | 配置文件 | |
| config_source | Configuration Source | 配置来源 | |
| mode | Processing Mode | 处理模式 | |
| default_mode | Default Mode | 默认模式 | |
| executor | Processing Method | 处理方式 | Use this in normal UI. |
| executor_technical | Executor | 执行器 | Use this only in advanced or diagnostic contexts. |
| diagnostics | Diagnostics | 诊断 | |

## Page Names

| Internal | English | 简体中文 |
| --- | --- | --- |
| overview | Overview | 概览 |
| settings | Settings | 设置 |
| tasks | Tasks | 任务 |
| forward_status | Forward Status | 转发状态 |
| full_flow | Full Flow | 完整流程 |

## Task Status

| Status Key | English | 简体中文 |
| --- | --- | --- |
| queued | Queued | 已排队 |
| preparing | Preparing | 准备中 |
| running | Running | 处理中 |
| finalizing | Finalizing | 收尾中 |
| cancelling | Cancelling | 正在中断 |
| cancelled | Cancelled | 已中断 |
| completed | Completed | 已完成 |
| failed | Failed | 已失败 |

## Common Actions

| Internal | English | 简体中文 |
| --- | --- | --- |
| save | Save | 保存 |
| save_and_test | Save and Test | 保存并测试 |
| test_connection | Test Connection | 测试连接 |
| test_executor | Test Processing Method | 测试处理方式 |
| cancel_task | Cancel Task | 中断任务 |
| copy_result | Copy Result | 复制结果 |
| back_home | Back Home | 返回首页 |
| clear | Clear | 清空 |

## Processing Methods

| Method ID | English | 简体中文 |
| --- | --- | --- |
| openclaw | OpenClaw Processing Method | OpenClaw 处理方式 |
| shell_command | Command Processing Method | 命令处理方式 |
| mock | Mock Processing Method | 模拟处理方式 |

## Common Errors

| Error Code | English | 简体中文 |
| --- | --- | --- |
| manual_verification_required | Manual verification required | 需要手动验证 |
| profile_revalidation_required | Verification expired | 验证状态已失效 |
| wechat_parameter_error | WeChat link parameter error | 微信链接参数异常 |
| executor_session_locked | Processing session is busy | 处理会话正忙 |
| executor_network_error | Processing network error | 处理网络错误 |
