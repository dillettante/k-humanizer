#!/usr/bin/env python3
"""Audit whether every ambiguous term occurrence has a recorded local decision."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from audit_term_migration import ALLOWED_SCOPES, read_manifest, scope_mask, validate_documents
from protected_spans import overlaps_protected, protected_spans


DECISIONS = {"replace", "preserve", "ask"}


def locate(text: str, phrase: str, line: int, occurrence: int) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        return None
    start = sum(len(item) for item in lines[: line - 1])
    matches = list(re.finditer(re.escape(phrase), lines[line - 1]))
    if occurrence < 1 or occurrence > len(matches):
        return None
    match = matches[occurrence - 1]
    return start + match.start(), start + match.end()


def validate_map(payload: dict[str, object]) -> list[dict[str, object]]:
    if payload.get("schema_version") != "0.1":
        raise ValueError("sense map schema_version must be 0.1")
    terms = payload.get("terms")
    if not isinstance(terms, list) or not terms:
        raise ValueError("sense map requires a non-empty terms list")
    identifiers: set[str] = set()
    validated: list[dict[str, object]] = []
    for number, raw in enumerate(terms, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"term {number} must be an object")
        identifier = raw.get("id")
        forms = raw.get("forms")
        senses = raw.get("senses")
        occurrences = raw.get("occurrences")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
            raise ValueError(f"term {number} requires a unique id")
        if not isinstance(forms, list) or not forms or any(not isinstance(item, str) or not item.strip() for item in forms):
            raise ValueError(f"term {identifier} requires non-empty forms")
        if len(set(forms)) != len(forms):
            raise ValueError(f"term {identifier} forms contain duplicates")
        if not isinstance(senses, list) or not senses:
            raise ValueError(f"term {identifier} requires senses")
        sense_ids: set[str] = set()
        for sense in senses:
            if not isinstance(sense, dict) or not isinstance(sense.get("id"), str) or not sense["id"].strip() or not isinstance(sense.get("definition"), str) or not sense["definition"].strip():
                raise ValueError(f"term {identifier} senses require id and definition")
            if sense["id"] in sense_ids:
                raise ValueError(f"term {identifier} sense ids must be unique")
            sense_ids.add(sense["id"])
        if not isinstance(occurrences, list) or not occurrences:
            raise ValueError(f"term {identifier} requires occurrences")
        normalized: list[dict[str, object]] = []
        coordinates: set[tuple[str, str, int, int, str]] = set()
        for position, item in enumerate(occurrences, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"term {identifier} occurrence {position} must be an object")
            document_id = item.get("document_id")
            scope = item.get("scope")
            line = item.get("line")
            occurrence = item.get("occurrence", 1)
            form = item.get("form")
            sense = item.get("sense")
            decision = item.get("decision")
            rationale = item.get("rationale")
            after = item.get("after")
            after_line = item.get("after_line")
            after_occurrence = item.get("after_occurrence")
            if not isinstance(document_id, str) or not document_id.strip() or scope not in ALLOWED_SCOPES:
                raise ValueError(f"term {identifier} occurrence {position} requires document_id and scope")
            if not isinstance(line, int) or isinstance(line, bool) or line < 1 or not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 1:
                raise ValueError(f"term {identifier} occurrence {position} requires positive line and occurrence")
            if form not in forms or sense not in sense_ids or decision not in DECISIONS:
                raise ValueError(f"term {identifier} occurrence {position} has unknown form, sense, or decision")
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValueError(f"term {identifier} occurrence {position} requires rationale")
            if decision == "replace" and (not isinstance(after, str) or not after.strip()):
                raise ValueError(f"term {identifier} replace occurrence {position} requires after")
            if decision != "replace" and after is not None:
                raise ValueError(f"term {identifier} non-replace occurrence {position} must omit after")
            has_after_coordinate = isinstance(after_line, int) and not isinstance(after_line, bool) and after_line >= 1 and isinstance(after_occurrence, int) and not isinstance(after_occurrence, bool) and after_occurrence >= 1
            if decision in {"replace", "preserve"} and not has_after_coordinate:
                raise ValueError(f"term {identifier} {decision} occurrence {position} requires positive after_line and after_occurrence")
            if decision == "ask" and (after_line is not None or after_occurrence is not None):
                raise ValueError(f"term {identifier} ask occurrence {position} must omit after_line and after_occurrence")
            coordinate = (document_id, str(scope), line, occurrence, str(form))
            if coordinate in coordinates:
                raise ValueError(f"term {identifier} occurrence {position} duplicates a coordinate")
            coordinates.add(coordinate)
            normalized.append(dict(item))
        identifiers.add(identifier)
        validated.append({"id": identifier, "forms": forms, "senses": senses, "occurrences": normalized})
    return validated


def audit_corpus(documents: list[dict[str, object]], sense_map: dict[str, object]) -> dict[str, object]:
    documents = validate_documents(documents)
    terms = validate_map(sense_map)
    document_by_id = {str(document["id"]): document for document in documents}
    failures: list[str] = []
    rows: list[dict[str, object]] = []
    for term in terms:
        declared: set[tuple[str, str, int, int, str]] = set()
        occurrence_rows: list[dict[str, object]] = []
        asks = 0
        for item in term["occurrences"]:
            document_id = str(item["document_id"])
            scope = str(item["scope"])
            form = str(item["form"])
            coordinate = (document_id, scope, int(item["line"]), int(item.get("occurrence", 1)), form)
            declared.add(coordinate)
            document = document_by_id.get(document_id)
            before_span = after_span = None
            problem = ""
            if document is None or scope not in document["scopes"]:
                problem = "문서 또는 scope가 manifest에 없음"
            else:
                before_view = scope_mask(str(document["before"]), scope)
                after_view = scope_mask(str(document["after"]), scope)
                before_span = locate(before_view, form, int(item["line"]), int(item.get("occurrence", 1)))
                if before_span is None:
                    problem = "변경 전 좌표에서 기존어를 찾지 못함"
                elif overlaps_protected(before_span[0], before_span[1], protected_spans(before_view)):
                    problem = "보호 구간 용례는 기존 term map 예외로 처리해야 함"
                elif item["decision"] != "ask":
                    expected = str(item.get("after", form))
                    after_span = locate(after_view, expected, int(item.get("after_line", 0)), int(item.get("after_occurrence", 0)))
                    if after_span is None:
                        problem = "변경 후 좌표에서 결정 표기를 찾지 못함"
            if problem:
                failures.append(f"{term['id']}: {document_id}:{item['line']} {problem}")
            if item["decision"] == "ask":
                asks += 1
            occurrence_rows.append({**item, "status": "확인" if not problem else "보류", "problem": problem})

        discovered: set[tuple[str, str, int, int, str]] = set()
        for document in documents:
            document_id = str(document["id"])
            for scope in document["scopes"]:
                view = scope_mask(str(document["before"]), str(scope))
                protected = protected_spans(view)
                for form in term["forms"]:
                    offset = 0
                    for line_number, line in enumerate(view.splitlines(keepends=True), start=1):
                        for ordinal, match in enumerate(re.finditer(re.escape(str(form)), line), start=1):
                            start = offset + match.start()
                            if not overlaps_protected(start, start + len(str(form)), protected):
                                discovered.add((document_id, str(scope), line_number, ordinal, str(form)))
                        offset += len(line)
        undeclared = sorted(discovered - declared)
        stale = sorted(declared - discovered)
        if undeclared:
            failures.append(f"{term['id']}: 결정 대장에 없는 기존어 용례 {len(undeclared)}건")
        if stale:
            failures.append(f"{term['id']}: 기존어가 아닌 대장 좌표 {len(stale)}건")
        if asks:
            failures.append(f"{term['id']}: ask 결정 {asks}건이 남음")
        rows.append({"id": term["id"], "occurrences": occurrence_rows, "discovered_count": len(discovered), "undeclared": [list(item) for item in undeclared], "stale": [list(item) for item in stale], "ask_count": asks})
    return {"schema_version": "0.1", "kind": "selective-terminology-audit", "status": "기계 확인 완료" if not failures else "보류", "terms": rows, "failures": failures, "limit": "정확 좌표의 용례 결정 완결성과 지정 표기만 확인한다. 개념 분류·연어·의미 보존·문법 적합성은 사람이 판정한다."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sense-map", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.sense_map.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("sense map root must be an object")
        result = audit_corpus(read_manifest(args.manifest), payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"selective terminology audit failed: {error}")
        return 1
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "기계 확인 완료" else 2


if __name__ == "__main__":
    raise SystemExit(main())
