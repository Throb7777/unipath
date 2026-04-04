from __future__ import annotations

from app.models import TaskRecord


def build_openclaw_command(settings, task: TaskRecord, message: str, resolution) -> list[str]:
    command = [*resolution.invocation_prefix, "agent"]
    if settings.openclaw_local and task.mode != "link_only_v1":
        command.append("--local")
    if settings.openclaw_target_mode == "agent":
        command.extend(["--agent", settings.openclaw_agent_id])
    elif settings.openclaw_target_mode == "session":
        command.extend(["--session-id", settings.openclaw_session_id])
    elif settings.openclaw_target_mode == "to":
        command.extend(["--to", settings.openclaw_to])
        if settings.openclaw_channel:
            command.extend(["--channel", settings.openclaw_channel])
    if settings.openclaw_json_output:
        command.append("--json")
    if settings.openclaw_thinking:
        command.extend(["--thinking", settings.openclaw_thinking])
    command.extend(["--timeout", str(settings.openclaw_timeout_seconds)])
    command.extend(["--message", message])
    return command


def build_openclaw_message(settings, task: TaskRecord, *, article_body: str | None = None) -> str:
    if task.mode == "link_only_v1":
        return _build_link_only_message(task)
    if task.mode == "paper_harvest_relaxed_v1":
        return _build_paper_harvest_message(settings, task, relaxed=True, article_body=article_body)
    return _build_paper_harvest_message(settings, task, relaxed=False, article_body=article_body)


def _build_link_only_message(task: TaskRecord) -> str:
    return (
        f"ARTICLE_URL={task.normalized_url}\n"
        f"SOURCE={task.source}\n"
        "TASK=forward_link_only\n\n"
        "Use ARTICLE_URL exactly as provided above. Do not ask for the URL.\n"
        "Return concise plain text in exactly this format:\n"
        "STATUS: completed|failed\n"
        "SUMMARY: <one short paragraph>\n"
        "LINK_USED: <exact URL used>"
    )


def _build_paper_harvest_message(settings, task: TaskRecord, *, relaxed: bool, article_body: str | None = None) -> str:
    parsing_mode = "relaxed" if relaxed else "strict"
    possible_related_block = (
        "POSSIBLY_RELATED_PAPERS:\n"
        "- <paper 1>\n"
        "- <paper 2>\n"
        "If there are no low-confidence candidates, write '- none'.\n"
        if relaxed
        else ""
    )
    if article_body is not None:
        clipped_body = _trim_text(article_body, settings.task_file_char_limit)
        return (
            f"ARTICLE_URL={task.normalized_url}\n"
            f"SOURCE={task.source}\n"
            f"PARSING_MODE={parsing_mode}\n"
            "TASK=extract_explicit_papers_from_prefetched_article\n\n"
            "The article body has already been fetched and is provided below in PAGE_TEXT.\n"
            "Do not ask for a URL. Do not fetch the page again. Use only PAGE_TEXT.\n"
            "Only list papers explicitly mentioned in PAGE_TEXT.\n"
            "Do not infer papers from the title, URL, or prior knowledge.\n\n"
            f"PAGE_TEXT:\n{clipped_body}\n\n"
            "Return exactly this format:\n"
            "STATUS: completed|failed\n"
            "REASON: <short reason or n/a>\n"
            "ARTICLE_URL_USED: <exact URL used>\n"
            "ARTICLE_TOPIC: <one short sentence>\n"
            "EXPLICIT_PAPER_COUNT: <integer>\n"
            "EXPLICIT_PAPERS:\n"
            "- <paper 1>\n"
            "- <paper 2>\n"
            "If none are explicitly mentioned, write '- none'.\n"
            f"{possible_related_block}"
            "KEY_TAKEAWAY: <one short sentence>\n"
            "Do not add extra headings, markdown tables, or explanatory notes."
        )

    return (
        f"ARTICLE_URL={task.normalized_url}\n"
        f"SOURCE={task.source}\n"
        f"PARSING_MODE={parsing_mode}\n"
        "TASK=fetch_article_and_extract_explicit_papers\n\n"
        "The article URL is already provided in ARTICLE_URL above. Do not ask for a URL.\n"
        "Fetch the article body from ARTICLE_URL.\n"
        "Only list papers explicitly mentioned in the article body.\n"
        "Do not infer papers from the title, the URL, or prior knowledge.\n"
        "If fetching fails, return STATUS: failed and a short REASON.\n"
        "Keep the answer concise and plain text.\n"
        "Do not add extra commentary before or after the requested fields.\n\n"
        "Return exactly this format:\n"
        "STATUS: completed|failed\n"
        "REASON: <short reason or n/a>\n"
        "ARTICLE_URL_USED: <exact URL used>\n"
        "ARTICLE_TOPIC: <one short sentence>\n"
        "EXPLICIT_PAPER_COUNT: <integer>\n"
        "EXPLICIT_PAPERS:\n"
        "- <paper 1>\n"
        "- <paper 2>\n"
        "If none are explicitly mentioned, write '- none'.\n"
        f"{possible_related_block}"
        "KEY_TAKEAWAY: <one short sentence>"
    )


def _trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
