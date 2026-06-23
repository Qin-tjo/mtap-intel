"""Security tests for audit/lib/{snapshot,urls,ctgov}.py.

These tests verify the input-validation guards that were added during the
security review: only http/https URL schemes are allowed, NCT IDs are
validated, and bad inputs are rejected without invoking curl.
"""

from __future__ import annotations
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import snapshot as snap_mod   # noqa: E402
from audit.lib import urls as urls_mod       # noqa: E402
from audit.lib import ctgov as ctgov_mod     # noqa: E402


class SnapshotSchemeGuardTests(unittest.TestCase):
    """snapshot.py must reject non-http(s) schemes BEFORE invoking curl."""

    def test_file_scheme_rejected(self):
        with patch("audit.lib.snapshot.subprocess.run") as m:
            r = snap_mod.snapshot("file:///etc/passwd", "test")
        self.assertEqual(r["status"], "error")
        self.assertIn("scheme", r["error"])
        m.assert_not_called()

    def test_gopher_scheme_rejected(self):
        with patch("audit.lib.snapshot.subprocess.run") as m:
            r = snap_mod.snapshot("gopher://example.com/", "test")
        self.assertEqual(r["status"], "error")
        m.assert_not_called()

    def test_dict_scheme_rejected(self):
        with patch("audit.lib.snapshot.subprocess.run") as m:
            r = snap_mod.snapshot("dict://internal:11211/", "test")
        self.assertEqual(r["status"], "error")
        m.assert_not_called()

    def test_empty_url_rejected(self):
        with patch("audit.lib.snapshot.subprocess.run") as m:
            r = snap_mod.snapshot("", "test")
        self.assertEqual(r["status"], "error")
        m.assert_not_called()

    def test_https_url_passes_guard(self):
        # Mock curl so we don't make a real network call
        with patch("audit.lib.snapshot.subprocess.run") as m:
            m.return_value.stdout = "200"
            m.return_value.stderr = ""
            r = snap_mod.snapshot("https://example.com/", "test_https")
        m.assert_called_once()
        # Verify proto=http,https flag is in the curl call
        cmd = m.call_args[0][0]
        self.assertIn("--proto", cmd)
        self.assertIn("=http,https", cmd)
        self.assertIn("--max-filesize", cmd)


class SafeFilenameTests(unittest.TestCase):
    """source_key must be sanitized before becoming a filename (no path traversal)."""

    def test_path_traversal_attempt_sanitized(self):
        self.assertEqual(snap_mod._safe("../../../etc/passwd"), "etc-passwd")

    def test_slash_sanitized(self):
        out = snap_mod._safe("foo/bar/baz")
        self.assertEqual(out, "foo-bar-baz")

    def test_dollar_dollar_sanitized(self):
        out = snap_mod._safe("$(rm -rf /)")
        self.assertNotIn("$", out)
        self.assertNotIn("(", out)
        self.assertNotIn(")", out)
        self.assertNotIn(" ", out)

    def test_allows_safe_chars(self):
        self.assertEqual(snap_mod._safe("rodon2024_annoncol"), "rodon2024_annoncol")
        self.assertEqual(snap_mod._safe("HSK41959-1"), "HSK41959-1")


class UrlSchemeGuardTests(unittest.TestCase):
    def test_file_scheme_rejected(self):
        with patch("audit.lib.urls.subprocess.run") as m:
            r = urls_mod.check_url("file:///etc/passwd")
        self.assertEqual(r["status"], "invalid")
        m.assert_not_called()

    def test_empty_url_rejected(self):
        with patch("audit.lib.urls.subprocess.run") as m:
            r = urls_mod.check_url("")
        self.assertEqual(r["status"], "invalid")
        m.assert_not_called()

    def test_https_url_curl_includes_proto_guard(self):
        with patch("audit.lib.urls.subprocess.run") as m:
            m.return_value.stdout = "OK200"
            m.return_value.stderr = ""
            urls_mod.check_url("https://example.com/")
        cmd = m.call_args[0][0]
        self.assertIn("--proto", cmd)
        self.assertIn("=http,https", cmd)
        self.assertIn("--max-filesize", cmd)


class CtgovNctValidationTests(unittest.TestCase):
    """ctgov.fetch_trial(nct) must reject anything that's not NCTdddddddd."""

    def test_invalid_nct_rejected(self):
        with patch("audit.lib.ctgov.subprocess.run") as m:
            r = ctgov_mod.fetch_trial("../../etc/passwd")
        self.assertIn("_error", r)
        self.assertIn("invalid NCT", r["_error"])
        m.assert_not_called()

    def test_short_nct_rejected(self):
        with patch("audit.lib.ctgov.subprocess.run") as m:
            r = ctgov_mod.fetch_trial("NCT123")
        self.assertIn("_error", r)
        m.assert_not_called()

    def test_letters_in_nct_rejected(self):
        with patch("audit.lib.ctgov.subprocess.run") as m:
            r = ctgov_mod.fetch_trial("NCT1234ABCD")
        self.assertIn("_error", r)
        m.assert_not_called()

    def test_empty_nct_rejected(self):
        with patch("audit.lib.ctgov.subprocess.run") as m:
            r = ctgov_mod.fetch_trial("")
        self.assertIn("_error", r)
        m.assert_not_called()

    def test_valid_nct_passes_guard(self):
        with patch("audit.lib.ctgov.subprocess.run") as m:
            m.return_value.returncode = 0
            m.return_value.stdout = '{"protocolSection": {"identificationModule": {"nctId": "NCT12345678", "briefTitle": "test"}}}'
            r = ctgov_mod.fetch_trial("NCT12345678")
        self.assertNotIn("_error", r)
        m.assert_called_once()
        cmd = m.call_args[0][0]
        self.assertIn("--proto", cmd)
        self.assertIn("--max-filesize", cmd)


if __name__ == "__main__":
    unittest.main()
