"""Tests for audit/render.py — marker replace, HTML escape, idempotence."""

from __future__ import annotations
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from audit import render as render_mod   # noqa: E402
from audit.lib import state as state_lib   # noqa: E402
from audit.tests.test_state import VALID_TRIAL   # noqa: E402


class MarkerReplaceTests(unittest.TestCase):
    def test_replace_between_markers_replaces_content(self):
        html = (
            "before\n"
            f"{render_mod.MARKER_START}\n"
            "OLD CONTENT\n"
            f"{render_mod.MARKER_END}\n"
            "after"
        )
        out = render_mod.replace_between_markers(html, "NEW BODY")
        self.assertIn("NEW BODY", out)
        self.assertNotIn("OLD CONTENT", out)
        self.assertIn("before\n", out)
        self.assertIn("\nafter", out)

    def test_replace_between_markers_idempotent(self):
        html = (
            "x\n"
            f"{render_mod.MARKER_START}\n"
            "ORIGINAL\n"
            f"{render_mod.MARKER_END}\n"
            "y"
        )
        once  = render_mod.replace_between_markers(html, "A")
        twice = render_mod.replace_between_markers(once, "A")
        self.assertEqual(once, twice)

    def test_replace_between_markers_missing_aborts(self):
        with self.assertRaisesRegex(RuntimeError, "Markers not found"):
            render_mod.replace_between_markers("no markers here", "X")

    def test_custom_marker_pair(self):
        html = "x\n<!-- AUDIT:LOG:START -->\nOLD\n<!-- AUDIT:LOG:END -->\ny"
        out = render_mod.replace_between_markers(
            html, "NEW",
            start="<!-- AUDIT:LOG:START -->",
            end="<!-- AUDIT:LOG:END -->",
        )
        self.assertIn("NEW", out)
        self.assertNotIn("OLD", out)


class HTMLEscapeTests(unittest.TestCase):
    """A drug label or sponsor with HTML special chars must not break out of its cell."""

    def _trial_with(self, **display_overrides):
        t = copy.deepcopy(VALID_TRIAL)
        t["display"].update(display_overrides)
        return t

    def test_drug_label_with_html_special_chars_is_escaped(self):
        t = self._trial_with(drug_label='<script>alert("XSS")</script>')
        out = render_mod.render_row("NCT12345678", t)
        self.assertNotIn("<script>alert", out)
        self.assertIn("&lt;script&gt;", out)

    def test_orr_tooltip_with_quotes_is_attribute_safe(self):
        t = self._trial_with(orr_tooltip='Has "double quotes" and <html>')
        out = render_mod.render_row("NCT12345678", t)
        # Attribute value must be properly encoded so the title="..." quote isn't closed
        self.assertIn('title="Has', out)
        self.assertIn('&quot;', out)
        self.assertNotIn('Has "double quotes" and <html>"', out)

    def test_search_keywords_with_quotes_is_attribute_safe(self):
        # The attack we're defending against: an unescaped quote could let the
        # value escape its attribute and inject an event-handler attribute.
        # Verify the closing quote of data-search="…" can't be reached early.
        t = self._trial_with(search_keywords='abc " onmouseover=alert(1) "')
        out = render_mod.render_row("NCT12345678", t)
        # Embedded quotes must be encoded so the attribute boundary stays intact
        self.assertIn('&quot;', out)
        self.assertNotIn(' onmouseover=alert(1) "', out)   # raw injection sequence rejected
        # The data-search attribute must still be balanced and well-formed
        import re
        m = re.search(r'data-search="([^"]*)"', out)
        self.assertIsNotNone(m, "data-search attribute is malformed")


class TbodyRenderTests(unittest.TestCase):
    def test_render_tbody_emits_one_row_per_trial(self):
        s = state_lib._empty_state()
        for nct in ("NCT11111111", "NCT22222222", "NCT33333333"):
            t = copy.deepcopy(VALID_TRIAL)
            t["tier_a"]["nct_id"] = nct
            s["trials"][nct] = t
        out = render_mod.render_tbody(s)
        self.assertEqual(out.count('class="tt-row"'), 3)
        self.assertEqual(out.count('class="tt-detail-row"'), 3)
        for nct in ("NCT11111111", "NCT22222222", "NCT33333333"):
            self.assertIn(nct, out)

    def test_render_tbody_handles_empty_state(self):
        s = state_lib._empty_state()
        out = render_mod.render_tbody(s)
        self.assertNotIn('class="tt-row"', out)


if __name__ == "__main__":
    unittest.main()
