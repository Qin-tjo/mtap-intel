"""One-shot extractor: parse the existing index.html trial table tbody into state.json.

This is a v1 lossless extractor. It captures every field needed to round-trip
the HTML through render.py. The readout body inside each tt-detail-row is
preserved as raw HTML in `display.detail_body_html` — accuracy.py will later
peel structured tier_b_claims out of that blob.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML = ROOT / "index.html"


def extract_trials_from_html(html_path: Path = INDEX_HTML) -> dict:
    soup = BeautifulSoup(html_path.read_text(), "lxml")
    table = soup.find("table", class_="trial-table")
    if not table:
        raise RuntimeError("trial-table not found")
    tbody = table.find("tbody")
    if not tbody:
        raise RuntimeError("tbody not found inside trial-table")

    rows = tbody.find_all("tr", recursive=False)
    trials: dict[str, dict] = {}

    i = 0
    while i < len(rows):
        row = rows[i]
        classes = row.get("class") or []
        if "tt-row" in classes:
            detail = rows[i + 1] if i + 1 < len(rows) else None
            if not (detail and "tt-detail-row" in (detail.get("class") or [])):
                detail = None
            trial = _parse_pair(row, detail)
            if trial:
                nct = trial["tier_a"]["nct_id"]
                row_id = nct
                # When the same NCT appears in multiple display contexts (e.g. listed
                # under both partner drugs), suffix the row_id so each display is
                # preserved. tier_a.nct_id remains the true NCT for CT.gov sync.
                suffix_n = 2
                while row_id in trials:
                    row_id = f"{nct}__view{suffix_n}"
                    suffix_n += 1
                if row_id != nct:
                    trial["provenance"]["notes"] = (
                        f"Secondary display variant of {nct} "
                        f"(cross-referenced under {trial['display'].get('drug_label')})"
                    )
                trials[row_id] = trial
            i += 2 if detail else 1
        else:
            i += 1

    return trials


def _parse_pair(row: Tag, detail: Tag | None) -> dict | None:
    nct_link = row.find("a", href=re.compile(r"NCT\d+"))
    if not nct_link:
        return None
    nct = re.search(r"NCT\d+", nct_link.get("href", "")).group()

    drug_cell = row.find("td", class_="tt-drug")
    drug_bold = drug_cell.find("b") if drug_cell else None
    drug_label = drug_bold.get_text(strip=True) if drug_bold else ""
    sponsor_div = drug_cell.find("div", class_="tt-sponsor") if drug_cell else None
    sponsor_label = sponsor_div.get_text(strip=True) if sponsor_div else ""

    pills = row.find_all("span", class_="pill")
    pill_texts = {_pill_kind(p): p.get_text(strip=True) for p in pills}

    indication_label = _td_text(row, "tt-indication")
    biomarker_tag = pill_texts.get("bm", "")
    combination_tag = pill_texts.get("cb", "")
    mechanism_tag = pill_texts.get("mech", "")
    phase_tag = pill_texts.get("ph", "")
    status_tag = pill_texts.get("st", "")

    orr_cell = row.find("td", class_="tt-orr")
    orr_display = orr_cell.get_text(strip=True) if orr_cell else ""
    orr_tooltip = orr_cell.get("title", "") if orr_cell else ""

    n_cell = row.find("td", class_="tt-n")
    n_ctx_span = n_cell.find("span", class_="n-ctx") if n_cell else None
    n_ctx = n_ctx_span.get_text(strip=True) if n_ctx_span else ""
    n_display = ""
    if n_cell:
        cell_text = n_cell.get_text(strip=True)
        n_display = cell_text.replace(n_ctx, "").strip() if n_ctx else cell_text

    date_cell = row.find("td", class_="tt-date")
    start_display = date_cell.get_text(strip=True) if date_cell else ""

    # results column: button vs em-dash
    has_results = row.get("data-has-results", "no")

    detail_body_html = ""
    if detail:
        body_div = detail.find("div", class_="tt-detail-body")
        if body_div:
            detail_body_html = body_div.decode_contents()

    return {
        "tier_a": {
            "nct_id": nct,
            "drug_canonical": None,           # to be filled by accuracy.py from CT.gov
            "drug_aliases": [],
            "sponsor": sponsor_label,
            "sponsor_history": [],
            "mechanism_class": row.get("data-class", ""),
            "phases": _phases_from_tag(row.get("data-phase", "")),
            "status": row.get("data-status", ""),
            "conditions": [],
            "interventions": [],
            "primary_endpoints": [],
            "start_date": row.get("data-sort-start", ""),
            "first_patient_dosed": None,
            "ctgov_url": f"https://clinicaltrials.gov/study/{nct}",
            "last_synced": None,
            "last_synced_status": "never-synced",
        },
        "tier_b_claims": [],   # populated incrementally by accuracy.py
        "display": {
            "drug_label": drug_label,
            "sponsor_label": sponsor_label,
            "mechanism_tag": mechanism_tag,
            "phase_tag": phase_tag,
            "status_tag": status_tag,
            "indication_label": indication_label,
            "biomarker_tag": biomarker_tag,
            "combination_tag": combination_tag,
            "orr_display": orr_display,
            "orr_tooltip": orr_tooltip,
            "n_display": n_display,
            "n_ctx": n_ctx,
            "start_display": start_display,
            "has_results": has_results,
            "sort_drug": row.get("data-sort-drug", ""),
            "sort_mech": row.get("data-sort-mech", ""),
            "sort_phase": row.get("data-sort-phase", ""),
            "sort_status": row.get("data-sort-status", ""),
            "sort_orr": row.get("data-sort-orr", "-1"),
            "sort_n": row.get("data-sort-n", "-1"),
            "sort_start": row.get("data-sort-start", ""),
            "search_keywords": row.get("data-search", ""),
            "pill_mech_class": _pill_class(pills, "mech"),
            "pill_phase_class": _pill_class(pills, "ph"),
            "pill_status_class": _pill_class(pills, "st"),
            "pill_bm_class": _pill_class(pills, "bm"),
            "pill_cb_class": _pill_class(pills, "cb"),
            "detail_body_html": detail_body_html,
        },
        "provenance": {
            "first_added": None,
            "first_added_pass": "extract-from-html-2026-06-23",
            "surfaced_by": [],
            "review_triangulation": [],
            "notes": "",
        },
        "in_scope": True,
        "scope_rationale": "Imported from pre-state-first HTML; scope rationale to be populated on next accuracy pass.",
    }


def _pill_kind(pill: Tag) -> str:
    for cls in pill.get("class") or []:
        if cls.startswith("mech-"):
            return "mech"
        if cls.startswith("ph-"):
            return "ph"
        if cls.startswith("st-"):
            return "st"
        if cls.startswith("bm-"):
            return "bm"
        if cls.startswith("cb-"):
            return "cb"
    return "?"


def _pill_class(pills: list[Tag], kind: str) -> str:
    """Return the full pill class string (e.g. 'pill mech-mta') for a given kind."""
    for p in pills:
        if _pill_kind(p) == kind:
            return " ".join(p.get("class") or [])
    return ""


def _td_text(row: Tag, td_class: str) -> str:
    td = row.find("td", class_=td_class)
    return td.get_text(strip=True) if td else ""


def _phases_from_tag(tag: str) -> list[str]:
    mapping = {
        "Ph1": ["Phase 1"],
        "Ph2": ["Phase 2"],
        "Ph3": ["Phase 3"],
        "Ph1/2": ["Phase 1", "Phase 2"],
        "Ph2/3": ["Phase 2", "Phase 3"],
        "Ph0": ["Phase 0"],
        "Ph0/1": ["Phase 0", "Phase 1"],
    }
    return mapping.get(tag, [tag] if tag else [])


if __name__ == "__main__":
    trials = extract_trials_from_html()
    print(f"Extracted {len(trials)} trials")
    for nct, t in list(trials.items())[:3]:
        print(f"  {nct}  {t['display']['drug_label']}  {t['tier_a']['sponsor']}")
