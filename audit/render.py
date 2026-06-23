"""state.json → HTML.

For v1, renders only the trial-table tbody. Replaces content between
the markers <!-- AUDIT:TRIAL_TABLE_TBODY:START --> and
<!-- AUDIT:TRIAL_TABLE_TBODY:END --> inside audit/state.json's referenced index.html.

If state.json is empty, the renderer bootstraps it from the existing HTML
via extract.py — this is a one-time migration.

Usage:
    python3 audit/render.py           # render and overwrite index.html
    python3 audit/render.py --check   # render and diff vs current index.html, no write
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"
STATE_PATH = ROOT / "audit" / "state.json"

MARKER_START = "<!-- AUDIT:TRIAL_TABLE_TBODY:START -->"
MARKER_END = "<!-- AUDIT:TRIAL_TABLE_TBODY:END -->"

sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402
from audit.lib import extract               # noqa: E402


def render_row(nct: str, trial: dict) -> str:
    """Render one trial as `<tr class="tt-row">...</tr><tr class="tt-detail-row" hidden>...</tr>`."""
    d = trial["display"]
    a = trial["tier_a"]

    # Build the main row
    # Order of data-* attributes mirrors the original markup for readability.
    attrs = [
        ("class", "tt-row"),
        ("data-search", d.get("search_keywords", "")),
        ("data-class", a.get("mechanism_class", "")),
        ("data-phase", _phase_tag_short(d.get("phase_tag", ""))),
        ("data-status", a.get("status", "") or d.get("status_tag", "")),
        ("data-biomarker", d.get("biomarker_tag", "")),
        ("data-combo", d.get("combination_tag", "")),
        ("data-has-results", d.get("has_results", "no")),
        ("data-sort-drug", d.get("sort_drug", "")),
        ("data-sort-mech", d.get("sort_mech", "")),
        ("data-sort-phase", d.get("sort_phase", "")),
        ("data-sort-status", d.get("sort_status", "")),
        ("data-sort-orr", d.get("sort_orr", "-1")),
        ("data-sort-n", d.get("sort_n", "-1")),
        ("data-sort-start", d.get("sort_start", "")),
    ]
    main_open = "<tr " + " ".join(f'{k}="{escape(str(v), quote=True)}"' for k, v in attrs) + ">"

    # NCT cell
    ctgov_url = a.get("ctgov_url") or f"https://clinicaltrials.gov/study/{nct}"
    nct_cell = (
        f'<td class="tt-nct">'
        f'<a href="{escape(ctgov_url)}" target="_blank" rel="noopener">{escape(nct)}</a>'
        f"</td>"
    )

    # Drug + sponsor
    drug_cell = (
        f'<td class="tt-drug"><b>{escape(d.get("drug_label", ""))}</b>'
        f'<div class="tt-sponsor">{escape(d.get("sponsor_label", ""))}</div></td>'
    )

    # Pills
    pill_mech = _pill(d.get("pill_mech_class", "pill"), d.get("mechanism_tag", ""))
    pill_phase = _pill(d.get("pill_phase_class", "pill"), d.get("phase_tag", ""))
    pill_status = _pill(d.get("pill_status_class", "pill"), d.get("status_tag", ""))
    pill_bm = _pill(d.get("pill_bm_class", "pill"), d.get("biomarker_tag", ""))
    pill_cb = _pill(d.get("pill_cb_class", "pill"), d.get("combination_tag", ""))

    indication_cell = f'<td class="tt-indication">{escape(d.get("indication_label", ""))}</td>'

    # ORR cell
    orr_tooltip = d.get("orr_tooltip", "")
    orr_display = d.get("orr_display", "—")
    title_attr = f' title="{escape(orr_tooltip, quote=True)}"' if orr_tooltip else ""
    orr_cell = f'<td class="tt-orr"{title_attr}>{escape(orr_display)}</td>'

    # n cell (number + optional context span)
    n_display = d.get("n_display", "—")
    n_ctx = d.get("n_ctx", "")
    if n_ctx:
        n_cell = f'<td class="tt-n">{escape(n_display)} <span class="n-ctx">{escape(n_ctx)}</span></td>'
    else:
        n_cell = f'<td class="tt-n">{escape(n_display)}</td>'

    date_cell = f'<td class="tt-date">{escape(d.get("start_display", ""))}</td>'

    # results column
    if d.get("has_results", "no") == "yes":
        results_cell = (
            '<td class="tt-results">'
            '<button class="results-toggle" type="button" aria-expanded="false">📄 readout</button>'
            '</td>'
        )
    else:
        results_cell = '<td class="tt-results"><span class="results-none">—</span></td>'

    main_row = (
        main_open
        + nct_cell
        + drug_cell
        + f"<td>{pill_mech}</td>"
        + f"<td>{pill_phase}</td>"
        + f"<td>{pill_status}</td>"
        + indication_cell
        + f"<td>{pill_bm}</td>"
        + f"<td>{pill_cb}</td>"
        + orr_cell
        + n_cell
        + date_cell
        + results_cell
        + "</tr>"
    )

    # Detail row (always present; hidden by default)
    detail_body = d.get("detail_body_html", "").strip()
    detail_row = (
        f'<tr class="tt-detail-row" hidden>'
        f'<td colspan="12"><div class="tt-detail-body">{detail_body}</div></td>'
        f"</tr>"
    )

    return main_row + "\n" + detail_row


def _pill(class_str: str, label: str) -> str:
    cls = class_str or "pill"
    return f'<span class="{escape(cls, quote=True)}">{escape(label)}</span>'


def _phase_tag_short(phase_tag: str) -> str:
    """Reverse-map display phase pill text to data-phase token."""
    return phase_tag  # Already in display form (e.g. "Ph1/2"); preserve as-is.


def render_tbody(state: dict) -> str:
    """Render the trial-table tbody body (between markers)."""
    lines = [""]
    # Deterministic order: by sort_start asc, then NCT asc (matches no-sort table state)
    items = list(state["trials"].items())

    def sort_key(item):
        _, trial = item
        return (trial["display"].get("sort_start") or "9999-99-99", item[0])

    # Preserve original insertion order from state.json (which mirrors extraction order).
    # Sorting is handled client-side by the existing JS; we keep file order stable.
    for nct, trial in items:
        lines.append(render_row(nct, trial))
    lines.append("")
    return "\n".join(lines)


def replace_between_markers(html: str, new_body: str) -> str:
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    if not pattern.search(html):
        raise RuntimeError(
            f"Markers not found in HTML. Add {MARKER_START!r} and {MARKER_END!r} "
            f"around the trial-table tbody."
        )
    replacement = f"{MARKER_START}\n{new_body}\n{MARKER_END}"
    return pattern.sub(replacement, html, count=1)


def ensure_state(state_path: Path = STATE_PATH) -> dict:
    """Load state.json; if absent, bootstrap from current HTML."""
    if state_path.exists():
        return state_lib.load_state(state_path)
    print(f"[render] state.json not found at {state_path}; bootstrapping from index.html")
    bootstrap = state_lib._empty_state()
    bootstrap["trials"] = extract.extract_trials_from_html()
    bootstrap["last_render"] = dt.datetime.utcnow().isoformat() + "Z"
    state_lib.save_state(bootstrap, state_path)
    print(f"[render] wrote bootstrapped state.json ({len(bootstrap['trials'])} trials)")
    return bootstrap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Render but do not write; report diff size only")
    ap.add_argument("--state", default=str(STATE_PATH))
    ap.add_argument("--html", default=str(INDEX_HTML))
    args = ap.parse_args()

    state = ensure_state(Path(args.state))
    body = render_tbody(state)

    html = Path(args.html).read_text()
    new_html = replace_between_markers(html, body)

    if args.check:
        same = (new_html == html)
        delta = len(new_html) - len(html)
        print(f"[render --check] identical: {same}; size delta: {delta:+d} bytes")
        return

    Path(args.html).write_text(new_html)
    state["last_render"] = dt.datetime.utcnow().isoformat() + "Z"
    state_lib.save_state(state, Path(args.state))
    print(f"[render] wrote {args.html} ({len(state['trials'])} trial rows)")


if __name__ == "__main__":
    main()
