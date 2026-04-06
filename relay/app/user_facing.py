from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ErrorAdvice:
    title: str
    message: str
    suggested_actions: tuple[str, ...]
    retryable: bool = False
    manual_action_required: bool = False


ERROR_ADVICE: dict[str, ErrorAdvice] = {
    "manual_verification_required": ErrorAdvice(
        title="Manual verification required",
        message="WeChat returned a verification step instead of the article body.",
        suggested_actions=(
            "Open the article in the managed browser and finish the verification step.",
            "Submit the task again after verification succeeds.",
        ),
        retryable=True,
        manual_action_required=True,
    ),
    "profile_revalidation_required": ErrorAdvice(
        title="Managed browser needs verification again",
        message="The saved WeChat verification or login state appears to have expired.",
        suggested_actions=(
            "Open the article again in the managed browser profile.",
            "Complete verification or sign in again, then retry the task.",
        ),
        retryable=True,
        manual_action_required=True,
    ),
    "wechat_parameter_error": ErrorAdvice(
        title="WeChat link is no longer valid",
        message="WeChat returned a parameter error page instead of the original article.",
        suggested_actions=(
            "Go back to the original article and share the article link again.",
            "Avoid shortened or expired share pages when resubmitting.",
        ),
    ),
    "wechat_body_too_short": ErrorAdvice(
        title="Article body was too short",
        message="The fetched page text did not look like a full WeChat article body.",
        suggested_actions=(
            "Open the article once in the managed browser and make sure it loads fully.",
            "Retry the task after the article body is visible.",
        ),
        retryable=True,
    ),
    "executor_session_locked": ErrorAdvice(
        title="Processing method is busy",
        message="The current OpenClaw lane is already being used by another task.",
        suggested_actions=(
            "Wait for the current run to finish and let the relay retry automatically.",
            "Avoid starting multiple tasks against the same OpenClaw target at the same time.",
        ),
        retryable=True,
    ),
    "executor_network_error": ErrorAdvice(
        title="Network or provider request failed",
        message="The processing method could not reach its upstream service.",
        suggested_actions=(
            "Check the current network or proxy settings on this machine.",
            "Retry the task after the network path is stable again.",
        ),
        retryable=True,
    ),
    "executor_auth_error": ErrorAdvice(
        title="Authentication is not ready",
        message="The selected processing method cannot use its local authentication or model credentials yet.",
        suggested_actions=(
            "Run openclaw doctor or the relay diagnostics view and fix the reported auth or session-state issue.",
            "Make sure the local OpenClaw state directory is writable and that the required model credentials are configured.",
        ),
    ),
    "executor_timeout": ErrorAdvice(
        title="Processing timed out",
        message="The task ran longer than the configured timeout window.",
        suggested_actions=(
            "Retry the task once to confirm whether the timeout was temporary.",
            "Increase the timeout only if this task type is expected to run longer.",
        ),
        retryable=True,
    ),
    "executor_start_failed": ErrorAdvice(
        title="Processing could not start",
        message="Relay could not launch the selected processing method.",
        suggested_actions=(
            "Check the configured command path and local tool installation.",
            "Use relay doctor or Web UI Diagnostics to confirm the environment.",
        ),
    ),
    "executor_command_not_found": ErrorAdvice(
        title="Processing command was not found",
        message="Relay could not resolve the configured command on this machine.",
        suggested_actions=(
            "Set the correct command path in Settings.",
            "Switch to the mock or shell-command processing method if you only need a smoke test.",
        ),
    ),
    "executor_command_not_configured": ErrorAdvice(
        title="Command template is missing",
        message="The shell-command processing method does not have a command template yet.",
        suggested_actions=(
            "Open Settings and add a trusted command template.",
            "Switch to another processing method if you do not plan to use a custom command.",
        ),
    ),
    "executor_nonzero_exit": ErrorAdvice(
        title="Processing command exited with an error",
        message="The selected processing method started, but returned a failure code.",
        suggested_actions=(
            "Open the task files and inspect stdout.txt and stderr.txt.",
            "Fix the underlying command error, then retry the task.",
        ),
    ),
    "executor_reported_failure": ErrorAdvice(
        title="Processing method reported a failure",
        message="The task finished, but the processing method reported a failed result.",
        suggested_actions=(
            "Review the result summary and task files for the reported reason.",
            "Retry only after confirming the cause is temporary or corrected.",
        ),
    ),
}


def advice_for_error(error_code: str) -> ErrorAdvice | None:
    return ERROR_ADVICE.get((error_code or "").strip())


def infer_health_advice(*, configured_executor: str, executor_available: bool, executor_message: str) -> ErrorAdvice | None:
    if executor_available:
        return None

    message = (executor_message or "").strip().lower()
    if not message:
        return None

    if "command could not be resolved" in message or "command was not found" in message:
        return advice_for_error("executor_command_not_found")
    if configured_executor == "shell_command" and ("template is empty" in message or "template" in message and "configured" not in message):
        return advice_for_error("executor_command_not_configured")
    if "authentication" in message or "login" in message or "api key" in message:
        return advice_for_error("executor_auth_error")
    if "timed out" in message or "timeout" in message:
        return advice_for_error("executor_timeout")
    if "could not launch" in message or "could not start" in message:
        return advice_for_error("executor_start_failed")
    if "network" in message or "proxy" in message or "upstream" in message:
        return advice_for_error("executor_network_error")
    return None


def health_advice_card(*, configured_executor: str, executor_available: bool, executor_message: str) -> dict[str, object] | None:
    advice = infer_health_advice(
        configured_executor=configured_executor,
        executor_available=executor_available,
        executor_message=executor_message,
    )
    if advice is None:
        return None
    payload = asdict(advice)
    payload["kind"] = "warn"
    return payload


def suggested_actions_for_task(*, status: str, error_code: str) -> list[str]:
    advice = advice_for_error(error_code)
    if advice is not None:
        return list(advice.suggested_actions)
    if status == "completed":
        return [
            "Review the result summary and task files if you want the full output.",
            "Reuse the same settings if you want to submit another task.",
        ]
    if status == "cancelled":
        return [
            "Open the task details if you need to confirm where the task stopped.",
            "Submit the task again when you are ready to continue.",
        ]
    if status in {"queued", "preparing", "running", "finalizing", "cancelling"}:
        return ["Wait for the relay to finish the current step, or cancel the task if you no longer need it."]
    if status == "failed":
        return [
            "Open the task files or diagnostics summary for more detail.",
            "Retry only after checking the likely cause.",
        ]
    return []


def problem_title_for_task(*, status: str, error_code: str) -> str:
    advice = advice_for_error(error_code)
    if advice is not None:
        return advice.title
    if status == "completed":
        return "Task completed"
    if status == "cancelled":
        return "Task cancelled"
    if status == "failed":
        return "Task failed"
    if status == "cancelling":
        return "Cancellation in progress"
    return ""


def result_summary_for_output(
    *,
    mode: str,
    executor_kind: str,
    raw_summary: str,
    normalized_url: str,
    fallback_message: str = "",
    limit: int = 800,
) -> str:
    raw_value = (raw_summary or "").strip()
    if _looks_like_formatted_summary(raw_value):
        return raw_value[:limit] if len(raw_value) > limit else raw_value

    structured = _parse_structured_output(raw_value)
    if mode == "link_only_v1" and structured:
        return _format_link_summary(structured, normalized_url=normalized_url, limit=limit)
    if mode == "paper_harvest_v1" and structured:
        return _format_strict_paper_summary(structured, normalized_url=normalized_url, limit=limit)
    if mode == "paper_harvest_relaxed_v1" and structured:
        return _format_relaxed_paper_summary(structured, normalized_url=normalized_url, limit=limit)

    cleaned_lines = _meaningful_summary_lines(raw_summary)
    if not cleaned_lines and fallback_message.strip():
        cleaned_lines = _meaningful_summary_lines(fallback_message)

    if mode == "link_only_v1":
        host = _display_host(normalized_url)
        highlights = cleaned_lines[:2]
        if not highlights:
            highlights = [f"Prepared link: {host or normalized_url}"]
        return _format_summary("Link processed successfully.", highlights, limit)

    if cleaned_lines:
        title = cleaned_lines[0]
        highlights = cleaned_lines[1:4]
        if executor_kind == "mock" and not highlights:
            highlights = [f"Mode: {mode}", f"Link: {normalized_url}"]
        return _format_summary(title, highlights, limit)

    default_title = "Task completed successfully."
    default_highlights = [f"Mode: {mode}", f"Link: {normalized_url}"] if executor_kind == "mock" else []
    return _format_summary(default_title, default_highlights, limit)


def build_diagnostic_summary(
    *,
    task_id: str,
    status: str,
    stage_label: str,
    mode: str,
    source: str,
    executor_kind: str,
    error_code: str,
    relay_message: str,
    error_message: str,
    normalized_url: str,
    duration_ms: int | None,
    timeline: list[dict[str, str]],
) -> str:
    lines = [
        f"Task ID: {task_id}",
        f"Status: {stage_label or status}",
        f"Mode: {mode}",
        f"Source: {source}",
        f"Processing Method: {executor_kind or '-'}",
        f"Prepared Link: {normalized_url}",
    ]
    if duration_ms is not None:
        lines.append(f"Duration: {max(0, duration_ms // 1000)}s")
    if error_code:
        lines.append(f"Error Code: {error_code}")
    message = (error_message or relay_message or "").strip()
    if message:
        lines.append(f"Message: {message}")
    suggested = suggested_actions_for_task(status=status, error_code=error_code)
    if suggested:
        lines.append("Suggested Next Steps:")
        lines.extend(f"- {item}" for item in suggested[:3])
    if timeline:
        lines.append("Recent Steps:")
        for entry in timeline[-3:]:
            label = entry.get("label") or entry.get("stepId") or entry.get("status") or "-"
            at = entry.get("at") or "-"
            lines.append(f"- {label} ({at})")
    return "\n".join(lines)


def _format_summary(title: str, highlights: list[str], limit: int) -> str:
    parts = [title.strip()]
    cleaned_highlights = [item.strip(" -•\t") for item in highlights if item and item.strip(" -•\t")]
    if cleaned_highlights:
        parts.append("")
        parts.append("Highlights:")
        parts.extend(f"- {item}" for item in cleaned_highlights[:3])
    text = "\n".join(parts).strip()
    if len(text) <= limit:
        return text
    trimmed = text[: max(0, limit - 1)].rstrip()
    return trimmed + "…"


def _format_link_summary(structured: dict[str, object], *, normalized_url: str, limit: int) -> str:
    summary = _clean_scalar(structured.get("SUMMARY"))
    link_used = _clean_scalar(structured.get("LINK_USED")) or normalized_url
    highlights: list[str] = []
    if summary:
        highlights.append(summary)
    if link_used:
        highlights.append(f"Link used: {link_used}")
    return _format_summary("Link processed successfully.", highlights, limit)


def _format_strict_paper_summary(structured: dict[str, object], *, normalized_url: str, limit: int) -> str:
    status = (_clean_scalar(structured.get("STATUS")) or "").lower()
    reason = _meaningful_reason(_clean_scalar(structured.get("REASON")))
    topic = _clean_scalar(structured.get("ARTICLE_TOPIC"))
    takeaway = _clean_scalar(structured.get("KEY_TAKEAWAY"))
    papers = _normalize_paper_list(structured.get("EXPLICIT_PAPERS"))
    explicit_count = _safe_int(structured.get("EXPLICIT_PAPER_COUNT")) or len(papers)

    if status == "failed":
        highlights = []
        if reason:
            highlights.append(f"Reason: {reason}")
        highlights.append(f"Article: {normalized_url}")
        return _format_summary("Article analysis failed.", highlights, limit)

    title = (
        f"Found {explicit_count} explicitly mentioned {_pluralize('paper', explicit_count)}."
        if explicit_count > 0
        else "No explicitly mentioned papers found."
    )
    highlights = _paper_summary_highlights(
        topic=topic,
        takeaway=takeaway,
        reason=reason if explicit_count == 0 else "",
        papers=papers,
    )
    return _format_summary(title, highlights, limit)


def _format_relaxed_paper_summary(structured: dict[str, object], *, normalized_url: str, limit: int) -> str:
    status = (_clean_scalar(structured.get("STATUS")) or "").lower()
    reason = _meaningful_reason(_clean_scalar(structured.get("REASON")))
    topic = _clean_scalar(structured.get("ARTICLE_TOPIC"))
    takeaway = _clean_scalar(structured.get("KEY_TAKEAWAY"))
    explicit_papers = _normalize_paper_list(structured.get("EXPLICIT_PAPERS"))
    explicit_count = _safe_int(structured.get("EXPLICIT_PAPER_COUNT")) or len(explicit_papers)
    possible_papers = _normalize_paper_list(structured.get("POSSIBLY_RELATED_PAPERS"))

    if status == "failed":
        highlights = []
        if reason:
            highlights.append(f"Reason: {reason}")
        highlights.append(f"Article: {normalized_url}")
        return _format_summary("Article analysis failed.", highlights, limit)

    if explicit_count > 0:
        title = f"Found {explicit_count} explicitly mentioned {_pluralize('paper', explicit_count)}."
    elif possible_papers:
        title = f"No explicit papers found. {len(possible_papers)} possible {_pluralize('paper', len(possible_papers))} detected."
    else:
        title = "No clearly related papers found."

    highlights = _paper_summary_highlights(
        topic=topic,
        takeaway=takeaway,
        reason=reason if explicit_count == 0 else "",
        papers=explicit_papers,
    )
    if possible_papers:
        highlights.extend(f"Possible: {paper}" for paper in possible_papers[:2])
    return _format_summary(title, highlights, limit)


def _meaningful_summary_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("status:"):
            continue
        if lower.startswith("reason:"):
            continue
        if lower.startswith("summary:"):
            line = line.partition(":")[2].strip()
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        line = line.strip("•*- ").strip()
        if not line:
            continue
        if line not in lines:
            lines.append(line)
    return lines


def _parse_structured_output(text: str) -> dict[str, object]:
    if not text:
        return {}
    scalar_keys = {
        "STATUS",
        "REASON",
        "SUMMARY",
        "ARTICLE_URL_USED",
        "LINK_USED",
        "ARTICLE_TOPIC",
        "EXPLICIT_PAPER_COUNT",
        "KEY_TAKEAWAY",
    }
    list_keys = {"EXPLICIT_PAPERS", "POSSIBLY_RELATED_PAPERS"}
    result: dict[str, object] = {}
    current_list: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in scalar_keys:
                result[key] = value
                current_list = None
                continue
            if key in list_keys:
                result.setdefault(key, [])
                current_list = key
                if value:
                    result[key].append(value.lstrip("- ").strip())
                continue
        if current_list and line.startswith("-"):
            result[current_list].append(line.lstrip("- ").strip())
    return result


def _paper_summary_highlights(
    *,
    topic: str,
    takeaway: str,
    reason: str,
    papers: list[str],
) -> list[str]:
    highlights: list[str] = []
    if topic:
        highlights.append(f"Topic: {topic}")
    if takeaway:
        highlights.append(f"Takeaway: {takeaway}")
    elif reason:
        highlights.append(f"Note: {reason}")
    highlights.extend(f"Paper: {paper}" for paper in papers[:3])
    return highlights


def _normalize_paper_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        paper = _clean_scalar(item)
        if not paper or paper.lower() == "none":
            continue
        normalized.append(paper)
    return normalized


def _clean_scalar(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_int(value: object) -> int:
    try:
        return max(0, int(str(value).strip()))
    except Exception:
        return 0


def _pluralize(noun: str, count: int) -> str:
    return noun if count == 1 else f"{noun}s"


def _meaningful_reason(reason: str) -> str:
    lowered = (reason or "").strip().lower()
    if not lowered or lowered == "n/a":
        return ""
    if lowered == "no papers explicitly mentioned in page_text":
        return "The article did not explicitly mention any papers."
    return reason.strip()


def _display_host(normalized_url: str) -> str:
    parsed = urlparse(normalized_url)
    return (parsed.netloc or "").replace("www.", "").strip()


def _looks_like_formatted_summary(text: str) -> bool:
    if not text:
        return False
    return "\n\nHighlights:\n-" in text or text.startswith("Link processed successfully.\n\nHighlights:\n-")
