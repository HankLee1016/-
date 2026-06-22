class TextNormalizer:
    @staticmethod
    def normalize(value) -> str:
        return " ".join(str(value or "").split())


class TextPolisher:
    REPLACEMENTS = {
        "很": "非常", "有點": "稍微", "幫忙": "協助", "要": "應",
        "可以": "可", "就": "", "會": "將", "還有": "此外", "如果": "若",
        "這樣": "如此", "問題": "議題", "成果": "成效", "比較": "較",
        "但": "然而", "而且": "並且", "不是": "非",
    }

    @classmethod
    def polish(cls, text: str) -> str:
        if not text:
            return ""
        cleaned = " ".join(text.replace("\n", " ").replace("　", " ").split())
        for old, new in cls.REPLACEMENTS.items():
            cleaned = cleaned.replace(old, new)
        cleaned = cleaned.strip()
        if cleaned and cleaned[-1] not in "。！？":
            cleaned += "。"
        return cleaned
