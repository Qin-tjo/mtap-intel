"""triage_apply.py — apply manual review decisions from the last triage pass.

Reads the most recent triage/<date>__candidates.json, augments the
review-needed entries with manual classifications (hard-coded below by NCT),
and applies the merged result to state.json:

  - out-of-scope entries are added to state.out_of_scope[]
  - in-scope entries are added to state.trials[] with display defaults
    derived from the CT.gov record (no Tier-B claims yet; backlog flag set)
"""

from __future__ import annotations
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402
from audit.lib import ctgov                # noqa: E402

TRIAGE_DIR = ROOT / "audit" / "triage"
TODAY = dt.date.today().isoformat()

# ===========================================================================
# Manual classifications for the 31 review-needed entries (by NCT).
# Decision was made by human reading the title / summary / interventions
# returned by CT.gov v2. Each line includes the reason for audit-trail.
# ===========================================================================

MANUAL_DECISIONS: dict[str, dict] = {
    # ---------- IN-SCOPE: new MTAP/PRMT5/MAT2A axis programmes ----------
    "NCT06593522": {
        "decision": "in-scope",
        "drug_label": "Anvumetostat",
        "drug_aliases": ["AMG 193"],
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "NSCLC",
        "notes": "Amgen MTAPESTRY 201 — Phase 2 anvumetostat in MTAP-deleted advanced NSCLC. Follow-on to the MTAPESTRY 101 Phase 1/2.",
    },
    "NCT06414460": {
        "decision": "in-scope",
        "drug_label": "ISM3412",
        "mechanism_class": "MTA-cooperative PRMT5i",   # InSilico Medicine PRMT5i — surfaced via MTAP query
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "InSilico Medicine ISM3412 — Phase 1 in advanced/metastatic solid tumours; surfaced via MTAP/PRMT5 query. Mechanism class assigned to MTA-cooperative PRMT5i based on sponsor's pipeline (verify on next accuracy pass).",
    },
    "NCT06589596": {
        "decision": "in-scope",
        "drug_label": "BGB-58067",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "BeOne / BeiGene BGB-58067 — FIH dose escalation/expansion ± combinations. Confirmed MTAP-axis programme by parallel investigator-initiated MTAP-del GBM study (NCT07485049).",
    },
    "NCT06796699": {
        "decision": "in-scope",
        "drug_label": "GH56",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "Suzhou Genhouse GH56 capsule — Phase Ia/Ib in MTAP-deleted advanced solid tumours.",
    },
    "NCT06971523": {
        "decision": "in-scope",
        "drug_label": "CTS3497",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "CytosinLab Therapeutics CTS3497 — Phase 1/2 in MTAP-deficient malignancies. Mechanism class assigned per company pipeline; verify next pass.",
    },
    "NCT06973863": {
        "decision": "in-scope",
        "drug_label": "PEP08",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "PharmaEngine PEP08 — Phase 1 in MTAP-deleted advanced/metastatic solid tumours.",
    },
    "NCT07485049": {
        "decision": "in-scope",
        "drug_label": "BGB-58067",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "GBM",
        "notes": "Investigator-initiated (Sanai / Ivy Brain Tumor Center) Phase 0/1 of BeiGene BGB-58067 in newly diagnosed MTAP-deleted glioblastoma.",
    },
    "NCT07567859": {
        "decision": "in-scope",
        "drug_label": "HS-10587",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "Jiangsu Hansoh Pharmaceutical HS-10587 — Phase 1 in advanced solid tumours; condition listed as 'MTAP Deletion'.",
    },
    "NCT07128303": {
        "decision": "in-scope",
        "drug_label": "GS-5319",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "Gilead GS-5319 — solid tumours with MTAP-related gene alteration. CT.gov brief summary explicitly mentions methylthioadenosine pathway.",
    },
    "NCT07601243": {
        "decision": "in-scope",
        "drug_label": "GS-2426",
        "mechanism_class": "MTA-cooperative PRMT5i",
        "biomarker_tag": "MTAP homdel",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid (basket)",
        "notes": "Gilead GS-2426 — Phase 1 in MTAP-deleted advanced solid tumours.",
    },
    "NCT05528055": {
        "decision": "in-scope",
        "drug_label": "SCR-6920",
        "mechanism_class": "First-gen PRMT5i (SAM-competitive)",
        "biomarker_tag": "Not selected",
        "combination_tag": "Monotherapy",
        "indication_label": "Solid · NHL",
        "notes": "Jiangsu Simcere SCR-6920 — Phase 1 PRMT5 inhibitor (first-generation, non-MTAP-selected enrolment) in advanced solid tumours and non-Hodgkin lymphoma. Included for mechanism-class completeness; MTAP-axis programmes are the dashboard's primary focus.",
    },

    # ---------- OUT-OF-SCOPE: not MTAP-axis therapeutics ----------
    "NCT03361358": {"decision": "out-of-scope", "reason": "Agios pre-screening study to identify MTAP loss — observational biomarker screen, no therapeutic intervention."},
    "NCT03380468": {"decision": "out-of-scope", "reason": "Adjuvant cisplatin/pemetrexed in early-stage NSCLC — standard chemotherapy, no PRMT5/MAT2A/MTAP-axis drug; 'methylthioadenosine' presumably in conditions/keywords."},
    "NCT03951142": {"decision": "out-of-scope", "reason": "Losartan imaging study evaluating perfusion in solid tumours — angiotensin receptor blocker, not MTAP-axis."},
    "NCT04177953": {"decision": "out-of-scope", "reason": "Nivolumab + chemo in resectable pleural mesothelioma — PD-1 immunotherapy, not MTAP-axis."},
    "NCT04222972": {"decision": "out-of-scope", "reason": "Pralsetinib (RET inhibitor) vs SoC in 1L NSCLC — RET-TKI, not MTAP-axis."},
    "NCT04297605": {"decision": "out-of-scope", "reason": "Pembrolizumab + single-agent chemo as 1L treatment — PD-1 + chemo, not MTAP-axis."},
    "NCT04581824": {"decision": "out-of-scope", "reason": "Dostarlimab vs pembrolizumab head-to-head — both PD-1 antibodies, not MTAP-axis."},
    "NCT04736823": {"decision": "out-of-scope", "reason": "AK112 (ivonescimab; PD-1/VEGF bispecific) + chemo in NSCLC — bispecific antibody, not MTAP-axis."},
    "NCT04902703": {"decision": "out-of-scope", "reason": "Sargramostim (GM-CSF) in Alzheimer's disease — non-oncology indication."},
    "NCT04964960": {"decision": "out-of-scope", "reason": "Pembrolizumab + chemo for brain metastases — PD-1 + chemo, not MTAP-axis."},
    "NCT05299125": {"decision": "out-of-scope", "reason": "Amivantamab + lazertinib + pemetrexed in EGFR-mutant NSCLC — EGFR-directed bispecific + EGFR-TKI, not MTAP-axis."},
    "NCT05335941": {"decision": "out-of-scope", "reason": "Pemetrexed + AB928 (etrumadenant; adenosine A2A/A2B antagonist) + zimberelimab (PD-1) — adenosine pathway, not MTAP-axis."},
    "NCT05382559": {"decision": "out-of-scope", "reason": "ASP3082 / setidegrasib (Astellas) — KRAS G12D-targeted degrader, not MTAP-axis."},
    "NCT05775796": {"decision": "out-of-scope", "reason": "Serplulimab (PD-1) + chemo in resectable NSCLC — PD-1 + chemo, not MTAP-axis."},
    "NCT05904379": {"decision": "out-of-scope", "reason": "AK112 + AK104 ± chemo in advanced NSCLC — PD-1/VEGF + PD-1/CTLA-4 bispecifics, not MTAP-axis."},
    "NCT06241807": {"decision": "out-of-scope", "reason": "Neoadjuvant camrelizumab (PD-1) + chemo in resectable stage IIIA-IIIB NSCLC — PD-1 + chemo, not MTAP-axis."},
    "NCT06380348": {"decision": "out-of-scope", "reason": "JMT101 (EGFR antibody) + osimertinib (EGFR-TKI) vs cisplatin/pemetrexed in EGFR-mutant NSCLC — EGFR-directed, not MTAP-axis."},
    "NCT06769295": {"decision": "out-of-scope", "reason": "AK112 (PD-1/VEGF bispecific) + chemo in NSCLC — bispecific antibody, not MTAP-axis."},
    "NCT07554846": {"decision": "out-of-scope", "reason": "Perioperative immunotherapy comparison in resectable NSCLC — immunotherapy timing study, not MTAP-axis."},
    "NCT07593573": {"decision": "out-of-scope", "reason": "Exploration of MTAP deletion in osteosarcoma by IHC — biomarker observational study, no therapeutic intervention."},
}


def make_trial_entry(nct: str, ctgov_rec: dict, decision: dict) -> dict:
    """Build a state.json trials[NCT] entry from a CT.gov record + manual decision."""
    phases = ctgov_rec.get("phases", [])
    phase_tag = _phase_short_tag(phases)
    status = ctgov_rec.get("status", "")
    status_short = _status_short(status)
    return {
        "tier_a": {
            "nct_id": nct,
            "drug_canonical": decision.get("drug_label"),
            "drug_aliases": decision.get("drug_aliases", []),
            "sponsor": ctgov_rec.get("sponsor", ""),
            "sponsor_history": [],
            "mechanism_class": decision["mechanism_class"],
            "phases": phases,
            "status": status,
            "conditions": ctgov_rec.get("conditions", []),
            "interventions": [i["name"] for i in ctgov_rec.get("interventions", [])],
            "primary_endpoints": ctgov_rec.get("primary_endpoints", []),
            "start_date": ctgov_rec.get("start_date", ""),
            "first_patient_dosed": None,
            "ctgov_url": f"https://clinicaltrials.gov/study/{nct}",
            "last_synced": TODAY,
            "last_synced_status": "fresh-from-triage",
        },
        "tier_b_claims": [],
        "display": {
            "drug_label": decision["drug_label"],
            "sponsor_label": ctgov_rec.get("sponsor", ""),
            "mechanism_tag": _mech_short(decision["mechanism_class"]),
            "phase_tag": phase_tag,
            "status_tag": status_short,
            "indication_label": decision.get("indication_label", "Solid (basket)"),
            "biomarker_tag": decision.get("biomarker_tag", "MTAP homdel"),
            "combination_tag": decision.get("combination_tag", "Monotherapy"),
            "orr_display": "—",
            "orr_tooltip": "No efficacy data disclosed at this time.",
            "n_display": "—",
            "n_ctx": "",
            "start_display": ctgov_rec.get("start_date", ""),
            "has_results": "no",
            "sort_drug": decision["drug_label"].lower(),
            "sort_mech": _mech_sort(decision["mechanism_class"]),
            "sort_phase": _phase_sort(phases),
            "sort_status": _status_sort(status),
            "sort_orr": "-1",
            "sort_n": "-1",
            "sort_start": ctgov_rec.get("start_date", ""),
            "search_keywords": " ".join([
                nct.lower(),
                decision["drug_label"].lower(),
                ctgov_rec.get("brief_title", "").lower(),
                ctgov_rec.get("sponsor", "").lower(),
            ]).strip(),
            "pill_mech_class": _pill_class("mech", _mech_short_css(decision["mechanism_class"])),
            "pill_phase_class": _pill_class("ph", _phase_short_css(phase_tag)),
            "pill_status_class": _pill_class("st", _status_short_css(status_short)),
            "pill_bm_class": _pill_class("bm", _bm_short_css(decision.get("biomarker_tag", "MTAP homdel"))),
            "pill_cb_class": _pill_class("cb", _cb_short_css(decision.get("combination_tag", "Monotherapy"))),
            "detail_body_html": _detail_body(ctgov_rec, decision),
        },
        "provenance": {
            "first_added": TODAY,
            "first_added_pass": f"triage-apply-{TODAY}",
            "surfaced_by": ["completeness-pass-" + TODAY],
            "review_triangulation": [],
            "notes": decision.get("notes", ""),
        },
        "in_scope": True,
        "scope_rationale": f"In-scope per scope.md: drug targets MTAP/PRMT5/MAT2A axis ({decision['mechanism_class']}); active trial; added via triage on {TODAY}.",
    }


def make_oos_entry(nct: str, ctgov_rec: dict, decision: dict) -> dict:
    interventions = [i["name"] for i in ctgov_rec.get("interventions", [])]
    return {
        "id": nct,
        "name": ctgov_rec.get("brief_title", ""),
        "drug": ", ".join(interventions),
        "sponsor": ctgov_rec.get("sponsor", ""),
        "first_seen": TODAY,
        "reason": decision["reason"],
        "surfaced_by": ["completeness-pass-" + TODAY],
    }


# ---------- small helpers for display defaults ----------

def _phase_short_tag(phases):
    if not phases: return ""
    if phases == ["Phase 1"]: return "Ph1"
    if phases == ["Phase 2"]: return "Ph2"
    if phases == ["Phase 3"]: return "Ph3"
    if phases == ["Phase 1", "Phase 2"]: return "Ph1/2"
    if phases == ["Phase 2", "Phase 3"]: return "Ph2/3"
    if phases == ["Phase 0/1"]: return "Ph0/1"
    return "/".join([p.replace("Phase ", "Ph") for p in phases])

def _status_short(s):
    if s == "Recruiting": return "Active"
    if s == "Active, not recruiting": return "Active"
    if s == "Not yet recruiting": return "Pending"
    if s == "Completed": return "Completed"
    if s == "Terminated": return "Terminated"
    return s or "Active"

def _mech_short(c):
    if "MTA-cooperative" in c: return "MTA-coop PRMT5i"
    if "First-gen PRMT5" in c: return "1st-gen PRMT5i"
    if "MAT2A" in c: return "MAT2A inh"
    return c

def _mech_sort(c):
    if "MTA-cooperative" in c: return "mta-coop prmt5i"
    if "First-gen" in c: return "1st-gen prmt5i"
    if "MAT2A" in c: return "mat2a inh"
    return c.lower()

def _phase_sort(p):
    if "Phase 3" in p: return "3"
    if "Phase 2" in p: return "2"
    if "Phase 1" in p: return "1"
    return "0"

def _status_sort(s):
    if s in ("Recruiting", "Active, not recruiting", "Enrolling by invitation"): return "1"
    if s == "Completed": return "3"
    if s == "Terminated": return "4"
    return "2"

def _mech_short_css(c):
    if "MTA-cooperative" in c: return "mta"
    if "First-gen" in c: return "fg"
    if "MAT2A" in c: return "mat2a"
    return ""

def _phase_short_css(p):
    if p == "Ph1": return "ph1"
    if p == "Ph2": return "ph2"
    if p == "Ph3": return "ph3"
    if p == "Ph1/2": return "ph12"
    if p == "Ph2/3": return "ph23"
    return ""

def _status_short_css(s):
    if s == "Active": return "active"
    if s == "Completed": return "completed"
    if s == "Terminated": return "terminated"
    if s == "Pending": return "pending"
    return ""

def _bm_short_css(b):
    if b == "Not selected": return "none"
    return "strict"

def _cb_short_css(c):
    if c == "Monotherapy": return "mono"
    if "chemo" in c.lower(): return "chemo"
    if "IO" in c or "PD" in c: return "io"
    if "KRAS" in c or "RAS" in c: return "kras"
    return "other"

def _pill_class(kind, css):
    return f"pill {kind}-{css}" if css else "pill"

def _detail_body(rec, decision):
    title = rec.get("brief_title", "")
    notes = decision.get("notes", "")
    return (
        f'<div class="trial-detail-row"><b>Summary:</b> {title} '
        f'(added via triage from completeness pass {TODAY}; '
        f'no efficacy data published as of this audit). {notes}</div>'
        f'<div class="trial-detail-row"><b>Interventions:</b> '
        f'{" | ".join(i["name"] for i in rec.get("interventions", []))}</div>'
    )


def main():
    # Load the auto-classified file for the 28 auto OOS
    auto_path = TRIAGE_DIR / f"{TODAY}__proposed_oos.json"
    if not auto_path.exists():
        print(f"Run audit/triage.py first to produce {auto_path}")
        return
    auto_oos = json.loads(auto_path.read_text())

    state = state_lib.load_state()
    existing_oos = {item["id"] for item in state.get("out_of_scope", [])}
    existing_trials = {t["tier_a"]["nct_id"] for t in state["trials"].values()}

    # 1) Apply auto OOS
    n_auto_oos_added = 0
    for entry in auto_oos:
        if entry["id"] in existing_oos:
            continue
        state["out_of_scope"].append(entry)
        existing_oos.add(entry["id"])
        n_auto_oos_added += 1
    print(f"[triage_apply] auto-OOS merged: {n_auto_oos_added}")

    # 2) Apply manual decisions
    n_manual_oos = n_manual_in = 0
    for nct, dec in MANUAL_DECISIONS.items():
        if dec["decision"] == "out-of-scope" and nct not in existing_oos:
            rec = ctgov.fetch_trial(nct) or {}
            time.sleep(0.1)
            state["out_of_scope"].append(make_oos_entry(nct, rec, dec))
            existing_oos.add(nct)
            n_manual_oos += 1
        elif dec["decision"] == "in-scope" and nct not in existing_trials:
            print(f"  fetching {nct} for in-scope add … ", end="", flush=True)
            rec = ctgov.fetch_trial(nct)
            time.sleep(0.15)
            if rec and "_error" not in rec:
                state["trials"][nct] = make_trial_entry(nct, rec, dec)
                existing_trials.add(nct)
                n_manual_in += 1
                print("ok")
            else:
                print(f"ERROR — skipped: {rec.get('_error','unknown')}")
    print(f"[triage_apply] manual OOS merged: {n_manual_oos}")
    print(f"[triage_apply] manual in-scope rows added: {n_manual_in}")

    state_lib.save_state(state)
    total = len(state['trials'])
    oos = len(state['out_of_scope'])
    print(f"\nstate.json now has {total} trials, {oos} out-of-scope entries.")


if __name__ == "__main__":
    main()
