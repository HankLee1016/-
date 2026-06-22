"""補助來源的分類與範圍說明（1-C-1）。

這個模組不是爬蟲本體，而是先把「要抓哪些來源、來源屬性、是否保留舊功能」
這件事說清楚。後續若新增更多政府單位，只要補來源清單，不必直接改壞爬蟲主流程。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# 這份清單先幫你把「要抓哪些來源」講清楚，後續如果每個政府單位要寫專屬解析器，
# 就只需要新增來源與對應 parser，不用改掉整個爬蟲主架構。


@dataclass(frozen=True)
class SubsidySource:
    name: str
    source_type: str
    description: str
    enabled: bool = True


DEFAULT_SUBSIDY_SOURCES = [
    SubsidySource("衛生福利部補助公告", "government", "社福、長照、弱勢家庭與福利機構補助。"),
    SubsidySource("原民會補助公告", "government", "原住民族相關服務與計畫補助。"),
    SubsidySource("地方政府社會局補助公告", "government", "各縣市社會局、社會處、社會福利中心公告。"),
    SubsidySource("現有 subsidies.json 種子資料", "seed", "保留原本專案內的補助資料，作為展示與測試的穩定來源。"),
]


def describe_sources() -> list[dict]:
    """回傳可讀版來源清單，方便顯示到管理介面或報告中。"""
    return [asdict(source) for source in DEFAULT_SUBSIDY_SOURCES]
