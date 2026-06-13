"""
Gemini AI client for Aethelgard family guide generation.

Requires GEMINI_API_KEY in config. Fails gracefully when the key is absent or
the API is unreachable — callers should handle RuntimeError and fall back to
the deterministic guide.

TODO (production):
  - Switch to Vertex AI (google-cloud-aiplatform) for enterprise SLA and VPC-SC.
  - Cache generated guides in DynamoDB (TTL 24 h) to avoid re-billing identical
    requests.
  - Stream the response via model.generate_content(..., stream=True) for large
    vaults so the HTTP connection does not time out.
  - Consider enabling safety settings to filter harmful content.
"""

import time

from app.core.config import settings

# Module-level singleton — re-created on first call after key changes.
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model

    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Set it in backend/.env to enable AI guide generation."
        )

    # Lazy import — allows the module to be imported without the package if
    # the package is not yet installed (tests that never call the AI path).
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    _model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 2048,
        },
    )
    return _model


def call_gemini(prompt: str, timeout_seconds: int = 30) -> str:
    """
    Sends `prompt` to Gemini and returns the response text.

    Implements 3-attempt exponential backoff (1 s → 2 s → fail).
    Raises RuntimeError on exhausted retries or configuration error.
    """
    model = _get_model()

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                request_options={"timeout": timeout_seconds},
            )
            return response.text
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2**attempt)  # 1 s, then 2 s

    raise RuntimeError(
        f"Gemini call failed after 3 attempts: {last_exc}"
    ) from last_exc
