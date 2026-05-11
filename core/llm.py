"""
core/llm.py — Provider-agnostic LLM wrapper.

Configure via .env:
  LLM_PROVIDER=gemini      (default)
  LLM_PROVIDER=anthropic

All agents call llm.chat() and llm.vision_chat() — never the SDK directly.
Retry logic for transient 503 errors lives here so agents don't repeat it.
"""
import logging
import time

from core.config import (
    LLM_PROVIDER,
    GOOGLE_API_KEY, ANTHROPIC_API_KEY,
    GEMINI_TEXT_MODEL, ANTHROPIC_TEXT_MODEL,
)

logger = logging.getLogger(__name__)


def chat(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.2) -> str:
    """Send a system + user prompt; return the model's text response."""
    if LLM_PROVIDER == "anthropic":
        return _anthropic_chat(system, user, max_tokens, temperature)
    return _gemini_chat(system, user, max_tokens, temperature)


def vision_chat(user_text: str, image_bytes: bytes) -> str:
    """Send image + text to the vision-capable model; return text response."""
    if LLM_PROVIDER == "anthropic":
        return _anthropic_vision(user_text, image_bytes)
    return _gemini_vision(user_text, image_bytes)


# ── Gemini ────────────────────────────────────────────────────────────────────

def _gemini_chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=GOOGLE_API_KEY)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return response.text.strip()
        except genai_errors.ServerError as e:
            wait = 30 * (attempt + 1)
            logger.warning(f"[LLM] Gemini 503, retrying in {wait}s: {e}")
            time.sleep(wait)
    raise RuntimeError("Gemini unavailable after 3 retries")


def _gemini_vision(user_text: str, image_bytes: bytes) -> str:
    import io
    import PIL.Image
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=GOOGLE_API_KEY)
    pil_image = PIL.Image.open(io.BytesIO(image_bytes))
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=[pil_image, user_text],
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=512,
                    temperature=0.1,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return response.text.strip()
        except genai_errors.ServerError as e:
            wait = 30 * (attempt + 1)
            logger.warning(f"[LLM] Gemini vision 503, retrying in {wait}s: {e}")
            time.sleep(wait)
    raise RuntimeError("Gemini vision unavailable after 3 retries")


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _anthropic_chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=ANTHROPIC_TEXT_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text.strip()
        except anthropic.InternalServerError as e:
            wait = 30 * (attempt + 1)
            logger.warning(f"[LLM] Anthropic 503, retrying in {wait}s: {e}")
            time.sleep(wait)
    raise RuntimeError("Anthropic unavailable after 3 retries")


def _anthropic_vision(user_text: str, image_bytes: bytes) -> str:
    import base64
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode()
    response = client.messages.create(
        model=ANTHROPIC_TEXT_MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": user_text},
            ],
        }],
    )
    return response.content[0].text.strip()
