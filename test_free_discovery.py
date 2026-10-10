
from app.services.free_company_discovery import discover_companies

results = discover_companies(limit=5)

print(f"Found {len(results)} candidates\n")

for item in results:
    print("Company candidate:", item["company_name"])
    print("Website:", item["company_website"])
    print("Source:", item["source_url"])
    print("-" * 40)