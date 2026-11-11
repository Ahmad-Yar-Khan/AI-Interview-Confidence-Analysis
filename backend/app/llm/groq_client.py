"""
groq_client.py
--------------
Low-level "talk to Groq" wrapper — the part that would change if the LLM
provider were ever swapped. It was renamed from the old provider-specific
module name, which had been misleading since the Groq migration.
"""

import asyncio
import logging
import re
import json

from groq import AsyncGroq, RateLimitError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Async client: awaiting a Groq response yields the event loop instead of
# holding a thread-pool thread for the 2-10 s the LLM takes to answer.
_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
_MODEL_NAME = settings.GROQ_MODEL

_MAX_RETRIES = 4


def _retry_delay(error: Exception, attempt: int) -> float:
    """Use Groq's suggested wait time when present, else exponential backoff."""
    match = re.search(r"try again in ([\d.]+)s", str(error))
    if match:
        return float(match.group(1)) + 1.0
    return min(30.0, 5.0 * (2 ** attempt))


def _supports_reasoning_effort(model: str) -> bool:
    # Only the gpt-oss models accept low/medium/high; other Groq models reject
    # the parameter, so it is dropped when GROQ_MODEL points elsewhere.
    return model.startswith("openai/gpt-oss")


async def chat(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Send a single user-turn prompt (optionally with a system message) and
    return the raw text response.

    reasoning_effort ("low" / "medium" / "high") limits the hidden reasoning
    tokens a gpt-oss model spends; those tokens count against Groq's
    tokens-per-minute limit, so simple agents should use "low". max_tokens caps
    the completion (reasoning included) so one call can't run away.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    extra: dict = {}
    if reasoning_effort and _supports_reasoning_effort(_MODEL_NAME):
        extra["reasoning_effort"] = reasoning_effort
    if max_tokens:
        extra["max_completion_tokens"] = max_tokens

    for attempt in range(_MAX_RETRIES):
        try:
            response = await _client.chat.completions.create(
                model=_MODEL_NAME,
                messages=messages,
                temperature=temperature,
                **extra,
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _retry_delay(e, attempt)
            logger.warning(
                f"Groq rate limit hit (attempt {attempt + 1}/{_MAX_RETRIES}); "
                f"retrying in {delay:.1f}s."
            )
            await asyncio.sleep(delay)


def parse_json(text: str):
    """Strip markdown fences and parse JSON from the model response."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text.strip())
