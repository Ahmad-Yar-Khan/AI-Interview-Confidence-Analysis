"""
groq_client.py
--------------
Low-level "talk to Groq" wrapper — the part that would change if the LLM
provider were ever swapped. Renamed from gemini_client.py, which hasn't
actually talked to Gemini since the Groq migration; the old name was actively
misleading about what this module does.
"""

import re
import json

from groq import AsyncGroq

from app.core.config import settings

# Async client: awaiting a Groq response yields the event loop instead of
# holding a thread-pool thread for the 2-10 s the LLM takes to answer.
_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
_MODEL_NAME = settings.GROQ_MODEL


async def chat(prompt: str) -> str:
    """Send a single user-turn prompt and return the raw text response."""
    response = await _client.chat.completions.create(
        model=_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


def parse_json(text: str):
    """Strip markdown fences and parse JSON from the model response."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text.strip())
