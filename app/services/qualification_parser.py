def parse_qualification(text: str) -> dict:

    result = {
        "category": "Potential",
        "buying_intent": "Medium",
        "pain_points": "",
        "summary": ""
    }

    for line in text.splitlines():

        line = line.strip()

        if line.startswith("CATEGORY:"):
            result["category"] = line.replace(
                "CATEGORY:", ""
            ).strip()

        elif line.startswith("BUYING_INTENT:"):
            result["buying_intent"] = line.replace(
                "BUYING_INTENT:", ""
            ).strip()

        elif line.startswith("PAIN_POINTS:"):
            result["pain_points"] = line.replace(
                "PAIN_POINTS:", ""
            ).strip()

        elif line.startswith("SUMMARY:"):
            result["summary"] = line.replace(
                "SUMMARY:", ""
            ).strip()

    return result