from google import genai

from app.core.config import settings


class AIQualifier:

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.google_api_key
        )

    def qualify_lead(self, lead):

        prompt = f"""
You are an AI sales qualification assistant.

Analyze this lead:

Name: {lead.name}
Designation: {lead.designation}
Company: {lead.company_name}
Industry: {lead.industry}
Location: {lead.location}
Business Requirement: {lead.business_requirement}
Company Size: {lead.company_size}

Give a simple qualification analysis.

Return exactly in this format:

CATEGORY: Qualified/Potential/Not Qualified
BUYING_INTENT: High/Medium/Low
PAIN_POINTS: short description
SUMMARY: short summary

Rules:
- Qualified = strong ICP match and clear business need
- Potential = some relevance but requirements are unclear
- Not Qualified = poor ICP match or no relevant business need
- Do not invent information.
"""

        response = self.client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        return response.text