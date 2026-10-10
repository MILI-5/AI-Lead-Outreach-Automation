
import json


def parse_qualification(text: str) -> dict:
    defaults = {
        "category": "Potential",
        "buying_intent": "Unknown",
        "pain_points": "Not established from available information",
        "summary": "Insufficient information to produce a summary.",
    }

    if not text or not text.strip():
        return defaults

    cleaned = text.strip()

    # Support JSON wrapped in Markdown code fences.
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)

        if not isinstance(data, dict):
            return defaults

        for field in defaults:
            value = data.get(field)
            if isinstance(value, str) and value.strip():
                defaults[field] = value.strip()

        if defaults["category"] not in {
            "Qualified", "Potential", "Not Qualified"
        }:
            defaults["category"] = "Potential"

        if defaults["buying_intent"] not in {
            "High", "Medium", "Low", "Unknown"
        }:
            defaults["buying_intent"] = "Unknown"

        return defaults

    except (json.JSONDecodeError, TypeError):
        # Backward compatibility with the previous line-based format.
        for line in text.splitlines():
            line = line.strip()

            for field, prefix in {
                "category": "CATEGORY:",
                "buying_intent": "BUYING_INTENT:",
                "pain_points": "PAIN_POINTS:",
                "summary": "SUMMARY:",
            }.items():
                if line.startswith(prefix):
                    value = line[len(prefix):].strip()
                    if value:
                        defaults[field] = value

        return defaults
