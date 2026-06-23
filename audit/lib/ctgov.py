"""ClinicalTrials.gov v2 REST API client.

Minimal client tailored to what accuracy.py needs. Returns dicts shaped like
state.json's tier_a object so the diff logic is straightforward.
"""

from __future__ import annotations
import json
import subprocess
from typing import Any

BASE = "https://clinicaltrials.gov/api/v2/studies"


def fetch_trial(nct: str, timeout: float = 20.0) -> dict[str, Any] | None:
    """Fetch one trial. Returns tier_a-shaped dict, or {'_error': ...} on failure.

    Uses `curl` to avoid SSL-truststore issues in some local environments
    (e.g. corporate MITM proxies that don't ship Python's default trust roots).
    """
    url = f"{BASE}/{nct}?format=json"
    try:
        r = subprocess.run(
            ["curl", "-sS", "-A", "mtap-intel-audit/1.0", "--max-time", str(int(timeout)), url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if r.returncode != 0:
            return {"_error": f"curl rc={r.returncode}: {r.stderr.strip()[:200]}"}
        data = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    p = data.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    spons = p.get("sponsorCollaboratorsModule", {})
    design = p.get("designModule", {})
    arms = p.get("armsInterventionsModule", {})
    cond = p.get("conditionsModule", {})
    outc = p.get("outcomesModule", {})

    return {
        "nct_id": ident.get("nctId", nct),
        "brief_title": ident.get("briefTitle", ""),
        "sponsor": spons.get("leadSponsor", {}).get("name", ""),
        "collaborators": [c.get("name", "") for c in spons.get("collaborators", [])],
        "phases": _normalize_phases(design.get("phases", [])),
        "status": _normalize_status(status.get("overallStatus", "")),
        "start_date": status.get("startDateStruct", {}).get("date", ""),
        "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get("date", ""),
        "conditions": cond.get("conditions", []),
        "interventions": [
            {"type": i.get("type", ""), "name": i.get("name", "")}
            for i in arms.get("interventions", [])
        ],
        "primary_endpoints": [
            o.get("measure", "")
            for o in outc.get("primaryOutcomes", [])
        ],
        "ctgov_url": f"https://clinicaltrials.gov/study/{nct}",
        "_raw": data,   # keep for debugging / future fields
    }


def _normalize_phases(phases: list[str]) -> list[str]:
    """API returns ['PHASE1', 'PHASE2']; we display ['Phase 1', 'Phase 2']."""
    mapping = {
        "EARLY_PHASE1": "Phase 0/1",
        "PHASE1": "Phase 1",
        "PHASE2": "Phase 2",
        "PHASE3": "Phase 3",
        "PHASE4": "Phase 4",
        "NA": "N/A",
    }
    return [mapping.get(p, p) for p in phases]


def _normalize_status(s: str) -> str:
    """API uses SHOUTY_SNAKE; humanize."""
    mapping = {
        "RECRUITING": "Recruiting",
        "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
        "COMPLETED": "Completed",
        "TERMINATED": "Terminated",
        "WITHDRAWN": "Withdrawn",
        "SUSPENDED": "Suspended",
        "NOT_YET_RECRUITING": "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "UNKNOWN": "Unknown",
    }
    return mapping.get(s, s.title().replace("_", " "))
