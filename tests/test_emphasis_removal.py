from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_emphasis_removal import audit  # noqa: E402


def test_audit_finds_bare_labels_and_consecutive_run() -> None:
    before = """**자료.** 숫자를 모은다.

**분류.** 기준대로 나눈다.

**검증.** 원문과 맞춘다.
"""
    after = before.replace("**", "")

    result = audit(before, after)

    assert result["finding_count"] == 3
    assert [item["label"] for item in result["findings"]] == ["자료", "분류", "검증"]
    assert result["consecutive_label_runs"] == [{"start_paragraph": 1, "end_paragraph": 3, "count": 3}]


def test_audit_excludes_full_sentences_and_unrelated_rewrites() -> None:
    before = "**이것이 결론이다.**\n\n**질문.** 무엇을 확인할까?"
    after = "이것이 결론이다.\n\n질문을 바꾸었다. 무엇을 확인할까?"

    result = audit(before, after)

    assert result["finding_count"] == 0


def test_audit_does_not_treat_retained_bold_as_removal() -> None:
    text = "**핵심.** 이 표지는 그대로 둔다."

    assert audit(text, text)["finding_count"] == 0
