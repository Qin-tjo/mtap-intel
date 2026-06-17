# MTAP target intelligence dashboard

A single-page, self-contained research dashboard summarizing the genomic, mechanistic,
clinical, and synthesis landscape for **MTAP** (and the MTAP / PRMT5 synthetic-lethal
axis) across the 33 TCGA indications.

**Live view:** https://<your-username>.github.io/<repo-name>/

## What it covers

1. **Genomic landscape** — MTAP homozygous / heterozygous deletion frequencies by
   TCGA indication (ABSOLUTE-corrected calls), CN → expression fidelity, co-deletion
   neighbourhood at 9p21.3, mutational landscape of MTAP-homdel patients, and
   panel-NGS validation.
2. **Mechanism & rationale** — Four-step MTAP / MTA / PRMT5 synthetic-lethal flow,
   biomarker rationale, and therapeutic-strategy classes.
3. **Clinical landscape** — Filterable / sortable table of MTAP-directed clinical
   trials (MTA-cooperative PRMT5 inhibitors, MAT2A inhibitors, first-gen PRMT5i)
   with reported ORRs where available.
4. **Synthesis** — Hedged thesis, patient-selection considerations, combination
   strategies, competitive landscape, risks, and proposed next steps.
5. **References & audit log** — 36 primary citations (PubMed / DOI links) and an
   audit trail of every analysis step.

Every scientific claim is linked to a primary citation; numerical claims in the
dashboard are traceable to the audit rows.

## How it was generated

- **Genomic layer:** TCGA ABSOLUTE allelic copy number (Taylor 2018 PanCanAtlas),
  recount3 uniformly-reprocessed RNA-seq (log2 TPM+1), MC3 public MAF (Ellrott 2018),
  OncoKB cancer-gene whitelist.
- **Validation layer:** MSK-IMPACT via cBioPortal, plus matched-sample IHC vs
  panel-NGS literature.
- **Clinical layer:** ClinicalTrials.gov v2 REST API + curated readouts from
  ASCO / AACR / JCO 2023–2026.
- **Render layer:** R with inline SVG (no client-side data dependency); the page
  is fully static and runs without any backend.

Source code for the pipeline lives in a separate repository.

## Data currency

Snapshot generated **2026-06-17**. Clinical-trial statuses (NCT IDs, enrolment,
ORRs) and primary-literature numbers will drift over time — verify against
[ClinicalTrials.gov](https://clinicaltrials.gov/) and the linked primary sources
before relying on any specific number.

## Disclaimer

For research and educational use only. Not medical advice. Nothing in this
dashboard is a treatment recommendation. Hedged language ("appears to", "likely",
"may") is used deliberately throughout; please honour the hedging when citing.

## License

Content is released under [CC BY 4.0](LICENSE) — attribution required,
redistribution and adaptation allowed.
