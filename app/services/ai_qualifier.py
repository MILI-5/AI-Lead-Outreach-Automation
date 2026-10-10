
import json
import logging

from google import genai

from app.core.config import settings


logger = logging.getLogger(__name__)


class AIQualifier:
    """Qualify leads using available evidence and an explicit ICP."""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is missing from the application settings."
            )

        self.client = genai.Client(
            api_key=settings.google_api_key
        )

    def qualify_lead(self, lead):
        """
        Return a JSON string containing:
        category, buying_intent, pain_points, and summary.

        Missing information is treated as uncertainty, not proof
        that a prospect is unsuitable.
        """

        lead_data = {
            "name": getattr(lead, "name", None),
            "designation": getattr(lead, "designation", None),
            "company_name": getattr(lead, "company_name", None),
            "company_website": getattr(lead, "company_website", None),
            "industry": getattr(lead, "industry", None),
            "location": getattr(lead, "location", None),
            "business_requirement": getattr(
                lead, "business_requirement", None
            ),
            "company_size": getattr(lead, "company_size", None),
            "source": getattr(lead, "source", None),
            "current_icp_score": getattr(lead, "icp_score", None),
            "verification_status": (
                "Unverified"
                if getattr(lead, "source", None) == "hacker_news"
                else "Not provided"
            ),
        }

        prompt = f"""
You are a careful B2B sales lead qualification assistant.

Evaluate the lead using only the supplied information.
Do not invent facts or assume that missing details are known.

LEAD DATA:
{json.dumps(lead_data, ensure_ascii=False, indent=2, default=str)}

QUALIFICATION GUIDELINES:

1. Qualified:
   Strong evidence of a relevant business use case, a reasonable
   fit with the target customer profile, and a clear business need.

2. Potential:
   Some plausible business relevance, but important details such as
   the actual need, company fit, decision-maker, or buying intent
   remain unclear.

3. Not Qualified:
   Available evidence indicates poor business fit or a clearly
   irrelevant use case. Do not use this category only because
   contact information or company size is missing.

IMPORTANT RULES:
- A discovered company or website marked unverified must remain
  unverified in your assessment.
- A public discussion or newsletter does not prove that a business
  is an active company or a prospective buyer.
- Do not treat a placeholder name such as "Contact not identified"
  as an actual person's name.
- Do not infer buying intent from the industry alone.
- If there is insufficient evidence, prefer Potential over an
  unsupported positive or negative conclusion.
- Do not claim that a person was contacted or expressed interest
  unless the data explicitly supports that claim.
- Keep pain points concise. If none are established, say
  "Not established from available information".
- Explain uncertainty in the summary.

Return ONLY a valid JSON object with these exact keys:
{{
  "category": "Qualified",
  "buying_intent": "Low",
  "pain_points": "Not established from available information",
  "summary": "Short evidence-based explanation."
}}

Allowed category values: Qualified, Potential, Not Qualified.
Allowed buying_intent values: High, Medium, Low, Unknown.
Do not include Markdown fences or text outside the JSON object.
"""

        try:
            response = self.client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )

            response_text = (response.text or "").strip()

            if not response_text:
                raise ValueError(
                    "Gemini returned an empty qualification response."
                )

            # Validate the JSON here so malformed AI output is caught
            # before it is returned to the API route.
            cleaned = response_text

            if cleaned.startswith("```"):
                cleaned = cleaned.removeprefix("```json").removeprefix(
                    "```"
                )
                cleaned = cleaned.removesuffix("```").strip()

            result = json.loads(cleaned)

            allowed_categories = {
                "Qualified",
                "Potential",
                "Not Qualified",
            }
            allowed_intents = {
                "High",
                "Medium",
                "Low",
                "Unknown",
            }

            category = result.get("category")
            buying_intent = result.get("buying_intent")

            if category not in allowed_categories:
                raise ValueError(
                    "Gemini returned an invalid qualification category."
                )

            if buying_intent not in allowed_intents:
                result["buying_intent"] = "Unknown"

            for field in ("pain_points", "summary"):
                value = result.get(field)
                if not isinstance(value, str) or not value.strip():
                    result[field] = (
                        "Not established from available information"
                        if field == "pain_points"
                        else "Insufficient information to produce a summary."
                    )

            # Return normalized JSON text for compatibility with
            # the existing parse_qualification() function.
            return json.dumps(result, ensure_ascii=False)

        except Exception:
            logger.exception(
                "AI qualification failed for lead ID %s",
                getattr(lead, "id", "unknown"),
            )
            raise
