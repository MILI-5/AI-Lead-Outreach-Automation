
from google import genai
from app.core.config import settings


class OutreachService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.google_api_key)

    def generate_message(self, lead):
        prompt = f"""
You are a professional B2B sales outreach assistant.

Write a personalized first outreach message for this prospect.

Name: {lead.name}
Designation: {lead.designation}
Company: {lead.company_name}
Industry: {lead.industry}
Business Requirement: {lead.business_requirement}

Rules:
- Keep it under 100 words.
- Sound natural, professional, and friendly.
- Explain briefly how AI automation may help with their requirement.
- Do not invent facts about the company.
- Do not claim we have met before.
- End with a simple question about whether they would be open to a short meeting.
- Return only the message.
"""
        response = self.client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        message = (response.text or "").strip()

        if not message:
            raise ValueError("AI generated an empty outreach message.")

        return message