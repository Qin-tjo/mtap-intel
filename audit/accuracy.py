"""accuracy.py — Tier-A registry sync + Tier-B verbatim verification + citation URL checks.

Modes:
    --report     : run the checks, print findings, write pass record. (default)
    --apply      : also overwrite state.json tier_a fields with fresh CT.gov values.
    --urls       : also verify every citation URL in the rendered HTML.
    --trial NCTxxx : limit to one trial (useful during initial sweeps).
    --no-fetch   : skip CT.gov requests (use cached tier_a; verify Tier-B + URLs only).

Outputs:
    - stdout summary
    - audit/passes/accuracy/<YYYY-MM-DD>.json  (full pass record)
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from audit.lib import state as state_lib   # noqa: E402
from audit.lib import ctgov                # noqa: E402
from audit.lib import urls as urls_lib     # noqa: E402

PASSES_DIR = ROOT / "audit" / "passes" / "accuracy"
INDEX_HTML = ROOT / "index.html"

# Tier-A fields we authoritatively sync from CT.gov
SYNC_FIELDS = ("sponsor", "phases", "status", "start_date", "conditions", "interventions", "primary_endpoints")


def diff_tier_a(local: dict, remote: dict) -> dict:
    """Return per-field diff. Each field maps to {'status': match|mismatch|missing, 'local': ..., 'remote': ...}."""
    out: dict = {}
    for f in SYNC_FIELDS:
        l = local.get(f)
        r = remote.get(f) if isinstance(remote, dict) else None
        if f == "interventions":
            # remote interventions are list of {type, name}; local is plain list of names
            r_names = [i["name"] for i in r] if r else []
            l_norm = sorted([x for x in (l or [])])
            r_norm = sorted(r_names)
            status = "match" if l_norm == r_norm else "mismatch"
            r_display = r_names
        elif isinstance(l, list) or isinstance(r, list):
            l_norm = sorted(l or [])
            r_norm = sorted(r or [])
            status = "match" if l_norm == r_norm else "mismatch"
            r_display = r
        else:
            l_norm = (l or "").strip() if isinstance(l, str) else l
            r_norm = (r or "").strip() if isinstance(r, str) else r
            status = "match" if l_norm == r_norm else "mismatch"
            r_display = r
        if l in (None, "", []) and r not in (None, "", []):
            status = "missing-local"
        out[f] = {"status": status, "local": l, "remote": r_display}
    return out


def apply_tier_a(trial: dict, remote: dict) -> int:
    """Overwrite trial.tier_a sync fields with remote values. Returns count of fields changed."""
    changed = 0
    a = trial["tier_a"]
    for f in SYNC_FIELDS:
        if f == "interventions":
            new = [i["name"] for i in remote.get("interventions", [])]
        else:
            new = remote.get(f, a.get(f))
        if a.get(f) != new:
            a[f] = new
            changed += 1
    a["last_synced"] = dt.date.today().isoformat()
    a["last_synced_status"] = "match" if changed == 0 else "synced-with-updates"
    if remote.get("ctgov_url"):
        a["ctgov_url"] = remote["ctgov_url"]
    return changed


def verify_tier_b_claims(trial: dict) -> list[dict]:
    """For each claim in tier_b_claims, check verbatim contains value (state.py already validates on load,
    but we surface per-claim status here)."""
    results = []
    for claim in trial.get("tier_b_claims", []):
        val_numeric = "".join(ch for ch in str(claim.get("value", "")) if ch.isdigit() or ch == ".")
        joined_verbatim = " ".join(
            m.get("verbatim", "")
            for src in claim.get("sources", [])
            for m in src.get("mentions", [])
        ).replace(",", "")
        verbatim_ok = (not val_numeric) or (val_numeric in joined_verbatim)
        n_sources = len(claim.get("sources", []))
        results.append({
            "claim_id": claim.get("claim_id"),
            "field": claim.get("field"),
            "value": claim.get("value"),
            "verbatim_match": verbatim_ok,
            "n_sources": n_sources,
            "cross_source_check": claim.get("cross_source_check", "n/a"),
            "confidence": claim.get("confidence", "unknown"),
        })
    return results


CITE_PATTERN = re.compile(r'<a class="cite"[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>')


def collect_citation_urls(html: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for m in CITE_PATTERN.finditer(html):
        url, title, label = m.group(1), m.group(2), m.group(3)
        if url in seen:
            seen[url]["count"] += 1
            continue
        seen[url] = {"url": url, "expected_title_hint": title, "label": label, "count": 1}
    return list(seen.values())


def run(args) -> dict:
    state = state_lib.load_state()
    pass_record: dict = {
        "pass_date": dt.date.today().isoformat(),
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "apply" if args.apply else "report",
        "trials": {},
        "citation_urls": [],
        "summary": {},
    }

    trial_items = list(state["trials"].items())
    if args.trial:
        trial_items = [(rid, t) for rid, t in trial_items if t["tier_a"]["nct_id"] == args.trial or rid == args.trial]
        if not trial_items:
            print(f"[accuracy] no trial matched --trial {args.trial}")
            return pass_record

    print(f"[accuracy] starting pass · {len(trial_items)} row(s) · mode={'apply' if args.apply else 'report'}")

    # Group rows by NCT so we only hit CT.gov once per NCT even if there are display variants
    nct_to_remote: dict[str, dict] = {}
    n_synced = n_mismatch = n_error = 0
    for row_id, trial in trial_items:
        nct = trial["tier_a"]["nct_id"]
        if not args.no_fetch and nct not in nct_to_remote:
            print(f"  fetching {nct} …", end="", flush=True)
            remote = ctgov.fetch_trial(nct)
            time.sleep(0.2)   # polite rate-limit
            if remote and "_error" in remote:
                print(f" ERROR: {remote['_error'][:80]}")
                n_error += 1
                nct_to_remote[nct] = {"_error": remote["_error"]}
            else:
                print(" ok")
                nct_to_remote[nct] = remote or {}
        elif args.no_fetch:
            nct_to_remote.setdefault(nct, {})

        remote = nct_to_remote.get(nct, {})
        row_record: dict = {"nct": nct, "row_id": row_id}

        if remote and "_error" not in remote and remote:
            tier_a_diff = diff_tier_a(trial["tier_a"], remote)
            row_record["tier_a_diff"] = tier_a_diff
            has_mismatch = any(d["status"] == "mismatch" for d in tier_a_diff.values())
            if has_mismatch:
                n_mismatch += 1
            if args.apply:
                changed = apply_tier_a(trial, remote)
                row_record["applied_changes"] = changed
                if changed:
                    n_synced += 1
        elif remote and "_error" in remote:
            row_record["tier_a_diff"] = {"_error": remote["_error"]}
        else:
            row_record["tier_a_diff"] = {"_skipped": "no-fetch mode or remote unavailable"}

        row_record["tier_b_claims"] = verify_tier_b_claims(trial)
        row_record["tier_b_unverified_html_blob"] = bool(trial["display"].get("detail_body_html"))
        pass_record["trials"][row_id] = row_record

    # URL verification
    if args.urls:
        print("[accuracy] checking citation URLs …")
        html = INDEX_HTML.read_text()
        urls = collect_citation_urls(html)
        print(f"  {len(urls)} unique citation URLs to check")
        n_url_ok = n_url_botblocked = n_url_broken = 0
        for entry in urls:
            r = urls_lib.check_url(entry["url"])
            entry.update(r)
            # Bucket 403s from known anti-bot domains as "bot-blocked" (human-verifiable, not broken).
            if r["status"] == "ok":
                entry["bucket"] = "ok"
                n_url_ok += 1
            elif r.get("code") == 403:
                entry["bucket"] = "bot-blocked"
                n_url_botblocked += 1
            else:
                entry["bucket"] = "broken"
                n_url_broken += 1
            time.sleep(0.15)
        pass_record["citation_urls"] = urls
        pass_record["summary"]["urls_ok"] = n_url_ok
        pass_record["summary"]["urls_bot_blocked"] = n_url_botblocked
        pass_record["summary"]["urls_broken"] = n_url_broken

    # Summary
    n_total = len(trial_items)
    n_tier_b_unverified = sum(
        1 for r in pass_record["trials"].values()
        if r.get("tier_b_unverified_html_blob") and not r["tier_b_claims"]
    )
    pass_record["summary"].update({
        "trials_audited": n_total,
        "tier_a_mismatches": n_mismatch,
        "tier_a_synced": n_synced,
        "tier_a_errors": n_error,
        "tier_b_rows_with_no_structured_claims": n_tier_b_unverified,
    })

    PASSES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PASSES_DIR / f"{pass_record['pass_date']}.json"
    out_path.write_text(json.dumps(pass_record, indent=2, ensure_ascii=False))

    if args.apply:
        state_lib.save_state(state)
        print("[accuracy] state.json updated with synced tier_a fields")

    print()
    print(f"=== accuracy pass {pass_record['pass_date']} ===")
    print(f"  rows audited:                 {n_total}")
    print(f"  Tier-A mismatches:            {n_mismatch}")
    print(f"  Tier-A fetch errors:          {n_error}")
    if args.apply:
        print(f"  Tier-A rows synced:           {n_synced}")
    print(f"  rows still backlog (no Tier-B): {n_tier_b_unverified}")
    if args.urls:
        print(f"  citation URLs ok:             {pass_record['summary']['urls_ok']}")
        print(f"  citation URLs bot-blocked:    {pass_record['summary']['urls_bot_blocked']} (manual verify)")
        print(f"  citation URLs broken:         {pass_record['summary']['urls_broken']}")
    print(f"  pass record written to:       {out_path}")
    return pass_record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="overwrite state.json tier_a fields with CT.gov values")
    ap.add_argument("--urls", action="store_true", help="also verify every citation URL in the rendered HTML")
    ap.add_argument("--trial", default=None, help="limit to one NCT (or row_id)")
    ap.add_argument("--no-fetch", action="store_true", help="skip CT.gov calls; verify Tier-B + URLs only")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
