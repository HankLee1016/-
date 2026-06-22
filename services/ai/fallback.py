from .sections import SectionRegistry
from .text_utils import TextNormalizer


class ProposalFallback:
    """Mock / 無 API 時的結構化草稿。"""

    @classmethod
    def section_body(cls, title: str, title_text, background, issues, goals) -> str:
        norm = TextNormalizer.normalize
        min_len = 40

        def ensure(text, default):
            text = norm(text)
            return text if len(text) >= min_len else (text + default if text else default)

        mapping = {
            "計畫緣起": ensure(
                background,
                "。本計畫依據組織使命與在地需求評估結果提出，請補充服務脈絡與推動本計畫之具體原因與政策依據。",
            ),
            "執行目標": (
                f"本計畫旨在回應「{norm(issues) or '服務對象核心需求'}」，"
                f"並朝向「{norm(goals) or '具體可衡量之預期成效'}」推進，"
                "目標需可量化、可驗證且符合補助規定。"
            ),
            "服務對象": (norm(issues) or "請補充") + "。服務對象需明確列示年齡層、身份背景、預估服務人數與選案依據，以確保資源配置精準。",
            "執行方式": "執行方式應包含服務流程、分工架構、資源配置、合作單位與各階段工作項目，並說明如何確保服務品質與持續性。",
            "預期效益": "預期效益需同時呈現量化指標（如服務人次、達成率）與質化成果（如滿意度、改善情形），並對應計畫目標逐項說明。",
            "經費概算": "經費概算應依補助規定拆分人事費、業務費與雜支，逐項說明用途、估算依據與金額配置比例，確保符合補助上限與核銷規定。",
            "風險與因應": "風險評估應涵蓋人力、經費、服務對象參與度與執行期程等面向，並為每項風險提出具體因應措施與責任分工。",
        }
        return mapping.get(title, "請補充本章節內容，並以正式公文語氣撰寫完整段落說明。")

    @classmethod
    def full(cls, title, background, issues, goals) -> str:
        norm = TextNormalizer.normalize
        lines = [f"計畫名稱：{norm(title) or '未命名計畫'}"]
        for section in SectionRegistry.SECTIONS:
            lines.append(f"{section.order}、{section.title}")
            lines.append(cls.section_body(section.title, title, background, issues, goals))
        return "\n".join(lines)


class ChatFallback:
    RULES = (
        (["服務對象", "族群", "對象", "受眾"], "請先明確列出服務對象的年齡層、身份背景與目前面臨的困難，這樣後續目標與服務方法會更精準。"),
        (["目標", "預期", "成效", "成果", "指標"], "成果指標建議分成數量、品質與時程三類，例如服務人次、滿意度、改善率與完成期限。"),
        (["預算", "經費", "費用", "成本"], "經費規劃可先拆成人事費、業務費與雜支，再依補助規定補上金額與比例。"),
        (["風險", "困難", "挑戰", "問題"], "風險可先從人力、經費、對象參與與執行期程四個面向整理，再為每項安排對應措施。"),
        (["時程", "期程", "多久", "期限"], "常見做法是分成籌備期、執行期與評估期三段，並標示每一階段的月數與主要工作。"),
        (["補助", "申請", "案件", "方案"], "請提供補助名稱、申請期限與服務重點，我可以幫您把內容整理成更接近正式送件格式。"),
    )

    @classmethod
    def reply(cls, user_input: str, history: list) -> str:
        lower = TextNormalizer.normalize(user_input).lower()
        for keywords, answer in cls.RULES:
            if any(k in lower for k in keywords):
                return answer
        if len(history) < 4:
            return "您好，請先簡單說明組織背景、服務族群與申請目的，我會依序幫您補齊企劃內容。"
        return "請補充目前可運用的資源、服務方式與期望成效，我會協助整理成更完整的企劃書。"
