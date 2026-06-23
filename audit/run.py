"""run.py — combined audit pass.

Runs (in order):
  1. completeness.py    (multi-source systematic search → PRISMA flow + provenance update)
  2. accuracy.py        (Tier-A registry sync + Tier-B verbatim verification + URL checks)
  3. render.py          (state.json → trial-table tbody + audit-log section)

This is the recommended single-command entry point. Run this before publishing
any change to the Clinical Landscape.

Flags forwarded to sub-tools:
  --no-fetch           : skip CT.gov fetches in accuracy.py
  --apply              : accuracy.py overwrites tier_a fields with CT.gov values
  --no-urls            : skip URL verification (faster; default is to verify)
  --sentinels-only     : completeness runs only the sentinel queries
  --skip-completeness  : skip completeness step
  --skip-accuracy      : skip accuracy step
"""

from __future__ import annotations
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit"


def run(cmd: list[str]) -> int:
    print()
    print(f"$ {' '.join(cmd)}")
    print("-" * 72)
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-urls", action="store_true")
    ap.add_argument("--sentinels-only", action="store_true")
    ap.add_argument("--skip-completeness", action="store_true")
    ap.add_argument("--skip-accuracy", action="store_true")
    ap.add_argument("--skip-triangulation", action="store_true")
    args = ap.parse_args()

    start = dt.datetime.now()
    print(f"=== audit/run.py · combined pass started {start.isoformat(timespec='seconds')} ===")

    if not args.skip_completeness:
        comp_cmd = [sys.executable, str(AUDIT / "completeness.py")]
        if args.sentinels_only:
            comp_cmd.append("--sentinels-only")
        rc = run(comp_cmd)
        if rc != 0:
            print(f"⚠️ completeness exited rc={rc}; continuing")
    else:
        print("[run] skipping completeness")

    if not args.skip_accuracy:
        acc_cmd = [sys.executable, str(AUDIT / "accuracy.py")]
        if args.apply:
            acc_cmd.append("--apply")
        if args.no_fetch:
            acc_cmd.append("--no-fetch")
        if not args.no_urls:
            acc_cmd.append("--urls")
        rc = run(acc_cmd)
        if rc != 0:
            print(f"⚠️ accuracy exited rc={rc}; continuing")
    else:
        print("[run] skipping accuracy")

    if not args.skip_triangulation:
        tri_cmd = [sys.executable, str(AUDIT / "triangulate.py")]
        rc = run(tri_cmd)
        if rc != 0:
            print(f"⚠️ triangulate exited rc={rc}; continuing")
    else:
        print("[run] skipping triangulation")

    rc = run([sys.executable, str(AUDIT / "render.py")])

    elapsed = (dt.datetime.now() - start).total_seconds()
    print()
    print(f"=== audit/run.py · combined pass complete in {elapsed:.1f}s ===")
    print("  Review the audit log on the dashboard (bottom section 'A').")
    print("  Newly surfaced trials in section A.4 need manual triage (add to state.json or out_of_scope).")


if __name__ == "__main__":
    main()
