"""Round 2 Tier-B seeding: JNJ-64619178 + AG-270 (both T1 peer-reviewed PubMed)."""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402

TODAY = "2026-06-23"
AUDITOR = "claude-opus-4-7 + human-readable verbatim from PubMed abstract"

JNJ_CLAIMS = [
    {
        "claim_id": "vieito2023_jnj64619178_orr_overall",
        "field": "ORR",
        "value": "5.6%",
        "value_numeric": 5.6,
        "n": {"count": 90, "type": "treated", "qualifier": "all dose levels, both schedules"},
        "subset": "all advanced solid tumours + NHL",
        "ci_95": None,
        "data_cutoff": None,
        "data_cutoff_confidence": "unknown",
        "sources": [
            {
                "tier": 1,
                "source_key": "vieito2023_jnj64619178_clincancerres",
                "mentions": [
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "Ninety patients received JNJ-64619178. Thrombocytopenia was identified as the only dose-limiting toxicity."
                    },
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "The objective response rate was 5.6% (5 of 90)."
                    },
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "Patients with adenoid cystic carcinoma (ACC) had an ORR of 11.5% (3 of 26) and a median progression-free survival of 19.1 months."
                    }
                ],
                "snapshot_path": "audit/snapshots/vieito2023_jnj64619178_pubmed__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T1",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "First-generation PRMT5i (SAM-competitive); not MTAP-selective. ACC subset (n=26) had elevated 11.5% ORR — biology of ACC may overlap with PRMT5 dependency. Limited activity outside ACC was a key signal that drove the field toward MTA-cooperative selectivity."
    }
]

AG270_CLAIMS = [
    {
        "claim_id": "gounder2025_ag270_orr_overall",
        "field": "ORR",
        "value": "5%",
        "value_numeric": 5.0,
        "n": {"count": 40, "type": "treated", "qualifier": "all dose levels, monotherapy"},
        "subset": "MTAP-deleted advanced malignancies (CDKN2A/MTAP homdel and/or MTAP IHC loss)",
        "ci_95": None,
        "data_cutoff": None,
        "data_cutoff_confidence": "unknown",
        "sources": [
            {
                "tier": 1,
                "source_key": "gounder2025_ag270_natcomm",
                "mentions": [
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "Forty patients were treated with AG-270/S095033."
                    },
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "Two partial responses were observed; five additional patients achieved radiographically confirmed stable disease for ≥16 weeks."
                    },
                    {
                        "location": "PubMed abstract (Methods/Patients section)",
                        "verbatim": "Eligible patients had tumors with homozygous deletion of CDKN2A/MTAP and/or loss of MTAP protein by immunohistochemistry."
                    }
                ],
                "snapshot_path": "audit/snapshots/gounder2025_ag270_pubmed__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T1",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "5% ORR = 2 PRs / 40 treated. Plus 5 SD ≥16 weeks. Eligibility was MTAP-deleted (by NGS) and/or MTAP IHC loss. AG-270/S095033 was the leading MAT2A programme until IDE397 superseded it as the field's preferred MAT2A inhibitor."
    }
]


def main():
    state = state_lib.load_state()
    by_nct: dict[str, str] = {}
    for row_id, t in state["trials"].items():
        nct = t["tier_a"]["nct_id"]
        if "__view" not in row_id:
            by_nct[nct] = row_id

    plan = {
        by_nct.get("NCT03573310"): JNJ_CLAIMS,   # JNJ-64619178 in solid tumors (Vieito 2023)
        by_nct.get("NCT03435250"): AG270_CLAIMS,  # AG-270 (Gounder 2025)
    }
    plan.pop(None, None)

    for row_id, claims in plan.items():
        existing = {c["claim_id"] for c in state["trials"][row_id].get("tier_b_claims", [])}
        new = [c for c in claims if c["claim_id"] not in existing]
        if new:
            state["trials"][row_id].setdefault("tier_b_claims", []).extend(new)
            print(f"  {row_id} — added {len(new)} claim(s)")
        else:
            print(f"  {row_id} — already seeded")

    state_lib.save_state(state)
    print(f"\nstate.json: {len(state['trials'])} trials.")


if __name__ == "__main__":
    main()
