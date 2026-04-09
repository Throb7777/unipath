from __future__ import annotations

from datetime import datetime
import ipaddress
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Iterable
from urllib.parse import urlparse

from app.models import TaskRecord
from app.user_facing import advice_for_error, result_summary_for_output


def format_duration_ms(duration_ms: int | None, lang: str = "en") -> str:
    if duration_ms is None:
        return "-"
    total_seconds = max(0, int(duration_ms / 1000))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if lang == "zh-CN":
        if hours:
            return f"{hours}小时 {minutes}分 {seconds}秒"
        if minutes:
            return f"{minutes}分 {seconds}秒"
        return f"{seconds}秒"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_iso_local(iso_value: str | None) -> str:
    if not iso_value:
        return "-"
    try:
        return datetime.fromisoformat(iso_value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso_value


def summarize_task_rows(tasks: Iterable[TaskRecord], lang: str = "en") -> list[dict]:
    rows: list[dict] = []
    source_cache: dict[str, str] = {}
    stage_cache: dict[tuple[str, str], str] = {}
    target_cache: dict[tuple[str, str], str] = {}
    summary_cache: dict[tuple[str, str, str, str, str, str, str, str], str] = {}
    for task in tasks:
        status = task.to_status_response()
        source_label_value = source_cache.setdefault(task.source, source_label(task.source, lang=lang))
        stage_key = (task.status, task.stage_label)
        stage_label = stage_cache.setdefault(stage_key, localize_stage_label(task.status, task.stage_label, lang=lang))
        target_key = (task.normalized_url, task.source)
        target = target_cache.setdefault(target_key, summarize_target(task.normalized_url, task.source, lang=lang))
        summary_key = (
            task.status,
            task.error_code,
            task.result_summary,
            task.error_message,
            task.relay_message,
            task.mode,
            task.executor_kind,
            task.normalized_url,
        )
        summary = summary_cache.setdefault(summary_key, summarize_result(task, status=status, lang=lang))
        rows.append(
            {
                "task_id": task.task_id,
                "mode": task.mode,
                "source": task.source,
                "source_label": source_label_value,
                "status": task.status,
                "stage_label": stage_label,
                "status_tone": status_tone(task.status),
                "created_at": format_iso_local(task.created_at),
                "updated_at": format_iso_local(task.updated_at),
                "duration": format_duration_ms(status.durationMs, lang=lang),
                "relay_message": task.relay_message,
                "executor_kind": task.executor_kind,
                "can_cancel": status.canCancel,
                "target": target,
                "summary": summary,
            }
        )
    return rows


def status_tone(status: str) -> str:
    if status in {"completed"}:
        return "ok"
    if status in {"failed", "cancelled"}:
        return "danger"
    if status in {"cancelling", "running", "finalizing", "preparing"}:
        return "warn"
    return "neutral"


def source_label(source: str, lang: str = "en") -> str:
    if source == "wechat_article":
        return "WeChat"
    if source == "xiaohongshu":
        return "小红书" if lang == "zh-CN" else "Xiaohongshu"
    return source.replace("_", " ").title()


def summarize_target(normalized_url: str, source: str, lang: str = "en") -> str:
    parsed = urlparse(normalized_url)
    host = (parsed.netloc or "").replace("www.", "").strip()
    if host:
        return host
    if source == "wechat_article":
        return "mp.weixin.qq.com"
    if source == "xiaohongshu":
        return "xiaohongshu.com"
    return "未知目标" if lang == "zh-CN" else "Unknown target"


def summarize_result(task: TaskRecord, *, status=None, lang: str = "en") -> str:
    if status is None:
        status = task.to_status_response()
    problem_title = localize_problem_title(task.status, task.error_code, status.problemTitle, lang=lang)
    actions = localize_suggested_actions(task.status, task.error_code, status.suggestedActions, lang=lang)
    first_action = next((item.strip() for item in actions if item and item.strip()), "")
    if problem_title and task.status in {"failed", "cancelled"}:
        if first_action:
            return f"{problem_title} {'后续建议：' if lang == 'zh-CN' else 'Next:'} {first_action}"
        return problem_title

    advice = advice_for_error(task.error_code)
    if advice is not None:
        return localize_problem_title(task.status, task.error_code, advice.title, lang=lang)
    normalized_summary = result_summary_for_output(
        mode=task.mode,
        executor_kind=task.executor_kind,
        raw_summary=task.result_summary,
        normalized_url=task.normalized_url,
        fallback_message=task.relay_message,
    )
    if normalized_summary.strip():
        return localize_result_summary(normalized_summary, lang=lang)
    for value in (task.result_summary, task.error_message, task.relay_message, task.stage_label):
        text = (value or "").strip()
        if text:
            return localize_dynamic_text(text, lang=lang)
    return "-"


def localize_task_status(task, lang: str = "en"):
    problem_title = localize_problem_title(task.status, task.errorCode, task.problemTitle, lang=lang)
    suggested_actions = localize_suggested_actions(task.status, task.errorCode, task.suggestedActions, lang=lang)
    localized_timeline = [
        {
            **entry.model_dump(),
            "label": localize_timeline_label(entry.stepId, entry.label, lang=lang),
            "message": localize_dynamic_text(entry.message, lang=lang),
        }
        for entry in task.timeline
    ]
    localized_diagnostic_summary = build_localized_diagnostic_summary(task, lang=lang)
    return task.model_copy(
        update={
            "stageLabel": localize_stage_label(task.status, task.stageLabel, lang=lang),
            "resultSummary": localize_result_summary(task.resultSummary, lang=lang),
            "relayMessage": localize_dynamic_text(task.relayMessage, lang=lang),
            "problemTitle": problem_title,
            "suggestedActions": suggested_actions,
            "diagnosticSummary": localized_diagnostic_summary,
            "timeline": localized_timeline,
        }
    )


def localize_diagnostic_report(report: dict[str, object], *, lang: str = "en") -> dict[str, object]:
    localized = dict(report)
    localized["status"] = localize_dynamic_text(str(report.get("status", "")), lang=lang)
    localized["summary"] = localize_dynamic_text(str(report.get("summary", "")), lang=lang)
    localized["blockers"] = [_localize_diagnostic_item(item, lang=lang) for item in report.get("blockers", [])]
    localized["items"] = [_localize_diagnostic_item(item, lang=lang) for item in report.get("items", [])]
    localized["sections"] = [
        {
            **section,
            "items": [_localize_diagnostic_item(item, lang=lang) for item in section.get("items", [])],
        }
        for section in report.get("sections", [])
    ]
    return localized


def localize_environment_summary(summary: str, *, lang: str = "en") -> str:
    return "\n".join(localize_dynamic_text(line, lang=lang) for line in summary.splitlines()).strip()


def localize_problem_title(status: str, error_code: str, raw_title: str, *, lang: str = "en") -> str:
    if lang != "zh-CN":
        return (raw_title or "").strip()
    mapped = {
        "manual_verification_required": "需要手动验证",
        "profile_revalidation_required": "需要重新验证",
        "wechat_parameter_error": "链接参数异常",
        "wechat_body_too_short": "文章正文过短",
        "executor_session_locked": "处理方式正忙",
        "executor_network_error": "网络或上游请求失败",
        "executor_auth_error": "认证尚未准备好",
        "executor_timeout": "处理已超时",
        "executor_start_failed": "无法启动处理方式",
        "executor_command_not_found": "未找到处理命令",
        "executor_command_not_configured": "命令模板尚未配置",
        "executor_nonzero_exit": "处理命令返回错误",
        "executor_reported_failure": "处理方式返回了失败结果",
    }.get((error_code or "").strip())
    if mapped:
        return mapped
    status_map = {
        "completed": "任务已完成",
        "cancelled": "任务已中断",
        "failed": "任务处理失败",
        "cancelling": "正在中断任务",
    }
    return status_map.get((status or "").strip(), "") or localize_dynamic_text(raw_title, lang=lang)


def localize_suggested_actions(status: str, error_code: str, actions: list[str], *, lang: str = "en") -> list[str]:
    if lang != "zh-CN":
        return [item for item in actions if item]
    mapped = {
        "manual_verification_required": [
            "请在受管浏览器中打开文章并完成验证。",
            "验证完成后，再重新提交任务。",
        ],
        "profile_revalidation_required": [
            "请在受管浏览器 profile 中重新打开这篇文章。",
            "重新完成验证或登录后，再重试任务。",
        ],
        "wechat_parameter_error": [
            "请回到原始文章页面，重新分享原始链接。",
            "重新提交时尽量避免使用已失效或被缩短的分享页。",
        ],
        "wechat_body_too_short": [
            "请先在受管浏览器中打开文章，并确认正文已完整加载。",
            "正文可见后，再重新重试任务。",
        ],
        "executor_session_locked": [
            "请等待当前任务结束，让转发服务自动重试。",
            "尽量避免同时对同一个目标发起多条任务。",
        ],
        "executor_network_error": [
            "请检查本机当前的网络或代理设置。",
            "网络恢复稳定后，再重试任务。",
        ],
        "executor_auth_error": [
            "请检查本地工具的登录状态或 API Key 配置。",
            "先运行一次诊断，再重新重试。",
        ],
        "executor_timeout": [
            "可以先重试一次，确认这次超时是否只是临时问题。",
            "只有在这类任务本来就会运行更久时，才建议调大超时时间。",
        ],
        "executor_start_failed": [
            "请检查命令路径和本地工具安装是否正确。",
            "可先打开诊断页或运行 relay doctor 确认环境。",
        ],
        "executor_command_not_found": [
            "请到设置里填写正确的命令路径。",
            "如果只是做冒烟测试，可以改用模拟处理方式或命令处理方式。",
        ],
        "executor_command_not_configured": [
            "请到设置中补充一条可信的命令模板。",
            "如果暂时不打算用自定义命令，可以切换到其他处理方式。",
        ],
        "executor_nonzero_exit": [
            "请打开任务文件，检查 stdout.txt 和 stderr.txt。",
            "修正底层命令错误后，再重试任务。",
        ],
        "executor_reported_failure": [
            "请先查看结果摘要和任务文件，确认失败原因。",
            "只有确认原因是临时问题或已经修正后，再重试任务。",
        ],
    }.get((error_code or "").strip())
    if mapped:
        return mapped
    status_map = {
        "completed": ["如果你需要完整输出，可以查看结果摘要或任务文件。", "如果还要继续处理，可以按当前设置再次提交任务。"],
        "cancelled": ["如果你想确认任务停在了哪一步，可以打开任务详情查看。", "准备好之后，可以重新提交这条任务。"],
        "queued": ["请等待当前步骤完成；如果不再需要这条任务，也可以直接中断。"],
        "preparing": ["请等待当前步骤完成；如果不再需要这条任务，也可以直接中断。"],
        "running": ["请等待当前步骤完成；如果不再需要这条任务，也可以直接中断。"],
        "finalizing": ["请等待当前步骤完成；如果不再需要这条任务，也可以直接中断。"],
        "cancelling": ["请等待当前步骤完成；如果不再需要这条任务，也可以直接中断。"],
        "failed": ["请先打开任务文件或诊断摘要，查看更详细的原因。", "确认可能原因后，再决定是否重试。"],
    }.get((status or "").strip())
    if status_map:
        return status_map
    return [localize_dynamic_text(item, lang=lang) for item in actions if item]


def localize_stage_label(status: str, raw_label: str, *, lang: str = "en") -> str:
    if lang != "zh-CN":
        return raw_label
    mapped = {
        "queued": "已排队",
        "preparing": "准备任务",
        "running": "处理中",
        "finalizing": "整理结果",
        "cancelling": "正在中断",
        "completed": "已完成",
        "failed": "已失败",
        "cancelled": "已中断",
    }.get((status or "").strip())
    return mapped or localize_dynamic_text(raw_label, lang=lang)


def localize_timeline_label(step_id: str, raw_label: str, *, lang: str = "en") -> str:
    if lang != "zh-CN":
        return raw_label
    mapped = {
        "queued": "已排队",
        "preparing": "准备任务",
        "running": "运行处理方式",
        "finalizing": "整理结果",
        "failed": "已失败",
        "cancelled": "已中断",
        "cancelling": "已请求中断",
    }.get((step_id or "").strip())
    if mapped:
        return mapped
    return localize_dynamic_text(raw_label, lang=lang)


def build_localized_diagnostic_summary(task, *, lang: str = "en") -> str:
    if lang != "zh-CN":
        return task.diagnosticSummary
    lines = [
        f"任务编号：{task.taskId}",
        f"状态：{localize_stage_label(task.status, task.stageLabel, lang=lang)}",
        f"处理模式：{task.mode}",
        f"来源：{source_label(task.source, lang=lang)}",
        f"处理方式：{task.executorKind or '-'}",
        f"准备后的链接：{task.normalizedUrl}",
    ]
    if task.durationMs is not None:
        lines.append(f"耗时：{format_duration_ms(task.durationMs, lang=lang)}")
    if task.errorCode:
        lines.append(f"错误代码：{task.errorCode}")
    message = localize_dynamic_text(task.errorMessage or task.relayMessage, lang=lang)
    if message:
        lines.append(f"说明：{message}")
    actions = localize_suggested_actions(task.status, task.errorCode, task.suggestedActions, lang=lang)
    if actions:
        lines.append("后续建议：")
        lines.extend(f"- {item}" for item in actions[:3])
    if task.timeline:
        lines.append("最近步骤：")
        for entry in task.timeline[-3:]:
            label = localize_timeline_label(entry.stepId, entry.label, lang=lang)
            lines.append(f"- {label} ({entry.at or '-'})")
    return "\n".join(lines)


def localize_dynamic_text(text: str, *, lang: str = "en") -> str:
    text = (text or "").strip()
    if not text or lang != "zh-CN":
        return text
    translated = _translate_result_summary_line(text)
    if translated != text:
        return translated
    if text == "Remote or private-network access is not ready":
        return "异网或私网访问尚未准备好"
    if text == "Remote or private-network access still needs protection":
        return "异网或私网访问仍缺少保护"
    if text == "Remote or private-network access looks ready":
        return "异网或私网访问看起来已经就绪"
    if text.startswith("Relay is listening on ") and text.endswith(". Another device cannot reach this bind address yet."):
        bind = text.removeprefix("Relay is listening on ").removesuffix(". Another device cannot reach this bind address yet.")
        return f"relay 当前监听在 {bind}，其他设备暂时还无法访问这个地址。"
    if text.startswith("Relay is reachable on ") and text.endswith(", but AUTH_TOKEN is still empty."):
        bind = text.removeprefix("Relay is reachable on ").removesuffix(", but AUTH_TOKEN is still empty.")
        return f"relay 已经可以通过 {bind} 被访问，但 AUTH_TOKEN 仍然为空。"
    if text.startswith("Relay is reachable on ") and text.endswith(" and auth token protection is enabled."):
        bind = text.removeprefix("Relay is reachable on ").removesuffix(" and auth token protection is enabled.")
        return f"relay 已经可以通过 {bind} 被访问，并且认证 token 保护已启用。"
    if text == "Set HOST=0.0.0.0 or another reachable interface before using a phone or private-network client.":
        return "在手机或私网客户端接入前，请先把 HOST 设成 0.0.0.0 或其他可访问的接口地址。"
    if text == "Keep AUTH_TOKEN enabled before exposing relay beyond the local machine.":
        return "在 relay 暴露到本机以外之前，请保持 AUTH_TOKEN 已启用。"
    if text == "Set AUTH_TOKEN before using relay from another device, a Tailscale network, or a public URL.":
        return "在其他设备、Tailscale 网络或公网地址访问 relay 前，请先配置 AUTH_TOKEN。"
    if text == "Retest the Android connection after saving the token and updating the app settings.":
        return "保存 token 并更新 Android 设置后，再重新测试一次连接。"
    if text.startswith("Relay Bind: "):
        return f"Relay 绑定地址：{text.removeprefix('Relay Bind: ')}"
    if text.startswith("Remote Access: "):
        state = text.removeprefix("Remote Access: ")
        return f"异网访问：{'已就绪' if state == 'ready' else '仍需配置' if state == 'needs setup' else state}"
    return {
        "ok": "正常",
        "warning": "警告",
        "blocked": "阻塞",
        "Relay is ready.": "转发服务已就绪。",
        "Relay is running with setup warnings.": "转发服务正在运行，但仍有配置提醒。",
        "Relay is blocked by an environment issue.": "转发服务被环境问题阻塞。",
        "Runtime": "运行环境",
        "Configuration": "配置",
        "Processing Method": "处理方式",
        "Runtime directory is ready": "运行目录已就绪",
        "Runtime directory is not writable": "运行目录不可写",
        "Database is ready": "数据库已就绪",
        "Database is not ready": "数据库尚未就绪",
        "Web UI is enabled": "Web 界面已启用",
        "Web UI is disabled": "Web 界面已禁用",
        "Processing method looks ready": "处理方式已基本就绪",
        "Selected processing method needs setup": "当前处理方式仍需配置",
        "Processing command was not found": "未找到处理命令",
        "Command template is missing": "命令模板尚未配置",
        "Processing could not start": "无法启动处理方式",
        "Processing timed out": "处理已超时",
        "Processing method is busy": "处理方式正忙",
        "Network or provider request failed": "网络或上游请求失败",
        "Authentication is not ready": "认证尚未准备好",
        "Processing command exited with an error": "处理命令返回错误",
        "Processing method reported a failure": "处理方式返回了失败结果",
        "Manual verification required": "需要手动验证",
        "Managed browser needs verification again": "需要重新验证受管浏览器",
        "WeChat link is no longer valid": "微信链接已失效",
        "Article body was too short": "文章正文过短",
        "WeChat returned a verification step instead of the article body.": "微信返回的是验证步骤，而不是文章正文。",
        "The saved WeChat verification or login state appears to have expired.": "之前保存的微信验证或登录状态似乎已经失效。",
        "WeChat returned a parameter error page instead of the original article.": "微信返回了参数错误页，而不是原始文章。",
        "The fetched page text did not look like a full WeChat article body.": "抓取到的页面文本不像一篇完整的微信文章正文。",
        "The current OpenClaw lane is already being used by another task.": "当前 OpenClaw 通道已被其他任务占用。",
        "The processing method could not reach its upstream service.": "处理方式无法连接到上游服务。",
        "The selected processing method is missing valid authentication.": "当前处理方式缺少有效认证。",
        "The task ran longer than the configured timeout window.": "任务运行时间超过了当前超时设置。",
        "Relay could not launch the selected processing method.": "relay 无法启动当前处理方式。",
        "Relay could not resolve the configured command on this machine.": "relay 无法在当前机器上解析已配置的命令。",
        "The shell-command processing method does not have a command template yet.": "命令处理方式尚未配置命令模板。",
        "The selected processing method started, but returned a failure code.": "处理方式已经启动，但返回了失败退出码。",
        "The task finished, but the processing method reported a failed result.": "任务已结束，但处理方式返回了失败结果。",
        "Open the article in the managed browser and finish the verification step.": "请在受管浏览器中打开文章并完成验证步骤。",
        "Submit the task again after verification succeeds.": "验证完成后，再重新提交任务。",
        "Open the article again in the managed browser profile.": "请在受管浏览器 profile 中重新打开这篇文章。",
        "Complete verification or sign in again, then retry the task.": "重新完成验证或登录后，再重试任务。",
        "Go back to the original article and share the article link again.": "请回到原始文章页面，重新分享文章链接。",
        "Avoid shortened or expired share pages when resubmitting.": "重新提交时尽量避免使用已失效或被缩短的分享页。",
        "Open the article once in the managed browser and make sure it loads fully.": "请先在受管浏览器中打开文章，并确认正文已完整加载。",
        "Retry the task after the article body is visible.": "正文可见后，再重新重试任务。",
        "Wait for the current run to finish and let the relay retry automatically.": "请等待当前任务结束，让 relay 自动重试。",
        "Avoid starting multiple tasks against the same OpenClaw target at the same time.": "尽量避免同时对同一个 OpenClaw 目标发起多条任务。",
        "Check the current network or proxy settings on this machine.": "请检查本机当前的网络或代理设置。",
        "Retry the task after the network path is stable again.": "网络恢复稳定后，再重试任务。",
        "Check the local tool login or API key configuration.": "请检查本地工具的登录状态或 API Key 配置。",
        "Run the diagnostics view or relay doctor before retrying.": "重试前，建议先打开诊断页或运行 relay doctor。",
        "Retry the task once to confirm whether the timeout was temporary.": "可以先重试一次，确认这次超时是否只是临时问题。",
        "Increase the timeout only if this task type is expected to run longer.": "只有在这类任务本来就会运行更久时，才建议调大超时时间。",
        "Check the configured command path and local tool installation.": "请检查命令路径和本地工具安装是否正确。",
        "Use relay doctor or Web UI Diagnostics to confirm the environment.": "可先运行 relay doctor 或打开 Web 诊断页确认环境。",
        "Set the correct command path in Settings.": "请到设置里填写正确的命令路径。",
        "Switch to the mock or shell-command processing method if you only need a smoke test.": "如果只是做冒烟测试，可以改用模拟处理方式或命令处理方式。",
        "Open Settings and add a trusted command template.": "请到设置中补充一条可信的命令模板。",
        "Switch to another processing method if you do not plan to use a custom command.": "如果暂时不打算用自定义命令，可以切换到其他处理方式。",
        "Open the task files and inspect stdout.txt and stderr.txt.": "请打开任务文件，检查 stdout.txt 和 stderr.txt。",
        "Fix the underlying command error, then retry the task.": "修正底层命令错误后，再重试任务。",
        "Review the result summary and task files for the reported reason.": "请先查看结果摘要和任务文件，确认失败原因。",
        "Retry only after confirming the cause is temporary or corrected.": "只有确认原因是临时问题或已经修正后，再重试任务。",
        "Default mode is compatible": "默认模式匹配当前处理方式",
        "Default mode does not match the selected processing method": "默认模式与当前处理方式不匹配",
        "Current Blockers:": "当前阻塞项：",
        "Current Blockers: none": "当前阻塞项：无",
        "Next: Submit a smoke test or a real task.": "下一步：运行一次冒烟测试，或直接提交真实任务。",
        "Check WORKSPACE_DIR and make sure the relay process can write to it.": "请检查 WORKSPACE_DIR，并确认 relay 进程拥有写入权限。",
        "Make sure the runtime data directory exists and that no other process is locking relay.sqlite3.": "请确认 runtime 数据目录存在，且没有其他进程锁住 relay.sqlite3。",
        "Enable WEB_UI_ENABLED if you want to manage relay from the browser.": "如果你希望通过浏览器管理 relay，请启用 WEB_UI_ENABLED。",
        "Open Settings and switch to a mode supported by the selected processing method.": "请打开设置，切换到当前处理方式支持的模式。",
    }.get(text, text)


def _translate_result_summary_line(text: str) -> str:
    if text == "Highlights:":
        return "要点："
    if text == "Link processed successfully.":
        return "链接已处理完成。"
    if text == "No explicitly mentioned papers found.":
        return "未发现文中明确提到的论文。"
    if text == "No clearly related papers found.":
        return "未发现明显相关的论文。"
    if text.startswith("Found ") and text.endswith(" explicitly mentioned paper."):
        count = text.removeprefix("Found ").removesuffix(" explicitly mentioned paper.")
        return f"发现 {count} 篇文中明确提到的论文。"
    if text.startswith("Found ") and text.endswith(" explicitly mentioned papers."):
        count = text.removeprefix("Found ").removesuffix(" explicitly mentioned papers.")
        return f"发现 {count} 篇文中明确提到的论文。"
    if text.startswith("No explicit papers found. ") and text.endswith(" possible papers detected."):
        count = text.removeprefix("No explicit papers found. ").removesuffix(" possible papers detected.")
        return f"未发现文中明确提到的论文，但识别到 {count} 篇可能相关的论文。"
    if text.startswith("- Topic: "):
        return f"- 主题：{text.removeprefix('- Topic: ')}"
    if text.startswith("- Takeaway: "):
        return f"- 结论：{text.removeprefix('- Takeaway: ')}"
    if text.startswith("- Note: "):
        return f"- 说明：{text.removeprefix('- Note: ')}"
    if text.startswith("- Paper: "):
        return f"- 论文：{text.removeprefix('- Paper: ')}"
    if text.startswith("- Possible: "):
        return f"- 可能相关：{text.removeprefix('- Possible: ')}"
    return text


def localize_result_summary(text: str, *, lang: str = "en") -> str:
    if lang != "zh-CN":
        return text
    return "\n".join(_translate_result_summary_line(line) for line in (text or "").splitlines()).strip()


def _localize_diagnostic_item(item: dict[str, object], *, lang: str = "en") -> dict[str, object]:
    return {
        **item,
        "title": localize_dynamic_text(str(item.get("title", "")), lang=lang),
        "message": localize_dynamic_text(str(item.get("message", "")), lang=lang),
        "suggested_actions": [localize_dynamic_text(str(action), lang=lang) for action in item.get("suggested_actions", [])],
    }


def _classify_ipv4_address(address: str) -> str:
    try:
        value = ipaddress.ip_address(address)
    except ValueError:
        return "other"
    if not isinstance(value, ipaddress.IPv4Address):
        return "other"
    if value.is_loopback:
        return "loopback"
    if value in ipaddress.ip_network("100.64.0.0/10"):
        return "private_network"
    if value.is_private:
        return "lan"
    return "other"


def _detect_host_ipv4_addresses() -> list[str]:
    candidates: set[str] = set()
    names = {
        socket.gethostname(),
        socket.getfqdn(),
        "localhost",
    }
    for name in names:
        if not name:
            continue
        try:
            _, _, addresses = socket.gethostbyname_ex(name)
        except OSError:
            continue
        for address in addresses:
            candidates.add(address)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.add(probe.getsockname()[0])
    except OSError:
        pass
    candidates.update(_detect_tailscale_ipv4_addresses())
    return sorted(candidates)


def _detect_tailscale_ipv4_addresses() -> list[str]:
    candidates: set[str] = set()
    command_candidates: list[list[str]] = []
    tailscale_path = shutil.which("tailscale") or shutil.which("tailscale.exe")
    if tailscale_path:
        command_candidates.append([tailscale_path, "ip", "-4"])
    windows_default = Path(r"C:\Program Files\Tailscale\tailscale.exe")
    if windows_default.exists():
        command_candidates.append([str(windows_default), "ip", "-4"])

    for command in command_candidates:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode != 0:
            continue
        for line in completed.stdout.splitlines():
            address = line.strip()
            if _classify_ipv4_address(address) == "private_network":
                candidates.add(address)
    return sorted(candidates)


def _format_urls(addresses: Iterable[str], port: int) -> list[str]:
    return [f"http://{address}:{port}" for address in addresses]


def build_connection_hints(host: str, port: int, public_url: str = "") -> dict[str, object]:
    detected_addresses = _detect_host_ipv4_addresses()
    lan_addresses = [address for address in detected_addresses if _classify_ipv4_address(address) == "lan"]
    private_addresses = [address for address in detected_addresses if _classify_ipv4_address(address) == "private_network"]
    if host not in {"0.0.0.0", "::", "127.0.0.1", "localhost", "::1"}:
        host_type = _classify_ipv4_address(host)
        if host_type == "lan" and host not in lan_addresses:
            lan_addresses.insert(0, host)
        elif host_type == "private_network" and host not in private_addresses:
            private_addresses.insert(0, host)
    bind_urls = _format_urls(private_addresses + lan_addresses, port)
    if host in {"127.0.0.1", "localhost", "::1"}:
        bind_urls = [f"http://127.0.0.1:{port}"]
    elif host not in {"0.0.0.0", "::"} and host not in {"127.0.0.1", "localhost", "::1"}:
        bind_urls = [f"http://{host}:{port}"] + [url for url in bind_urls if url != f"http://{host}:{port}"]
    bind_copy = bind_urls[0] if bind_urls else f"http://127.0.0.1:{port}"
    return {
        "local": f"http://127.0.0.1:{port}",
        "android_emulator": f"http://10.0.2.2:{port}",
        "bind": f"{host}:{port}",
        "bind_display": bind_copy,
        "bind_urls": bind_urls,
        "bind_copy": bind_copy,
        "lan": _format_urls(lan_addresses, port),
        "private": _format_urls(private_addresses, port),
        "public": public_url.strip(),
    }


def collect_task_artifacts(task_dir: str) -> list[dict[str, str]]:
    if not task_dir:
        return []
    root = Path(task_dir)
    if not root.exists():
        return []
    preferred = [
        "request.json",
        "status.json",
        "prompt.txt",
        "command.txt",
        "browser_body.txt",
        "browser_body_cleaned.txt",
        "stdout.txt",
        "stderr.txt",
        "result.txt",
    ]
    artifacts: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in preferred:
        path = root / name
        if path.exists():
            artifacts.append({"name": name, "path": str(path)})
            seen.add(name)
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name in seen:
            continue
        artifacts.append({"name": path.name, "path": str(path)})
    return artifacts
