"""Runtime configuration. Secrets come ONLY from environment / .env — never hardcoded."""
from __future__ import annotations
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv optional at runtime
    pass


@dataclass
class Settings:
    # --- OpenRouter (OpenAI-compatible) ---
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"))
    openrouter_fallback_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_FALLBACK_MODEL", "google/gemini-flash-1.5"))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    app_url: str = field(default_factory=lambda: os.getenv("OPENROUTER_APP_URL", "https://example.com/label-lag-sentinel"))
    app_name: str = field(default_factory=lambda: os.getenv("OPENROUTER_APP_NAME", "Label Lag Sentinel"))

    # --- Public pharma data APIs ---
    openfda_api_key: str = field(default_factory=lambda: os.getenv("OPENFDA_API_KEY", ""))
    openfda_base: str = "https://api.fda.gov/drug/event.json"
    dailymed_base: str = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
    rxnorm_base: str = "https://rxnav.nlm.nih.gov/REST"

    # --- HTTP behaviour ---
    http_timeout: float = 30.0
    max_retries: int = 3

    @property
    def llm_ready(self) -> bool:
        return bool(self.openrouter_api_key)


def get_settings() -> "Settings":
    return Settings()
