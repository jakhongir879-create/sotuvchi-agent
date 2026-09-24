"""Gemini API bilan ishlash: bir nechta modelni navbat bilan sinaydi (band bo'lsa keyingisiga o'tadi)."""
import asyncio
import logging
import os

import httpx

log = logging.getLogger("gemini")

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODELS = [m.strip() for m in os.getenv(
    "GEMINI_MODELS",
    "gemini-3-flash-preview,gemini-3.6-flash,gemini-flash-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite",
).split(",") if m.strip()]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_client = httpx.AsyncClient(timeout=90)


class GeminiBusy(Exception):
    pass


async def generate(system: str, contents: list, tools: list) -> list:
    """Model javobidagi `parts` ro'yxatini qaytaradi."""
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "tools": [{"functionDeclarations": tools}],
        "generationConfig": {"temperature": 0.5, "thinkingConfig": {"thinkingLevel": "low"}},
    }
    last_err = None
    for attempt in range(2):
        for model in MODELS:
            try:
                r = await _client.post(
                    URL.format(model=model),
                    headers={"x-goog-api-key": API_KEY},
                    json=body,
                )
            except httpx.HTTPError as e:
                last_err = f"{model}: {e!r}"
                log.warning(last_err)
                continue
            if r.status_code == 200:
                data = r.json()
                cands = data.get("candidates") or []
                if cands and cands[0].get("content", {}).get("parts"):
                    return cands[0]["content"]["parts"]
                last_err = f"{model}: bo'sh javob {data}"
                log.warning(last_err)
                continue
            last_err = f"{model}: {r.status_code} {r.text[:300]}"
            log.warning(last_err)
            if r.status_code in (400, 401, 403):
                # kalit yoki so'rov xato — boshqa model ham yordam bermaydi
                if "API key" in r.text or r.status_code in (401, 403):
                    raise RuntimeError(last_err)
        await asyncio.sleep(3 * (attempt + 1))
    raise GeminiBusy(last_err)
