from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_iterations import audit
from measure_edit import measure


def test_final_no_change_requires_human_convergence_decision() -> None:
    baseline = "# 제목\n\n첫 문장이다.\n"
    revised = "# 제목\n\n첫 문장이다. 둘째 문장이다.\n"
    result = audit(baseline, [("pass-1", revised), ("pass-2", revised)])

    assert result["status"] == "기계 확인 완료"
    assert result["warnings"] == []
    assert result["versions"][-1]["same_as_previous"] is True
    assert result["requires_human_convergence_decision"] is True
    assert result["baseline"]["sha256"]


def test_change_after_no_change_requires_review() -> None:
    baseline = "# 제목\n\n첫 문장이다.\n"
    revised = "# 제목\n\n고친 문장이다.\n"
    changed_again = "# 제목\n\n다시 고친 문장이다.\n"
    result = audit(
        baseline,
        [("pass-1", revised), ("pass-2", revised), ("pass-3", changed_again)],
    )

    assert result["status"] == "사람 검토"
    assert "무수정 회차 뒤 본문이 다시 변경됨—새 edit 근거 확인 필요" in result["warnings"]


def test_markdown_structure_change_requires_review() -> None:
    baseline = "# 제목\n\n본문이다.\n"
    revised = "## 제목 변경\n\n본문이다.\n"
    result = audit(baseline, [("pass-1", revised), ("pass-2", revised)])

    assert result["status"] == "사람 검토"
    assert "baseline 대비 Markdown 구조가 달라짐" in result["warnings"]


def test_sentence_insertion_counts_as_change() -> None:
    result = measure("첫 문장이다.\n", "첫 문장이다. 둘째 문장이다.\n")

    assert result["changed_sentence_slots"] == 1


def test_exact_return_to_earlier_version_flags_oscillation() -> None:
    result = audit(
        "A\n",
        [("pass-1", "B\n"), ("pass-2", "A\n"), ("pass-3", "B\n")],
    )

    assert result["status"] == "사람 검토"
    assert "본문이 이전 회차의 동일 상태로 되돌아감—표현 왕복 근거 확인 필요" in result["warnings"]
    assert result["oscillations"] == [
        {"current": "pass-2", "returned_to": "baseline"},
        {"current": "pass-3", "returned_to": "pass-1"},
    ]
