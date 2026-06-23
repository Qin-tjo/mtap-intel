"""URL verification helpers for citation links."""

from __future__ import annotations
import re
import subprocess
from typing import Any


def check_url(url: str, timeout: float = 15.0) -> dict[str, Any]:
    """Use curl to GET the URL; return status code + extracted <title> if HTML.

    curl avoids local SSL-truststore issues. We follow redirects (-L) and
    capture both HTTP status + first 8KB of body for title extraction.
    """
    if not url or not url.startswith(("http://", "https://")):
        return {"url": url, "status": "invalid", "code": None, "title": None}

    try:
        # Write headers+status to /dev/stderr-like stream so we can split them.
        # Use curl's -w to emit final HTTP code on stderr, body on stdout.
        r = subprocess.run(
            [
                "curl", "-sL", "--max-time", str(int(timeout)),
                "-A", "Mozilla/5.0 (compatible; mtap-intel-audit/1.0)",
                "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9",
                "-w", "%{http_code}",
                "-o", "-",
                url,
            ],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"url": url, "status": "error", "code": None, "title": f"{type(e).__name__}"}

    # curl with -w "%{http_code}" appends the code at end of stdout
    out = r.stdout
    if len(out) < 3:
        return {"url": url, "status": "error", "code": None, "title": (r.stderr or "")[:80]}
    code_str, body = out[-3:], out[:-3]
    try:
        code = int(code_str)
    except ValueError:
        return {"url": url, "status": "error", "code": None, "title": "bad-status-trailer"}

    if code >= 400 or code == 0:
        return {"url": url, "status": "http-error", "code": code, "title": None}

    title = None
    if body and "<title" in body[:8192].lower():
        m = re.search(r"<title[^>]*>(.*?)</title>", body[:8192], re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    return {"url": url, "status": "ok", "code": code, "title": title}
