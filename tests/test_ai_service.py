"""1-A 煙霧測試：mock 模式企劃生成與檢核。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AI_MOCK_MODE", "true")

from services.ai import proposal_service, chat_service
from services.ai.sections import SectionRegistry
from services.ai.validator import ProposalValidator
from services.ai.config import AIConfig


def test_mock_proposal():
    result = proposal_service.generate(
        "社區關懷計畫",
        "本會長期服務弱勢家庭。",
        "高齡獨居長者缺乏照護資源。",
        "提升服務覆蓋率並建立志工網絡。",
    )
    assert result.text
    assert result.source == "mock"
    assert result.within_timeout
    for header in SectionRegistry.headers():
        assert header in result.text, f"缺少章節：{header}"
    print(f"[OK] mock 企劃生成 {result.elapsed_ms}ms, source={result.source}")


def test_validator_repair():
    config = AIConfig.from_env()
    v = ProposalValidator(config)
    broken = "一、計畫緣起\n太短。"
    fixed = v.repair(broken, "測試", "背景", "問題", "目標")
    check = v.validate(fixed)
    assert check.ok, f"修補後仍不合格: missing={check.missing}, short={check.short}"
    print("[OK] 破損草稿修補通過")


def test_chat_fallback():
    reply = chat_service.reply("請幫我規劃經費", [], "")
    assert "經費" in reply or "人事費" in reply
    print(f"[OK] 對話 fallback: {reply[:40]}...")


if __name__ == "__main__":
    test_mock_proposal()
    test_validator_repair()
    test_chat_fallback()
    print("全部 1-A 煙霧測試通過。")
