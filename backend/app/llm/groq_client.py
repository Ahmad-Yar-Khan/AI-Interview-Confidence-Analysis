"""
groq_client.py
--------------
Low-level "talk to Groq" wrapper — the part that would change if the LLM
provider were ever swapped. It was renamed from the old provider-specific
module name, which had been misleading since the Groq migration.
"""

import re
import json

from groq import AsyncGroq

from app.core.config import settings

# Async client: awaiting a Groq response yields the event loop instead of
# holding a thread-pool thread for the 2-10 s the LLM takes to answer.
_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
_MODEL_NAME = settings.GROQ_MODEL


async def chat(prompt: str, *, system: str | None = None, temperature: float = 0.7) -> str:
    """Send a single user-turn prompt (optionally with a system message) and return the raw text response."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = await _client.chat.completions.create(
        model=_MODEL_NAME,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def parse_json(text: str):
    """Strip markdown fences and parse JSON from the model response."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text.strip())
