from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


_WORD_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"(?<=[。！？!?\.])\s*")


@dataclass
class RAGDocument:
    doc_id: str
    source_name: str
    content: str
    chunk_index: int
    metadata: dict
    created_at: str


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WORD_RE.sub(" ", text)
    return text.strip()


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    # 切塊時優先保留段落邏輯；若段落過長，再切成句子。
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= chunk_size:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
            continue
        sentences = [s.strip() for s in _SENTENCE_RE.split(paragraph) if s.strip()]
        if not sentences:
            sentences = [paragraph]
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 <= chunk_size:
                buffer = f"{buffer}{sentence} ".strip()
            else:
                if buffer:
                    chunks.append(buffer.strip())
                buffer = sentence
        current = buffer
    if current:
        chunks.append(current.strip())

    if overlap > 0 and len(chunks) > 1:
        merged = [chunks[0]]
        for chunk in chunks[1:]:
            prefix = merged[-1][-overlap:]
            merged.append(f"{prefix} {chunk}".strip())
        return merged
    return chunks


def ingest_text(text: str, source_name: str, metadata: dict | None = None) -> list[RAGDocument]:
    # 把原始文本轉成多個文件片段，後續檢索時更容易命中局部內容。
    metadata = metadata or {}
    chunks = chunk_text(text)
    created_at = datetime.utcnow().isoformat()
    docs: list[RAGDocument] = []
    for idx, chunk in enumerate(chunks):
        docs.append(
            RAGDocument(
                doc_id=f"{source_name}:{idx}",
                source_name=source_name,
                content=chunk,
                chunk_index=idx,
                metadata=metadata,
                created_at=created_at,
            )
        )
    return docs


def _extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def ingest_file(path: str | Path) -> list[RAGDocument]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    text = ""
    if suffix in {".txt", ".md", ".html", ".htm"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    elif suffix == ".pdf":
        text = _extract_text_from_pdf(file_path)
    else:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    return ingest_text(text, file_path.name, {"path": str(file_path), "suffix": suffix})


def ingest_directory(directory: str | Path, patterns: Iterable[str] = ("*.pdf", "*.txt", "*.md", "*.html", "*.htm")) -> list[RAGDocument]:
    root = Path(directory)
    docs: list[RAGDocument] = []
    for pattern in patterns:
        for path in root.glob(pattern):
            docs.extend(ingest_file(path))
    return docs


def serialize_documents(documents: list[RAGDocument]) -> str:
    return json.dumps([asdict(doc) for doc in documents], ensure_ascii=False, indent=2)
