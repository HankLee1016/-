from __future__ import annotations

from pathlib import Path

from .admin_tools import RAGAdminTools


def rebuild_from_path(path: str | Path) -> int:
    """重新建立知識庫索引。

    如果傳入的是檔案，就匯入單一文件；如果傳入的是資料夾，
    就批次匯入整個資料夾，方便後台做重新索引。
    """
    tools = RAGAdminTools()
    source = Path(path)
    if source.is_dir():
        return tools.ingest_folder(source)
    return tools.ingest_upload(source)
