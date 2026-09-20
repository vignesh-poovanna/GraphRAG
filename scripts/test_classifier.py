from src.classifier.formulation_classifier import WIZARD_QUESTIONS, ARCHETYPES, classify_from_answers

print(f"Questions: {len(WIZARD_QUESTIONS)}, Archetypes: {len(ARCHETYPES)}")

# Test classical path
r = classify_from_answers({
    "Q1": "Yes - the exact name and method appear in the authoritative text",
    "Q2": "No modifications - it is exactly the classical formula",
    "Q3": "No - whole herb powders or unpurified extracts only",
    "Q4": "Health/wellness claims only",
    "Q5": "Oral internal use",
    "Q6": "Sourced entirely within India",
})
print(f"Classical test -> archetype {r['archetype']}: {r['posture']['name']}")
assert r["archetype"] == 1, f"Expected 1, got {r['archetype']}"

# Test cosmetic path
r2 = classify_from_answers({
    "Q1": "No - it is not listed in any classical text",
    "Q2": "Completely new formulation",
    "Q3": "No - whole herb powders",
    "Q4": "Cosmetic/beauty claims - moisturises skin",
    "Q5": "Topical external use",
    "Q6": "Sourced entirely within India",
})
print(f"Cosmetic test -> archetype {r2['archetype']}: {r2['posture']['name']}")
assert r2["archetype"] == 6, f"Expected 6, got {r2['archetype']}"

# Test phytopharmaceutical path
r3 = classify_from_answers({
    "Q1": "No",
    "Q2": "Significant modifications",
    "Q3": "Yes - extracts with defined marker compound specifications",
    "Q4": "Therapeutic/medicinal claims",
    "Q5": "Oral internal use",
    "Q6": "Mix",
})
print(f"Phyto test -> archetype {r3['archetype']}: {r3['posture']['name']}")
assert r3["archetype"] == 4, f"Expected 4, got {r3['archetype']}"

print("ALL TESTS PASSED")
