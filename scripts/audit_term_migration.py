#!/usr/bin/env python3
"""Audit terminology migration coverage and candidate side effects without rewriting."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from protected_spans import overlaps_protected, protected_spans


TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
SENTENCE = re.compile(r"[^.!?]+(?:[.!?]|$)")
ALLOWED_SCOPES = {"body", "glossary", "table", "heading", "footnote", "index"}


def validate_term_map(payload: dict[str, object]) -> list[dict[str, object]]:
    if payload.get("schema_version") != "0.1":
        raise ValueError("term map schema_version must be 0.1")
    terms = payload.get("terms")
    if not isinstance(terms, list) or not terms:
        raise ValueError("term map requires a non-empty terms list")

    validated: list[dict[str, object]] = []
    identifiers: set[str] = set()
    new_terms: set[str] = set()
    old_owners: dict[str, str] = {}
    for index, raw in enumerate(terms, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"term {index} must be an object")
        identifier_raw = raw.get("id")
        new_raw = raw.get("new")
        identifier = identifier_raw.strip() if isinstance(identifier_raw, str) else ""
        new = new_raw.strip() if isinstance(new_raw, str) else ""
        old_raw = raw.get("old")
        if isinstance(old_raw, str):
            old = [old_raw.strip()] if old_raw.strip() else []
        elif isinstance(old_raw, list) and all(isinstance(item, str) for item in old_raw):
            old = [item.strip() for item in old_raw if item.strip()]
        else:
            raise ValueError(f"term {identifier or index} old must be a non-empty string or list")
        scopes = raw.get("scope")
        exceptions = raw.get("exceptions", [])
        rationale_raw = raw.get("rationale")
        rationale = rationale_raw.strip() if isinstance(rationale_raw, str) else ""
        components_raw = raw.get("components")
        source = raw.get("source")
        do_not_use = raw.get("do_not_use", [])

        if not identifier or identifier in identifiers:
            raise ValueError(f"term {index} requires a unique id")
        if not new or new in new_terms:
            raise ValueError(f"term {identifier} requires a unique non-empty new value")
        if not old:
            raise ValueError(f"term {identifier} requires at least one old value")
        if len(set(old)) != len(old):
            raise ValueError(f"term {identifier} old contains duplicates")
        if new in old:
            raise ValueError(f"term {identifier} new value must not also be an old value")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(item, str) or item not in ALLOWED_SCOPES for item in scopes):
            raise ValueError(f"term {identifier} scope must be a non-empty list of supported scopes")
        if len(set(scopes)) != len(scopes):
            raise ValueError(f"term {identifier} scope contains duplicates")
        if not rationale:
            raise ValueError(f"term {identifier} requires rationale")
        if not isinstance(exceptions, list):
            raise ValueError(f"term {identifier} exceptions must be a list")
        if source is not None and not isinstance(source, str):
            raise ValueError(f"term {identifier} source must be a string or null")
        if not isinstance(do_not_use, list) or any(not isinstance(item, str) or not item.strip() for item in do_not_use):
            raise ValueError(f"term {identifier} do_not_use must be a list of strings")

        normalized_exceptions: list[dict[str, object]] = []
        for exception_index, exception in enumerate(exceptions, start=1):
            if not isinstance(exception, dict):
                raise ValueError(f"term {identifier} exception {exception_index} must be an object")
            text_raw = exception.get("text")
            reason_raw = exception.get("reason")
            document_raw = exception.get("document_id")
            scope_raw = exception.get("scope")
            line_raw = exception.get("line")
            occurrence_raw = exception.get("occurrence", 1)
            text = text_raw.strip() if isinstance(text_raw, str) else ""
            reason = reason_raw.strip() if isinstance(reason_raw, str) else ""
            document_id = document_raw.strip() if isinstance(document_raw, str) else ""
            if not text or not reason or not document_id:
                raise ValueError(f"term {identifier} exception {exception_index} requires text, reason, and document_id")
            if not isinstance(scope_raw, str) or scope_raw not in ALLOWED_SCOPES:
                raise ValueError(f"term {identifier} exception {exception_index} requires a supported scope")
            if not isinstance(line_raw, int) or isinstance(line_raw, bool) or line_raw < 1:
                raise ValueError(f"term {identifier} exception {exception_index} requires a positive line")
            if not isinstance(occurrence_raw, int) or isinstance(occurrence_raw, bool) or occurrence_raw < 1:
                raise ValueError(f"term {identifier} exception {exception_index} occurrence must be positive")
            normalized_exceptions.append(
                {"text": text, "reason": reason, "document_id": document_id, "scope": scope_raw, "line": line_raw, "occurrence": occurrence_raw}
            )

        if components_raw is None:
            components = sorted({token for token in TOKEN.findall(new) if len(token) >= 2})
        elif isinstance(components_raw, list) and components_raw and all(isinstance(item, str) and item.strip() for item in components_raw):
            components = sorted({item.strip() for item in components_raw})
        else:
            raise ValueError(f"term {identifier} components must be a non-empty list when provided")
        if any(component not in new for component in components):
            raise ValueError(f"term {identifier} components must be substrings of new")

        for old_value in old:
            owner = old_owners.get(old_value)
            if owner and owner != identifier:
                raise ValueError(f"old value {old_value} belongs to both {owner} and {identifier}")
            old_owners[old_value] = identifier
        identifiers.add(identifier)
        new_terms.add(new)
        validated.append(
            {
                **raw,
                "id": identifier,
                "old": old,
                "new": new,
                "scope": scopes,
                "exceptions": normalized_exceptions,
                "rationale": rationale,
                "components": components,
            }
        )
    return validated


def occurrence_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in re.finditer(re.escape(phrase), text)]


def exact_exception_spans(text: str, exceptions: list[dict[str, object]], document_id: str, scope: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    spans: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    for exception in exceptions:
        if exception["document_id"] != document_id or exception["scope"] != scope:
            continue
        text_value = str(exception["text"])
        line_number = int(exception["line"])
        occurrence = int(exception["occurrence"])
        lines = text.splitlines(keepends=True)
        if line_number > len(lines):
            unmatched.append({**exception, "problem": "line outside document"})
            continue
        line_start = sum(len(line) for line in lines[: line_number - 1])
        line_text = lines[line_number - 1]
        matches = list(re.finditer(re.escape(text_value), line_text))
        if occurrence > len(matches):
            unmatched.append({**exception, "problem": "occurrence not found on line"})
            continue
        match = matches[occurrence - 1]
        spans.append({"kind": "term-map-exception", "start": line_start + match.start(), "end": line_start + match.end(), "value": text_value})
    return spans, unmatched


def scope_mask(text: str, scope: str) -> str:
    lines = text.splitlines(keepends=True)
    kinds = ["body"] * len(lines)
    excluded = [False] * len(lines)

    # 자동 치환에서 손대면 안 되는 코드 펜스와 편집 주석은 모든 scope에서 뺀다.
    in_fence = False
    fence_marker = ""
    fence_length = 0
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})", stripped)
        if in_fence:
            excluded[index] = True
            closing = re.match(r"^\s*(`{3,}|~{3,})\s*$", line.rstrip("\r\n"))
            if closing and closing.group(1)[0] == fence_marker and len(closing.group(1)) >= fence_length:
                in_fence = False
            continue
        if fence:
            excluded[index] = True
            in_fence = True
            fence_marker = fence.group(1)[0]
            fence_length = len(fence.group(1))
            continue

    for index, line in enumerate(lines):
        if excluded[index]:
            continue
        stripped = line.lstrip()
        if re.match(r"#{1,6}[ \t]+", stripped):
            kinds[index] = "heading"
        if re.match(r"\[\^[^\]]+\]:", stripped):
            kinds[index] = "footnote"
            following = index + 1
            while following < len(lines) and (not lines[following].strip() or re.match(r"(?: {4}|\t)", lines[following])):
                kinds[following] = "footnote"
                following += 1

    # Setext 제목은 밑줄과 바로 앞 행을 하나의 heading으로 분류한다.
    for index in range(1, len(lines)):
        if excluded[index] or excluded[index - 1]:
            continue
        if (
            kinds[index] == "body"
            and kinds[index - 1] == "body"
            and re.match(r"^\s*(?:=+|-+)\s*$", lines[index].rstrip("\r\n"))
            and lines[index - 1].strip()
        ):
            kinds[index - 1] = "heading"
            kinds[index] = "heading"

    # 외곽 파이프가 없는 CommonMark 표도 구분자 행을 기준으로 블록 전체를 찾는다.
    separator = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
    for index, line in enumerate(lines):
        if excluded[index] or not separator.match(line.rstrip("\r\n")):
            continue
        if index > 0 and not excluded[index - 1] and kinds[index - 1] == "body" and re.search(r"(?<!\\)\|", lines[index - 1]):
            kinds[index - 1] = "table"
        if kinds[index] == "body":
            kinds[index] = "table"
        following = index + 1
        while following < len(lines) and not excluded[following] and lines[following].strip() and re.search(r"(?<!\\)\|", lines[following]):
            if kinds[following] == "body":
                kinds[following] = "table"
            following += 1

    pieces: list[str] = []
    for index, line in enumerate(lines):
        if not excluded[index] and (scope in {"glossary", "index"} or kinds[index] == scope):
            pieces.append(line)
        else:
            pieces.append("".join("\n" if char == "\n" else " " for char in line))
    if text and not text.endswith("\n") and not pieces:
        return " " * len(text)
    view = "".join(pieces)
    comment_spans = [
        {"start": match.start(), "end": match.end()}
        for match in re.finditer(r"<!--[\s\S]*?(?:-->|\Z)", text)
    ]
    return mask_spans(view, comment_spans)


def nonoverlapping_old_spans(text: str, phrases: list[str], exclusions: list[dict[str, object]]) -> dict[str, list[tuple[int, int]]]:
    candidates = [
        (start, end, phrase)
        for phrase in phrases
        for start, end in occurrence_spans(text, phrase)
        if not overlaps_protected(start, end, exclusions)
    ]
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    selected: list[tuple[int, int, str]] = []
    for candidate in candidates:
        start, end, _ = candidate
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end, _ in selected):
            continue
        selected.append(candidate)
    return {phrase: [(start, end) for start, end, selected_phrase in selected if selected_phrase == phrase] for phrase in phrases}


def contexts_for_spans(text: str, spans: list[tuple[int, int]], radius: int = 60) -> list[dict[str, object]]:
    return [
        {
            "start": start,
            "end": end,
            "line": text.count("\n", 0, start) + 1,
            "context": re.sub(r"\s+", " ", text[max(0, start - radius) : min(len(text), end + radius)]).strip(),
        }
        for start, end in spans
    ]


def filtered_spans(text: str, phrase: str, exclusions: list[dict[str, object]]) -> list[tuple[int, int]]:
    return [(start, end) for start, end in occurrence_spans(text, phrase) if not overlaps_protected(start, end, exclusions)]


def mask_spans(text: str, spans: list[dict[str, object]]) -> str:
    characters = list(text)
    for span in spans:
        for index in range(int(span["start"]), int(span["end"])):
            if characters[index] != "\n":
                characters[index] = " "
    return "".join(characters)


def containing_sentences(text: str, phrase: str) -> list[tuple[int, int, str]]:
    results: list[tuple[int, int, str]] = []
    for match in SENTENCE.finditer(text):
        sentence = re.sub(r"\s+", " ", match.group(0)).strip()
        if phrase in sentence:
            results.append((match.start(), match.end(), sentence))
    return results


def echo_candidates(text: str, term: str, components: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for start, end, sentence in containing_sentences(text, term):
        term_count = sentence.count(term)
        if term_count > 1:
            results.append({"kind": "full-term-repeat", "component": term, "count": term_count, "line": text.count("\n", 0, start) + 1, "start": start, "end": end, "context": sentence})
        for component in components:
            actual = sentence.count(component)
            contained = term_count * term.count(component)
            if actual > contained:
                results.append(
                    {
                        "kind": "component-echo",
                        "component": component,
                        "count": actual,
                        "outside_term_count": actual - contained,
                        "line": text.count("\n", 0, start) + 1,
                        "start": start,
                        "end": end,
                        "context": sentence,
                    }
                )
    return results


def validate_documents(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    if not documents:
        raise ValueError("at least one document is required")
    identifiers: set[str] = set()
    validated: list[dict[str, object]] = []
    for index, document in enumerate(documents, start=1):
        identifier_raw = document.get("id")
        identifier = identifier_raw.strip() if isinstance(identifier_raw, str) else ""
        scopes = document.get("scopes")
        if not identifier or identifier in identifiers:
            raise ValueError(f"document {index} requires a unique id")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(item, str) or item not in ALLOWED_SCOPES for item in scopes):
            raise ValueError(f"document {identifier} scopes must be a non-empty list of supported scopes")
        if len(set(scopes)) != len(scopes):
            raise ValueError(f"document {identifier} scopes contain duplicates")
        if ({"glossary", "index"} & set(scopes)) and len(scopes) > 1:
            raise ValueError(f"document {identifier} glossary or index scope must use a dedicated document")
        before = document.get("before")
        after = document.get("after")
        if not isinstance(before, str) or not isinstance(after, str):
            raise ValueError(f"document {identifier} requires before and after text")
        identifiers.add(identifier)
        validated.append({"id": identifier, "scopes": scopes, "before": before, "after": after})
    return validated


def audit_corpus(documents: list[dict[str, object]], term_map: dict[str, object]) -> dict[str, object]:
    documents = validate_documents(documents)
    terms = validate_term_map(term_map)
    covered_scopes = sorted({scope for document in documents for scope in document["scopes"]})
    rows: list[dict[str, object]] = []
    failures: list[str] = []
    warnings: list[str] = []
    total_residues = 0
    total_echoes = 0
    total_occurrences = 0

    for term in terms:
        identifier = str(term["id"])
        old_values = list(term["old"])
        new = str(term["new"])
        required_scopes = set(term["scope"])
        missing_scopes = sorted(required_scopes - set(covered_scopes))
        if missing_scopes:
            failures.append(f"{identifier}: 검사하지 않은 scope {', '.join(missing_scopes)}")

        document_rows: list[dict[str, object]] = []
        old_before_total = 0
        new_before_total = 0
        new_after_total = 0
        residue_total = 0
        echo_total = 0
        replacement_gap_total = 0
        unmatched_exceptions: list[dict[str, object]] = []

        documents_by_id = {str(document["id"]): document for document in documents}
        for exception in term["exceptions"]:
            target = documents_by_id.get(str(exception["document_id"]))
            if target is None:
                failures.append(f"{identifier}: 예외가 없는 문서 {exception['document_id']}를 가리킴")
            elif exception["scope"] not in required_scopes:
                failures.append(f"{identifier}: 예외 scope {exception['scope']}가 용어 적용 scope 밖임")
            elif exception["scope"] not in target["scopes"]:
                failures.append(f"{identifier}: 예외 scope {exception['scope']}가 문서 {exception['document_id']}에 없음")

        for document in documents:
            document_id = str(document["id"])
            before = str(document["before"])
            after = str(document["after"])
            active_scopes = sorted(required_scopes.intersection(document["scopes"]))
            if not active_scopes:
                continue
            scope_rows: list[dict[str, object]] = []
            document_old_count = 0
            document_new_before = 0
            document_new_after = 0
            document_residue_count = 0
            document_echo_count = 0
            document_gap = 0

            for scope in active_scopes:
                before_view = scope_mask(before, scope)
                after_view = scope_mask(after, scope)
                before_new_raw = occurrence_spans(before_view, new)
                after_new_raw = occurrence_spans(after_view, new)
                before_exception_spans, before_unmatched = exact_exception_spans(before_view, list(term["exceptions"]), document_id, scope)
                exception_spans, after_unmatched = exact_exception_spans(after_view, list(term["exceptions"]), document_id, scope)
                unmatched_exceptions.extend({**item, "phase": "before"} for item in before_unmatched)
                unmatched_exceptions.extend({**item, "phase": "after"} for item in after_unmatched)
                before_protected = protected_spans(before_view)
                after_protected = protected_spans(after_view)
                before_new_exclusions = [{"kind": "new-term", "start": start, "end": end, "value": new} for start, end in before_new_raw]
                after_new_exclusions = [{"kind": "new-term", "start": start, "end": end, "value": new} for start, end in after_new_raw]
                before_old_spans = nonoverlapping_old_spans(
                    before_view,
                    old_values,
                    before_protected + before_exception_spans + before_new_exclusions,
                )
                after_old_all = nonoverlapping_old_spans(after_view, old_values, after_new_exclusions)
                residues = {
                    old: contexts_for_spans(
                        after,
                        [(start, end) for start, end in spans if not overlaps_protected(start, end, after_protected + exception_spans)],
                    )
                    for old, spans in after_old_all.items()
                }
                protected_residues = {
                    old: contexts_for_spans(
                        after,
                        [(start, end) for start, end in spans if overlaps_protected(start, end, after_protected + exception_spans)],
                    )
                    for old, spans in after_old_all.items()
                }
                old_count = sum(len(items) for items in before_old_spans.values())
                residue_count = sum(len(items) for items in residues.values())
                new_before_spans = filtered_spans(before_view, new, before_protected)
                new_after_spans = filtered_spans(after_view, new, after_protected)
                echo_view = mask_spans(after_view, after_protected + exception_spans)
                echoes = echo_candidates(echo_view, new, list(term["components"]))
                # 범위별로 세어 본문 삭제분이 제목·표의 추가 출현으로 상쇄되지 않게 한다.
                scope_gap = max(0, len(new_before_spans) + old_count - len(new_after_spans))

                document_old_count += old_count
                document_new_before += len(new_before_spans)
                document_new_after += len(new_after_spans)
                document_residue_count += residue_count
                document_echo_count += len(echoes)
                document_gap += scope_gap
                scope_rows.append(
                    {
                        "scope": scope,
                        "old_counts_before": {old: len(items) for old, items in before_old_spans.items()},
                        "residue_count": residue_count,
                        "residues": residues,
                        "protected_or_excepted_residues": protected_residues,
                        "new_count_before": len(new_before_spans),
                        "new_count_after": len(new_after_spans),
                        "replacement_gap": scope_gap,
                        "new_sentence_contexts": [
                            {"line": after.count("\n", 0, start) + 1, "start": start, "end": end, "context": sentence}
                            for start, end, sentence in containing_sentences(mask_spans(after_view, after_protected), new)
                        ],
                        "echo_candidates": echoes,
                    }
                )

            if document_residue_count:
                failures.append(f"{identifier}/{document_id}: 기존어 {document_residue_count}건 잔존")
            if document_gap:
                failures.append(f"{identifier}/{document_id}: 이관 또는 내용 보존을 확인할 수 없는 계수 차이 {document_gap}건")

            old_before_total += document_old_count
            new_before_total += document_new_before
            new_after_total += document_new_after
            residue_total += document_residue_count
            echo_total += document_echo_count
            replacement_gap_total += document_gap
            document_rows.append(
                {
                    "document_id": document_id,
                    "scopes": active_scopes,
                    "old_count_before": document_old_count,
                    "residue_count": document_residue_count,
                    "new_count_before": document_new_before,
                    "new_count_after": document_new_after,
                    "replacement_gap": document_gap,
                    "echo_candidate_count": document_echo_count,
                    "scope_results": scope_rows,
                }
            )

        if unmatched_exceptions:
            failures.append(f"{identifier}: 지정 위치에서 찾지 못한 예외 {len(unmatched_exceptions)}건")

        total_residues += residue_total
        total_echoes += echo_total
        total_occurrences += new_after_total
        rows.append(
            {
                "id": identifier,
                "source": term.get("source"),
                "old": old_values,
                "new": new,
                "components": term["components"],
                "required_scopes": sorted(required_scopes),
                "missing_scopes": missing_scopes,
                "exceptions": term["exceptions"],
                "unmatched_exceptions": unmatched_exceptions,
                "old_count_before": old_before_total,
                "new_count_before": new_before_total,
                "new_count_after": new_after_total,
                "replacement_gap": replacement_gap_total,
                "residue_count": residue_total,
                "echo_candidate_count": echo_total,
                "documents": document_rows,
                "requires_human_collocation_review": new_after_total > 0,
            }
        )

    return {
        "schema_version": "0.3",
        "kind": "term-migration-audit",
        "status": "보류" if failures else "기계 확인 완료",
        "document_count": len(documents),
        "covered_scopes": covered_scopes,
        "term_count": len(rows),
        "new_occurrences_total": total_occurrences,
        "residue_count": total_residues,
        "echo_candidate_count": total_echoes,
        "terms": rows,
        "failures": failures,
        "warnings": warnings,
        "requires_human_context_review": True,
        "limit": "단순 Markdown 행 휴리스틱으로 구분한 manifest scope, 파일·scope별 기존어 잔존, 확정어 계수·문장, 명시 구성어 되풀이 후보만 확인한다. 복잡한 다중 행 표·각주, 의미 보존, 연어·개념 범위·제목 기능·전수 문맥 검토는 판정하지 않는다.",
    }


def audit(before: str, after: str, term_map: dict[str, object], *, document_id: str = "single-input", scopes: list[str] | None = None) -> dict[str, object]:
    return audit_corpus([{"id": document_id, "scopes": scopes or ["body"], "before": before, "after": after}], term_map)


def read_manifest(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "0.1":
        raise ValueError("manifest schema_version must be 0.1")
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValueError("manifest requires a non-empty documents list")
    documents: list[dict[str, object]] = []
    for raw in raw_documents:
        if not isinstance(raw, dict):
            raise ValueError("manifest documents must be objects")
        if raw.get("include", True) is False:
            continue
        before_path = (path.parent / str(raw.get("before", ""))).resolve()
        after_path = (path.parent / str(raw.get("after", ""))).resolve()
        documents.append(
            {
                "id": raw.get("id"),
                "scopes": raw.get("scopes"),
                "before": before_path.read_text(encoding="utf-8"),
                "after": after_path.read_text(encoding="utf-8"),
            }
        )
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--scope", choices=sorted(ALLOWED_SCOPES), action="append")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--term-map", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        if args.manifest:
            if args.before or args.after or args.scope:
                raise ValueError("--manifest cannot be combined with --before, --after, or --scope")
            documents = read_manifest(args.manifest)
        else:
            if not args.before or not args.after:
                raise ValueError("use --manifest or provide both --before and --after")
            documents = [
                {
                    "id": "single-input",
                    "scopes": args.scope or ["body"],
                    "before": args.before.read_text(encoding="utf-8"),
                    "after": args.after.read_text(encoding="utf-8"),
                }
            ]
        term_map = json.loads(args.term_map.read_text(encoding="utf-8"))
        if not isinstance(term_map, dict):
            raise ValueError("term map root must be an object")
        result = audit_corpus(documents, term_map)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"term migration audit failed: {error}")
        return 1

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "기계 확인 완료" else 2


if __name__ == "__main__":
    raise SystemExit(main())
