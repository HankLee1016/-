from __future__ import annotations

from pathlib import Path

from .ingest import ingest_directory, ingest_file
from .retriever import LocalRAGRetriever


class RAGAdminTools:
    """給後台用的知識庫管理工具。

    目前先維持簡單的本地檔案索引，讓你可以先完成 1-B-3、1-B-6
    的功能落地；之後若要換成向量資料庫，只要保留同樣的介面即可。
    """

    def __init__(self, retriever: LocalRAGRetriever | None = None):
        self.retriever = retriever or LocalRAGRetriever()

    def ingest_upload(self, file_path: str | Path) -> int:
        """將單一上傳檔匯入知識庫。"""
        return self.retriever.ingest_file(file_path)

    def ingest_folder(self, folder_path: str | Path) -> int:
        """將資料夾內的文件批次匯入知識庫。"""
        return self.retriever.ingest_directory(folder_path)

    def list_documents(self) -> list[dict]:
        """回傳目前知識庫內容，供後台列表使用。"""
        return [doc.__dict__ for doc in self.retriever.documents]

    def remove_document(self, doc_id: str) -> int:
        """依文件 ID 刪除知識庫文件。"""
        before = len(self.retriever.documents)
        self.retriever.documents = [doc for doc in self.retriever.documents if doc.doc_id != doc_id]
        if len(self.retriever.documents) != before:
            self.retriever._save()
        return before - len(self.retriever.documents)
