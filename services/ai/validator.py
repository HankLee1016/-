import re
from dataclasses import dataclass, field

from .config import AIConfig
from .fallback import ProposalFallback
from .sections import SectionRegistry
from .text_utils import TextNormalizer


@dataclass
class ValidationResult:
    ok: bool
    missing: list[str] = field(default_factory=list)
    short: list[str] = field(default_factory=list)


class ProposalValidator:
    def __init__(self, config: AIConfig):
        self.config = config

    def validate(self, text: str) -> ValidationResult:
        if not text or not text.strip():
            return ValidationResult(False, missing=SectionRegistry.titles())

        missing, short = [], []
        for header in SectionRegistry.headers():
            if header not in text:
                missing.append(header.split("、", 1)[1])
                continue
            body = self._section_body(text, header)
            if len(body.strip()) < self.config.min_section_chars:
                short.append(header.split("、", 1)[1])

        ok = not missing and not short and len(text.strip()) >= self.config.min_total_chars
        return ValidationResult(ok, missing, short)

    def repair(self, text: str, title, background, issues, goals) -> str:
        """以 AI 原文為基底，補齊缺章或過短段落。"""
        norm = TextNormalizer.normalize
        lines = [f"計畫名稱：{norm(title) or '未命名計畫'}"]
        for section in SectionRegistry.SECTIONS:
            header = f"{section.order}、{section.title}"
            lines.append(header)
            body = self._section_body(text, header) if text else ""
            if len(body.strip()) >= self.config.min_section_chars:
                lines.append(body)
            else:
                lines.append(ProposalFallback.section_body(section.title, title, background, issues, goals))
        return "\n".join(lines)

    @staticmethod
    def _section_body(text: str, header: str) -> str:
        pattern = re.escape(header) + r"\s*([\s\S]*?)(?=\n[一二三四五六七八九十]+、|$)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""
