# app/ai.py — Lab 5: the ONLY file that knows which AI provider we call.
#
# It speaks the "OpenAI-compatible" chat-completions format, which Gemini, Groq and
# OpenRouter all accept. Changing provider = changing AI_BASE_URL, AI_MODEL and the key
# in the environment. No other file changes.
import hashlib
import os
import time

import httpx2

AI_BASE_URL = os.environ.get(
    "AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
)
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.5-flash-lite")
PROMPT_VERSION = "v1"  # change it when you change the prompt (only matters if you cache)
# Lab 5, Step 2: THIS is the only part you change — describe YOUR feature.
# Keep {text}: it is replaced by the record from your database.
PROMPT = (
    "Summarise the text below in at most three short sentences. "
    "Use only facts that appear in the text. Reply in the language of the text.\n\n"
    "TEXT:\n{text}"
)
MAX_INPUT_CHARS = 8000  # cap the input: long text costs tokens and can exceed the limit
TIMEOUT_S = 15.0  # never wait forever on the network


class AIUnavailable(Exception):
    """No summary could be produced. `reason` is for the logs, never for the browser."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def cache_key(text: str) -> str:
    # Same model + same prompt + same text = same summary, so it can be stored and reused.
    raw = f"{AI_MODEL}\n{PROMPT_VERSION}\n{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def summarize(text: str, client: httpx2.Client | None = None) -> str:
    """One call to the provider. Raises httpx2 errors or AIUnavailable."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise AIUnavailable("GEMINI_API_KEY is not set")
    body = {
        "model": AI_MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(text=text[:MAX_INPUT_CHARS])}],
        "temperature": 0.2,  # low randomness: this is a summary
        "max_tokens": 1024,  # caps cost; Gemini 3 "thinking" tokens count here too
        "reasoning_effort": "low",  # little thinking needed to summarise
    }
    own_client = client is None
    client = client or httpx2.Client(timeout=TIMEOUT_S)
    try:
        r = client.post(
            f"{AI_BASE_URL}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {key}"},  # the key travels in a header only
        )
        r.raise_for_status()
        data = r.json()
    finally:
        if own_client:
            client.close()
    # Check the shape before trusting it: refusals and cut-off answers look different.
    try:
        choice = data["choices"][0]
        answer = (choice["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError, AttributeError) as err:
        raise AIUnavailable(f"unexpected response shape: {err!r}") from err
    if not answer:
        raise AIUnavailable(f"empty answer, finish_reason={choice.get('finish_reason')}")
    return answer


def summarize_safe(text: str, client: httpx2.Client | None = None, sleep=time.sleep) -> str:
    """summarize() plus the failure policy. Returns a summary or raises AIUnavailable."""
    attempts = 3
    for attempt in range(attempts):
        try:
            return summarize(text, client)
        except httpx2.HTTPStatusError as err:
            status = err.response.status_code
            if status == 429 or status >= 500:  # temporary: wait, then try again
                if attempt < attempts - 1:
                    sleep(2**attempt)  # 1 s, then 2 s
                    continue
                raise AIUnavailable(f"HTTP {status} after {attempts} attempts") from err
            # 400 / 401 / 403 / 404: a bad request or a bad key never becomes good
            raise AIUnavailable(f"HTTP {status} (not retried)") from err
        except httpx2.TimeoutException as err:
            raise AIUnavailable("timeout") from err  # we already waited TIMEOUT_S
        except httpx2.TransportError as err:
            raise AIUnavailable(f"network error: {type(err).__name__}") from err
    raise AIUnavailable("unreachable")  # for the type checker; the loop always returns
