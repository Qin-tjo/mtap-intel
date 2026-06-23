"""Round 3 Tier-B: vopimetostat (TNG462) monotherapy — Tango press Oct 23 2025."""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402

TODAY = "2026-06-23"
AUDITOR = "claude-opus-4-7 + human-readable verbatim from snapshot"

TNG462_MONO_CLAIMS = [
    {
        "claim_id": "tng462_mono_histology_agnostic_orr_oct2025",
        "field": "ORR",
        "value": "49%",
        "value_numeric": 49.0,
        "n": {
            "count": 41,
            "type": "treated-at-active-dose",
            "qualifier": "13 different cancers; ≥6 months follow-up; histology-agnostic cohort"
        },
        "subset": "MTAP-deleted advanced cancers (histology-agnostic), monotherapy",
        "ci_95": None,
        "data_cutoff": "2025-09-01",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "tng462_monotherapy_press_oct2025",
                "mentions": [
                    {
                        "location": "Press release narrative",
                        "verbatim": "Today, we also announced data from the histology-agnostic cohort of the vopimetostat phase 1/2 trial, where we observed a 49% ORR and mPFS of 9.1 months (excluding sarcoma)."
                    },
                    {
                        "location": "Press release 'Efficacy Results in the Histology Agnostic Cohort' section",
                        "verbatim": "As of September 1, 2025, 41 patients with 13 different cancers were enrolled at active doses and had received a first dose more than 6 months prior to the analysis."
                    },
                    {
                        "location": "Press release 'Efficacy Results in the Histology Agnostic Cohort' section",
                        "verbatim": "In this histology agnostic cohort: ORR: 49% DCR: 89% mPFS: 9.1 months"
                    }
                ],
                "snapshot_path": "audit/snapshots/tng462_monotherapy_press_oct2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "49% ORR is in histology-agnostic cohort (excludes sarcoma per source). 41 patients at active doses with ≥6 months follow-up as of Sep 1, 2025 data cutoff. Source is sponsor press release; non-peer-reviewed."
    },
    {
        "claim_id": "tng462_mono_pdac_2L_orr_oct2025",
        "field": "ORR",
        "value": "25%",
        "value_numeric": 25.0,
        "n": {
            "count": None,
            "type": "subset",
            "qualifier": "2L MTAP-deleted PDAC patients within the 39 active-dose pancreatic cohort"
        },
        "subset": "MTAP-deleted PDAC, 2nd-line",
        "ci_95": None,
        "data_cutoff": "2025-09-01",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "tng462_monotherapy_press_oct2025",
                "mentions": [
                    {
                        "location": "Press release narrative",
                        "verbatim": "In 2L MTAP-deleted pancreatic cancer, the median PFS is 7.2 months and the ORR is 25%, more than double that observed in historical control studies, supporting our decision to initiate a pivotal trial in this patient population in 2026."
                    },
                    {
                        "location": "Press release efficacy bullets",
                        "verbatim": "ORR in 2L pancreatic cancer patients: 25% ORR for all pancreatic cancer patients: 15% DCR for all pancreatic cancer patients: 71% mPFS in 2L patients: 7.2 months"
                    }
                ],
                "snapshot_path": "audit/snapshots/tng462_monotherapy_press_oct2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "2L MTAP-del PDAC monotherapy ORR. Note: all-PDAC ORR was 15% (including 1L); the 25% 2L figure supported the planned 2L PDAC pivotal trial. This monotherapy result is the comparator that vopimetostat + daraxonrasib's 92% (NCT06922591) must beat in combination context."
    }
]


def main():
    state = state_lib.load_state()
    by_nct = {t["tier_a"]["nct_id"]: rid for rid, t in state["trials"].items() if "__view" not in rid}
    rid = by_nct.get("NCT05732831")
    if not rid:
        print("NCT05732831 not in state.json")
        return
    existing = {c["claim_id"] for c in state["trials"][rid].get("tier_b_claims", [])}
    new = [c for c in TNG462_MONO_CLAIMS if c["claim_id"] not in existing]
    if new:
        state["trials"][rid].setdefault("tier_b_claims", []).extend(new)
        print(f"  {rid} — added {len(new)} claim(s)")
    else:
        print(f"  {rid} — already seeded")
    state_lib.save_state(state)


if __name__ == "__main__":
    main()
