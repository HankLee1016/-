from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .ingest import RAGDocument, ingest_file, ingest_directory, normalize_text


@dataclass
class RetrievalResult:
    # 代表一次檢索命中的結果，保留文件內容與分數供後續排序。
    document: RAGDocument
    score: float
    highlights: list[str]


class LocalRAGRetriever:
    def __init__(self, store_path: str | Path | None = None):
        # 預設把索引資料存成 JSON，方便目前專題階段先落地。
        self.store_path = Path(store_path) if store_path else Path(__file__).with_name("rag_store.json")
        self.documents: list[RAGDocument] = []
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            self.documents = []
            return
        raw = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.documents = [RAGDocument(**item) for item in raw]

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps([doc.__dict__ for doc in self.documents], ensure_ascii=False, indent=2), encoding="utf-8")

    def ingest_documents(self, documents: Iterable[RAGDocument]) -> int:
        # 以 doc_id 去重，避免同一份文件重複寫入索引。
        added = 0
        existing = {doc.doc_id for doc in self.documents}
        for doc in documents:
            if doc.doc_id in existing:
                continue
            self.documents.append(doc)
            added += 1
        if added:
            self._save()
        return added

    def ingest_file(self, path: str | Path) -> int:
        return self.ingest_documents(ingest_file(path))

    def ingest_directory(self, directory: str | Path) -> int:
        return self.ingest_documents(ingest_directory(directory))

    def _score(self, query: str, content: str) -> tuple[float, list[str]]:
        query_terms = [t for t in normalize_text(query).split() if len(t) > 1]
        if not query_terms:
            return 0.0, []
        content_lower = content.lower()
        counts = Counter(term.lower() for term in query_terms)
        score = 0.0
        highlights = []
        for term, freq in counts.items():
            if term in content_lower:
                score += 2.0 * freq
                highlights.append(term)
        return score, highlights

    def search(self, query: str, *, top_k: int = 4) -> list[RetrievalResult]:
        scored: list[RetrievalResult] = []
        for doc in self.documents:
            score, highlights = self._score(query, doc.content)
            if score <= 0:
                continue
            scored.append(RetrievalResult(doc, score, highlights))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
