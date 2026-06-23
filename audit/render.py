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
LOG_MARKER_START = "<!-- AUDIT:LOG:START -->"
LOG_MARKER_END = "<!-- AUDIT:LOG:END -->"
PASSES_ACC_DIR = Path(__file__).resolve().parent / "passes" / "accuracy"

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


def replace_between_markers(html: str, new_body: str, start: str = MARKER_START, end: str = MARKER_END) -> str:
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    if not pattern.search(html):
        raise RuntimeError(f"Markers not found in HTML: {start!r} / {end!r}")
    replacement = f"{start}\n{new_body}\n{end}"
    return pattern.sub(replacement, html, count=1)


def latest_accuracy_pass() -> dict | None:
    if not PASSES_ACC_DIR.exists():
        return None
    files = sorted(PASSES_ACC_DIR.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text())


def render_audit_log(state: dict, pass_record: dict | None) -> str:
    """Render the audit-log HTML block (goes between LOG markers, at bottom of dashboard)."""
    from html import escape as e
    lines = []
    lines.append('<section id="audit-log" class="section audit-log">')
    lines.append('  <div class="sec-h">')
    lines.append('    <div class="sec-num ref-num">A</div>')
    lines.append('    <div>')
    lines.append('      <div class="sec-title">Audit log</div>')
    lines.append('      <div class="sec-q">Provenance, verification status, and known gaps for the Clinical Landscape.</div>')
    lines.append('    </div>')
    lines.append('  </div>')

    if pass_record is None:
        lines.append('  <p>No accuracy pass has been recorded yet.</p>')
        lines.append('</section>')
        return "\n".join(lines)

    s = pass_record.get("summary", {})
    lines.append(f'  <h3>A.1 · Last full accuracy pass — {e(pass_record["pass_date"])}</h3>')
    lines.append('  <ul class="audit-summary">')
    lines.append(f'    <li>Rows audited: <b>{s.get("trials_audited", 0)}</b></li>')
    lines.append(f'    <li>Tier-A registry sync mismatches: <b>{s.get("tier_a_mismatches", 0)}</b></li>')
    lines.append(f'    <li>Rows with no structured Tier-B claims yet (extraction backlog): <b>{s.get("tier_b_rows_with_no_structured_claims", 0)}</b></li>')
    if "urls_ok" in s:
        lines.append(f'    <li>Citation URLs verified: <b>{s.get("urls_ok", 0)} ok</b> · '
                     f'<b>{s.get("urls_bot_blocked", 0)} bot-blocked</b> (manual verify needed) · '
                     f'<b>{s.get("urls_broken", 0)} broken</b></li>')
    lines.append('  </ul>')

    # Per-trial table
    lines.append('  <h3>A.2 · Per-trial audit status</h3>')
    lines.append('  <table class="audit-table">')
    lines.append('    <thead><tr><th>NCT</th><th>Drug</th><th>Tier-A sync</th><th>Tier-B claims</th><th>Status</th></tr></thead>')
    lines.append('    <tbody>')
    for row_id, row_rec in pass_record["trials"].items():
        trial = state["trials"].get(row_id, {})
        drug = (trial.get("display", {}).get("drug_label") or "—")
        nct = row_rec["nct"]
        tdiff = row_rec.get("tier_a_diff", {})
        if "_error" in tdiff:
            tier_a_status = f'⚠️ {e(tdiff["_error"][:40])}'
        elif "_skipped" in tdiff:
            tier_a_status = '🔄 skipped'
        else:
            mis = [f for f, info in tdiff.items() if info["status"] == "mismatch"]
            tier_a_status = '✅ match' if not mis else f'⚠️ {", ".join(mis)}'
        n_claims = len(row_rec.get("tier_b_claims", []))
        if n_claims == 0:
            tier_b_status = '🔄 backlog (no structured claims)'
        else:
            verified = sum(1 for c in row_rec["tier_b_claims"] if c["verbatim_match"])
            tier_b_status = f'{verified}/{n_claims} verified'
        overall = '✅' if (tier_a_status.startswith('✅') and n_claims > 0) else '🔄'
        lines.append(
            f'      <tr><td><a href="https://clinicaltrials.gov/study/{e(nct)}" target="_blank" rel="noopener">{e(nct)}</a></td>'
            f'<td>{e(drug)}</td><td>{tier_a_status}</td><td>{tier_b_status}</td><td>{overall}</td></tr>'
        )
    lines.append('    </tbody>')
    lines.append('  </table>')

    # Citation URL bucket
    if pass_record.get("citation_urls"):
        bot_blocked = [u for u in pass_record["citation_urls"] if u.get("bucket") == "bot-blocked"]
        broken = [u for u in pass_record["citation_urls"] if u.get("bucket") == "broken"]
        if bot_blocked or broken:
            lines.append('  <h3>A.3 · Citation URLs flagged for manual review</h3>')
            if bot_blocked:
                lines.append('  <details><summary>Bot-blocked (HTTP 403 to scripts; human-accessible — verify periodically by hand)</summary>')
                lines.append('  <ul class="audit-urls">')
                for u in bot_blocked:
                    lines.append(f'    <li><a href="{e(u["url"])}" target="_blank" rel="noopener">{e(u["url"][:120])}</a></li>')
                lines.append('  </ul></details>')
            if broken:
                lines.append('  <details open><summary><b>Broken (needs replacement)</b></summary>')
                lines.append('  <ul class="audit-urls">')
                for u in broken:
                    lines.append(f'    <li>{e(u.get("status",""))} {e(str(u.get("code","")))} — <a href="{e(u["url"])}" target="_blank" rel="noopener">{e(u["url"][:120])}</a></li>')
                lines.append('  </ul></details>')

    # Scope + limitations footer
    lines.append('  <h3>A.4 · Scope &amp; known limitations</h3>')
    lines.append('  <p>This audit log is generated by <a href="audit/accuracy.py">audit/accuracy.py</a>. '
                 'See <a href="audit/scope.md">audit/scope.md</a> for the inclusion criteria and '
                 '<a href="audit/state.schema.md">audit/state.schema.md</a> for the data schema. '
                 'The trial-table tbody is rendered from <a href="audit/state.json">audit/state.json</a> '
                 'by <a href="audit/render.py">audit/render.py</a>.</p>')
    lines.append('  <p>Known limitations: '
                 '(1) ChiCTR / EUDRA-CT / JRCT registries are not yet covered by the completeness tool; '
                 '(2) Industry pipeline subscriptions (Citeline / Cortellis) are not used; '
                 '(3) Pre-registration disclosures may lag behind sponsor IR; '
                 '(4) Tier-B extraction backlog: structured verbatim-anchored claims are being added '
                 'incrementally — until a row shows "verified" in column 4 above, the dashboard '
                 'displays figures from raw HTML readouts which are not yet machine-verified.</p>')
    lines.append('</section>')
    return "\n".join(lines)


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

    # Audit log section (if markers present)
    if LOG_MARKER_START in new_html:
        pass_rec = latest_accuracy_pass()
        log_block = render_audit_log(state, pass_rec)
        new_html = replace_between_markers(new_html, log_block, LOG_MARKER_START, LOG_MARKER_END)

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
