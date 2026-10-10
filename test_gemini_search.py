
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is missing from your .env file")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=(
        "Use Google Search to find 3 real Indian AI startups. "
        "For each, provide its company name, official website, "
        "industry, and source URLs. Do not invent missing details."
    ),
    config=types.GenerateContentConfig(
        tools=[
            types.Tool(
                google_search=types.GoogleSearch()
            )
        ]
    ),
)

print("\n=== GEMINI SEARCH RESULTS ===\n")
print(response.text)

print("\n=== GROUNDING SOURCES ===\n")

if response.candidates:
    metadata = response.candidates[0].grounding_metadata

    if metadata and metadata.grounding_chunks:
        for chunk in metadata.grounding_chunks:
            if chunk.web:
                print(f"{chunk.web.title}: {chunk.web.uri}")
    else:
        print("No grounding sources returned.")