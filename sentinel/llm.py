"""OpenRouter LLM client (OpenAI-compatible) with retry + model fallback."""
from __future__ import annotations
import time
from typing import Optional
from .config import Settings


class LLMError(RuntimeError):
    pass


class OpenRouterLLM:
    def __init__(self, settings: Settings):
        self.s = settings
        if not settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set. Add it to .env or the sidebar.")
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise LLMError("The 'openai' package is required: pip install openai") from e
        self.client = OpenAI(api_key=settings.openrouter_api_key,
                             base_url=settings.openrouter_base_url)

    def chat(self, system: str, user: str, model: Optional[str] = None,
             temperature: float = 0.2, max_tokens: int = 1400) -> str:
        models = [model or self.s.openrouter_model]
        if self.s.openrouter_fallback_model and self.s.openrouter_fallback_model not in models:
            models.append(self.s.openrouter_fallback_model)
        headers = {"HTTP-Referer": self.s.app_url, "X-Title": self.s.app_name}
        last_err = None
        for m in models:
            for attempt in range(self.s.max_retries):
                try:
                    resp = self.client.chat.completions.create(
                        model=m, temperature=temperature, max_tokens=max_tokens,
                        extra_headers=headers,
                        messages=[{"role": "system", "content": system},
                                  {"role": "user", "content": user}],
                    )
                    return (resp.choices[0].message.content or "").strip()
                except Exception as e:  # network / rate / model errors
                    last_err = e
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s
        raise LLMError(f"OpenRouter call failed after retries + fallback: {last_err}")
