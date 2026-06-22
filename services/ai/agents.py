AI_AGENTS = [
    {"name": "企劃師小智", "description": "專注策略、落地執行與協調資源，適合需要具體方案的個案。"},
    {"name": "社服諮詢官", "description": "擅長需求分析與風險檢視，適合有情緒、家庭或心理層面議題的個案。"},
    {"name": "資源協調員", "description": "側重整合在地支持與長期追蹤，適合希望建立持續支持網絡的個案。"},
]


class AgentSelector:
    @staticmethod
    def choose(background: str, issues: str) -> dict:
        combined = f"{background} {issues}".lower()
        if any(k in combined for k in ["家庭", "親子", "孩童", "青少", "情緒", "心理"]):
            return AI_AGENTS[1]
        if any(k in combined for k in ["工作", "就業", "收入", "經濟", "社區"]):
            return AI_AGENTS[2]
        return AI_AGENTS[0]
