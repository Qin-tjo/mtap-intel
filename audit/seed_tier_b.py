"""One-shot script: add verbatim-anchored tier_b_claims for the top-5 clinically important rows.

Each claim's `verbatim` field is the EXACT text from the snapshotted source.
No paraphrasing. No "as reported" interpretive language.

Verifiable by re-reading audit/snapshots/<source_key>__2026-06-23.html.

Run once; do not re-run (will create duplicate claim_ids).
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402

TODAY = "2026-06-23"
AUDITOR = "claude-opus-4-7 + human-readable verbatim from snapshot"

# ---------- TRIAL: NCT05094336 (AMG 193 / anvumetostat) ----------

AMG193_CLAIMS = [
    {
        "claim_id": "rodon2024_amg193_orr_active_dose",
        "field": "ORR",
        "value": "21.4%",
        "value_numeric": 21.4,
        "n": {
            "count": 42,
            "type": "efficacy-assessable",
            "qualifier": "active and tolerable doses (800 mg o.d., 1200 mg o.d., or 600 mg b.i.d.)"
        },
        "subset": "all tumour types at active doses",
        "ci_95": "10.3% to 36.8%",
        "data_cutoff": "2024-05-23",
        "data_cutoff_confidence": "stated-in-paper",
        "sources": [
            {
                "tier": 1,
                "source_key": "rodon2024_annoncol",
                "mentions": [
                    {
                        "location": "PubMed abstract (Results section)",
                        "verbatim": "Among the efficacy-assessable patients treated at the active and tolerable doses of 800 mg o.d., 1200 mg o.d., or 600 mg b.i.d. (n = 42), objective response rate was 21.4% (95% confidence interval 10.3% to 36.8%)."
                    },
                    {
                        "location": "PubMed abstract (Results section, follow-up sentence)",
                        "verbatim": "Responses were observed across eight different tumor types, including squamous/non-squamous non-small-cell lung cancer, pancreatic adenocarcinoma, and biliary tract cancer."
                    }
                ],
                "snapshot_path": "audit/snapshots/rodon2024_pubmed__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T1",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "Distinct from the 80-patient all-doses safety cohort (40 mg to 1600 mg o.d. or 600 mg b.i.d.) which is the safety denominator. The 21.4% ORR refers to efficacy-assessable patients at the three active dose levels only."
    }
]

# ---------- TRIAL: NCT05245500 (BMS-986504 / navlimetostat) ----------

BMS986504_CLAIMS = [
    {
        "claim_id": "bms986504_nsclc_orr_iaslc2025",
        "field": "ORR",
        "value": "29%",
        "value_numeric": 29.0,
        "n": {
            "count": 35,
            "type": "clinically-evaluable",
            "qualifier": "NSCLC cohort, doses 200 mg to 800 mg"
        },
        "subset": "MTAP-deleted NSCLC",
        "ci_95": None,
        "data_cutoff": None,
        "data_cutoff_confidence": "unknown",
        "sources": [
            {
                "tier": 4,
                "source_key": "bms986504_iaslc2025",
                "mentions": [
                    {
                        "location": "IASLC press release body",
                        "verbatim": "Among clinically evaluable patients in the NSCLC cohort (n=35), BMS-986504 demonstrated a 29% overall response rate (ORR) and a 80% disease control rate."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_iaslc2025__2026-06-23.html"
            },
            {
                "tier": 4,
                "source_key": "bms986504_ascopost2025",
                "mentions": [
                    {
                        "location": "ASCO Post 'Key Study Findings' section",
                        "verbatim": "Among 35 evaluable patients with pretreated, advanced or metastatic NSCLC treated with doses of 200 mg to 800 mg of BMS-986504, responses were reported in 29% of patients."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_ascopost2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "multi-source-agree",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "Two independent press-release sources (IASLC + ASCO Post) report identical figure. Non-peer-reviewed; awaiting peer-reviewed publication."
    },
    {
        "claim_id": "bms986504_nsclc_dcr_iaslc2025",
        "field": "DCR",
        "value": "80%",
        "value_numeric": 80.0,
        "n": {
            "count": 35,
            "type": "clinically-evaluable",
            "qualifier": "NSCLC cohort"
        },
        "subset": "MTAP-deleted NSCLC",
        "ci_95": None,
        "data_cutoff": None,
        "data_cutoff_confidence": "unknown",
        "sources": [
            {
                "tier": 4,
                "source_key": "bms986504_iaslc2025",
                "mentions": [
                    {
                        "location": "IASLC press release body",
                        "verbatim": "Among clinically evaluable patients in the NSCLC cohort (n=35), BMS-986504 demonstrated a 29% overall response rate (ORR) and a 80% disease control rate."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_iaslc2025__2026-06-23.html"
            },
            {
                "tier": 4,
                "source_key": "bms986504_ascopost2025",
                "mentions": [
                    {
                        "location": "ASCO Post 'Key Study Findings' section",
                        "verbatim": "The overall disease control rate was 80%."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_ascopost2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "multi-source-agree",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": ""
    },
    {
        "claim_id": "bms986504_nsclc_mdor_iaslc2025",
        "field": "mDOR",
        "value": "10.5 months",
        "value_numeric": 10.5,
        "n": {
            "count": 35,
            "type": "clinically-evaluable",
            "qualifier": "NSCLC cohort, of those with response"
        },
        "subset": "MTAP-deleted NSCLC responders",
        "ci_95": None,
        "data_cutoff": None,
        "data_cutoff_confidence": "unknown",
        "sources": [
            {
                "tier": 4,
                "source_key": "bms986504_iaslc2025",
                "mentions": [
                    {
                        "location": "IASLC press release body",
                        "verbatim": "Median duration of response: 10.5 months; time to response: 4.3 months."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_iaslc2025__2026-06-23.html"
            },
            {
                "tier": 4,
                "source_key": "bms986504_ascopost2025",
                "mentions": [
                    {
                        "location": "ASCO Post 'Key Study Findings' section",
                        "verbatim": "The median duration of overall response was 10.5 months, with a median time to response of 4.3 months."
                    }
                ],
                "snapshot_path": "audit/snapshots/bms986504_ascopost2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "multi-source-agree",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "IASLC/WCLC 2025 reports TTR 4.3 months for the NSCLC cohort; the 4.6-month figure quoted elsewhere in the dashboard refers to the all-tumour-type cohort from ASCO 2025 abstract 3011 (George B 2025), not NSCLC specifically."
    }
]

# ---------- TRIAL: NCT06137144 (AZD3470 PRIMAVERA) ----------

AZD3470_CLAIMS = [
    {
        "claim_id": "azd3470_primavera_orr_450mg",
        "field": "ORR",
        "value": "58%",
        "value_numeric": 58.0,
        "n": {
            "count": 31,
            "type": "treated",
            "qualifier": "patients receiving ≥450 mg dose"
        },
        "subset": "R/R classical Hodgkin Lymphoma, ≥450 mg",
        "ci_95": None,
        "data_cutoff": "2026-05-30",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "azd3470_clinicaltrialsarena_asco2026",
                "mentions": [
                    {
                        "location": "Clinical Trials Arena article body",
                        "verbatim": "Encouragingly, positive efficacy was indicated in patients treated with ≥450mg of the drug (N=31), with an objective response rate (ORR) of 58%, and complete response (CR) of 35%."
                    }
                ],
                "snapshot_path": "audit/snapshots/azd3470_clinicaltrialsarena_asco2026__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "ASCO 2026 first disclosure. Dose-escalation only; 39 R/R cHL patients total in escalation cohort; median 6 prior lines incl. brentuximab vedotin + anti-PD1. The 600 mg subset (N=16) reported ORR 63%, CR 44% by the same source."
    },
    {
        "claim_id": "azd3470_primavera_cr_450mg",
        "field": "CR",
        "value": "35%",
        "value_numeric": 35.0,
        "n": {
            "count": 31,
            "type": "treated",
            "qualifier": "patients receiving ≥450 mg dose"
        },
        "subset": "R/R classical Hodgkin Lymphoma, ≥450 mg",
        "ci_95": None,
        "data_cutoff": "2026-05-30",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "azd3470_clinicaltrialsarena_asco2026",
                "mentions": [
                    {
                        "location": "Clinical Trials Arena article body",
                        "verbatim": "Encouragingly, positive efficacy was indicated in patients treated with ≥450mg of the drug (N=31), with an objective response rate (ORR) of 58%, and complete response (CR) of 35%."
                    }
                ],
                "snapshot_path": "audit/snapshots/azd3470_clinicaltrialsarena_asco2026__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": ""
    }
]

# ---------- TRIAL: NCT04794699 (IDE397 + Trodelvy in MTAP-del urothelial) ----------

IDE397_CLAIMS = [
    {
        "claim_id": "ide397_trodelvy_urothelial_dl1_orr",
        "field": "ORR",
        "value": "33%",
        "value_numeric": 33.0,
        "n": {
            "count": 9,
            "type": "evaluable",
            "qualifier": "Dose Level 1 (IDE397 15 mg + Trodelvy 10 mg/kg)"
        },
        "subset": "MTAP-deleted urothelial cancer, DL1",
        "ci_95": None,
        "data_cutoff": "2025-08-29",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "ide397_ideayapress_sep2025",
                "mentions": [
                    {
                        "location": "IDEAYA press release, key findings table",
                        "verbatim": "Dose Level 1 (DL1) Dose Level 2 (DL2) IDE397 (15mg) + Trodelvy (10mg/kg) IDE397 (30mg) + Trodelvy (7.5mg/kg) Evaluable patients (n) n=9 n=7 ORR (cPR+uPR) 33% (3cPR) 57% (3cPR +1uPR) DCR% 100% (9/9) 71% (5/7)"
                    },
                    {
                        "location": "IDEAYA press release, narrative summary",
                        "verbatim": "33% ORR at DL1 (3/9); 3 confirmed partial responses (cPR), including one patient with a confirmed response after the cut-off date, and 57% ORR at DL2 (3 cPR and 1 unconfirmed partial response (uPR))."
                    }
                ],
                "snapshot_path": "audit/snapshots/ide397_ideayapress_sep2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "Same press release reports DL2 ORR 57% (4/7; 3 cPR + 1 uPR). DCR 100% at DL1, 71% at DL2. mPFS and mDOR not reached."
    },
    {
        "claim_id": "ide397_trodelvy_urothelial_dl2_orr",
        "field": "ORR",
        "value": "57%",
        "value_numeric": 57.0,
        "n": {
            "count": 7,
            "type": "evaluable",
            "qualifier": "Dose Level 2 (IDE397 30 mg + Trodelvy 7.5 mg/kg)"
        },
        "subset": "MTAP-deleted urothelial cancer, DL2",
        "ci_95": None,
        "data_cutoff": "2025-08-29",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "ide397_ideayapress_sep2025",
                "mentions": [
                    {
                        "location": "IDEAYA press release, key findings table",
                        "verbatim": "Dose Level 1 (DL1) Dose Level 2 (DL2) IDE397 (15mg) + Trodelvy (10mg/kg) IDE397 (30mg) + Trodelvy (7.5mg/kg) Evaluable patients (n) n=9 n=7 ORR (cPR+uPR) 33% (3cPR) 57% (3cPR +1uPR) DCR% 100% (9/9) 71% (5/7)"
                    },
                    {
                        "location": "IDEAYA press release, narrative summary",
                        "verbatim": "33% ORR at DL1 (3/9); 3 confirmed partial responses (cPR), including one patient with a confirmed response after the cut-off date, and 57% ORR at DL2 (3 cPR and 1 unconfirmed partial response (uPR))."
                    }
                ],
                "snapshot_path": "audit/snapshots/ide397_ideayapress_sep2025__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "Of the 4 responses at DL2, 3 are confirmed partial (cPR), 1 is unconfirmed (uPR)."
    }
]

# ---------- TRIAL: Tango vopimetostat + daraxonrasib in MTAP-del PDAC ----------
# The dashboard's row is NCT06922591 (TNG462 + Daraxonrasib). Confirm.

TNG462_DARA_CLAIMS = [
    {
        "claim_id": "tng462_daraxonrasib_pdac_orr_2026",
        "field": "ORR",
        "value": "92%",
        "value_numeric": 92.0,
        "n": {
            "count": 12,
            "type": "response-evaluable",
            "qualifier": "PDAC patients with ≥14 weeks follow-up"
        },
        "subset": "MTAP-deleted, RAS-mutant PDAC; vopimetostat + daraxonrasib arm",
        "ci_95": None,
        "data_cutoff": "2026-05-28",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "tng462_daraxonrasib_press_2026",
                "mentions": [
                    {
                        "location": "Press release headline + body",
                        "verbatim": "Tango Therapeutics Announces Combination of Vopimetostat and Daraxonrasib Demonstrated 92% Objective Response Rate in Pancreatic Cancer"
                    },
                    {
                        "location": "Press release 'Topline Clinical Data Highlights' section",
                        "verbatim": "PDAC: 92% objective response rate (ORR) (11/12; 9 of 11 responses confirmed) 90% 6-month PFS rate 100% disease control rate (DCR)"
                    },
                    {
                        "location": "Press release narrative",
                        "verbatim": "As of the data cutoff, 12 patients with PDAC and 3 patients with NSCLC were response evaluable with at least 14 weeks of follow up."
                    }
                ],
                "snapshot_path": "audit/snapshots/tng462_daraxonrasib_press_2026__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": "IMPORTANT: 92% = 11/12 (not 9/11). Of those 11 responses, 9 are confirmed. The dashboard tooltip previously stated '9/11 confirmed' which is technically true but misleading without the 11/12 context. DCR 100%; 6-month PFS rate 90% (median PFS not yet reached). Single-arm Phase 1/2 dose-escalation; not peer-reviewed."
    },
    {
        "claim_id": "tng462_daraxonrasib_pdac_dcr_2026",
        "field": "DCR",
        "value": "100%",
        "value_numeric": 100.0,
        "n": {
            "count": 12,
            "type": "response-evaluable",
            "qualifier": "PDAC patients with ≥14 weeks follow-up"
        },
        "subset": "MTAP-deleted, RAS-mutant PDAC; vopimetostat + daraxonrasib arm",
        "ci_95": None,
        "data_cutoff": "2026-05-28",
        "data_cutoff_confidence": "stated-in-press",
        "sources": [
            {
                "tier": 4,
                "source_key": "tng462_daraxonrasib_press_2026",
                "mentions": [
                    {
                        "location": "Press release 'Topline Clinical Data Highlights' section",
                        "verbatim": "PDAC: 92% objective response rate (ORR) (11/12; 9 of 11 responses confirmed) 90% 6-month PFS rate 100% disease control rate (DCR)"
                    }
                ],
                "snapshot_path": "audit/snapshots/tng462_daraxonrasib_press_2026__2026-06-23.html"
            }
        ],
        "cross_source_check": "single-source-T4",
        "confidence": "verified",
        "last_audited": TODAY,
        "audited_by": AUDITOR,
        "notes": ""
    }
]


def map_to_trials(state: dict) -> dict[str, list[dict]]:
    """Find the row_id for each NCT we care about."""
    by_nct: dict[str, str] = {}
    for row_id, t in state["trials"].items():
        nct = t["tier_a"]["nct_id"]
        # Prefer the primary row (without __viewN suffix) for the seeded claims.
        if "__view" not in row_id:
            by_nct[nct] = row_id

    plan = {
        by_nct.get("NCT05094336"): AMG193_CLAIMS,
        by_nct.get("NCT05245500"): BMS986504_CLAIMS,
        by_nct.get("NCT06137144"): AZD3470_CLAIMS,
        by_nct.get("NCT04794699"): IDE397_CLAIMS,
        # Vopimetostat + daraxonrasib PDAC — find the row by drug+combo
    }
    for row_id, t in state["trials"].items():
        if "vopimetostat" in t["display"].get("drug_label", "").lower() or t["display"].get("drug_label", "").startswith("TNG462"):
            sort_orr = t["display"].get("sort_orr", "-1")
            if str(sort_orr).startswith("92"):
                plan[row_id] = TNG462_DARA_CLAIMS
                break

    plan.pop(None, None)
    return plan


def main():
    state = state_lib.load_state()
    plan = map_to_trials(state)
    print(f"Plan: {len(plan)} trials to seed")
    for row_id, claims in plan.items():
        t = state["trials"][row_id]
        existing_ids = {c["claim_id"] for c in t.get("tier_b_claims", [])}
        new = [c for c in claims if c["claim_id"] not in existing_ids]
        if not new:
            print(f"  {row_id} [{t['display']['drug_label']}] — already seeded, skip")
            continue
        t.setdefault("tier_b_claims", []).extend(new)
        print(f"  {row_id} [{t['display']['drug_label']}] — added {len(new)} claim(s): "
              + ", ".join(c['claim_id'] for c in new))

    state_lib.save_state(state)
    print(f"\nstate.json updated. Total trials: {len(state['trials'])}.")


if __name__ == "__main__":
    main()
