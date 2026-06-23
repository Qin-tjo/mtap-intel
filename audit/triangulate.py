"""triangulate.py — cross-check state.json against published-review trial lists.

For each registered review (defined in REVIEWS below), reads the snapshot,
extracts trial NCT IDs and drug-name mentions, and produces a triangulation
record per review:

  - NCTs in review covered by state.json (trials or out_of_scope)  → ✅
  - NCTs in review NOT in state.json                                 → ⚠️ potential miss
  - Drug names in review without representation in state.json        → ⚠️ potential miss

Output:
    audit/passes/triangulation/<YYYY-MM-DD>.json
"""

from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402

PASSES_DIR = ROOT / "audit" / "passes" / "triangulation"
SNAPS = ROOT / "audit" / "snapshots"
TODAY = dt.date.today().isoformat()

# Registered reviews. Each has a stable key, citation metadata, snapshot file,
# and the parser type (html or pdf).
REVIEWS = [
    {
        "key": "hu2024_mtacoop_review",
        "title": "A review of the known MTA-cooperative PRMT5 inhibitors.",
        "authors": "Hu M, Chen X.",
        "journal": "RSC Advances",
        "year": 2024,
        "pmid": "39691229",
        "doi": "10.1039/d4ra05497k",
        "snapshot": "audit/snapshots/cracking_prmt5_iupui_review__2026-06-23.pdf",
        "parser": "pdf",
        "tier": 1,
        "notes": "Comprehensive published review of MTA-cooperative PRMT5 inhibitors.",
    },
    {
        "key": "patsnap_prmt5_review_2025",
        "title": "PRMT5 inhibitors for MTAP-deleted cancers (industry blog).",
        "authors": "PatSnap editorial",
        "year": 2025,
        "snapshot": "audit/snapshots/patsnap_prmt5_review__2026-06-23.html",
        "parser": "html",
        "tier": 4,
        "notes": "Industry pipeline tracker; less comprehensive than peer-reviewed reviews but useful cross-check.",
    },
]

# Drug names that are mentioned in reviews but are preclinical-only tool compounds.
# Per scope.md, preclinical-only programmes are out of scope for the dashboard.
PRECLINICAL_ONLY_DRUGS = {
    "EPZ015666",   # Epizyme tool compound; structure-elucidation chemistry, never IND'd.
    "GSK591",
    "JBI-778",
    "LLY-283",
    "PRMT5-INH-1",
}

# Known drug-name patterns we want to triangulate.
DRUG_PATTERNS = [
    "MRTX1719", "BMS-986504", "navlimetostat", "AMG 193", "AMG-193", "anvumetostat",
    "TNG908", "TNG462", "vopimetostat", "TNG456",
    "IDE397", "IDE-397", "IDE892", "IDE-892",
    "AZD3470", "AZD-3470",
    "HSK41959",
    "BAY 3713372", "BAY-3713372", "BAY3713372",
    "GSK3326595",
    "JNJ-64619178",
    "PRT543", "PRT811",
    "PF-06939999",
    "AG-270", "AG270", "S095033",
    "EPZ015666",
    "BGB-58067",
    "GH56",
    "CTS3497",
    "PEP08",
    "HS-10587",
    "GS-5319", "GS-2426",
    "SCR-6920",
    "ISM3412",
]


def extract_text(path: Path, parser: str) -> str:
    """Extract plain text from a snapshot file."""
    if parser == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("pip install pypdf required for PDF parsing")
        r = PdfReader(str(path))
        return "\n".join(p.extract_text() for p in r.pages)
    elif parser == "html":
        text = path.read_text(errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[#a-zA-Z0-9]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    raise ValueError(f"Unknown parser: {parser}")


def triangulate_review(review: dict, state: dict) -> dict:
    snap = ROOT / review["snapshot"]
    if not snap.exists():
        return {
            "review_key": review["key"], "error": f"snapshot missing: {snap}",
            "ncts_in_review": [], "drugs_in_review": [],
            "ncts_covered": [], "ncts_missed": [],
            "drugs_covered": [], "drugs_missed": [],
        }

    text = extract_text(snap, review["parser"])
    ncts_in_review = sorted(set(re.findall(r"NCT\d{8}", text)))
    drugs_in_review = []
    for p in DRUG_PATTERNS:
        if re.search(re.escape(p), text, re.IGNORECASE):
            drugs_in_review.append(p)

    state_ncts = {t["tier_a"]["nct_id"] for t in state["trials"].values()}
    out_of_scope_ncts = {item["id"] for item in state.get("out_of_scope", [])}

    ncts_covered = [n for n in ncts_in_review if n in state_ncts or n in out_of_scope_ncts]
    ncts_missed = [n for n in ncts_in_review if n not in state_ncts and n not in out_of_scope_ncts]

    state_drugs_lower: set[str] = set()
    for t in state["trials"].values():
        for d in [t["display"].get("drug_label", ""), *t["tier_a"].get("drug_aliases", [])]:
            if d:
                state_drugs_lower.add(d.lower().replace(" ", "").replace("-", ""))

    def normalize(d: str) -> str:
        return d.lower().replace(" ", "").replace("-", "")

    drugs_covered = [d for d in drugs_in_review if normalize(d) in state_drugs_lower]
    drugs_missed = [
        d for d in drugs_in_review
        if normalize(d) not in state_drugs_lower
        and d not in PRECLINICAL_ONLY_DRUGS
    ]
    drugs_excluded_preclinical = [d for d in drugs_in_review if d in PRECLINICAL_ONLY_DRUGS]

    return {
        "review_key": review["key"],
        "review_meta": {k: review.get(k) for k in ("title", "authors", "year", "pmid", "doi", "tier")},
        "ncts_in_review": ncts_in_review,
        "drugs_in_review": drugs_in_review,
        "ncts_covered": ncts_covered,
        "ncts_missed": ncts_missed,
        "drugs_covered": drugs_covered,
        "drugs_missed": drugs_missed,
        "drugs_excluded_preclinical": drugs_excluded_preclinical,
    }


def main():
    state = state_lib.load_state()
    record = {
        "pass_date": TODAY,
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "reviews": [],
        "summary": {},
    }

    print(f"[triangulate] cross-checking against {len(REVIEWS)} review(s)")
    n_total_missed_ncts: set[str] = set()
    n_total_missed_drugs: set[str] = set()

    for review in REVIEWS:
        r = triangulate_review(review, state)
        record["reviews"].append(r)
        if "error" in r:
            print(f"  {review['key']:50}  ERROR: {r['error']}")
            continue
        n_in = len(r["ncts_in_review"])
        n_cov = len(r["ncts_covered"])
        n_miss = len(r["ncts_missed"])
        n_drugs_miss = len(r["drugs_missed"])
        print(f"  {review['key']:50}  NCTs {n_cov}/{n_in} covered · missed {n_miss}  drugs missed {n_drugs_miss}")
        n_total_missed_ncts.update(r["ncts_missed"])
        n_total_missed_drugs.update(r["drugs_missed"])

    record["summary"] = {
        "reviews_processed": len(REVIEWS),
        "total_unique_missed_ncts": sorted(n_total_missed_ncts),
        "total_unique_missed_drugs": sorted(n_total_missed_drugs),
    }

    PASSES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PASSES_DIR / f"{TODAY}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))

    print()
    print(f"=== triangulation pass {TODAY} ===")
    if n_total_missed_ncts:
        print(f"  ⚠️ NCTs mentioned in review(s) but not in state.json: {len(n_total_missed_ncts)}")
        for n in sorted(n_total_missed_ncts):
            print(f"    {n}  https://clinicaltrials.gov/study/{n}")
    else:
        print("  ✅ All review-cited NCTs covered by state.json")
    if n_total_missed_drugs:
        print(f"  ⚠️ Drugs mentioned in review(s) but not in state.json: {len(n_total_missed_drugs)}")
        for d in sorted(n_total_missed_drugs):
            print(f"    {d}")
    else:
        print("  ✅ All review-mentioned drugs represented in state.json")
    print(f"  pass record: {out_path}")


if __name__ == "__main__":
    main()
