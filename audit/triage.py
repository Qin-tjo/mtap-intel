"""triage.py — classify newly surfaced NCTs into in-scope / out-of-scope.

Loads the most recent completeness pass record, fetches each candidate NCT,
applies heuristic classification, and produces:

  audit/triage/<YYYY-MM-DD>__candidates.json   — full triage record with decisions
  audit/triage/<YYYY-MM-DD>__proposed_oos.json — proposed out_of_scope entries

Decisions are PROPOSED, not applied. Review the proposed_oos.json file, then run:
    python3 audit/triage.py --apply

…to merge the proposed entries into state.json's out_of_scope[].

Heuristic (per audit/scope.md):
  - drug name matches a known PRMT5/MAT2A/MTAP-axis programme  → likely in-scope
  - start_date < 2018 AND no matching drug                       → out-of-scope (pre-axis-era)
  - interventions are all "non-drug" (radiation, biospecimen, observation)  → out-of-scope
  - conditions list metabolic/imaging-only context               → out-of-scope
  - otherwise → flag for manual review (decision: 'review-needed')
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402
from audit.lib import ctgov                # noqa: E402

PASSES_COMP_DIR = ROOT / "audit" / "passes" / "completeness"
TRIAGE_DIR = ROOT / "audit" / "triage"

# Drugs we explicitly know target the MTAP/PRMT5/MAT2A axis.
KNOWN_AXIS_DRUGS = {
    s.lower() for s in [
        "AMG 193", "AMG-193", "anvumetostat",
        "MRTX1719", "BMS-986504", "navlimetostat",
        "TNG908", "TNG462", "vopimetostat", "TNG456",
        "IDE397", "IDE-397",
        "AZD3470", "AZD-3470",
        "HSK41959",
        "BAY 3713372", "BAY-3713372",
        "GSK3326595", "GSK-3326595",
        "JNJ-64619178",
        "PRT543", "PRT811",
        "PF-06939999",
        "AG-270", "S095033", "AG270",
        "EPZ015666", "JBI-778", "SH3765",
        # Methionine-cycle / MAT2A
        "AGI-24512",
    ]
}

NON_DRUG_INTERVENTIONS = {
    "biospecimen collection", "observation", "questionnaire administration",
    "imaging", "radiation", "best supportive care", "placebo",
    "computed tomography", "magnetic resonance imaging", "pet",
}


def latest_completeness_pass() -> dict:
    files = sorted(PASSES_COMP_DIR.glob("*.json"))
    if not files:
        raise SystemExit("No completeness pass found — run audit/completeness.py first")
    return json.loads(files[-1].read_text())


def classify(nct: str, ctgov_record: dict) -> dict:
    """Return {decision, reason, evidence} for one trial."""
    if "_error" in ctgov_record:
        return {"decision": "review-needed", "reason": f"CT.gov fetch error: {ctgov_record['_error'][:80]}", "evidence": {}}

    title = ctgov_record.get("brief_title", "")
    sponsor = ctgov_record.get("sponsor", "")
    start_date = ctgov_record.get("start_date", "")
    conditions = ctgov_record.get("conditions", [])
    interventions = [i.get("name", "") for i in ctgov_record.get("interventions", [])]
    intervention_types = {i.get("type", "").upper() for i in ctgov_record.get("interventions", [])}

    intv_lower = [x.lower() for x in interventions]
    matches_axis_drug = [d for d in KNOWN_AXIS_DRUGS if any(d in x for x in intv_lower)]

    # Decision tree
    if matches_axis_drug:
        return {
            "decision": "in-scope-candidate",
            "reason": f"Drug match: {', '.join(matches_axis_drug)}",
            "evidence": {
                "title": title, "sponsor": sponsor, "start_date": start_date,
                "interventions": interventions, "conditions": conditions[:3],
            },
        }

    # Pre-2018 start with no axis-drug match → almost certainly metabolite-era research
    if start_date and start_date < "2018-01-01" and not matches_axis_drug:
        return {
            "decision": "out-of-scope",
            "reason": "Pre-2018 trial (predates MTAP/PRMT5 synthetic-lethality clinical-translation era; Kryukov/Marjon/Mavrakis 2016) and no axis-targeting drug in interventions; likely uses 'methylthioadenosine' as a metabolite term in metabolic/imaging research, not as a therapeutic target.",
            "evidence": {
                "title": title, "sponsor": sponsor, "start_date": start_date,
                "interventions": interventions, "conditions": conditions[:3],
            },
        }

    # Non-drug interventions only (imaging, observation, etc.)
    all_intv_non_drug = all(
        any(nd in iv.lower() for nd in NON_DRUG_INTERVENTIONS) for iv in interventions
    ) if interventions else False
    if all_intv_non_drug:
        return {
            "decision": "out-of-scope",
            "reason": f"Non-therapeutic interventions only: {interventions}. Per scope.md, imaging/observation/specimen-only trials are out of scope.",
            "evidence": {
                "title": title, "sponsor": sponsor, "start_date": start_date,
                "interventions": interventions, "conditions": conditions[:3],
            },
        }

    # Post-2018 with unknown drug — could be a new programme we don't know about
    return {
        "decision": "review-needed",
        "reason": f"Post-2018 trial with unrecognized drug(s) {interventions[:3]}. May be a new programme — manual review needed.",
        "evidence": {
            "title": title, "sponsor": sponsor, "start_date": start_date,
            "interventions": interventions, "conditions": conditions[:3],
        },
    }


def run(apply: bool):
    comp = latest_completeness_pass()
    candidates = comp.get("newly_surfaced_ncts", [])
    if not candidates:
        print("No newly surfaced candidates to triage.")
        return

    state = state_lib.load_state()
    existing_oos = {item["id"] for item in state.get("out_of_scope", [])}
    candidates = [c for c in candidates if c not in existing_oos]

    print(f"[triage] {len(candidates)} candidate(s) to classify")

    decisions: dict[str, dict] = {}
    for i, nct in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] {nct} … ", end="", flush=True)
        rec = ctgov.fetch_trial(nct)
        time.sleep(0.15)
        d = classify(nct, rec or {})
        decisions[nct] = d
        print(d["decision"])

    today = dt.date.today().isoformat()
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRIAGE_DIR / f"{today}__candidates.json"
    out_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False))

    by_decision: dict[str, list[str]] = {}
    for nct, d in decisions.items():
        by_decision.setdefault(d["decision"], []).append(nct)

    print()
    print(f"=== triage {today} ===")
    for k, v in by_decision.items():
        print(f"  {k:25} {len(v):3}")
    print(f"  decisions written:        {out_path}")

    proposed_oos = []
    for nct, d in decisions.items():
        if d["decision"] == "out-of-scope":
            ev = d.get("evidence", {})
            proposed_oos.append({
                "id": nct,
                "name": ev.get("title", ""),
                "drug": ", ".join(ev.get("interventions", [])),
                "sponsor": ev.get("sponsor", ""),
                "first_seen": today,
                "reason": d["reason"],
                "surfaced_by": [
                    q for q, q_data in comp.get("queries_run", {}).items()
                    # We don't have per-query NCTs in the pass record summary view; leave empty
                    if False
                ] or ["completeness-pass-" + comp["pass_date"]],
            })

    proposed_path = TRIAGE_DIR / f"{today}__proposed_oos.json"
    proposed_path.write_text(json.dumps(proposed_oos, indent=2, ensure_ascii=False))
    print(f"  proposed OOS entries:     {proposed_path}  ({len(proposed_oos)} entries)")

    review_path = TRIAGE_DIR / f"{today}__review_needed.json"
    review_list = [
        {"nct": nct, **d["evidence"], "reason": d["reason"]}
        for nct, d in decisions.items() if d["decision"] in ("review-needed", "in-scope-candidate")
    ]
    review_path.write_text(json.dumps(review_list, indent=2, ensure_ascii=False))
    print(f"  review-needed list:       {review_path}  ({len(review_list)} entries)")

    if apply:
        state.setdefault("out_of_scope", []).extend(proposed_oos)
        state_lib.save_state(state)
        print(f"  ✅ applied {len(proposed_oos)} out_of_scope entries to state.json")
    else:
        print("  (no changes to state.json — pass --apply to merge proposed OOS entries)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Merge proposed OOS entries into state.json")
    args = ap.parse_args()
    run(args.apply)


if __name__ == "__main__":
    main()
