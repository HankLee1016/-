import time
from dataclasses import dataclass

from .agents import AgentSelector
from .config import AIConfig
from .fallback import ChatFallback, ProposalFallback
from .prompts import ChatPromptBuilder, ProposalPromptBuilder
from .providers import MockProposalProvider, OpenAIChatProvider
from .text_utils import TextNormalizer, TextPolisher
from .validator import ProposalValidator
from services.rag import RAGPipeline


@dataclass
class ProposalResult:
    text: str
    source: str  # openai | mock | fallback | repaired
    elapsed_ms: int
    within_timeout: bool


class ProposalService:
    def __init__(self, config: AIConfig | None = None, rag_pipeline: RAGPipeline | None = None):
        self.config = config or AIConfig.from_env()
        self.prompts = ProposalPromptBuilder()
        self.validator = ProposalValidator(self.config)
        self.provider = OpenAIChatProvider(self.config)
        self.mock = MockProposalProvider(self.config)
        # 預設把 RAG 當成企劃生成的前置知識層。
        self.rag = rag_pipeline or RAGPipeline()

    def _build_rag_context(self, title, background, issues, goals) -> str:
        # 先把企劃重點合併成搜尋條件，再找出最相關的補助段落。
        query = " ".join(part for part in [title, background, issues, goals] if part)
        rag_answer = self.rag.answer(query, top_k=3)
        if not rag_answer.contexts:
            return ""
        blocks = ["【知識庫參考】"]
        for idx, context in enumerate(rag_answer.contexts, start=1):
            blocks.append(f"第 {idx} 段：{context}")
        return "\n".join(blocks)

    def generate(self, title, background, issues, goals, agent_name="") -> ProposalResult:
        start = time.perf_counter()
        timeout_ms = self.config.timeout_seconds * 1000
        rag_context = self._build_rag_context(title, background, issues, goals)

        if self.config.mock_mode or not self.provider.available:
            text = self.mock.generate(title, background, issues, goals)
            if rag_context:
                text = f"{text}\n\n{rag_context}"
            elapsed = int((time.perf_counter() - start) * 1000)
            return ProposalResult(text, "mock", elapsed, elapsed <= timeout_ms)

        system, user = self.prompts.build(title, background, issues, goals)
        if rag_context:
            user = f"{user}\n\n請優先參考以下知識庫內容：\n{rag_context}"
        raw = self.provider.complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=1200,
        )
        elapsed = int((time.perf_counter() - start) * 1000)

        if not raw:
            text = ProposalFallback.full(title, background, issues, goals)
            if rag_context:
                text = f"{text}\n\n{rag_context}"
            return ProposalResult(text, "fallback", elapsed, elapsed <= timeout_ms)

        check = self.validator.validate(raw)
        if check.ok:
            return ProposalResult(raw, "openai", elapsed, elapsed <= timeout_ms)

        repaired = self.validator.repair(raw, title, background, issues, goals)
        if rag_context:
            repaired = f"{repaired}\n\n{rag_context}"
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProposalResult(repaired, "repaired", elapsed, elapsed <= timeout_ms)


class ChatService:
    def __init__(self, config: AIConfig | None = None, rag_pipeline: RAGPipeline | None = None):
        self.config = config or AIConfig.from_env()
        self.prompts = ChatPromptBuilder()
        self.provider = OpenAIChatProvider(self.config)
        # 對話模式也共用同一套 RAG，避免生成與對話引用不同資料來源。
        self.rag = rag_pipeline or RAGPipeline()

    def reply(self, user_input, history, subsidy_summary="") -> str:
        normalized = TextNormalizer.normalize(user_input)
        if not normalized:
            return "請先輸入要優化的內容，我會協助整理成正式企劃語氣。"

        rag_answer = self.rag.answer(" ".join(filter(None, [normalized, subsidy_summary])), top_k=2)
        if self.config.mock_mode or not self.provider.available:
            fallback = ChatFallback.reply(normalized, history)
            if rag_answer.contexts:
                return f"{fallback}\n\n【知識庫參考】\n" + "\n".join(f"- {ctx}" for ctx in rag_answer.contexts)
            return fallback

        messages = self.prompts.build_messages(normalized, history, subsidy_summary)
        if rag_answer.contexts:
            rag_context = "\n".join(f"- {ctx}" for ctx in rag_answer.contexts)
            messages.insert(1, {"role": "system", "content": f"請優先參考以下補助/簡章知識庫內容：\n{rag_context}"})
        content = self.provider.complete(messages, temperature=0.35, max_tokens=700)
        if not content:
            return ChatFallback.reply(normalized, history)
        if rag_answer.contexts:
            return f"{TextPolisher.polish(content)}\n\n【知識庫參考】\n" + "\n".join(f"- {ctx}" for ctx in rag_answer.contexts)
        return TextPolisher.polish(content)


# 模組級積木：app.py 直接呼叫。
# 這裡把服務實體先建好，讓路由只需要關心「送入資料、拿回結果」，
# 具體的模型選擇、RAG 檢索與 fallback 都封裝在 service 層。
_config = AIConfig.from_env()
proposal_service = ProposalService(_config)
chat_service = ChatService(_config)


def choose_ai_agent(background, issues):
    return AgentSelector.choose(background, issues)


def generate_case_proposal(title, background, issues, goals, agent_name=""):
    return proposal_service.generate(title, background, issues, goals, agent_name).text


def generate_chat_response(user_input, history, subsidy_summary=""):
    return chat_service.reply(user_input, history, subsidy_summary)
