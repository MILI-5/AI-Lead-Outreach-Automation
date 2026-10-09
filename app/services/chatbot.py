
from google import genai

from app.core.config import settings
from app.services.conversation_service import (
    get_conversation_history,
    save_message,
)


class LeadChatbot:

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.google_api_key
        )

    def reply(self, db, lead):
        history = get_conversation_history(
            db=db,
            lead_id=lead.id
        )

        conversation = "\n".join(
            f"{item.role}: {item.message}"
            for item in history
        )

        prompt = f"""
You are a helpful and professional B2B sales assistant.

Lead:
Name: {lead.name}
Company: {lead.company_name}
Industry: {lead.industry}
Requirement: {lead.business_requirement}

Previous conversation:
{conversation or "No previous messages."}

Instructions:
- Respond naturally and professionally.
- Use the previous conversation for context.
- Do not repeat questions already answered.
- Ask only one relevant question at a time.
- Do not invent company information or make promises.
- If the lead is not interested, politely respect their decision.
- Keep your reply under 100 words.

Write only the reply to the lead.
"""

        response = self.client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        reply_text = (response.text or "").strip()

        if not reply_text:
            raise ValueError(
                "The AI returned an empty response."
            )

        save_message(
            db=db,
            lead_id=lead.id,
            role="assistant",
            message=reply_text
        )

        return reply_text