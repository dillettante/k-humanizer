from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from verify_strength_ledger import verify_strength_ledger


def ledger() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "strengths": [
            {
                "id": "rough-line",
                "baseline_text": "의자는 비를 조금씩 기억하고 있었다.",
                "position": "첫 문단 둘째 문장",
                "function": "사물에 남은 시간을 한 문장에 압축한다.",
                "surface_cost": "사물 주어와 기억 술어의 결합이 낯설다.",
                "risk_if_smoothed": "평범한 상태 설명으로 바뀐다.",
                "policy": "exact",
            }
        ],
        "sequences": [
            {
                "id": "delayed-recognition",
                "baseline_anchors": ["처음에는", "사흘 뒤", "그제야"],
                "candidate_anchors": ["처음에는", "사흘 뒤", "그제야"],
                "function": "판단이 뒤늦게 형성된다.",
                "review": "preserved",
                "reviewer_note": "세 계기가 같은 순서와 간격으로 남았다.",
            }
        ],
    }


def test_exact_strength_and_ordered_sequence_are_recorded() -> None:
    text = "처음에는 지나쳤다. 의자는 비를 조금씩 기억하고 있었다. 사흘 뒤 멈췄다. 그제야 알았다."
    result = verify_strength_ledger(text, text, ledger())

    assert result["status"] == "사람 판정 기록"
    assert result["failures"] == []
    assert result["requires_human_strength_decision"] is True


def test_smoothing_and_early_answer_are_held() -> None:
    baseline = "처음에는 지나쳤다. 의자는 비를 조금씩 기억하고 있었다. 사흘 뒤 멈췄다. 그제야 알았다."
    candidate = "그제야 알았다. 처음에는 지나쳤다. 의자는 젖어 있었다. 사흘 뒤 멈췄다."
    result = verify_strength_ledger(baseline, candidate, ledger())

    assert result["status"] == "보류"
    assert "rough-line: exact strength missing from candidate" in result["failures"]
    assert "delayed-recognition: candidate anchors missing or out of order" in result["failures"]


def test_ask_policy_cannot_be_closed_by_the_machine() -> None:
    text = "이 문장은 일부러 조금 걸린다."
    ask_ledger = {
        "schema_version": "0.1",
        "strengths": [
            {
                "id": "possible-roughness",
                "baseline_text": text,
                "position": "첫 문장",
                "function": "의도 확인이 필요하다.",
                "surface_cost": "짧은 문장이 한 번 걸린다.",
                "risk_if_smoothed": "호흡을 잃을 수 있다.",
                "policy": "ask",
            }
        ],
    }

    result = verify_strength_ledger(text, text, ask_ledger)

    assert result["status"] == "보류"
    assert result["failures"] == ["possible-roughness: author decision required"]


def test_functional_strength_requires_a_located_human_decision() -> None:
    baseline = "대답은 오지 않았다. 그래서 질문을 접지 않았다."
    candidate = "대답이 없었다. 질문은 그대로 두었다."
    functional_ledger = {
        "schema_version": "0.1",
        "strengths": [
            {
                "id": "unclosed-question",
                "baseline_text": baseline,
                "candidate_text": candidate,
                "position": "전문",
                "function": "질문을 결론으로 봉합하지 않는다.",
                "surface_cost": "결말이 설명 없이 멈춘다.",
                "risk_if_smoothed": "일반적인 교훈이 덧붙는다.",
                "policy": "functional",
                "review": "preserved",
                "reviewer_note": "후보도 질문을 답으로 바꾸지 않았다.",
            }
        ],
    }

    result = verify_strength_ledger(baseline, candidate, functional_ledger)

    assert result["status"] == "사람 판정 기록"
    assert result["failures"] == []


def test_ordered_anchors_do_not_hide_sequence_compression() -> None:
    baseline = "처음에는 지나쳤다.\n\n사흘 뒤 얼룩을 보았다.\n\n그제야 사람이 머문 줄 알았다."
    candidate = "처음에는 지나쳤지만 사흘 뒤 얼룩을 보고 그제야 사람이 머문 줄 알았다."
    result = verify_strength_ledger(baseline, candidate, ledger())

    assert result["status"] == "보류"
    assert "delayed-recognition: sequence layout compressed; compression review required" in result["failures"]
    assert result["sequences"][0]["baseline_ordered"] is True
    assert result["sequences"][0]["candidate_ordered"] is True
    assert result["sequences"][0]["layout_compressed"] is True


def test_sequence_compression_can_only_close_with_a_separate_human_reason() -> None:
    baseline = "처음에는 지나쳤다.\n\n사흘 뒤 얼룩을 보았다.\n\n그제야 사람이 머문 줄 알았다."
    candidate = "처음에는 지나쳤다. 사흘 뒤 얼룩을 보았다. 그제야 사람이 머문 줄 알았다."
    sequence_only = {
        "schema_version": "0.1",
        "sequences": [
            {
                "id": "delayed-recognition",
                "baseline_anchors": ["처음에는", "사흘 뒤", "그제야"],
                "candidate_anchors": ["처음에는", "사흘 뒤", "그제야"],
                "function": "판단이 뒤늦게 형성된다.",
                "review": "preserved",
                "reviewer_note": "세 단계의 관찰과 결론이 남았다.",
                "compression_review": "preserved",
                "compression_note": "문단만 합쳤고 각 단계는 독립 문장으로 유지했다.",
            }
        ],
    }

    result = verify_strength_ledger(baseline, candidate, sequence_only)

    assert result["status"] == "사람 판정 기록"
    assert result["failures"] == []
    assert result["sequences"][0]["compression_review"] == "preserved"
