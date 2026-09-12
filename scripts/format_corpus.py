#!/usr/bin/env python3
"""
Format and enrich all Markdown files in your_docs_here with structured YAML frontmatter,
explicit legal category taxonomies, and cross-document relational edges for the Knowledge Graph.
Processes documents from smallest to largest.
"""

import os
import re
from pathlib import Path

METADATA_REGISTRY = {
    "Press Release Page _ Press Information Bureau.md": {
        "title": "PIB Press Release: Traditional Knowledge and AYUSH IPR Safeguards",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "PIB Ayush Release",
        "year": "2023",
        "jurisdiction": "India",
        "document_type": "policy",
        "related": [
            "Press Release Page _ Press Information Bureau Pharmacopoeia Commission for Indian Medicine.md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md",
            "ncsm_aayush.md"
        ]
    },
    "Press Release Page _ Press Information Bureau Pharmacopoeia Commission for Indian Medicine.md": {
        "title": "PCIM&H Press Release: Pharmacopoeia Commission for Indian Medicine & Homoeopathy",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "PCIM&H Press Release",
        "year": "2023",
        "jurisdiction": "India",
        "document_type": "policy",
        "related": [
            "Ayurvedic Pharmacopoeia of India All Volume .md",
            "ncsm_aayush.md",
            "itra_act.md"
        ]
    },
    "The Patents (Amendment) Act - 26 March 1999.md": {
        "title": "The Patents (Amendment) Act, 1999 (Mailbox & EMR Provisions)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "Patents Amendment Act 1999",
        "year": "1999",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act, 2002 (38 of 2002).md",
            "The Patents (Amendment) Act 2005.md",
            "wto-27-trips.md"
        ]
    },
    "wipo.md": {
        "title": "WIPO Overview: Intellectual Property and Genetic Resources, Traditional Knowledge and Folklore",
        "category": "National & International IP Policy",
        "act_or_source_name": "WIPO TK & Genetic Resources Framework",
        "year": "2020",
        "jurisdiction": "International",
        "document_type": "treaty",
        "related": [
            "wto-27-trips.md",
            "nagoya-protocol-en.md",
            "cbd-en.md",
            "2016-_National_IPR_Policy-2016__English_and_Hindi.md"
        ]
    },
    "Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md": {
        "title": "Guidelines for Processing of Patent Applications Relating to Traditional Knowledge and Biological Material (2012)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "IPO TK & Bio-Material Patent Guidelines 2012",
        "year": "2012",
        "jurisdiction": "India",
        "document_type": "guidelines",
        "related": [
            "patents_act_1970.md",
            "Biodiversity_Act_2002.md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md",
            "Guidelines for Examination of Biotechnology Applications for Patent - 2013.md"
        ]
    },
    "The Geographical Indications of Goods (Registration and Protection) (Amendment) Rules, 2025.md": {
        "title": "The Geographical Indications of Goods (Registration and Protection) (Amendment) Rules, 2025",
        "category": "Trademarks & Geographical Indications",
        "act_or_source_name": "GI Amendment Rules 2025",
        "year": "2025",
        "jurisdiction": "India",
        "document_type": "rules",
        "related": [
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md",
            "trademarks act 1999.md",
            "2016-_National_IPR_Policy-2016__English_and_Hindi.md"
        ]
    },
    "itra_act.md": {
        "title": "Institute of Teaching and Research in Ayurveda (ITRA) Act, 2020",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "ITRA Act 2020",
        "year": "2020",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "ncsm_aayush.md",
            "Ayurvedic Pharmacopoeia of India All Volume .md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md"
        ]
    },
    "Guidelines for Examination of Ayush Related Inventions-2025.md": {
        "title": "Guidelines for Examination of Ayush-Related Inventions (CGPDTM 2025)",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "CGPDTM Ayush Guidelines 2025",
        "year": "2025",
        "jurisdiction": "India",
        "document_type": "guidelines",
        "related": [
            "patents_act_1970.md",
            "Biodiversity_Act_2002.md",
            "Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md",
            "Ayurvedic Pharmacopoeia of India All Volume .md"
        ]
    },
    "Copyright-Rules Amendment 2021.md": {
        "title": "Copyright (Amendment) Rules, 2021",
        "category": "Copyrights & Digital Media",
        "act_or_source_name": "Copyright Amendment Rules 2021",
        "year": "2021",
        "jurisdiction": "India",
        "document_type": "rules",
        "related": [
            "copyright rules 2013.md",
            "cpoyrights act.md"
        ]
    },
    "tribunal_reforms_act.md": {
        "title": "The Tribunals Reforms Act, 2021 (Abolition of IPAB & Transfer to High Courts)",
        "category": "National & International IP Policy",
        "act_or_source_name": "Tribunals Reforms Act 2021",
        "year": "2021",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "trademarks act 1999.md",
            "cpoyrights act.md",
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md"
        ]
    },
    "Biodiversity_Act_2002.md": {
        "title": "The Biological Diversity Act, 2002 (Regulation of Bio-Resources & Prior NBA Approval)",
        "category": "Biodiversity & Access-Benefit Sharing",
        "act_or_source_name": "Biological Diversity Act 2002",
        "year": "2002",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "nagoya-protocol-en.md",
            "cbd-en.md",
            "Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md",
            "patents_act_1970.md"
        ]
    },
    "nagoya-protocol-en.md": {
        "title": "Nagoya Protocol on Access to Genetic Resources and the Fair and Equitable Sharing of Benefits (ABS)",
        "category": "Biodiversity & Access-Benefit Sharing",
        "act_or_source_name": "Nagoya Protocol",
        "year": "2010",
        "jurisdiction": "International",
        "document_type": "treaty",
        "related": [
            "cbd-en.md",
            "Biodiversity_Act_2002.md",
            "wipo.md"
        ]
    },
    "Guidelines for Examination of Biotechnology Applications for Patent - 2013.md": {
        "title": "Guidelines for Examination of Biotechnology Applications for Patent (2013)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "IPO Biotech Patent Guidelines 2013",
        "year": "2013",
        "jurisdiction": "India",
        "document_type": "guidelines",
        "related": [
            "patents_act_1970.md",
            "Biodiversity_Act_2002.md",
            "Guidelines for examination of patent applications in the field of Pharmaceuticals - 2014.md"
        ]
    },
    "cbd-en.md": {
        "title": "Convention on Biological Diversity (CBD, Rio 1992)",
        "category": "Biodiversity & Access-Benefit Sharing",
        "act_or_source_name": "Convention on Biological Diversity",
        "year": "1992",
        "jurisdiction": "International",
        "document_type": "treaty",
        "related": [
            "nagoya-protocol-en.md",
            "Biodiversity_Act_2002.md",
            "wipo.md"
        ]
    },
    "The Patents (Amendment) Act 2005.md": {
        "title": "The Patents (Amendment) Act, 2005 (Product Patents & Section 3(d) / 3(p))",
        "category": "Patent Law & Examination",
        "act_or_source_name": "Patents Amendment Act 2005",
        "year": "2005",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act, 2002 (38 of 2002).md",
            "Guidelines for examination of patent applications in the field of Pharmaceuticals - 2014.md",
            "wto-27-trips.md"
        ]
    },
    "The Patents (Amendment) Act - 25 June 200.md": {
        "title": "The Patents (Amendment) Act, 2002 (Commencement & 20-Year Term Harmonization)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "Patents Amendment Act 2002 Rules",
        "year": "2003",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act, 2002 (38 of 2002).md",
            "The Patents (Amendment) Act 2005.md"
        ]
    },
    "The Patents (Amendment) Act, 2002 (38 of 2002).md": {
        "title": "The Patents (Amendment) Act, 2002 (No. 38 of 2002 - Section 3(p) & TK Exclusion)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "Patents Amendment Act 2002",
        "year": "2002",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act 2005.md",
            "Biodiversity_Act_2002.md",
            "Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md"
        ]
    },
    "wto-27-trips.md": {
        "title": "WTO TRIPS Agreement: Article 27 (Patentable Subject Matter & Exclusions)",
        "category": "National & International IP Policy",
        "act_or_source_name": "TRIPS Article 27",
        "year": "1994",
        "jurisdiction": "International",
        "document_type": "treaty",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act 2005.md",
            "wipo.md",
            "cbd-en.md"
        ]
    },
    "ncsm_aayush.md": {
        "title": "National Commission for Indian System of Medicine (NCISM) Act, 2020",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "NCISM Act 2020",
        "year": "2020",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "itra_act.md",
            "Ayurvedic Pharmacopoeia of India All Volume .md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md"
        ]
    },
    "2016-_National_IPR_Policy-2016__English_and_Hindi.md": {
        "title": "National Intellectual Property Rights (IPR) Policy 2016 (Creative India; Innovative India)",
        "category": "National & International IP Policy",
        "act_or_source_name": "National IPR Policy 2016",
        "year": "2016",
        "jurisdiction": "India",
        "document_type": "policy",
        "related": [
            "patents_act_1970.md",
            "Biodiversity_Act_2002.md",
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md",
            "trademarks act 1999.md"
        ]
    },
    "The_Geographical_Indications_of_Goods_Registration_and_Protec.md": {
        "title": "The Geographical Indications of Goods (Registration and Protection) Act, 1999",
        "category": "Trademarks & Geographical Indications",
        "act_or_source_name": "GI Act 1999",
        "year": "1999",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "The Geographical Indications of Goods (Registration and Protection) (Amendment) Rules, 2025.md",
            "trademarks act 1999.md",
            "2016-_National_IPR_Policy-2016__English_and_Hindi.md"
        ]
    },
    "Guidelines for examination of patent applications in the field of Pharmaceuticals - 2014.md": {
        "title": "Guidelines for Examination of Patent Applications in the Field of Pharmaceuticals (2014)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "IPO Pharma Patent Guidelines 2014",
        "year": "2014",
        "jurisdiction": "India",
        "document_type": "guidelines",
        "related": [
            "patents_act_1970.md",
            "The Patents (Amendment) Act 2005.md",
            "Guidelines for Examination of Biotechnology Applications for Patent - 2013.md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md"
        ]
    },
    "THE JAN VISHWAS (AMENDMENT OF PROVISIONS) ACT, 2023.md": {
        "title": "The Jan Vishwas (Amendment of Provisions) Act, 2023 (Decriminalization of Minor IP Offenses)",
        "category": "National & International IP Policy",
        "act_or_source_name": "Jan Vishwas Act 2023",
        "year": "2023",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "patents_act_1970.md",
            "trademarks act 1999.md",
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md",
            "cpoyrights act.md"
        ]
    },
    "copyright rules 2013.md": {
        "title": "The Copyright Rules, 2013 (Copyright Societies, Royalty Determination & Registrations)",
        "category": "Copyrights & Digital Media",
        "act_or_source_name": "Copyright Rules 2013",
        "year": "2013",
        "jurisdiction": "India",
        "document_type": "rules",
        "related": [
            "cpoyrights act.md",
            "Copyright-Rules Amendment 2021.md"
        ]
    },
    "Rules & Regulations & Bye Laws _ Council of Scientific & Industrial Research.md": {
        "title": "CSIR Rules, Regulations & Bye-Laws (TKDL Administration & R&D Framework)",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "CSIR Rules and Bye-Laws",
        "year": "2019",
        "jurisdiction": "India",
        "document_type": "rules",
        "related": [
            "Guidelines for Processing of Patent Applications relating to Traditional Knowledge and Biological Material - 2012.md",
            "Ayurvedic Pharmacopoeia of India All Volume .md",
            "ncsm_aayush.md"
        ]
    },
    "cpoyrights act.md": {
        "title": "The Copyright Act, 1957 (Protection of Original Literary, Artistic & Traditional Works)",
        "category": "Copyrights & Digital Media",
        "act_or_source_name": "Copyright Act 1957",
        "year": "1957",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "copyright rules 2013.md",
            "Copyright-Rules Amendment 2021.md",
            "THE JAN VISHWAS (AMENDMENT OF PROVISIONS) ACT, 2023.md"
        ]
    },
    "trademarks act 1999.md": {
        "title": "The Trade Marks Act, 1999 (Registration and Protection of Trademarks & Collective Marks)",
        "category": "Trademarks & Geographical Indications",
        "act_or_source_name": "Trade Marks Act 1999",
        "year": "1999",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "trademarks rules.md",
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md",
            "THE JAN VISHWAS (AMENDMENT OF PROVISIONS) ACT, 2023.md"
        ]
    },
    "patents_act_1970.md": {
        "title": "The Patents Act, 1970 (Consolidated with Section 3(d), 3(p) & Compulsory Licensing)",
        "category": "Patent Law & Examination",
        "act_or_source_name": "The Patents Act 1970",
        "year": "1970",
        "jurisdiction": "India",
        "document_type": "statute",
        "related": [
            "The Patents (Amendment) Act 2005.md",
            "The Patents (Amendment) Act, 2002 (38 of 2002).md",
            "Guidelines for Examination of Biotechnology Applications for Patent - 2013.md",
            "Guidelines for examination of patent applications in the field of Pharmaceuticals - 2014.md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md",
            "Biodiversity_Act_2002.md"
        ]
    },
    "trademarks rules.md": {
        "title": "The Trade Marks Rules, 2017 (Procedures, Expedited Examination & Renewal)",
        "category": "Trademarks & Geographical Indications",
        "act_or_source_name": "Trade Marks Rules 2017",
        "year": "2017",
        "jurisdiction": "India",
        "document_type": "rules",
        "related": [
            "trademarks act 1999.md",
            "The_Geographical_Indications_of_Goods_Registration_and_Protec.md"
        ]
    },
    "Ayurvedic Pharmacopoeia of India All Volume .md": {
        "title": "The Ayurvedic Pharmacopoeia of India (API - Complete Formulary & Monographs)",
        "category": "Ayurveda & Traditional Knowledge",
        "act_or_source_name": "Ayurvedic Pharmacopoeia of India",
        "year": "2016",
        "jurisdiction": "India",
        "document_type": "pharmacopoeia",
        "related": [
            "ncsm_aayush.md",
            "itra_act.md",
            "Guidelines for Examination of Ayush Related Inventions-2025.md",
            "Press Release Page _ Press Information Bureau Pharmacopoeia Commission for Indian Medicine.md"
        ]
    }
}

def clean_and_normalize_markdown(content: str) -> str:
    """Strip existing frontmatter if present and normalize structural headings."""
    # Strip existing frontmatter
    fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
    if fm_match:
        content = content[fm_match.end():]

    # Normalize noisy chapter / section headers
    content = re.sub(r'#{1,6}\s*\*{0,2}CHAPTER[\s\-_]+([IVXLCDM\d]+)\*{0,2}', r'## Chapter \1', content, flags=re.IGNORECASE)
    content = re.sub(r'#{1,6}\s*\*{0,2}PART[\s\-_]+([IVXLCDM\d]+)\*{0,2}', r'## Part \1', content, flags=re.IGNORECASE)
    content = re.sub(r'#{1,6}\s*\*{0,2}SCHEDULE[\s\-_]+([IVXLCDM\d]+)\*{0,2}', r'## Schedule \1', content, flags=re.IGNORECASE)
    
    # Normalize excessive consecutive newlines
    content = re.sub(r'\n{4,}', '\n\n', content)
    return content.strip()

def build_frontmatter(meta: dict) -> str:
    """Build clean YAML frontmatter."""
    lines = ["---"]
    lines.append(f'title: "{meta["title"]}"')
    lines.append(f'category: "{meta["category"]}"')
    lines.append(f'act_or_source_name: "{meta["act_or_source_name"]}"')
    lines.append(f'year: "{meta["year"]}"')
    lines.append(f'jurisdiction: "{meta["jurisdiction"]}"')
    lines.append(f'document_type: "{meta["document_type"]}"')
    
    related = meta.get("related", [])
    if related:
        lines.append("related:")
        for r in related:
            lines.append(f'  - "{r}"')
    else:
        lines.append("related: []")
    
    lines.append("---\n\n")
    return "\n".join(lines)

def main():
    docs_dir = Path("your_docs_here")
    if not docs_dir.exists():
        print(f"Directory {docs_dir} not found!")
        return 1

    files = list(docs_dir.glob("*.md"))
    # Sort files smallest to largest
    files.sort(key=lambda p: p.stat().st_size)

    print(f"Found {len(files)} markdown files. Formatting from smallest to largest...")

    for i, filepath in enumerate(files, 1):
        filename = filepath.name
        meta = METADATA_REGISTRY.get(filename)
        if not meta:
            # Fallback if unmapped
            meta = {
                "title": filename.replace(".md", "").replace("_", " ").title(),
                "category": "National & International IP Policy",
                "act_or_source_name": filename.replace(".md", ""),
                "year": "2020",
                "jurisdiction": "India",
                "document_type": "statute",
                "related": []
            }
        
        raw_text = filepath.read_text(encoding="utf-8", errors="replace")
        cleaned_body = clean_and_normalize_markdown(raw_text)
        frontmatter = build_frontmatter(meta)
        
        formatted_content = frontmatter + cleaned_body
        filepath.write_text(formatted_content, encoding="utf-8")
        
        size_kb = len(formatted_content.encode("utf-8")) / 1024
        print(f"[{i:02d}/{len(files)}] Formatted: {filename} ({size_kb:.1f} KB) -> Category: {meta['category']}")

    print("\nAll 30 markdown files formatted successfully!")
    return 0

if __name__ == "__main__":
    exit(main())
