# Imported Documents Log (IP-SAKTI Sahayak)
# Updated: 2026-09-12 (Enriched Knowledge Graph & Markdown Corpus)
# Total Documents: 30 | Total Chunks: 11,147 | Relationships: 22,509 | Categories: 6

## 🏛️ Knowledge Graph Categorization & Corpus

All 30 documents have been enriched with YAML frontmatter, normalized section headings, domain taxonomies, and cross-act relational edges.

| # | Document | Domain Category | Format | Neo4j Status |
|---|----------|-----------------|--------|--------------|
| 1 | `Press Release Page _ Press Information Bureau.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 2 | `Press Release Page _ Press Information Bureau Pharmacopoeia Commission for Indian Medicine.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 3 | `The Patents (Amendment) Act - 26 March 1999.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 4 | `wipo.md` | National & International IP Policy | Markdown | ✅ Ingested |
| 5 | `Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 6 | `The Geographical Indications of Goods (Registration and Protection) (Amendment) Rules, 2025.md` | Trademarks & Geographical Indications | Markdown | ✅ Ingested |
| 7 | `itra_act.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 8 | `Guidelines for Examination of Ayush Related Inventions-2025.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 9 | `Copyright-Rules Amendment 2021.md` | Copyrights & Digital Media | Markdown | ✅ Ingested |
| 10 | `tribunal_reforms_act.md` | National & International IP Policy | Markdown | ✅ Ingested |
| 11 | `Biodiversity_Act_2002.md` | Biodiversity & Access-Benefit Sharing | Markdown | ✅ Ingested |
| 12 | `nagoya-protocol-en.md` | Biodiversity & Access-Benefit Sharing | Markdown | ✅ Ingested |
| 13 | `Guidelines for Examination of Biotechnology Applications for Patent - 2013.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 14 | `cbd-en.md` | Biodiversity & Access-Benefit Sharing | Markdown | ✅ Ingested |
| 15 | `The Patents (Amendment) Act 2005.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 16 | `The Patents (Amendment) Act - 25 June 200.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 17 | `The Patents (Amendment) Act, 2002 (38 of 2002).md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 18 | `wto-27-trips.md` | National & International IP Policy | Markdown | ✅ Ingested |
| 19 | `ncsm_aayush.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 20 | `2016-_National_IPR_Policy-2016__English_and_Hindi.md` | National & International IP Policy | Markdown | ✅ Ingested |
| 21 | `The_Geographical_Indications_of_Goods_Registration_and_Protec.md` | Trademarks & Geographical Indications | Markdown | ✅ Ingested |
| 22 | `Guidelines for examination of patent applications in the field of Pharmaceuticals - 2014.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 23 | `THE JAN VISHWAS (AMENDMENT OF PROVISIONS) ACT, 2023.md` | National & International IP Policy | Markdown | ✅ Ingested |
| 24 | `copyright rules 2013.md` | Copyrights & Digital Media | Markdown | ✅ Ingested |
| 25 | `Rules & Regulations & Bye Laws _ Council of Scientific & Industrial Research.md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |
| 26 | `cpoyrights act.md` | Copyrights & Digital Media | Markdown | ✅ Ingested |
| 27 | `trademarks act 1999.md` | Trademarks & Geographical Indications | Markdown | ✅ Ingested |
| 28 | `patents_act_1970.md` | Patent Law & Examination | Markdown | ✅ Ingested |
| 29 | `trademarks rules.md` | Trademarks & Geographical Indications | Markdown | ✅ Ingested |
| 30 | `Ayurvedic Pharmacopoeia of India All Volume .md` | Ayurveda & Traditional Knowledge | Markdown | ✅ Ingested |

---

## 📊 Knowledge Graph Architecture

- **Total Documents:** 30
- **Total Chunks:** 11,147
- **Total Graph Relationships:** 22,509
- **Domain Categories:**
  1. `Patent Law & Examination`
  2. `Ayurveda & Traditional Knowledge`
  3. `Biodiversity & Access-Benefit Sharing`
  4. `Trademarks & Geographical Indications`
  5. `Copyrights & Digital Media`
  6. `National & International IP Policy`
- **Relationship Types:**
  - `(d:Document)-[:HAS_CHUNK]->(c:Chunk)` (Parent-to-child)
  - `(c1:Chunk)-[:NEXT]->(c2:Chunk)` (Sequential narrative flow)
  - `(d1:Document)-[:RELATED_TO {via: 'shared_category'}]->(d2:Document)` (Domain cluster edges)
  - `(d1:Document)-[:RELATED_TO {via: 'manual'}]->(d2:Document)` (Cross-act legal dependency edges)
