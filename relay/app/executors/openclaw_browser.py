from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WechatArticleAnalysis:
    cleaned_text: str
    noisy_markers: tuple[str, ...]
    paragraph_count: int
    char_count: int


def decode_browser_text(raw_body: str) -> str:
    if not raw_body:
        return ""
    candidate = raw_body
    try:
        decoded = json.loads(raw_body)
        if isinstance(decoded, str):
            candidate = decoded
    except Exception:
        candidate = raw_body
    decoded_base64 = _decode_base64_text(candidate.strip())
    if decoded_base64 is not None:
        return _normalize_browser_text(decoded_base64)
    return _normalize_browser_text(candidate)


def classify_wechat_browser_text(text: str) -> tuple[str, str, str] | None:
    lowered = text.lower()
    if "参数错误" in text or "parameter error" in lowered:
        return ("wechat_parameter_error", "WeChat returned a parameter error page instead of the article body.", "The WeChat page returned a parameter error page.")

    profile_revalidation_markers = ["重新验证", "请重新验证", "重新登录", "请重新登录", "登录已过期", "登录过期", "会话已过期", "会话失效", "verify again", "sign in again", "login again", "session expired"]
    if any(marker in text or marker in lowered for marker in profile_revalidation_markers):
        return ("profile_revalidation_required", "The managed browser profile appears to have lost its WeChat verification or login state and needs to be verified again.", "The managed browser profile needs to be re-verified for WeChat.")

    manual_verification_markers = ["环境异常", "完成验证后即可继续访问", "去验证", "请完成验证", "异常访问", "安全验证", "captcha", "verification", "verify"]
    if any(marker in text or marker in lowered for marker in manual_verification_markers):
        return ("manual_verification_required", "WeChat requires manual verification or a logged-in browser session in the managed browser profile.", "WeChat requires manual verification in the managed browser profile.")
    return None


def clean_wechat_article_text(text: str) -> str:
    return analyze_wechat_article_text(text).cleaned_text


def extract_text_from_browser_snapshot(snapshot_text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    for raw_line in snapshot_text.splitlines():
        candidate = _extract_snapshot_line_text(raw_line)
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        lines.append(candidate)

    return "\n".join(lines)


def analyze_wechat_article_text(text: str) -> WechatArticleAnalysis:
    lines = [_normalize_wechat_line(line) for line in text.splitlines()]
    lines = _trim_leading_wechat_noise(lines)
    cleaned = _trim_trailing_blank_lines(lines)
    cleaned = _trim_wechat_footer_sections(cleaned)
    noisy_markers = set(_detect_noisy_markers("\n".join(cleaned)))
    cleaned = _strip_inline_promotional_lines(cleaned)
    cleaned = _strip_trailing_wechat_action_lines(cleaned)
    cleaned = _collapse_blank_lines(cleaned)
    cleaned = _trim_trailing_blank_lines(cleaned)
    text_value = "\n".join(cleaned).strip()
    noisy_markers.update(_detect_noisy_markers(text_value))
    paragraph_count = sum(1 for line in cleaned if line.strip())
    return WechatArticleAnalysis(
        cleaned_text=text_value,
        noisy_markers=tuple(sorted(noisy_markers)),
        paragraph_count=paragraph_count,
        char_count=len(text_value),
    )


def _decode_base64_text(text: str) -> str | None:
    if not text:
        return None
    try:
        raw = base64.b64decode(text, validate=True)
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _normalize_browser_text(text: str) -> str:
    normalized = text.strip()
    repaired = _repair_gbk_mojibake(normalized)
    return repaired or normalized


def _repair_gbk_mojibake(text: str) -> str | None:
    try:
        repaired = text.encode("gbk").decode("utf-8")
    except Exception:
        return None
    repaired = repaired.strip()
    return repaired if repaired and repaired != text else None


def _normalize_wechat_line(line: str) -> str:
    return line.replace("\u200b", "").replace("\ufeff", "").rstrip()


def _extract_snapshot_line_text(line: str) -> str:
    stripped = line.strip()
    if not stripped.startswith("- "):
        return ""
    content = stripped[2:].strip()
    if not content:
        return ""

    quoted = re.findall(r'"([^"]+)"', content)
    if content.startswith(("heading ", "paragraph ", "generic ", "link ", "button ", "emphasis ")):
        if ": " in content:
            tail = content.rsplit(": ", 1)[1].strip()
            if tail and not tail.startswith("["):
                return tail
        if quoted:
            candidate = quoted[0].strip()
            if content.startswith("button "):
                return ""
            return candidate
    return ""


def _trim_trailing_blank_lines(lines: list[str]) -> list[str]:
    end = len(lines)
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    return lines[:end]


def _trim_wechat_footer_sections(lines: list[str]) -> list[str]:
    if len(lines) < 12:
        return lines
    footer_markers = ["推荐阅读", "相关阅读", "延伸阅读", "更多阅读", "往期推荐", "往期回顾", "继续滑动看下一个", "轻触阅读原文", "阅读原文", "喜欢此内容的人还喜欢", "微信扫一扫关注该公众号", "长按识别二维码", "扫码关注", "点击关注", "关注我们", "欢迎关注", "公众号名片", "视频号名片", "作者名片", "识别二维码", "长按二维码", "扫码阅读全文", "收录于合集", "继续阅读", "下一个", "上一篇", "下一篇", "分享", "收藏", "点赞", "在看"]
    short_promotional_markers = ["公众号", "视频号", "二维码", "名片", "关注", "推荐", "回顾"]
    start_search = max(8, len(lines) // 3)
    footer_start = None
    for index in range(start_search, len(lines)):
        line = lines[index].strip()
        lowered = line.lower()
        if not line:
            continue
        if any(marker in line or marker in lowered for marker in footer_markers):
            footer_start = index
            break
        if index >= len(lines) - 12 and len(line) <= 20 and any(marker in line for marker in short_promotional_markers):
            footer_start = index
            break
    if footer_start is None:
        return lines
    body = lines[:footer_start]
    if len(body) < 8:
        return lines
    return body


def _trim_leading_wechat_noise(lines: list[str]) -> list[str]:
    if not lines:
        return lines
    leading_markers = (
        "以下文章来源于",
        "文章来源于",
        "微信号",
        "原标题",
        "Original title",
        "Source:",
        "From:",
    )
    index = 0
    while index < min(6, len(lines)):
        candidate = lines[index].strip()
        if not candidate:
            index += 1
            continue
        if len(candidate) <= 40 and any(marker in candidate for marker in leading_markers):
            index += 1
            continue
        break
    return lines[index:]


def _strip_inline_promotional_lines(lines: list[str]) -> list[str]:
    if not lines:
        return lines
    promotional_markers = (
        "Scan the QR code",
        "Read more",
        "Recommended reading",
        "Like this content",
        "Video account",
        "关注",
        "扫码",
        "二维码",
        "推荐阅读",
        "相关阅读",
    )
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) <= 28 and any(marker in stripped for marker in promotional_markers):
            continue
        result.append(line)
    return result


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        result.append(line)
        previous_blank = blank
    return result


def _strip_trailing_wechat_action_lines(lines: list[str]) -> list[str]:
    action_markers = {"分享", "收藏", "点赞", "在看", "写留言", "留言", "推荐", "阅读原文", "扫码关注", "长按识别", "公众号", "视频号", "名片", "二维码"}
    result = list(lines)
    while result:
        tail = result[-1].strip()
        if not tail:
            result.pop()
            continue
        if len(tail) <= 12 and any(marker in tail for marker in action_markers):
            result.pop()
            continue
        break
    return result


def _detect_noisy_markers(text: str) -> list[str]:
    markers: list[str] = []
    lowered = text.lower()
    if "recommended reading" in lowered or "相关阅读" in text or "推荐阅读" in text:
        markers.append("related_reading")
    if "scan the qr code" in lowered or "二维码" in text or "扫码" in text:
        markers.append("qr_prompt")
    if "follow us" in lowered or "关注" in text:
        markers.append("follow_prompt")
    return markers
