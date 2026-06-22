"""政府補助資訊爬蟲（1-C 主線）。

設計原則：
1. 保留原本 `subsidies.json` 作為穩定種子資料，不直接刪除舊功能。
2. 爬取來源採「逐一嘗試」：上一個來源抓不到，才進下一個來源。
3. 每次執行只處理一個成功來源，避免多來源同時匯入造成重複資料。

目前支援三種模式：
- `--seed subsidies.json`：先把既有 JSON 資料匯入，最穩定。
- `--url https://...`：抓單一頁面的 HTML 補助清單。
- `--auto`：依預設來源清單逐一嘗試，抓到第一個可用來源就停止。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests

from subsidy_sources import DEFAULT_SUBSIDY_SOURCES

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None


@dataclass
class SubsidyRecord:
    """補助資料標準格式。"""

    id: int
    title: str
    category: str
    agency: str
    subsidy_number: str
    deadline: str
    amount_range: str
    eligibility: str
    description: str
    source_url: str


_FIELD_ALIASES = {
    "title": ["title", "name", "補助名稱", "標題"],
    "category": ["category", "分類", "類別"],
    "agency": ["agency", "機關", "單位", "主辦機關"],
    "subsidy_number": ["subsidy_number", "編號", "案號", "計畫編號"],
    "deadline": ["deadline", "截止日", "申請截止日", "收件截止日"],
    "amount_range": ["amount_range", "金額", "補助金額", "經費"],
    "eligibility": ["eligibility", "資格", "申請資格", "對象"],
    "description": ["description", "說明", "內容", "補助內容"],
    "source_url": ["source_url", "url", "來源", "連結"],
}


class CrawlError(RuntimeError):
    """來源抓取失敗時使用的統一例外。"""



def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()



def _pick(data: dict, key: str, default: str = "") -> str:
    for alias in _FIELD_ALIASES.get(key, [key]):
        value = data.get(alias)
        if value not in (None, ""):
            return _normalize_text(str(value))
    return default



def load_seed_records(path: str | Path) -> list[SubsidyRecord]:
    """直接讀取專案內的 JSON 補助資料。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    records: list[SubsidyRecord] = []
    for item in raw.get("subsidies", []):
        records.append(
            SubsidyRecord(
                id=int(item.get("id", len(records) + 1)),
                title=_pick(item, "title"),
                category=_pick(item, "category", "其他"),
                agency=_pick(item, "agency", "未知機關"),
                subsidy_number=_pick(item, "subsidy_number"),
                deadline=_pick(item, "deadline"),
                amount_range=_pick(item, "amount_range"),
                eligibility=_pick(item, "eligibility"),
                description=_pick(item, "description"),
                source_url=_pick(item, "source_url"),
            )
        )
    return records



def fetch_html_list(url: str, *, timeout: int = 20) -> list[SubsidyRecord]:
    """從 HTML 頁面抓補助公告清單。"""
    if BeautifulSoup is None:
        raise CrawlError("請先安裝 beautifulsoup4，才能使用 HTML 補助爬取功能")

    response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    records: list[SubsidyRecord] = []
    candidates = soup.select("table tr, article, li, .card, .news-item, .announcement")
    for idx, node in enumerate(candidates, start=1):
        text = _normalize_text(node.get_text(" ", strip=True))
        if len(text) < 12:
            continue
        link = node.find("a")
        source_url = urljoin(url, link.get("href")) if link and link.get("href") else url
        records.append(
            SubsidyRecord(
                id=idx,
                title=text[:60],
                category="政府補助",
                agency="政府網站",
                subsidy_number="",
                deadline="",
                amount_range="",
                eligibility="",
                description=text,
                source_url=source_url,
            )
        )
    return records



def dedupe_records(records: Iterable[SubsidyRecord]) -> list[SubsidyRecord]:
    """依標題與來源去重，避免多來源或重跑時資料重複。"""
    seen: set[tuple[str, str]] = set()
    unique: list[SubsidyRecord] = []
    for record in records:
        key = (record.title.lower().strip(), record.source_url.strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique



def export_records(records: Iterable[SubsidyRecord], output_path: str | Path) -> Path:
    """把補助資料輸出成與現有專案相容的 JSON。"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"subsidies": [asdict(record) for record in dedupe_records(records)]}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output



def crawl_source(mode: str, value: str | None) -> list[SubsidyRecord]:
    """依模式抓單一來源資料。"""
    if mode == "seed":
        if not value:
            raise ValueError("seed 模式需要提供檔案路徑")
        return load_seed_records(value)
    if mode == "url":
        if not value:
            raise ValueError("url 模式需要提供網址")
        return fetch_html_list(value)
    raise ValueError(f"不支援的模式：{mode}")



def crawl_auto_sources() -> tuple[list[SubsidyRecord], str]:
    """逐一嘗試預設來源，只採用第一個成功的來源。"""
    # 先試種子資料，若有就直接使用，避免多來源重複匯入。
    for source in DEFAULT_SUBSIDY_SOURCES:
        if source.source_type == "seed":
            seed_path = Path("subsidies.json")
            if not seed_path.exists():
                continue
            records = load_seed_records(seed_path)
            if records:
                return records, source.name
            continue

        # 政府來源先以可擴充的 URL 清單示意，未來可替每個來源寫專屬 parser。
        candidate_urls = [
            "https://www.mohw.gov.tw/",
            "https://www.cip.gov.tw/",
            "https://www.gov.tw/",
        ]
        for url in candidate_urls:
            try:
                records = fetch_html_list(url)
            except Exception:
                continue
            if records:
                return records, f"{source.name} | {url}"
    return [], ""



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="政府補助資訊爬蟲")
    parser.add_argument("--seed", help="從既有 JSON 種子檔匯入")
    parser.add_argument("--url", help="從單一 HTML 頁面抓取補助公告")
    parser.add_argument("--auto", action="store_true", help="依預設來源逐一嘗試，抓到第一個成功來源就停止")
    parser.add_argument("--output", default="subsidies.crawled.json", help="輸出 JSON 路徑")
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.auto:
        records, picked_source = crawl_auto_sources()
        if not records:
            raise SystemExit("自動模式未抓到任何補助資料")
        export_path = export_records(records, args.output)
        print(f"自動模式使用來源：{picked_source}")
        print(f"已輸出 {len(records)} 筆補助資料到 {export_path}")
        return

    records: list[SubsidyRecord] = []
    if args.seed:
        records = crawl_source("seed", args.seed)
    elif args.url:
        records = crawl_source("url", args.url)
    else:
        parser.error("請至少提供 --seed、--url 或 --auto 其中一個來源")

    export_path = export_records(records, args.output)
    print(f"已輸出 {len(records)} 筆補助資料到 {export_path}")


if __name__ == "__main__":
    main()
