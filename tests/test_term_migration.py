from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_term_migration import audit, audit_corpus, validate_term_map


TERM_MAP = {
    "schema_version": "0.1",
    "terms": [
        {
            "id": "review-order",
            "source": "review hierarchy",
            "old": ["검토 위계"],
            "new": "검토 순서",
            "scope": ["body"],
            "exceptions": [],
            "rationale": "서열보다 적용 차례를 뜻함",
        }
    ],
}


def test_reports_component_echo_after_migration() -> None:
    result = audit(
        "검토 위계는 항목을 적용하는 기준이다.",
        "검토 순서는 항목을 검토하는 순서다.",
        TERM_MAP,
    )

    assert result["status"] == "기계 확인 완료"
    assert result["residue_count"] == 0
    assert result["echo_candidate_count"] == 2
    echoes = result["terms"][0]["documents"][0]["scope_results"][0]["echo_candidates"]
    assert {item["component"] for item in echoes} == {"검토", "순서"}
    assert result["requires_human_context_review"] is True


def test_residual_old_term_blocks_mechanical_completion() -> None:
    result = audit(
        "검토 위계를 따른다.",
        "본문은 검토 순서를 따르지만 표에는 검토 위계가 남았다.",
        TERM_MAP,
    )

    assert result["status"] == "보류"
    assert result["residue_count"] == 1
    assert result["terms"][0]["documents"][0]["scope_results"][0]["residues"]["검토 위계"][0]["line"] == 1


def test_clean_migration_still_requires_human_collocation_review() -> None:
    result = audit(
        "검토 위계를 따른다.",
        "항목은 검토 순서에 따라 살핀다.",
        TERM_MAP,
    )

    assert result["status"] == "기계 확인 완료"
    assert result["echo_candidate_count"] == 0
    assert result["terms"][0]["requires_human_collocation_review"] is True


def test_term_map_rejects_same_old_and_new_value() -> None:
    with pytest.raises(ValueError, match="must not also be an old value"):
        validate_term_map({"schema_version": "0.1", "terms": [{"id": "bad", "old": ["같은 말"], "new": "같은 말", "scope": ["body"], "rationale": "시험"}]})


def test_protected_quote_and_exact_exception_do_not_count_as_residue() -> None:
    term_map = {
        **TERM_MAP,
        "terms": [
            {
                **TERM_MAP["terms"][0],
                "exceptions": [
                    {
                        "text": "과거 문서는 검토 위계라고 불렀다",
                        "reason": "역사적 명칭",
                        "document_id": "single-input",
                        "scope": "body",
                        "line": 1,
                        "occurrence": 1
                    }
                ],
            }
        ],
    }
    result = audit(
        "검토 위계를 따른다. 과거 문서는 검토 위계라고 불렀다.",
        "검토 순서를 따른다. 과거 문서는 검토 위계라고 불렀다. “검토 위계”는 직접 인용이다.",
        term_map,
    )

    assert result["status"] == "기계 확인 완료"
    assert result["residue_count"] == 0
    protected = result["terms"][0]["documents"][0]["scope_results"][0]["protected_or_excepted_residues"]["검토 위계"]
    assert len(protected) == 2


def test_old_value_inside_new_value_is_not_residue() -> None:
    term_map = {
        "schema_version": "0.1",
        "terms": [
            {"id": "qualified-review", "old": ["검토"], "new": "검토 순서", "scope": ["body"], "exceptions": [], "rationale": "행위보다 절차 개념을 뜻함"}
        ],
    }
    result = audit("검토를 따른다.", "검토 순서를 따른다.", term_map)

    assert result["status"] == "기계 확인 완료"
    assert result["residue_count"] == 0


def test_deleting_old_sentence_while_reusing_existing_new_term_is_blocked() -> None:
    result = audit(
        "검토 위계는 A다. 검토 순서는 B다.",
        "검토 순서는 B다.",
        TERM_MAP,
    )

    assert result["status"] == "보류"
    assert result["terms"][0]["replacement_gap"] == 1


def test_missing_scope_blocks_completion() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["body", "glossary"]}]}
    result = audit("검토 위계를 따른다.", "검토 순서를 따른다.", term_map)

    assert result["status"] == "보류"
    assert result["terms"][0]["missing_scopes"] == ["glossary"]


def test_manifest_like_corpus_covers_multiple_scopes() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["body", "glossary"]}]}
    result = audit_corpus(
        [
            {"id": "chapter", "scopes": ["body"], "before": "검토 위계를 따른다.", "after": "검토 순서를 따른다."},
            {"id": "glossary", "scopes": ["glossary"], "before": "검토 위계: 적용 기준.", "after": "검토 순서: 적용 기준."},
        ],
        term_map,
    )

    assert result["status"] == "기계 확인 완료"
    assert result["covered_scopes"] == ["body", "glossary"]


def test_compound_components_can_be_declared_and_line_break_is_not_boundary() -> None:
    term_map = {
        "schema_version": "0.1",
        "terms": [
            {
                "id": "disclosure",
                "old": ["공개 체계"],
                "new": "정보공개",
                "components": ["정보", "공개"],
                "scope": ["body"],
                "exceptions": [],
                "rationale": "정식 제도명",
            }
        ],
    }
    result = audit("공개 체계를 설명한다.", "정보공개는 정보를\n공개하는 절차다.", term_map)

    assert result["status"] == "기계 확인 완료"
    echoes = result["terms"][0]["documents"][0]["scope_results"][0]["echo_candidates"]
    assert {item["component"] for item in echoes} == {"정보", "공개"}


def test_schema_and_field_types_are_enforced() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        validate_term_map({"schema_version": "999", "terms": TERM_MAP["terms"]})
    with pytest.raises(ValueError, match="scope"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "scope": "banana"}]})
    with pytest.raises(ValueError, match="exceptions"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "exceptions": "all"}]})
    with pytest.raises(ValueError, match="old must"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "old": [None]}]})
    with pytest.raises(ValueError, match="non-empty new"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "new": 123}]})
    with pytest.raises(ValueError, match="substrings of new"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "components": ["banana"]}]})
    with pytest.raises(ValueError, match="old contains duplicates"):
        validate_term_map({"schema_version": "0.1", "terms": [{**TERM_MAP["terms"][0], "old": ["검토 위계", "검토 위계"]}]})


def test_body_scope_does_not_scan_heading_residue() -> None:
    before = "# 검토 위계의 역사\n\n검토 위계를 따른다.\n"
    after = "# 검토 위계의 역사\n\n검토 순서를 따른다.\n"
    result = audit(before, after, TERM_MAP, scopes=["body", "heading"])

    assert result["status"] == "기계 확인 완료"
    assert result["residue_count"] == 0


def test_pipe_less_markdown_table_is_scanned_as_table() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["table"]}]}
    text = "용어 | 설명\n--- | ---\n검토 위계 | 기준\n"
    result = audit(text, text, term_map, scopes=["table"])

    assert result["status"] == "보류"
    assert result["residue_count"] == 1


def test_setext_heading_is_scanned_as_heading() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["heading"]}]}
    text = "검토 위계\n=========\n"
    result = audit(text, text, term_map, scopes=["heading"])

    assert result["status"] == "보류"
    assert result["residue_count"] == 1


def test_fenced_code_and_html_comments_are_not_body_terms() -> None:
    text = "````text\n```not-a-close\n검토 위계\n````\n<!-- 검토 위계 -->\n검토 순서를 따른다.\n"
    result = audit(text, text, TERM_MAP)

    assert result["status"] == "기계 확인 완료"
    assert result["residue_count"] == 0
    assert result["new_occurrences_total"] == 1


def test_inline_html_comment_does_not_hide_body_on_same_line() -> None:
    text = "검토 위계는 본문이다. <!-- 검토 위계는 주석이다. --> 다음 본문.\n"
    result = audit(text, text, TERM_MAP)

    assert result["status"] == "보류"
    assert result["residue_count"] == 1


def test_footnote_container_takes_precedence_over_nested_table_and_setext() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["footnote"]}]}
    table_note = "[^1]: 검토 위계 | 설명\n    --- | ---\n    A | B\n"
    setext_note = "[^1]: 검토 위계\n    --------\n"

    table_result = audit(table_note, table_note, term_map, scopes=["footnote", "table"])
    setext_result = audit(setext_note, setext_note, term_map, scopes=["footnote", "heading"])

    assert table_result["residue_count"] == 1
    assert setext_result["residue_count"] == 1


def test_atx_heading_is_not_overwritten_by_table_shape() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["heading"]}]}
    text = "# 검토 위계 | 설명\n--- | ---\nA | B\n"
    result = audit(text, text, term_map, scopes=["heading", "table"])

    assert result["status"] == "보류"
    assert result["residue_count"] == 1


def test_replacement_gap_is_enforced_per_document() -> None:
    result = audit_corpus(
        [
            {"id": "a", "scopes": ["body"], "before": "검토 위계를 설명한다.", "after": "설명을 지웠다."},
            {"id": "b", "scopes": ["body"], "before": "검토 순서를 따른다.", "after": "검토 순서와 검토 순서를 따른다."},
        ],
        TERM_MAP,
    )

    assert result["status"] == "보류"
    assert result["terms"][0]["documents"][0]["replacement_gap"] == 1


def test_replacement_gap_is_enforced_per_scope() -> None:
    term_map = {**TERM_MAP, "terms": [{**TERM_MAP["terms"][0], "scope": ["body", "heading"]}]}
    result = audit(
        "# 검토 순서\n\n본문에서 검토 위계를 설명한다.\n",
        "# 검토 순서와 검토 순서\n\n본문 설명을 지웠다.\n",
        term_map,
        scopes=["body", "heading"],
    )

    assert result["status"] == "보류"
    scope_rows = result["terms"][0]["documents"][0]["scope_results"]
    assert {row["scope"]: row["replacement_gap"] for row in scope_rows} == {"body": 1, "heading": 0}


def test_exception_masks_only_one_line_occurrence() -> None:
    term_map = {
        **TERM_MAP,
        "terms": [
            {
                **TERM_MAP["terms"][0],
                "exceptions": [
                    {
                        "text": "검토 위계",
                        "reason": "첫 줄은 역사적 명칭",
                        "document_id": "single-input",
                        "scope": "body",
                        "line": 1,
                        "occurrence": 1,
                    }
                ],
            }
        ],
    }
    result = audit("검토 위계.\n검토 위계.", "검토 위계.\n검토 위계.", term_map)

    assert result["status"] == "보류"
    assert result["residue_count"] == 1


def test_overlapping_old_variants_count_longest_once() -> None:
    term_map = {
        "schema_version": "0.1",
        "terms": [
            {
                "id": "overlap",
                "old": ["검토", "검토 위계"],
                "new": "검토 순서",
                "scope": ["body"],
                "exceptions": [],
                "rationale": "긴 표기를 정식 용어로 이관",
            }
        ],
    }
    result = audit("검토 위계를 따른다.", "검토 순서를 따른다.", term_map)

    assert result["status"] == "기계 확인 완료"
    assert result["terms"][0]["old_count_before"] == 1


def test_stale_exception_document_is_blocked() -> None:
    term_map = {
        **TERM_MAP,
        "terms": [
            {
                **TERM_MAP["terms"][0],
                "exceptions": [
                    {"text": "검토 위계", "reason": "시험", "document_id": "absent", "scope": "body", "line": 1}
                ],
            }
        ],
    }
    result = audit("검토 위계를 따른다.", "검토 순서를 따른다.", term_map)

    assert result["status"] == "보류"
    assert any("없는 문서" in failure for failure in result["failures"])


def test_exception_scope_outside_term_scope_is_blocked() -> None:
    term_map = {
        **TERM_MAP,
        "terms": [
            {
                **TERM_MAP["terms"][0],
                "exceptions": [
                    {"text": "검토 위계", "reason": "시험", "document_id": "single-input", "scope": "heading", "line": 1}
                ],
            }
        ],
    }
    result = audit("# 검토 위계\n\n검토 순서를 따른다.\n", "# 검토 위계\n\n검토 순서를 따른다.\n", term_map, scopes=["body", "heading"])

    assert result["status"] == "보류"
    assert any("용어 적용 scope 밖" in failure for failure in result["failures"])


def test_exception_coordinate_must_exist_before_and_after() -> None:
    term_map = {
        **TERM_MAP,
        "terms": [
            {
                **TERM_MAP["terms"][0],
                "exceptions": [
                    {"text": "검토 위계", "reason": "역사적 명칭", "document_id": "single-input", "scope": "body", "line": 2}
                ],
            }
        ],
    }
    result = audit("검토 위계를 역사적으로 설명한다.\n", "검토 위계를 역사적으로 설명한다.\n", term_map)

    assert result["status"] == "보류"
    phases = {item["phase"] for item in result["terms"][0]["unmatched_exceptions"]}
    assert phases == {"before", "after"}
