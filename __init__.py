"""Label Lag Sentinel — pharmacovigilance label-gap detection agent."""
from .config import get_settings, Settings
from .orchestrator import Coordinator, SentinelResult
from .llm import OpenRouterLLM, LLMError

__all__ = ["get_settings", "Settings", "Coordinator", "SentinelResult",
           "OpenRouterLLM", "LLMError"]
__version__ = "1.0.0"
