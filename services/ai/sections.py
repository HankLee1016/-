from dataclasses import dataclass


@dataclass(frozen=True)
class ProposalSection:
    order: str
    title: str


class SectionRegistry:
    """送件版企劃章節（1-A-4 規格）。"""

    SECTIONS = (
        ProposalSection("一", "計畫緣起"),
        ProposalSection("二", "執行目標"),
        ProposalSection("三", "服務對象"),
        ProposalSection("四", "執行方式"),
        ProposalSection("五", "預期效益"),
        ProposalSection("六", "經費概算"),
        ProposalSection("七", "風險與因應"),
    )

    @classmethod
    def headers(cls) -> list[str]:
        return [f"{s.order}、{s.title}" for s in cls.SECTIONS]

    @classmethod
    def prompt_outline(cls) -> str:
        return "\n".join(cls.headers())

    @classmethod
    def titles(cls) -> list[str]:
        return [s.title for s in cls.SECTIONS]
