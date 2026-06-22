from __future__ import annotations

from dataclasses import dataclass

from .retriever import LocalRAGRetriever


@dataclass
class RAGAnswer:
    # answer 是給前端/AI 使用的摘要文字；contexts/citations 則保留可追溯來源。
    answer: str
    contexts: list[str]
    citations: list[str]


class RAGPipeline:
    def __init__(self, retriever: LocalRAGRetriever | None = None):
        self.retriever = retriever or LocalRAGRetriever()

    def answer(self, query: str, *, top_k: int = 4) -> RAGAnswer:
        # 先檢索再組摘要，避免直接把整份文件灌給模型。
        results = self.retriever.search(query, top_k=top_k)
        if not results:
            return RAGAnswer(
                answer="目前知識庫中尚未找到相關內容，建議先匯入補助簡章或條文文件。",
                contexts=[],
                citations=[],
            )

        contexts = [result.document.content for result in results]
        citations = [result.document.source_name for result in results]
        summary_lines = ["以下是根據知識庫整理的重點："]
        for idx, result in enumerate(results, start=1):
            snippet = result.document.content[:180].strip()
            summary_lines.append(f"{idx}. {result.document.source_name}（分段 {result.document.chunk_index + 1}）：{snippet}")
        summary_lines.append("如需正式送件內容，建議再結合企劃目標與機構背景進行整理。")
        return RAGAnswer(answer="\n".join(summary_lines), contexts=contexts, citations=citations)
