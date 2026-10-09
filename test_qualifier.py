from app.database.database import SessionLocal
from app.database.models import Lead
from app.services.ai_qualifier import AIQualifier
from app.services.qualification_parser import parse_qualification


db = SessionLocal()

lead = db.query(Lead).first()

if not lead:
    print("No leads found.")
else:
    ai = AIQualifier()

    result = ai.qualify_lead(lead)

    print("\n--- AI RESPONSE ---")
    print(result)

    parsed = parse_qualification(result)

    print("\n--- PARSED RESULT ---")
    print(parsed)

db.close()