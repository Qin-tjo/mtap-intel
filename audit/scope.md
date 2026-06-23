# MTAP / PRMT5 Clinical Landscape — Scope Statement

**Version:** 1
**Effective:** 2026-06-23
**Maintainer:** dashboard author (qinyu5155@gmail.com)

This document defines what trials are eligible for inclusion in the Clinical Landscape section of the MTAP target-intelligence dashboard, what is explicitly out of scope, and how scope decisions are recorded.

---

## In scope

A trial is **in scope** if it satisfies all of (1), (2), and (3):

**(1) Drug mechanism.** The investigational agent's primary mechanism of action targets one of:
  - PRMT5 (any selectivity profile, including first-generation non-selective and MTA-cooperative inhibitors)
  - MAT2A (the upstream methionine-cycle enzyme that generates SAM for PRMT5)
  - Other components of the MTAP / methionine-salvage / SAM-PRMT5 axis (e.g., AHCY, MAT1A, MTAP-pathway degraders, MTA-pathway modulators)

**(2) Study type.** The trial is a **prospective interventional clinical trial** in human participants. Phase 0 through Phase 4 are all eligible. Both monotherapy and combination arms are included.

**(3) Activity window.** The trial is in at least one of:
  - Currently active (status: Recruiting, Active not recruiting, Enrolling by invitation)
  - First-patient-dosed within the last 10 years (i.e., start date ≥ 2016-01-01)
  - Presented data at a major oncology conference within the last 5 years (ASCO Annual, ASCO GI/GU/GYN, ESMO, ESMO Asia, AACR, WCLC, ASH, EHA, SITC)

If a trial is registered but never dosed a patient (status: Withdrawn before enrolment), it is **out of scope** unless its registration itself was a notable disclosure event (e.g., a sponsor announcing a pivotal Phase 3 plan).

## Out of scope (with documentation)

The following are explicitly excluded. Each exclusion is logged in `state.json` under `out_of_scope[]` with a reason:

  - **Preclinical-only programmes** without an open IND or registered FIH trial.
  - **Imaging-only or biomarker-only trials** without a therapeutic intervention (e.g., MTAP-PET tracers, MTAP-IHC validation studies).
  - **Retrospective analyses, real-world-evidence studies, registry studies, and meta-analyses.**
  - **Trials where PRMT5 / MAT2A / MTAP-axis activity is incidental** — e.g., a broad epigenetic basket where one arm contains a PRMT5i but the trial isn't designed to test MTAP-axis biology.
  - **Veterinary, paediatric (<18 y) standalone studies, and healthy-volunteer Phase 0** are out of scope for the main table but flagged in `notes` for completeness.

## Geography

All geographies are in scope. Searches must include:
  - ClinicalTrials.gov (US/global)
  - WHO ICTRP (meta-registry)
  - ChiCTR (China)
  - EU CTR / EudraCT (Europe)
  - JRCT (Japan)
  - ANZCTR (Australia/NZ)

A trial may be registered only in a non-US registry; this does not exclude it.

## Biomarker definition (for indication tagging)

  - **MTAP homdel** — homozygous deletion confirmed by NGS panel CN, FISH, or whole-genome/exome sequencing.
  - **MTAP-loss by IHC** — protein-level loss; not necessarily homozygous deletion (heterozygous loss + silencing can produce the same IHC phenotype).
  - **MTAP+CDKN2A co-del** — when the trial explicitly requires both.
  - **Not selected** — no MTAP biomarker requirement (used for first-generation PRMT5i programmes).

Mismatch between the trial's eligibility definition and the dashboard's biomarker tag is a Tier-A error.

## Citation tier scale

Every Tier-B factual claim (ORR, n, DCR, mDOR, mPFS, CR, data cutoff) must be sourced and tier-tagged:

  - **T1** — peer-reviewed paper indexed in PubMed
  - **T2** — prospectively published conference abstract in a peer-reviewed journal supplement (e.g., JCO, JTO, Annals of Oncology, Blood, HemaSphere supplements)
  - **T3** — conference presentation only (slides, oral, poster image not yet published in supplement)
  - **T4** — company press release, IR deck, SEC filing
  - **T5** — preprint (bioRxiv, medRxiv) or inference from registry data

**Display rule:** any headline figure in the trial table, 4.4 cards, or synthesis text must cite ≥T2. T4-sourced figures are allowed in the table only when explicitly tagged "preliminary" and downgrade the row's confidence to ⚠️.

## Scope changes

Any change to this scope statement bumps `version` and is accompanied by a commit message of the form `audit-scope: <change description>`. Any newly-excluded trials are moved from `trials{}` to `out_of_scope[]` in the same commit. Any newly-included scope dimension triggers a re-run of `completeness.py` with updated queries.

## Known limitations

Documented here so a reviewer can see them on the dashboard:

  1. **ChiCTR queries** require Chinese-language search and are run quarterly rather than per audit pass.
  2. **Industry pipeline subscriptions** (Citeline / Pharmaprojects, Cortellis, Adis Insight, GlobalData) are not used. Their proprietary entries may include pre-public programmes not yet on ClinicalTrials.gov.
  3. **Pre-registration disclosures** (e.g., a sponsor announcing an IND submission before the trial is registered) are added on a best-effort basis from sponsor IR pages and major conference programmes.
  4. **Investigator-initiated single-site studies** may be under-detected if not registered on ClinicalTrials.gov.
  5. Completeness can be approximated by documented systematic search; it cannot be proven. The search registry in `queries.json` is the audit trail.

---

*End of scope statement.*
