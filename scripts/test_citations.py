from src.utils.citation_index import load_citations_index, enrich_with_url

n = load_citations_index('./data/citations_index.txt')
print(f"Loaded {n} entries")

tests = [
    {"citation": "Patents Act 1970, Section 3(p)", "act_or_source_name": "Patents Act 1970"},
    {"citation": "Nagoya Protocol, Article 5",     "act_or_source_name": "Nagoya Protocol"},
    {"citation": "WIPO GRATK Treaty 2024",          "act_or_source_name": "WIPO GRATK Treaty 2024"},
    {"citation": "Biological Diversity Rules 2024", "act_or_source_name": "Biological Diversity Rules 2024"},
    {"citation": "PPV&FR Act 2001",                 "act_or_source_name": "PPV&FR Act 2001"},
]

ok = 0
for t in tests:
    result = enrich_with_url(t)
    url = result.get("url", "NOT FOUND")
    status = "OK" if url != "NOT FOUND" else "MISSING"
    print(f"[{status}] {t['act_or_source_name'][:40]} -> {url[:60]}")
    if status == "OK":
        ok += 1

print(f"\n{ok}/{len(tests)} matched")
