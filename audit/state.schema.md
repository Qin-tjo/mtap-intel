# `state.json` — Source-of-Truth Schema

`state.json` is the **single source of truth** for the Clinical Landscape section of the dashboard. The trial table, the 4.4 competitive landscape cards, the synthesis ORR figures, and the audit log are all rendered from this file by `render.py`. **Never edit the HTML directly** for clinical content — edit `state.json` and re-render.

**Schema version:** 1
**Status:** draft for review

---

## Top-level structure

```jsonc
{
  "schema_version": 1,
  "last_render": "2026-06-23T18:42:00Z",
  "scope_doc_version": 1,                    // matches audit/scope.md version
  "trials": {
    "NCT05094336": { /* see Trial object */ },
    "NCT05245500": { /* ... */ }
  },
  "out_of_scope": [
    { /* see OutOfScope entry */ }
  ],
  "synthesis_figures": [
    { /* see SynthesisFigure */ }
  ],
  "competitive_cards": [
    { /* see CompetitiveCard */ }
  ]
}
```

## Trial object

One entry per NCT ID. The object splits into three sub-objects:

```jsonc
{
  "tier_a": { /* registry-authoritative, mechanically verifiable */ },
  "tier_b_claims": [ /* literature-authoritative, human-verified */ ],
  "display": { /* how this trial renders in the HTML */ },
  "provenance": { /* how this trial entered state.json */ },
  "in_scope": true,
  "scope_rationale": "MTA-cooperative PRMT5i; Phase 1/2; recruiting"
}
```

### `tier_a` — registry-authoritative fields

These are pulled from `ClinicalTrials.gov` v2 API on every `accuracy.py` run. A mismatch between `tier_a` and the live registry response is a hard error.

```jsonc
{
  "nct_id": "NCT05094336",
  "drug_canonical": "Anvumetostat",              // INN, when assigned
  "drug_aliases": ["AMG 193"],                   // historical codes
  "sponsor": "Amgen",
  "sponsor_history": [],                         // e.g., Mirati → BMS handoff
  "mechanism_class": "MTA-cooperative PRMT5i",   // controlled vocabulary
  "phases": ["Phase 1", "Phase 2"],
  "status": "Active, not recruiting",
  "conditions": ["NSCLC", "Biliary Tract Cancer", "..."],
  "interventions": ["Anvumetostat", "Docetaxel"],
  "primary_endpoints": ["ORR", "DLT", "AEs"],
  "start_date": "2022-02-01",                    // registry-reported start
  "first_patient_dosed": null,                   // sponsor-reported (optional)
  "ctgov_url": "https://clinicaltrials.gov/study/NCT05094336",
  "last_synced": "2026-06-23",
  "last_synced_status": "match"                  // match | mismatch | error
}
```

### `tier_b_claims` — literature-authoritative figures

An array. Each entry is one numerical/categorical claim sourced from literature (paper, abstract, press release). The structure enforces verbatim capture and multi-source corroboration.

```jsonc
[
  {
    "claim_id": "rodon2024_orr_active",          // stable; used in render
    "field": "ORR",                              // ORR | DCR | mDOR | mPFS | CR | n
    "value": "21.4%",                            // canonical display string
    "value_numeric": 21.4,
    "n": {
      "count": 42,
      "type": "response-evaluable",              // enrolled | response-evaluable | efficacy-evaluable | safety-evaluable
      "qualifier": "active doses only (800 QD / 1200 QD / 600 BID)"
    },
    "subset": "all tumour types at active doses",// what slice of the trial
    "ci_95": "10.3–36.8%",
    "data_cutoff": "2024-04-15",                 // best-known cutoff
    "data_cutoff_confidence": "stated-in-paper", // stated-in-paper | inferred | unknown
    "sources": [
      {
        "tier": 1,
        "source_key": "rodon2024",               // → sources.json
        "mentions": [
          {
            "location": "abstract",
            "verbatim": "Among those receiving an active dose, the ORR was 21.4% (95% CI 10.3-36.8%) with 9 confirmed responses across 8 tumour types..."
          },
          {
            "location": "Table 2 / Results §3.2",
            "verbatim": "All active doses · n=42 · ORR 21.4% · DCR 54.8% · mDOR 8.3 months."
          }
        ],
        "snapshot_path": "audit/snapshots/rodon2024__2026-06-23.html"
      }
    ],
    "cross_source_check": "single-source-T1",    // multi-source-agree | multi-source-conflict | single-source-T1 | single-source-T2 | etc.
    "confidence": "verified",                    // verified | needs-recheck | conflict
    "last_audited": "2026-06-23",
    "audited_by": "claude-opus-4-7",
    "notes": "Distinct from 12.8% all-comers ORR (5/39) which includes sub-therapeutic doses; do not conflate."
  }
]
```

**Drift-detection rule** in `accuracy.py`:
  - For every mention, `value.replace('%','')` must appear in `verbatim` (or appear once in any cross-referenced mention). If not, the entry flips to ⚠️.
  - Mentions across the same source must agree numerically.
  - `sources.length ≥ 2` upgrades `cross_source_check` accordingly.

### `display` — render hints

Optional overrides for how the row renders. `render.py` uses sensible defaults from `tier_a` + `tier_b_claims`; this block only contains intentional overrides.

```jsonc
{
  "drug_label": "AMG 193",                       // table prefers code name where used by community
  "sponsor_label": "Amgen",
  "indication_label": "Solid (basket)",
  "biomarker_tag": "MTAP+CDKN2A",
  "combination_tag": "Combo: chemo",
  "orr_display": "21.4%",                        // pulls from claim_id "rodon2024_orr_active"
  "orr_claim_id": "rodon2024_orr_active",        // tells render.py which claim
  "orr_tooltip_template": "{value} ORR at active doses ({n.qualifier}; n={n.count}; 95% CI {ci_95}). {notes}",
  "n_display": "42",
  "n_ctx": "· active doses · 8 types",
  "start_display": "2022-02-01",
  "sort_orr": 21.400,
  "sort_n": 42,
  "search_keywords": "nct05094336 amg 193 anvumetostat mtap-null solid tumor amgen mtapestry"
}
```

### `provenance` — how this row got here

```jsonc
{
  "first_added": "2026-06-15",
  "first_added_pass": "manual-2026-06-15",       // or "completeness-2026-06-20"
  "surfaced_by": [                               // which queries find this trial today
    "ctgov_query_prmt5_mtap",
    "asco2024_search_amg193"
  ],
  "review_triangulation": [                       // which published reviews list it
    "lin2023_commentary",
    "cottrell2024_review"
  ]
}
```

A row with `surfaced_by: []` is suspect — the documented search wouldn't reproduce it. `completeness.py` flags this.

## OutOfScope entry

Trials that surfaced in searches but were judged out of scope. Documenting these is how we defend against "you missed X" — the answer is "X was considered and excluded for reason Y on date Z."

```jsonc
{
  "id": "NCT04603807",
  "name": "Phase I study of <drug> in advanced solid tumors",
  "drug": "GSK3326595",
  "sponsor": "GlaxoSmithKline",
  "first_seen": "2026-06-22",
  "reason": "First-generation non-selective PRMT5i, completed 2021, not MTAP-selected enrolment, no current development; mentioned in mechanism context only (Section 2).",
  "surfaced_by": ["ctgov_query_prmt5"]
}
```

## SynthesisFigure

For the headline ORR numbers in section 4 (synthesis). Each figure quoted in the prose carries a claim_id reference.

```jsonc
{
  "figure_id": "synthesis_pdac_vopi_dara_92orr",
  "location": "section 4.1 / §thesis",
  "claimed_text": "~92% ORR in 12 MTAP-deleted RAS-mut PDAC patients",
  "claim_id": "tng462_daraxonrasib_2026_pdac",   // → claim in trials[NCTxxxxx].tier_b_claims
  "source_keys": ["tango_press_2026-06-08"],
  "tier": 4,
  "confidence": "preliminary-press-release"
}
```

## CompetitiveCard

For the 4.4 competitive landscape cards.

```jsonc
{
  "card_id": "bms_navlimetostat",
  "sponsor": "Bristol Myers Squibb",
  "drug_label": "Navlimetostat (BMS-986504 / MRTX1719)",
  "positioning": "<text>",
  "catalysts": "<text>",
  "referenced_trials": ["NCT05245500", "NCT07076121", "NCT06855771", "NCT07063745"],
  "referenced_claims": ["bms986504_overall_orr_asco2025"],
  "last_audited": "2026-06-23",
  "confidence": "verified"
}
```

## Citation registry (`sources.json` — separate file)

Decoupled from `state.json` so a citation cited on 12 rows is verified once, not 12 times.

```jsonc
{
  "rodon2024": {
    "tier": 1,
    "type": "peer-reviewed",
    "authors": "Rodon J, Prenen H, Sacher A, et al.",
    "title": "First-in-human study of AMG 193, an MTA-cooperative PRMT5 inhibitor, in patients with MTAP-deleted solid tumors: results from phase I dose exploration.",
    "journal": "Annals of Oncology",
    "year": 2024,
    "volume": "35",
    "pages": "1138-1147",
    "url": "https://www.annalsofoncology.org/article/S0923-7534(24)03919-X/fulltext",
    "pmid": null,
    "doi": "10.1016/j.annonc.2024.08.2339",
    "snapshot_path": "audit/snapshots/rodon2024__2026-06-23.html",
    "last_url_check": "2026-06-23",
    "url_status": "200",
    "url_title_match": true                      // does the page title still match `title`?
  }
}
```

## Search-query registry (`queries.json` — separate file)

```jsonc
{
  "ctgov_query_prmt5_mtap": {
    "source": "ClinicalTrials.gov v2 API",
    "query": "PRMT5 OR MTAP OR MAT2A AND inhibitor",
    "filters": {"status": "all", "phase": "all"},
    "rationale": "Broad mechanism-class sweep of US/global registry",
    "history": [
      { "date": "2026-06-23", "raw_hits": 42, "after_dedup": 38, "in_scope": 28 }
    ]
  },
  "asco2026_jco_supplement_search": {
    "source": "JCO 2026 ASCO Annual Meeting supplement (44:16_suppl)",
    "query": "MTAP OR PRMT5 OR MAT2A within abstract titles",
    "rationale": "Conference abstract sweep",
    "history": [
      { "date": "2026-06-23", "raw_hits": 11, "in_scope": 4, "newly_added": ["NCT06968572"] }
    ]
  }
}
```

## Validation rules (enforced by `lib/state.py`)

On every load:

  1. `schema_version` must match the version this code knows.
  2. Every `trials[NCT].tier_b_claims[].claim_id` must be unique within the trial.
  3. Every `claim_id` referenced by `display.orr_claim_id`, `SynthesisFigure.claim_id`, etc., must exist.
  4. Every `source_key` referenced anywhere must exist in `sources.json`.
  5. Every `surfaced_by` query name must exist in `queries.json`.
  6. Every `snapshot_path` must point to an existing file under `audit/snapshots/`.
  7. For every claim with `value` containing a number: the number (digits + optional decimal) must appear in at least one `mentions[].verbatim` string.
  8. Every NCT in `trials{}` must have `in_scope: true`. Out-of-scope items live in `out_of_scope[]`, not `trials{}`.

Any failure aborts the render.

---

*End of schema documentation.*
