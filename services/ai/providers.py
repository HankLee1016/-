try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import AIConfig
from .fallback import ProposalFallback


class OpenAIChatProvider:
    def __init__(self, config: AIConfig):
        self.config = config
        self._client = None
        if OpenAI and config.use_real_api:
            self._client = OpenAI(api_key=config.api_key, timeout=config.timeout_seconds)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, messages: list[dict], *, temperature: float, max_tokens: int) -> str | None:
        if not self._client:
            return None
        try:
            res = self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = res.choices[0].message.content
            return content.strip() if content else None
        except Exception:
            return None


class MockProposalProvider:
    """開發/demo 模式：不呼叫 API，直接產出結構化草稿。"""

    def __init__(self, config: AIConfig):
        self.config = config

    def generate(self, title, background, issues, goals) -> str:
        return ProposalFallback.full(title, background, issues, goals)
