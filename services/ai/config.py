import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    api_key: str
    mock_mode: bool
    timeout_seconds: int
    model: str
    min_section_chars: int
    min_total_chars: int

    @classmethod
    def from_env(cls) -> "AIConfig":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            mock_mode=os.getenv("AI_MOCK_MODE", "false").strip().lower() in {"1", "true", "yes", "on"},
            timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "15")),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            min_section_chars=int(os.getenv("AI_MIN_SECTION_CHARS", "40")),
            min_total_chars=int(os.getenv("AI_MIN_TOTAL_CHARS", "380")),
        )

    @property
    def use_real_api(self) -> bool:
        return bool(self.api_key) and not self.mock_mode
