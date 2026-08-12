from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_selective_terms import audit_corpus, validate_map


DOCUMENTS = [
    {
        "id": "chapter-1",
        "scopes": ["body"],
        "before": "기존 글을 줄이지 않는다.\n기존 글의 출처를 찾는다.\n",
        "after": "기존 글을 줄이지 않는다.\n최초 출처를 찾는다.\n",
    }
]


SENSE_MAP = {
    "schema_version": "0.1",
    "terms": [
        {
            "id": "source-text",
            "forms": ["기존 글"],
            "senses": [
                {"id": "full-text", "definition": "축약 전의 글 전체"},
                {"id": "first-source", "definition": "재인용 전 최초 출처"},
            ],
            "occurrences": [
                {"document_id": "chapter-1", "scope": "body", "line": 1, "occurrence": 1, "after_line": 1, "after_occurrence": 1, "form": "기존 글", "sense": "full-text", "decision": "preserve", "rationale": "분량 축의 뜻"},
                {"document_id": "chapter-1", "scope": "body", "line": 2, "occurrence": 1, "after_line": 2, "after_occurrence": 1, "form": "기존 글", "sense": "first-source", "decision": "replace", "after": "최초 출처", "rationale": "출처 차수의 뜻"},
            ],
        }
    ],
}


def test_selective_term_audit_requires_a_decision_for_every_occurrence() -> None:
    result = audit_corpus(DOCUMENTS, SENSE_MAP)

    assert result["status"] == "기계 확인 완료"
    assert result["terms"][0]["discovered_count"] == 2


def test_undeclared_ambiguous_occurrence_blocks_completion() -> None:
    partial = {**SENSE_MAP, "terms": [{**SENSE_MAP["terms"][0], "occurrences": SENSE_MAP["terms"][0]["occurrences"][:1]}]}
    result = audit_corpus(DOCUMENTS, partial)

    assert result["status"] == "보류"
    assert any("결정 대장에 없는 기존어 용례 1건" in item for item in result["failures"])


def test_ask_decision_keeps_result_on_hold() -> None:
    pending = {
        **SENSE_MAP,
        "terms": [
            {
                **SENSE_MAP["terms"][0],
                "occurrences": [
                    {key: value for key, value in {**SENSE_MAP["terms"][0]["occurrences"][0], "decision": "ask"}.items() if key not in {"after_line", "after_occurrence"}},
                    SENSE_MAP["terms"][0]["occurrences"][1],
                ],
            }
        ],
    }
    result = audit_corpus(DOCUMENTS, pending)

    assert result["status"] == "보류"
    assert result["terms"][0]["ask_count"] == 1


def test_invalid_selective_map_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires after"):
        validate_map(
            {
                **SENSE_MAP,
                "terms": [
                    {
                        **SENSE_MAP["terms"][0],
                        "occurrences": [{**SENSE_MAP["terms"][0]["occurrences"][0], "decision": "replace"}],
                    }
                ],
            }
        )


def test_after_coordinates_handle_two_decisions_on_one_line() -> None:
    documents = [
        {
            "id": "chapter-1",
            "scopes": ["body"],
            "before": "기존 글과 기존 글을 구분한다.\n",
            "after": "최초 출처와 기존 글을 구분한다.\n",
        }
    ]
    sense_map = {
        **SENSE_MAP,
        "terms": [
            {
                **SENSE_MAP["terms"][0],
                "occurrences": [
                    {**SENSE_MAP["terms"][0]["occurrences"][1], "line": 1, "occurrence": 1, "after_line": 1, "after_occurrence": 1},
                    {**SENSE_MAP["terms"][0]["occurrences"][0], "line": 1, "occurrence": 2, "after_line": 1, "after_occurrence": 1},
                ],
            }
        ],
    }

    assert audit_corpus(documents, sense_map)["status"] == "기계 확인 완료"
