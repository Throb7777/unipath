from __future__ import annotations

import unittest

from app.executors.openclaw_browser import analyze_wechat_article_text, extract_text_from_browser_snapshot
from app.user_facing import advice_for_error, result_summary_for_output


class UserFacingTests(unittest.TestCase):
    def test_result_summary_for_link_mode_stays_concise(self) -> None:
        summary = result_summary_for_output(
            mode="link_only_v1",
            executor_kind="shell_command",
            raw_summary="shell executor ok\nsecond line",
            normalized_url="https://example.com/article",
        )
        self.assertIn("Link processed successfully.", summary)
        self.assertIn("shell executor ok", summary)

    def test_error_advice_lookup_returns_clear_steps(self) -> None:
        advice = advice_for_error("manual_verification_required")
        self.assertIsNotNone(advice)
        assert advice is not None
        self.assertEqual(advice.title, "Manual verification required")
        self.assertGreaterEqual(len(advice.suggested_actions), 2)

    def test_wechat_article_analysis_trims_footer_and_marks_noise(self) -> None:
        sample = "\n".join(
            [
                "Article title",
                "",
                "This is the main body paragraph.",
                "Another useful paragraph for the article body.",
                "",
                "Recommended reading",
                "Scan the QR code",
            ]
        )
        analysis = analyze_wechat_article_text(sample)
        self.assertIn("Article title", analysis.cleaned_text)
        self.assertNotIn("Recommended reading", analysis.cleaned_text)
        self.assertIn("qr_prompt", analysis.noisy_markers)

    def test_extract_text_from_browser_snapshot_keeps_article_text(self) -> None:
        snapshot = "\n".join(
            [
                '- generic [active] [ref=e1]:',
                '  - heading "Article title" [level=1] [ref=e7]',
                '  - generic [ref=e22]: First body paragraph.',
                '  - paragraph [ref=e24]:',
                '    - generic [ref=e25]: Second body paragraph.',
                '  - button "Share" [ref=e83]:',
            ]
        )
        extracted = extract_text_from_browser_snapshot(snapshot)
        self.assertIn("Article title", extracted)
        self.assertIn("First body paragraph.", extracted)
        self.assertIn("Second body paragraph.", extracted)

    def test_result_summary_for_strict_paper_mode_is_structured(self) -> None:
        raw = "\n".join(
            [
                "STATUS: completed",
                "REASON: n/a",
                "ARTICLE_URL_USED: https://example.com/article",
                "ARTICLE_TOPIC: Foundation models for robotics",
                "EXPLICIT_PAPER_COUNT: 2",
                "EXPLICIT_PAPERS:",
                "- RT-2",
                "- RT-H",
                "KEY_TAKEAWAY: The article compares two explicitly named robotics papers.",
            ]
        )
        summary = result_summary_for_output(
            mode="paper_harvest_v1",
            executor_kind="openclaw",
            raw_summary=raw,
            normalized_url="https://example.com/article",
        )
        self.assertIn("Found 2 explicitly mentioned papers.", summary)
        self.assertIn("Topic: Foundation models for robotics", summary)
        self.assertIn("Paper: RT-2", summary)

    def test_result_summary_for_relaxed_mode_surfaces_possible_papers(self) -> None:
        raw = "\n".join(
            [
                "STATUS: completed",
                "REASON: n/a",
                "ARTICLE_URL_USED: https://example.com/article",
                "ARTICLE_TOPIC: Vision-language planning",
                "EXPLICIT_PAPER_COUNT: 0",
                "EXPLICIT_PAPERS:",
                "- none",
                "POSSIBLY_RELATED_PAPERS:",
                "- PaLM-E",
                "KEY_TAKEAWAY: The article hints at one likely related paper without naming it clearly in context.",
            ]
        )
        summary = result_summary_for_output(
            mode="paper_harvest_relaxed_v1",
            executor_kind="openclaw",
            raw_summary=raw,
            normalized_url="https://example.com/article",
        )
        self.assertIn("No explicit papers found. 1 possible paper detected.", summary)
        self.assertIn("Possible: PaLM-E", summary)


if __name__ == "__main__":
    unittest.main()
