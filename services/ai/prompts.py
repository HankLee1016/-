from .sections import SectionRegistry
from .text_utils import TextNormalizer


class ProposalPromptBuilder:
    SYSTEM = (
        "你是政府補助計畫書撰寫助手。請以正式、公文式、可送件的語氣撰寫，"
        "內容需穩定、分段清楚、避免口語化、避免重複，並優先使用使用者提供的資訊。"
        "請嚴格遵守下列格式要求：\n"
        "1. 以「一、」「二、」等標題列出各章節，章節名稱需固定且一致。\n"
        "2. 每一章需有具體段落，避免只列點不說明。\n"
        "3. 內容必須補足計畫可送件所需的基本要素，不可留下空白章節。\n"
        "4. 語氣需正式、穩定、客觀，避免宣傳式、聊天式或推測式語句。"
    )

    def build(self, title, background, issues, goals) -> tuple[str, str]:
        norm = TextNormalizer.normalize
        user = (
            f"計畫名稱：{norm(title)}\n"
            f"計畫背景：{norm(background)}\n"
            f"主要問題：{norm(issues)}\n"
            f"計畫目標：{norm(goals)}\n\n"
            "請輸出完整企劃草案，並嚴格依下列章節順序撰寫：\n"
            f"{SectionRegistry.prompt_outline()}\n\n"
            "「執行目標」需整合問題分析與預期成效；"
            "「服務對象」需說明年齡層、身份背景與服務規模；"
            "「經費概算」需依人事費、業務費、雜支分項說明。"
        )
        return self.SYSTEM, user


class ChatPromptBuilder:
    SYSTEM = (
        "你是補助企劃書優化助理，任務是協助使用者補強、潤飾與結構化企劃內容。"
        "回覆須正式、精簡、可寫入送件文件，避免閒聊。"
        "若資訊不足，請指出需補充的欄位與建議寫法。"
    )

    def build_system(self, subsidy_summary: str = "") -> str:
        if not subsidy_summary:
            return self.SYSTEM
        return f"{self.SYSTEM}\n\n使用者選定補助方案摘要：\n{subsidy_summary}"

    def build_messages(self, user_input, history, subsidy_summary="") -> list[dict]:
        norm = TextNormalizer.normalize
        messages = [{"role": "system", "content": self.build_system(subsidy_summary)}]
        for item in history:
            content = norm(item.get("content", ""))
            if content:
                messages.append({"role": item.get("role", "user"), "content": content})
        messages.append({"role": "user", "content": norm(user_input)})
        return messages
