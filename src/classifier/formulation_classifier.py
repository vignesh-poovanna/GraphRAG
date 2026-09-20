"""
formulation_classifier.py — Phase B

Multi-turn formulation wizard: 6 questions, tap-to-choose options,
classify into one of 6 regulatory archetypes, return full IP/ABS posture.

Two server endpoints use this:
  GET  /classify/questions  -> returns WIZARD_QUESTIONS (all 6 at once, for frontend slides)
  POST /classify            -> accepts all answers, returns archetype + posture
"""

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

WIZARD_QUESTIONS = [
    {
        "key": "Q1",
        "text": (
            "Is your formulation's name and preparation method listed verbatim "
            "in a First-Schedule classical text — such as Charaka Samhita, Sushruta "
            "Samhita, Ashtanga Hridayam, Ayurvedic Formulary of India, or the "
            "Siddha Formulary of India?"
        ),
        "options": [
            "Yes — the exact name and method appear in the authoritative text",
            "No — it is not listed in any classical text",
            "Partially — the formula is similar but not identical",
            "I am not sure / need to verify",
        ],
        "has_custom": True,
    },
    {
        "key": "Q2",
        "text": (
            "Have you made any modification to the classical formula — "
            "such as changing an ingredient, its proportion, the solvent, "
            "or the dosage form (tablet, capsule, syrup)?"
        ),
        "options": [
            "No modifications — it is exactly the classical formula",
            "Minor modifications — added excipients or changed dosage form only",
            "Significant modifications — different ingredient ratios or new ingredients",
            "Completely new formulation inspired by classical texts",
        ],
        "has_custom": True,
    },
    {
        "key": "Q3",
        "text": (
            "Does your product contain standardized botanical extracts "
            "with defined pharmacognostic markers? "
            "(e.g., 'curcuminoids not less than 95%', 'withanolides ≥ 5%')"
        ),
        "options": [
            "Yes — extracts with defined marker compound specifications",
            "No — whole herb powders or unpurified extracts only",
            "Mix — some standardized extracts, some whole herbs",
            "Not applicable — no botanical extracts in the formulation",
        ],
        "has_custom": True,
    },
    {
        "key": "Q4",
        "text": (
            "What claims does your product make on the label or in advertising?"
        ),
        "options": [
            "Therapeutic/medicinal claims — treats, cures, or prevents a named disease",
            "Health/wellness claims only — supports immunity, promotes digestion, etc.",
            "No claims — plain product description only",
            "Cosmetic/beauty claims — moisturises, conditions, brightens skin or hair",
        ],
        "has_custom": True,
    },
    {
        "key": "Q5",
        "text": (
            "How is your product primarily intended to be consumed or applied?"
        ),
        "options": [
            "Oral internal use — tablet, capsule, syrup, powder, or decoction",
            "Topical external use — oil, cream, lotion, balm, or ubtan",
            "Oral food/supplement — health drink, food ingredient, or functional food",
            "Multiple routes — both internal and external",
        ],
        "has_custom": True,
    },
    {
        "key": "Q6",
        "text": (
            "What is the origin of the biological resources (plants, minerals, "
            "microbial strains) in your formulation?"
        ),
        "options": [
            "Sourced entirely within India from domestic suppliers",
            "Sourced from abroad — imported plant extracts or raw materials",
            "Mix — some Indian, some imported",
            "Cultivated in-house or captive cultivation",
        ],
        "has_custom": True,
    },
]


# ---------------------------------------------------------------------------
# Archetypes — full IP/ABS posture for each
# ---------------------------------------------------------------------------

ARCHETYPES = {
    1: {
        "name": "Classical / Generic Ayurvedic Medicine",
        "patent_eligibility": (
            "Not patentable. Section 3(p) of the Patents Act 1970 bars patents on "
            "traditional knowledge, and classical Ayurvedic formulations fall squarely "
            "within this exclusion. Any third party attempting to patent this formula "
            "can be opposed using TKDL prior-art records."
        ),
        "tkdl_defense": (
            "TKDL records serve as globally accessible prior art. Indian Patent Examiners "
            "and international patent offices (USPTO, EPO, JPO) can access TKDL to reject "
            "any patent claim based on this formulation."
        ),
        "abs_duty": (
            "ABS approval (NBA Form I or Form II) is required only when a foreign national "
            "or foreign-funded entity accesses the biological resource. Domestic Vaidyas, "
            "AYUSH practitioners, and codified-knowledge users are exempt under the "
            "Biological Diversity (Amendment) Act, 2023."
        ),
        "trademark": (
            "Trademark registration is strongly recommended for the brand name, logo, and "
            "packaging under the Trade Marks Act 1999. A Geographical Indication (GI) tag "
            "is available if the product has a defined regional origin."
        ),
        "regulatory_path": (
            "Register as an Ayurvedic Medicine under the Drugs and Cosmetics Act 1940, "
            "Chapter IV-A. Obtain a manufacturing licence from the State Licensing Authority "
            "(SLA). Must comply with GMP standards under Schedule T of the D&C Rules 1945."
        ),
        "recommended_actions": [
            "File trademark for brand name and logo at IP India (Form TM-A)",
            "Obtain State Licensing Authority manufacturing licence",
            "Document the classical text reference and First-Schedule lineage in records",
            "Consider GI tag if the product has a defined regional identity",
            "Conduct TKDL search to identify existing prior-art entries for your formulation",
        ],
    },
    2: {
        "name": "Patent & Proprietary Medicine (PPM)",
        "patent_eligibility": (
            "Conditionally patentable. A process patent is available if the manufacturing "
            "method is novel and involves an inventive step. A composition patent requires "
            "demonstrating a non-obvious synergistic effect between ingredients — Section "
            "3(e) bars patents on mere admixtures without proven synergy. Section 3(d) bars "
            "known substances without significantly enhanced efficacy."
        ),
        "tkdl_defense": (
            "TKDL prior-art search is mandatory during patent examination. The examiner "
            "will cite TKDL records against any ingredient or method with a classical basis. "
            "Ensure your novel element is clearly differentiated from classical knowledge."
        ),
        "abs_duty": (
            "NBA Form III approval is mandatory before filing a patent in India or abroad "
            "(Section 6, Biological Diversity Act 2002, as amended 2023). Obtaining Form III "
            "after filing is not permitted."
        ),
        "trademark": (
            "Eligible for trademark registration. The brand name and proprietary formulation "
            "trade name should both be registered under the Trade Marks Act 1999."
        ),
        "regulatory_path": (
            "Licence as a Proprietary/Patent Medicine under D&C Act Rule 158-B. Safety and "
            "efficacy data may be required. GMP compliance under Schedule T is mandatory."
        ),
        "recommended_actions": [
            "Conduct TKDL prior-art search before drafting patent claims",
            "Obtain NBA Form III approval before filing the patent application",
            "File patent application (Form 1 + Form 2 complete specification) at IP India",
            "Register trademark for brand name and trade name",
            "Apply for PPM manufacturing licence from State Licensing Authority",
        ],
    },
    3: {
        "name": "New / Non-Classical Ayurvedic Drug",
        "patent_eligibility": (
            "Strong patent potential. Novel extraction methods, new therapeutic indications, "
            "new dosage forms, and new drug delivery systems are patentable if inventive step "
            "and industrial applicability are established. Section 3(d) requires demonstrating "
            "significantly enhanced therapeutic efficacy over the known plant or herb."
        ),
        "tkdl_defense": (
            "TKDL prior art is checked by examiners against every ingredient. Clearly "
            "distinguish your innovation from traditional uses documented in TKDL. Novel "
            "extraction process and standardized marker profile are the strongest patentable "
            "elements."
        ),
        "abs_duty": (
            "NBA Form III mandatory before any patent filing. If biological resources are "
            "sourced from abroad, Nagoya Protocol compliance (Mutually Agreed Terms and "
            "Prior Informed Consent from the source country) is additionally required."
        ),
        "trademark": "Eligible for trademark registration.",
        "regulatory_path": (
            "Regulated as a New Drug under D&C Act Rule 158-B and the New Drugs and Clinical "
            "Trials Rules 2019. Clinical safety and efficacy evidence is required before "
            "grant of manufacturing and marketing approval."
        ),
        "recommended_actions": [
            "Generate pre-clinical and clinical safety/efficacy data per Rule 158-B",
            "Obtain NBA Form III before filing patent",
            "File complete specification patent covering composition, process, and use",
            "Register trademark",
            "Apply for New Drug manufacturing approval",
            "Consider phytopharmaceutical route (Archetype 4) if extract can be standardised",
        ],
    },
    4: {
        "name": "Phytopharmaceutical",
        "patent_eligibility": (
            "Strong. Standardized botanical extracts with defined pharmacognostic markers "
            "and demonstrated pharmacological activity are patentable. Section 3(d) applies: "
            "must demonstrate significantly enhanced efficacy over the known plant's "
            "traditional therapeutic use. Extraction process, standardisation method, "
            "and marker-compound specification are the core patentable elements."
        ),
        "tkdl_defense": (
            "TKDL prior art covers traditional uses of the source plant. The novel elements "
            "are the standardised extract, the defined pharmacognostic markers, and the "
            "clinical evidence of enhanced efficacy — these are your freedom-to-operate zone."
        ),
        "abs_duty": (
            "NBA Form III mandatory before filing. For biological resources sourced from "
            "outside India, Nagoya Protocol compliance (MAT/PIC) is required at the "
            "country of origin."
        ),
        "trademark": "Eligible for trademark registration.",
        "regulatory_path": (
            "Regulated under the Drugs and Cosmetics (Amendment) Rules, 2015 for "
            "Phytopharmaceuticals. Requires documented pharmacognostic standards, marker "
            "compound specification, and Phase I/II/III clinical trial data."
        ),
        "recommended_actions": [
            "Define and document pharmacognostic markers with analytical standards",
            "Obtain NBA Form III before filing",
            "File patent for extraction process and standardised composition",
            "Register trademark",
            "Apply for phytopharmaceutical manufacturing and marketing approval",
        ],
    },
    5: {
        "name": "Ayurveda-Aahar / Nutraceutical",
        "patent_eligibility": (
            "Limited. The formulation itself cannot be patented if it uses traditional "
            "knowledge ingredients. Novel delivery systems — encapsulation, sustained-release, "
            "novel combinations in non-obvious ratios with demonstrated enhanced bioavailability "
            "— may qualify for process patents."
        ),
        "tkdl_defense": (
            "Section 3(p) bars patents on traditional knowledge-based formulations. TKDL "
            "protects against any third-party attempt to patent the same formulation."
        ),
        "abs_duty": (
            "ABS duty arises only if specific biological resources (not widely traded "
            "commodities) are accessed. For commonly traded herbal ingredients, NBA approval "
            "may not be required — confirm with NBA on a case-by-case basis."
        ),
        "trademark": (
            "Highly recommended. Brand name, trade dress, and label design are all "
            "registrable. Packaging design is additionally registrable under the Designs Act 2000."
        ),
        "regulatory_path": (
            "Regulated by FSSAI under the Food Safety and Standards (Ayurveda Aahar) "
            "Regulations, 2022. Requires FSSAI Central/State licence via the FoSCoS portal. "
            "No medicinal claims permitted on label or in advertising."
        ),
        "recommended_actions": [
            "Obtain FSSAI licence via the FoSCoS portal (foscos.fssai.gov.in)",
            "Review all label claims against FSSAI Ayurveda Aahar permitted claims schedule",
            "Verify advertising compliance with Drugs and Magic Remedies Act 1954",
            "Register trademark (brand name + logo)",
            "Register packaging/bottle design under Designs Act 2000",
        ],
    },
    6: {
        "name": "Ayurvedic Cosmetic",
        "patent_eligibility": (
            "Limited for the formulation itself due to Section 3(p). Novel fragrance "
            "compositions, novel applicator mechanisms, novel preservation techniques, "
            "and novel delivery forms (nanoemulsion, microencapsulation) for external "
            "use may qualify for process or device patents if inventive step is established."
        ),
        "tkdl_defense": (
            "TKDL covers traditional cosmetic formulations (ubtan, hair oils, kajal). "
            "Third-party patents on classical cosmetic knowledge can be challenged using "
            "TKDL records."
        ),
        "abs_duty": (
            "ABS duty arises if specific plant extracts that are not widely traded are sourced. "
            "For widely traded commodities such as turmeric, neem, or amla, exemptions "
            "typically apply."
        ),
        "trademark": (
            "Trademark registration is the primary IP protection strategy for cosmetics. "
            "Register brand name, logo, and trade dress. Register packaging design under "
            "the Designs Act 2000."
        ),
        "regulatory_path": (
            "Regulated under the Drugs and Cosmetics Act 1940, Part XIII and Schedule S "
            "(Standards for Cosmetics). Manufacturing licence required from State Licensing "
            "Authority. AYUSH Premium Mark certification is available to signal authenticity."
        ),
        "recommended_actions": [
            "Obtain D&C Act cosmetic manufacturing licence from State Licensing Authority",
            "Register trademark (name + logo + trade dress) at IP India",
            "Register packaging and applicator design under Designs Act 2000",
            "Verify advertising claims against DMR Act 1954 and D&C Act Rule 144",
            "Apply for AYUSH Premium Mark certification",
        ],
    },
}


# ---------------------------------------------------------------------------
# Decision tree
# ---------------------------------------------------------------------------

def classify_from_answers(answers: dict) -> dict:
    """
    Apply decision tree to the 6 collected answers.
    answers = {"Q1": "<chosen option or custom text>", "Q2": ..., ..., "Q6": ...}
    Returns {"archetype": int, "posture": dict}
    """
    def _ans(key: str) -> str:
        return answers.get(key, "").lower()

    q1 = _ans("Q1")
    q2 = _ans("Q2")
    q3 = _ans("Q3")
    q4 = _ans("Q4")
    q5 = _ans("Q5")

    # --- Phytopharmaceutical: standardised extracts with markers ---
    if any(k in q3 for k in ("yes", "standardized", "marker", "extracts with defined")):
        archetype_id = 4

    # --- Cosmetic: external/topical/beauty claims ---
    elif any(k in q4 for k in ("cosmetic", "beauty", "moistur", "brightens", "conditions")) \
         or any(k in q5 for k in ("topical", "external", "oil, cream", "balm", "ubtan")):
        archetype_id = 6

    # --- Nutraceutical/Aahar: food/supplement use ---
    elif any(k in q5 for k in ("food", "supplement", "health drink", "functional food")):
        archetype_id = 5

    # --- Classical unchanged ---
    elif any(k in q1 for k in ("yes", "exact", "verbatim", "authoritative")) \
         and any(k in q2 for k in ("no modification", "exactly the classical", "no modif")):
        archetype_id = 1

    # --- Medicinal claims → PPM ---
    elif any(k in q4 for k in ("therapeutic", "medicinal", "treats", "cures", "prevents", "disease")):
        archetype_id = 2

    # --- Explicitly not classical or significantly modified → New Drug ---
    elif any(k in q1 for k in ("no —", "not listed", "no,")) \
         or any(k in q2 for k in ("significant", "completely new", "new formulation")):
        archetype_id = 3

    # --- Fallback: classical with minor mods → PPM ---
    else:
        archetype_id = 2

    return {"archetype": archetype_id, "posture": ARCHETYPES[archetype_id]}


# ---------------------------------------------------------------------------
# Context formatter (used by orchestrator to enrich the synthesis prompt)
# ---------------------------------------------------------------------------

_Q_LABELS = {
    "Q1": "Classical text reference",
    "Q2": "Modifications to formula",
    "Q3": "Standardised extracts / pharmacognostic markers",
    "Q4": "Product claims (label / advertising)",
    "Q5": "Route of use",
    "Q6": "Origin of biological resources",
}


def format_wizard_context(answers: dict) -> str:
    """
    Convert wizard answers into a concise product-profile paragraph
    to prepend to the LLM synthesis prompt as additional context.

    Example output:
      PRODUCT PROFILE (user-provided):
      - Classical text reference: Yes — exact method in Ayurvedic Formulary of India
      - Modifications to formula: No modifications
      ...
    """
    if not answers:
        return ""
    lines = ["PRODUCT PROFILE (provided by user before asking this question):"]
    for key, label in _Q_LABELS.items():
        val = answers.get(key, "").strip()
        if val:
            lines.append(f"  - {label}: {val}")
    return "\n".join(lines)
