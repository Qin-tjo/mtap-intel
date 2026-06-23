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
PASSES_COMP_DIR = Path(__file__).resolve().parent / "passes" / "completeness"
PASSES_TRI_DIR = Path(__file__).resolve().parent / "passes" / "triangulation"

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


def latest_completeness_pass() -> dict | None:
    if not PASSES_COMP_DIR.exists():
        return None
    files = sorted(PASSES_COMP_DIR.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text())


def latest_triangulation_pass() -> dict | None:
    if not PASSES_TRI_DIR.exists():
        return None
    files = sorted(PASSES_TRI_DIR.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text())


def render_audit_log(state: dict, pass_record: dict | None, comp_pass: dict | None = None,
                     tri_pass: dict | None = None) -> str:
    """Render the audit-log HTML block (goes between LOG markers, at bottom of dashboard).

    Three-block layout:
      1. Pass-status overview — single grid covering accuracy / completeness / triangulation
      2. Per-trial audit table — the 53-row workhorse
      3. Methodology & known limitations
    Detail expansions live in <details> elements within each block.
    """
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
    cs = comp_pass.get("summary", {}) if comp_pass else {}
    ts = tri_pass.get("summary", {}) if tri_pass else {}

    # ---------- Block 1: pass-status overview ----------
    lines.append('  <div class="audit-overview">')
    # Accuracy card
    lines.append('    <div class="audit-card">')
    lines.append(f'      <div class="audit-card-h"><b>Accuracy</b> <span class="audit-date">{e(pass_record["pass_date"])}</span></div>')
    lines.append('      <ul>')
    lines.append(f'        <li>Rows audited: <b>{s.get("trials_audited", 0)}</b></li>')
    lines.append(f'        <li>Tier-A registry sync: <b>{s.get("tier_a_mismatches", 0)} mismatches</b></li>')
    lines.append(f'        <li>Tier-B verified: <b>{s.get("tier_b_verified", 0)}</b> · backlog: <b>{s.get("tier_b_extraction_backlog", 0)}</b> · no efficacy yet: <b>{s.get("tier_b_no_claims_needed", 0)}</b></li>')
    if "urls_ok" in s:
        lines.append(f'        <li>Citation URLs: <b>{s.get("urls_ok", 0)} ok</b> · {s.get("urls_bot_blocked", 0)} bot-blocked · {s.get("urls_broken", 0)} broken</li>')
    lines.append('      </ul></div>')

    # Completeness card
    if comp_pass:
        lines.append('    <div class="audit-card">')
        lines.append(f'      <div class="audit-card-h"><b>Completeness</b> <span class="audit-date">{e(comp_pass["pass_date"])}</span></div>')
        lines.append('      <ul>')
        lines.append(f'        <li>Search queries: <b>{cs.get("queries_run", 0)}</b> ({cs.get("queries_errored", 0)} errored)</li>')
        lines.append(f'        <li>In-state trials covered by ≥1 query: <b>{cs.get("in_state_now_surfaced", 0)} / {cs.get("in_state", 0)}</b></li>')
        if cs.get("in_state_but_not_surfaced", 0) > 0:
            lines.append(f'        <li>⚠️ Search-registry gap: <b>{cs["in_state_but_not_surfaced"]}</b> in-state trial(s) with no query hit</li>')
        lines.append(f'        <li>Newly surfaced needing triage: <b>{cs.get("newly_surfaced_to_review", 0)}</b></li>')
        lines.append('      </ul></div>')

    # Triangulation card
    if tri_pass:
        missed_ncts = ts.get("total_unique_missed_ncts", [])
        missed_drugs = ts.get("total_unique_missed_drugs", [])
        lines.append('    <div class="audit-card">')
        lines.append(f'      <div class="audit-card-h"><b>Triangulation</b> <span class="audit-date">{e(tri_pass["pass_date"])}</span></div>')
        lines.append('      <ul>')
        lines.append(f'        <li>Reviews cross-checked: <b>{ts.get("reviews_processed", 0)}</b></li>')
        if missed_ncts:
            lines.append(f'        <li>⚠️ Review-cited NCTs not in state.json: <b>{len(missed_ncts)}</b></li>')
        else:
            lines.append('        <li>✅ All review-cited NCTs present in state.json</li>')
        if missed_drugs:
            lines.append(f'        <li>⚠️ Drugs in reviews not represented: <b>{", ".join(missed_drugs)}</b></li>')
        else:
            lines.append('        <li>✅ All review-mentioned clinical-stage drugs represented</li>')
        lines.append('      </ul></div>')
    lines.append('  </div>')

    # ---------- Details collapsibles tied to the overview ----------
    # Citation URL detail
    if pass_record.get("citation_urls"):
        bot_blocked = [u for u in pass_record["citation_urls"] if u.get("bucket") == "bot-blocked"]
        broken = [u for u in pass_record["citation_urls"] if u.get("bucket") == "broken"]
        if bot_blocked or broken:
            lines.append('  <details class="audit-details">')
            lines.append(f'    <summary>Citation URLs needing manual review ({len(bot_blocked)} bot-blocked · {len(broken)} broken)</summary>')
            if broken:
                lines.append('    <p class="audit-bad"><b>Broken (needs replacement):</b></p><ul class="audit-urls">')
                for u in broken:
                    lines.append(f'      <li>{e(u.get("status",""))} {e(str(u.get("code","")))} — <a href="{e(u["url"])}" target="_blank" rel="noopener">{e(u["url"][:120])}</a></li>')
                lines.append('    </ul>')
            if bot_blocked:
                lines.append('    <p><b>Bot-blocked</b> (HTTP 403 to scripts; verify by hand on a normal browser):</p><ul class="audit-urls">')
                for u in bot_blocked:
                    lines.append(f'      <li><a href="{e(u["url"])}" target="_blank" rel="noopener">{e(u["url"][:120])}</a></li>')
                lines.append('    </ul>')
            lines.append('  </details>')

    # Completeness candidate list
    if comp_pass:
        candidates = comp_pass.get("newly_surfaced_ncts", [])
        if candidates:
            lines.append('  <details class="audit-details">')
            lines.append(f'    <summary>Newly surfaced NCTs needing triage ({len(candidates)})</summary>')
            lines.append('    <ul class="audit-urls">')
            for nct in candidates[:50]:
                lines.append(f'      <li><a href="https://clinicaltrials.gov/study/{e(nct)}" target="_blank" rel="noopener">{e(nct)}</a></li>')
            if len(candidates) > 50:
                lines.append(f'      <li>… and {len(candidates) - 50} more (see <code>audit/passes/completeness/{e(comp_pass["pass_date"])}.json</code>)</li>')
            lines.append('    </ul></details>')

    # Triangulation per-review detail
    if tri_pass and tri_pass.get("reviews"):
        lines.append('  <details class="audit-details">')
        lines.append(f'    <summary>Per-review detail ({len(tri_pass["reviews"])} reviews)</summary>')
        lines.append('    <table class="audit-table">')
        lines.append('      <thead><tr><th>Review</th><th>Tier</th><th>NCTs in review</th><th>Covered</th><th>Drugs mentioned</th></tr></thead>')
        lines.append('      <tbody>')
        for r in tri_pass["reviews"]:
            meta = r.get("review_meta", {})
            title = (meta.get("title") or "")[:80]
            tier = meta.get("tier", "?")
            n_in = len(r.get("ncts_in_review", []))
            n_cov = len(r.get("ncts_covered", []))
            n_drugs = len(r.get("drugs_in_review", []))
            lines.append(f'        <tr><td>{e(title)} ({e(str(meta.get("year","")))})</td><td>T{e(str(tier))}</td><td>{n_in}</td><td>{n_cov}/{n_in}</td><td>{n_drugs}</td></tr>')
        lines.append('      </tbody></table></details>')

    # ---------- Block 2: per-trial table ----------
    lines.append('  <h3>Per-trial audit status</h3>')
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
        state_label = row_rec.get("tier_b_state", "no-claims-needed")
        if n_claims:
            verified = sum(1 for c in row_rec["tier_b_claims"] if c["verbatim_match"])
            tier_b_status = f'{verified}/{n_claims} verified'
        elif state_label == "extraction-backlog":
            tier_b_status = '🔄 displays ORR — needs verbatim'
        else:
            tier_b_status = '➖ no efficacy yet'
        if tier_a_status.startswith('✅') and (n_claims or state_label == "no-claims-needed"):
            overall = '✅'
        else:
            overall = '🔄'
        lines.append(
            f'      <tr><td><a href="https://clinicaltrials.gov/study/{e(nct)}" target="_blank" rel="noopener">{e(nct)}</a></td>'
            f'<td>{e(drug)}</td><td>{tier_a_status}</td><td>{tier_b_status}</td><td>{overall}</td></tr>'
        )
    lines.append('    </tbody></table>')

    # ---------- Block 3: methodology + limitations ----------
    lines.append('  <h3>Methodology &amp; known limitations</h3>')
    lines.append('  <p><b>How this audit log is built.</b> '
                 '<a href="audit/run.py">audit/run.py</a> chains '
                 '<a href="audit/completeness.py">completeness.py</a> '
                 '→ <a href="audit/accuracy.py">accuracy.py</a> '
                 '→ <a href="audit/triangulate.py">triangulate.py</a> '
                 '→ <a href="audit/render.py">render.py</a>. '
                 'Inclusion criteria in <a href="audit/scope.md">audit/scope.md</a>. '
                 'Schema in <a href="audit/state.schema.md">audit/state.schema.md</a>. '
                 'The trial-table tbody, the 4.4 competitive table, and this audit log are all rendered from '
                 '<a href="audit/state.json">audit/state.json</a> — '
                 'no clinical content lives only in HTML.</p>')
    lines.append('  <p><b>Known limitations.</b> '
                 '(1) ChiCTR / EUDRA-CT / JRCT registries are not yet covered by the completeness queries; '
                 '(2) Industry pipeline subscriptions (Citeline / Cortellis) are not used; '
                 '(3) Pre-registration disclosures may lag behind sponsor IR pages; '
                 '(4) Tier-B extraction is incremental — rows showing "no efficacy yet" have no published numerical efficacy to verify, '
                 'rows showing "displays ORR — needs verbatim" have a source that is currently bot-blocked to scripted snapshotting and '
                 'await a manual verification pass.</p>')
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
        comp_rec = latest_completeness_pass()
        tri_rec = latest_triangulation_pass()
        log_block = render_audit_log(state, pass_rec, comp_rec, tri_rec)
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
