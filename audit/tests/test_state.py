"""Tests for audit/lib/state.py — schema validation + drift detector."""

from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402


VALID_TRIAL = {
    "tier_a": {
        "nct_id": "NCT12345678",
        "drug_canonical": "TestDrug",
        "drug_aliases": [],
        "sponsor": "ACME",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "phases": ["Phase 1"],
        "status": "Recruiting",
        "start_date": "2025-01-01",
    },
    "tier_b_claims": [],
    "display": {
        "drug_label": "TestDrug",
        "sponsor_label": "ACME",
        "orr_display": "—",
        "sort_orr": "-1",
        "detail_body_html": "",
    },
    "provenance": {
        "first_added": "2026-06-23",
        "surfaced_by": [],
    },
    "in_scope": True,
    "scope_rationale": "test",
}


def _state_with(trial_overrides=None):
    s = state_lib._empty_state()
    t = copy.deepcopy(VALID_TRIAL)
    if trial_overrides:
        for k, v in trial_overrides.items():
            cur = t
            keys = k.split(".")
            for kk in keys[:-1]:
                cur = cur[kk]
            cur[keys[-1]] = v
    s["trials"]["NCT12345678"] = t
    return s


class SchemaValidationTests(unittest.TestCase):
    def test_empty_state_validates(self):
        state_lib._validate(state_lib._empty_state())

    def test_valid_trial_validates(self):
        state_lib._validate(_state_with())

    def test_schema_version_mismatch_rejected(self):
        s = state_lib._empty_state()
        s["schema_version"] = 999
        with self.assertRaisesRegex(ValueError, "schema_version"):
            state_lib._validate(s)

    def test_missing_top_level_key_rejected(self):
        s = state_lib._empty_state()
        del s["trials"]
        with self.assertRaisesRegex(ValueError, "trials"):
            state_lib._validate(s)

    def test_non_nct_key_rejected(self):
        s = state_lib._empty_state()
        s["trials"]["bogus_key"] = copy.deepcopy(VALID_TRIAL)
        with self.assertRaisesRegex(ValueError, "NCT-prefixed"):
            state_lib._validate(s)

    def test_in_scope_false_in_trials_rejected(self):
        s = _state_with({"in_scope": False})
        with self.assertRaisesRegex(ValueError, "in_scope=false"):
            state_lib._validate(s)

    def test_missing_tier_a_nct_id_rejected(self):
        s = _state_with()
        s["trials"]["NCT12345678"]["tier_a"]["nct_id"] = ""
        with self.assertRaisesRegex(ValueError, "tier_a.nct_id"):
            state_lib._validate(s)


class DriftDetectorTests(unittest.TestCase):
    """The verbatim drift detector is the single most important QC mechanism.

    Rule: if a tier_b_claim has a numeric value, that numeric value must
    appear somewhere in the verbatim mentions across its sources.
    """

    def _claim(self, value, verbatim):
        return {
            "claim_id": "test_claim",
            "field": "ORR",
            "value": value,
            "sources": [{
                "tier": 1, "source_key": "test_src",
                "mentions": [{"location": "abstract", "verbatim": verbatim}],
            }],
        }

    def _state_with_claim(self, claim):
        s = _state_with()
        s["trials"]["NCT12345678"]["tier_b_claims"] = [claim]
        return s

    def test_numeric_value_in_verbatim_accepted(self):
        c = self._claim("21.4%", "The ORR was 21.4% (95% CI ...)")
        state_lib._validate(self._state_with_claim(c))

    def test_numeric_value_missing_from_verbatim_rejected(self):
        c = self._claim("21.4%", "The ORR was 27.3% (95% CI ...)")
        with self.assertRaisesRegex(ValueError, "not found in any verbatim"):
            state_lib._validate(self._state_with_claim(c))

    def test_value_with_comma_normalized(self):
        # Drift detector strips commas before substring check
        c = self._claim("1500", "Among 1,500 patients")
        state_lib._validate(self._state_with_claim(c))

    def test_non_numeric_value_skipped(self):
        # If value has no digits the rule doesn't apply
        c = self._claim("Not Reached", "mDOR was not reached at data cutoff")
        state_lib._validate(self._state_with_claim(c))

    def test_duplicate_claim_id_across_trials_rejected(self):
        s = state_lib._empty_state()
        for nct in ("NCT11111111", "NCT22222222"):
            t = copy.deepcopy(VALID_TRIAL)
            t["tier_a"]["nct_id"] = nct
            t["tier_b_claims"] = [self._claim("10%", "ORR was 10% overall")]
            s["trials"][nct] = t
        with self.assertRaisesRegex(ValueError, "duplicate claim_id"):
            state_lib._validate(s)


class RoundtripTests(unittest.TestCase):
    def test_save_load_roundtrip_preserves_data(self):
        s1 = _state_with()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = Path(f.name)
        try:
            state_lib.save_state(s1, tmp)
            s2 = state_lib.load_state(tmp)
            self.assertEqual(s1["trials"], s2["trials"])
        finally:
            tmp.unlink()


if __name__ == "__main__":
    unittest.main()
