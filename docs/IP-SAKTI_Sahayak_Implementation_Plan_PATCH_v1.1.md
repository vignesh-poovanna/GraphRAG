# IP-SAKTI Sahayak — Implementation Plan Patch v1.1

Patches the five gaps identified against the target scope (licensing, cross-border compliance, trademark, procedural queries). Additive only — no changes to Phases 3–4 or the existing corpus/schema entries.

---

## 1. Phase 1 Patch — Corpus Expansion

### 1.1 New category: Manufacturing Licensing (India)

| Document | Why it's needed | Source |
|---|---|---|
| Drugs and Cosmetics Act, 1940 | Parent statute — defines "Ayurvedic, Siddha or Unani drug," licensing powers, offences | India Code |
| Drugs and Cosmetics Rules, 1945, Rules 151–170 | Procedural core: licensing authorities, manufacturing license (Form 25/25-D), loan license (Form 25-A/25-E), application process | [Full consolidated text (as amended to 30 Sep 2020)](https://www.thc.nic.in/Tripura%20State%20Lagislation%20Rules/Drugs%20and%20Cosmetics%20Rules,%201945.pdf) |
| Schedule T (Rule 157) | GMP standard for ASU manufacturing premises — Part I (factory/hygiene) and Part II (machinery, minimum manufacturing standards per dosage form) | Same instrument, Schedule T |
| **Drugs (Eleventh Amendment) Rules, 2026** | **Currently in force — notified 24 Jul 2026, gazetted 5 Aug 2026.** Rewrites Rules 154/154A (licenses now perpetual, no renewal), omits Rules 156/156A, revises Rule 157(1C) proviso on single-plant-ingredient extracts, and touches product coding, labelling, stability studies, and inspector qualifications. If the corpus ingests only the pre-2026 consolidated Rules text, "how do I get/renew a license" answers will be **wrong** — flag this as the highest-priority single ingestion item. | [TeamLease RegTech summary + G.S.R. 657(E)](https://teamleaseregtech.com/updates/article/58127/drugs-eleventh-amendment-rules-2026/); [Lexplosion summary](https://lexplosion.in/?p=151762) |
| Jan Vishwas (Amendment of Provisions) Act, 2026 — AYUSH provisions | In force from 1 Jul 2026. Converts several minor D&C Act offences (misbranding, labelling, minor licence violations, recordkeeping) from criminal prosecution to monetary penalty. Relevant whenever a query touches penalties/consequences, not just procedure. | Ministry of AYUSH notification (referenced via [Corpseed summary](https://www.corpseed.com/law-update/ayush-jan-vishwas-act-amendments-effective-from-1-july-2026)) |
| e-AUSHADHI portal procedure notes | The actual filing mechanics (online application, self-compliance declaration) sit outside the Rules text itself — needed for a genuinely "step-by-step" answer rather than a statutory paraphrase | www.e-aushadhi.gov.in |

**Note on staleness risk:** manufacturing licensing is the fastest-moving category in this corpus (three amendments/notifications in 2025–2026 alone). Recommend a re-ingestion cadence for this category specifically — e.g., quarterly — separate from the slower-moving IP statutes.

### 1.2 New category: Cross-Border Export Compliance

| Jurisdiction | Document | Scope |
|---|---|---|
| USA | Dietary Supplement Health and Education Act (DSHEA), 1994 | Defines "dietary supplement," places it under the food umbrella (not drug), sets labeling/structure-function-claim rules |
| USA | 21 CFR Part 111 | cGMP requirements for dietary supplement manufacturing, packing, labeling, holding — this is what a US importer will actually audit against |
| USA | FDA Botanical Drug Development Guidance (CDER) | Only triggers if the herb is positioned as a *drug* rather than a supplement (structure/function claim vs. disease claim is the fork) — needed so the orchestrator can correctly route "is my product a supplement or a drug" | [fda.gov/about-fda/cder-offices-and-divisions/what-botanical-drug](https://www.fda.gov/about-fda/cder-offices-and-divisions/what-botanical-drug) |
| EU | Directive 2004/24/EC (THMPD) | Simplified registration route for traditional herbal medicinal products — 30 years traditional use (15 in EU), no clinical trial requirement, but real registration burden per member state | [EUR-Lex 32004L0024](https://eur-lex.europa.eu/eli/dir/2004/24/oj) |
| EU | Regulation (EU) 2015/2283 (Novel Food Regulation) | Governs the *other* route — if the herb/ingredient has no history of significant EU food consumption pre-1997, it needs novel-food authorisation regardless of THMPD status. Many Ayurvedic botanicals (e.g., ashwagandha in some member states) fall into this trap | EUR-Lex |
| EU | EFSA guidance on botanical/botanical preparation safety assessment | Working data EFSA actually uses to evaluate novel-food and health-claim dossiers | efsa.europa.eu |

**Design implication:** cross-border queries are inherently a **jurisdiction-comparison** (which the plan already has a mode for), but the *first* question the orchestrator needs to resolve is usually "supplement/food route vs. drug/medicinal route," since that fork determines which sub-corpus (DSHEA+21CFR111 vs. FDA botanical guidance; THMPD vs. Novel Food) applies. Suggest adding this as an explicit disambiguation step at the top of the jurisdiction-comparison mode rather than assuming supplement-route by default.

### 1.3 Addition to existing IP corpus: Trademark

| Document | Scope |
|---|---|
| Trade Marks Act, 1999 (Act No. 47 of 1999) | Registration, protection, infringement, passing-off, well-known marks | [Official text — IP India](https://ipindia.gov.in/tm-act-1999) |
| Trade Marks Rules, 2017 | Filing procedure, forms, fee schedule | IP India |

---

## 2. Phase 2 Patch — Schema

`IPProtectionType` enum — add `TRADEMARK`:

```
enum IPProtectionType {
  PATENT
  GEOGRAPHICAL_INDICATION
  TRADEMARK        // new
  COPYRIGHT         // (if not already present — check)
}
```

No other schema changes required; GI and Patent paths already model the fields (applicant, class/category, prior-art-check flag) that Trademark needs.

---

## 3. Phase 5 Patch — New Orchestrator Mode: `PROCEDURAL`

The existing four modes (novelty-check, jurisdiction-comparison, precedent, general) all resolve to a single retrieved answer or a side-by-side comparison. Licensing questions ("how do I get a manufacturing license") need a fifth shape: **retrieve multiple rule sections, then order them into a sequence**, because the rules themselves are not written in procedural order (definitions, then licensing authority powers, then application requirements, then GMP certification are scattered across non-contiguous Rule numbers).

**Mode behavior:**
1. Retrieve all corpus chunks tagged with the relevant licensing category (e.g., `manufacturing_license`, `loan_license`, `export_registration`).
2. Classify each chunk by procedural stage using metadata set at ingestion time (`stage: application | documentation | inspection | certification | renewal | penalty`) rather than inferring order from the LLM — this keeps the "no hallucination" guarantee intact, since ordering is a retrieval/metadata operation, not a generative one.
3. Render as a numbered sequence, each step still carrying its own `"According to Section X..."` citation from Phase 4's formatter — the citation guardrail is untouched by this mode.
4. If a step depends on a form or portal (e.g., e-AUSHADHI submission) that isn't itself a statutory citation, mark it distinctly (e.g., "Procedural note," not "Legal citation") so the strict source-attribution guarantee isn't diluted by non-legal howto content.

This requires one new ingestion-time field (`stage`) on chunks in the licensing/export categories only — existing IP-protection chunks don't need it and shouldn't get it, since forcing a `stage` tag onto e.g. a GI Act section would be meaningless.

---

## 4. Updated Gap Table

| Gap | Status after this patch |
|---|---|
| Missing Drugs & Cosmetics Act/Rules + AYUSH licensing procedure | Corpus list defined; **2026 Eleventh Amendment flagged as priority ingestion** |
| Missing US/EU export regs | Corpus list defined; supplement-vs-drug fork identified as a required disambiguation step |
| Missing Trade Marks Act, 1999 | Corpus + schema patch defined |
| No procedural answer mode | New `PROCEDURAL` orchestrator mode designed, with `stage` metadata as the ordering mechanism |
| `IPProtectionType` missing Trademark | One-line enum addition |

Nothing here requires touching Phase 3 (embedding/retrieval) or Phase 4 (citation formatting) — the `generate_answer()` guardrail and citation renderer apply unchanged to all five corpus categories and all five orchestrator modes.
