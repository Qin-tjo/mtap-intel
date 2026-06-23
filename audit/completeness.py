"""completeness.py — systematic-search pass over the Clinical Landscape.

Runs every query in audit/queries.json, dedupes NCTs, cross-references with
state.json, and produces a PRISMA-style flow record. The pass surfaces:

  (a) trials in search results that are NOT in state.json (potentially missed)
  (b) trials in state.json with NO `surfaced_by` evidence (search registry gap)
  (c) sentinel query hits since the last pass

For each "missed" trial, the human reviewer either adds a row (state.json) or
adds an out-of-scope entry with reason. The tool does not add rows automatically.

Output:
    audit/passes/completeness/<YYYY-MM-DD>.json — the full PRISMA record
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audit.lib import state as state_lib   # noqa: E402

QUERIES_PATH = ROOT / "audit" / "queries.json"
PASSES_DIR = ROOT / "audit" / "passes" / "completeness"


def run_ctgov_query(qkey: str, qspec: dict) -> dict:
    """Execute one CT.gov v2 query; return {ncts: set, raw_count: int, error: str|None}."""
    params = qspec["query_params"].copy()
    # Convert pageSize for the API
    # CT.gov v2 returns up to 1000 per page; pageSize/markup
    query_string = urllib.parse.urlencode(params)
    url = f'{qspec["endpoint"]}?{query_string}&format=json'

    all_ncts: list[str] = []
    page_token = None
    raw_count = 0
    pages_fetched = 0
    while pages_fetched < 10:   # hard cap
        page_url = url
        if page_token:
            page_url = f"{url}&pageToken={page_token}"
        try:
            r = subprocess.run(
                ["curl", "-sS", "-A", "mtap-intel-audit/1.0", "--max-time", "20", page_url],
                capture_output=True, text=True, timeout=25,
            )
            if r.returncode != 0:
                return {"ncts": set(all_ncts), "raw_count": raw_count, "error": f"curl rc={r.returncode}", "pages": pages_fetched}
            data = json.loads(r.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return {"ncts": set(all_ncts), "raw_count": raw_count, "error": f"{type(e).__name__}", "pages": pages_fetched}

        studies = data.get("studies", [])
        for s in studies:
            ident = s.get("protocolSection", {}).get("identificationModule", {})
            n = ident.get("nctId")
            if n:
                all_ncts.append(n)
        raw_count += len(studies)
        page_token = data.get("nextPageToken")
        pages_fetched += 1
        if not page_token:
            break
        time.sleep(0.2)

    return {"ncts": set(all_ncts), "raw_count": raw_count, "error": None, "pages": pages_fetched}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(QUERIES_PATH))
    ap.add_argument("--sentinels-only", action="store_true",
                    help="Only run queries listed in sentinel_queries[]")
    args = ap.parse_args()

    state = state_lib.load_state()
    queries = json.loads(Path(args.queries).read_text())

    pass_record: dict = {
        "pass_date": dt.date.today().isoformat(),
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "queries_run": {},
        "all_surfaced_ncts": [],
        "in_state_ncts": [],
        "newly_surfaced_ncts": [],
        "in_state_not_surfaced": [],
        "summary": {},
    }

    # Build the in-state NCT set
    in_state_ncts = {t["tier_a"]["nct_id"] for t in state["trials"].values()}
    out_of_scope_ncts = {item["id"] for item in state.get("out_of_scope", [])}
    pass_record["in_state_ncts"] = sorted(in_state_ncts)

    # Which queries to run
    query_keys = list(queries["queries"].keys())
    if args.sentinels_only:
        query_keys = queries.get("sentinel_queries", [])

    print(f"[completeness] running {len(query_keys)} quer{'y' if len(query_keys)==1 else 'ies'}")
    all_surfaced: set[str] = set()
    surfaced_by_query: dict[str, set[str]] = {}
    for qkey in query_keys:
        qspec = queries["queries"][qkey]
        print(f"  {qkey} … ", end="", flush=True)
        result = run_ctgov_query(qkey, qspec)
        all_surfaced.update(result["ncts"])
        surfaced_by_query[qkey] = result["ncts"]
        pass_record["queries_run"][qkey] = {
            "raw_count": result["raw_count"],
            "unique_ncts": len(result["ncts"]),
            "pages": result["pages"],
            "error": result["error"],
            "rationale": qspec["rationale"],
        }
        print(f"raw={result['raw_count']} ncts={len(result['ncts'])}"
              + (f" ERROR: {result['error']}" if result['error'] else ""))
        time.sleep(0.3)

    pass_record["all_surfaced_ncts"] = sorted(all_surfaced)

    # PRISMA: trials surfaced but not in state and not explicitly out-of-scope
    candidates = all_surfaced - in_state_ncts - out_of_scope_ncts
    pass_record["newly_surfaced_ncts"] = sorted(candidates)

    # Inverse: in state but not surfaced by any documented query (search registry gap)
    missing_surfacing = in_state_ncts - all_surfaced
    pass_record["in_state_not_surfaced"] = sorted(missing_surfacing)

    # Cross-record provenance: update state's surfaced_by
    for row_id, t in state["trials"].items():
        nct = t["tier_a"]["nct_id"]
        prov = t.setdefault("provenance", {})
        surfaced_by = prov.get("surfaced_by", []) or []
        for qkey, ncts in surfaced_by_query.items():
            if nct in ncts and qkey not in surfaced_by:
                surfaced_by.append(qkey)
        prov["surfaced_by"] = surfaced_by
    state_lib.save_state(state)

    pass_record["summary"] = {
        "queries_run": len(query_keys),
        "queries_errored": sum(1 for q in pass_record["queries_run"].values() if q["error"]),
        "total_unique_ncts_surfaced": len(all_surfaced),
        "in_state": len(in_state_ncts),
        "in_state_now_surfaced": len(in_state_ncts) - len(missing_surfacing),
        "newly_surfaced_to_review": len(candidates),
        "in_state_but_not_surfaced": len(missing_surfacing),
    }

    PASSES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PASSES_DIR / f"{pass_record['pass_date']}.json"
    out_path.write_text(json.dumps(pass_record, indent=2, ensure_ascii=False))

    print()
    print(f"=== completeness pass {pass_record['pass_date']} ===")
    s = pass_record["summary"]
    print(f"  queries run:                       {s['queries_run']}")
    print(f"  total unique NCTs surfaced:        {s['total_unique_ncts_surfaced']}")
    print(f"  in-state trials covered by search: {s['in_state_now_surfaced']} / {s['in_state']}")
    print(f"  in-state but no search hit:        {s['in_state_but_not_surfaced']}  ⚠️ if >0, search registry has a gap")
    print(f"  newly surfaced (need review):      {s['newly_surfaced_to_review']}")
    print(f"  pass record:                       {out_path}")
    if candidates:
        print()
        print("Newly surfaced NCTs to review (add as trials, or document as out-of-scope):")
        for nct in sorted(candidates)[:30]:
            print(f"    {nct}  https://clinicaltrials.gov/study/{nct}")
        if len(candidates) > 30:
            print(f"    … and {len(candidates) - 30} more (see pass record)")
    if missing_surfacing:
        print()
        print(f"⚠️ In-state NCTs not surfaced by any query (search-registry gap):")
        for nct in sorted(missing_surfacing):
            print(f"    {nct}")


if __name__ == "__main__":
    main()
