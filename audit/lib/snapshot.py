"""Snapshot a source URL to audit/snapshots/ for time-of-extraction provenance."""

from __future__ import annotations
import datetime as dt
import re
import subprocess
from pathlib import Path

SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "snapshots"


def snapshot(url: str, source_key: str, timeout: int = 20) -> dict:
    """Fetch the URL with curl and write to snapshots/<source_key>__<YYYY-MM-DD>.html.

    Returns {'path': ..., 'status': ok|error, 'code': int, 'bytes': int}.
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    fname = f"{_safe(source_key)}__{today}.html"
    out_path = SNAPSHOTS_DIR / fname

    r = subprocess.run(
        [
            "curl", "-sL", "--max-time", str(timeout),
            "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "-H", "Accept: text/html,application/xhtml+xml",
            "-w", "%{http_code}",
            "-o", str(out_path),
            url,
        ],
        capture_output=True, text=True,
    )
    code = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
    n_bytes = out_path.stat().st_size if out_path.exists() else 0

    if code >= 400 or code == 0 or n_bytes < 200:
        return {"path": str(out_path.relative_to(out_path.parents[2])), "status": "error", "code": code, "bytes": n_bytes}
    return {"path": str(out_path.relative_to(out_path.parents[2])), "status": "ok", "code": code, "bytes": n_bytes}


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", s).strip("-")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: snapshot.py <source_key> <url>")
        sys.exit(1)
    print(snapshot(sys.argv[2], sys.argv[1]))
