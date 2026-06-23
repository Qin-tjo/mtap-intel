"""state.json read/save + minimal validation.

The schema lives in audit/state.schema.md (human-readable). This module
enforces the structural invariants that the renderer depends on.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
HERE = Path(__file__).resolve().parent.parent
STATE_PATH = HERE / "state.json"
SOURCES_PATH = HERE / "sources.json"
QUERIES_PATH = HERE / "queries.json"


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    data = json.loads(path.read_text())
    _validate(data)
    return data


def save_state(data: dict[str, Any], path: Path = STATE_PATH) -> None:
    _validate(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_render": None,
        "scope_doc_version": 1,
        "trials": {},
        "out_of_scope": [],
        "synthesis_figures": [],
        "competitive_cards": [],
    }


def _validate(data: dict[str, Any]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version mismatch: file has {data.get('schema_version')}, "
            f"code expects {SCHEMA_VERSION}"
        )
    for key in ("trials", "out_of_scope", "synthesis_figures", "competitive_cards"):
        if key not in data:
            raise ValueError(f"missing top-level key: {key}")

    seen_claim_ids: set[str] = set()
    for row_id, trial in data["trials"].items():
        if not row_id.startswith("NCT"):
            raise ValueError(f"trial key not NCT-prefixed: {row_id}")
        actual_nct = trial.get("tier_a", {}).get("nct_id", "")
        if not actual_nct.startswith("NCT") or len(actual_nct) < 8:
            raise ValueError(f"{row_id}: tier_a.nct_id missing or invalid: {actual_nct!r}")
        nct = row_id
        for required in ("tier_a", "tier_b_claims", "display", "provenance"):
            if required not in trial:
                raise ValueError(f"{nct}: missing required key {required}")
        if not trial.get("in_scope", True):
            raise ValueError(
                f"{nct}: in_scope=false but lives in trials{{}}; move to out_of_scope[]"
            )
        for claim in trial["tier_b_claims"]:
            cid = claim.get("claim_id")
            if not cid:
                raise ValueError(f"{nct}: claim without claim_id")
            if cid in seen_claim_ids:
                raise ValueError(f"duplicate claim_id across state: {cid}")
            seen_claim_ids.add(cid)
            # Drift detector: any numeric value must appear in at least one verbatim.
            val = str(claim.get("value", ""))
            numeric_part = "".join(ch for ch in val if ch.isdigit() or ch == ".")
            if numeric_part:
                joined = " ".join(
                    m.get("verbatim", "")
                    for src in claim.get("sources", [])
                    for m in src.get("mentions", [])
                )
                if numeric_part not in joined.replace(",", ""):
                    raise ValueError(
                        f"{nct}/{cid}: claim value '{val}' not found in any verbatim mention"
                    )
