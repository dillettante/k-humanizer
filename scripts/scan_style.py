#!/usr/bin/env python3
"""Find deterministic Korean style-candidate anchors; never infer authorship."""

from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import re
import sys
from pathlib import Path

from protected_spans import custom_values, overlaps_protected, protected_spans


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR.parent / "references" / "quick-rules.json"
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_CODE = re.compile(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$")
PROTECT_START = re.compile(r"<!--\s*k-humanizer:protect-start\s*-->", re.IGNORECASE)
PROTECT_END = re.compile(r"<!--\s*k-humanizer:protect-end\s*-->", re.IGNORECASE)
PROVENANCES = ("raw_ai", "ai_edited", "human_draft", "human_polished", "unknown")
HEADING = re.compile(r"^[ \t]*(#{1,6})[ \t]+(.+?)\s*$")
SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+(?:\*\*)?|$)")
BOLD = re.compile(r"\*\*([^*\n]{1,72})\*\*")


def document_structure(text: str) -> list[dict[str, object]]:
    """Return offset-preserving prose blocks and sentence positions for Markdown text."""

    paragraphs: list[dict[str, object]] = []
    offset = 0
    start: int | None = None
    chunks: list[str] = []

    def finish(end: int) -> None:
        nonlocal start, chunks
        if start is None:
            return
        raw = "".join(chunks)
        heading = HEADING.match(raw.strip()) if "\n" not in raw.rstrip("\n") else None
        sentences = [
            {"start": start + match.start(), "end": start + match.end()}
            for match in SENTENCE.finditer(raw)
            if match.group(0).strip()
        ]
        if not sentences:
            sentences = [{"start": start, "end": end}]
        paragraphs.append(
            {
                "start": start,
                "end": end,
                "kind": "heading" if heading else "body",
                "heading": heading.group(2).strip() if heading else "",
                "heading_level": len(heading.group(1)) if heading else 0,
                "sentences": sentences,
            }
        )
        start = None
        chunks = []

    for line in text.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = offset
            chunks.append(line)
        else:
            finish(offset)
        offset += len(line)
    finish(offset)

    heading_stack: list[str] = []
    body_indexes = [index for index, paragraph in enumerate(paragraphs) if paragraph["kind"] == "body"]
    body_tail_rank = {index: len(body_indexes) - position for position, index in enumerate(body_indexes)}
    last_body = body_indexes[-1] if body_indexes else -1
    for index, paragraph in enumerate(paragraphs):
        if paragraph["kind"] == "heading":
            level = int(paragraph["heading_level"])
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(str(paragraph["heading"]))
        paragraph["paragraph"] = index + 1
        paragraph["section_heading"] = " > ".join(heading_stack)
        paragraph["is_document_last"] = index == last_body
        paragraph["body_paragraphs_to_end"] = body_tail_rank.get(index, 0)
    return paragraphs


def location_metadata(structure: list[dict[str, object]], index: int) -> dict[str, object]:
    starts = [int(paragraph["start"]) for paragraph in structure]
    paragraph_index = bisect_right(starts, index) - 1
    if paragraph_index < 0:
        return {"paragraph": 0, "sentence_in_paragraph": 0, "is_paragraph_first": False, "is_paragraph_last": False, "paragraph_kind": "unknown", "section_heading": "", "is_document_last": False, "body_paragraphs_to_end": 0}
    paragraph = structure[paragraph_index]
    sentences = list(paragraph["sentences"])
    sentence_index = next((position for position, sentence in enumerate(sentences) if int(sentence["start"]) <= index < int(sentence["end"])), len(sentences) - 1)
    return {
        "paragraph": int(paragraph["paragraph"]),
        "sentence_in_paragraph": sentence_index + 1,
        "is_paragraph_first": sentence_index == 0,
        "is_paragraph_last": sentence_index == len(sentences) - 1,
        "paragraph_kind": str(paragraph["kind"]),
        "section_heading": str(paragraph["section_heading"]),
        "is_document_last": bool(paragraph["is_document_last"]),
        "body_paragraphs_to_end": int(paragraph["body_paragraphs_to_end"]),
    }


def line_column(text: str, index: int) -> tuple[int, int]:
    return text.count("\n", 0, index) + 1, index - text.rfind("\n", 0, index)


def context(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 24) : min(len(text), end + 24)].split())


def finding(
    rule_id: str,
    text: str,
    start: int,
    end: int,
    evidence: str,
    *,
    structure: list[dict[str, object]],
    shape: str | None = None,
) -> dict[str, object]:
    line, column = line_column(text, start)
    result = {
        "rule_id": rule_id,
        "start": start,
        "end": end,
        "line": line,
        "column": column,
        "evidence": evidence,
        "context": context(text, start, end),
        **location_metadata(structure, start),
    }
    if shape:
        result["shape"] = shape
    return result


def mask_preserving_offsets(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """Mask non-prose without changing offsets or line numbers."""

    matches = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal matches
        matches += 1
        return "".join("\n" if character == "\n" else " " for character in match.group(0))

    return pattern.sub(replacement, text), matches


def non_prose_mask(text: str) -> tuple[str, dict[str, int]]:
    masked, comments = mask_preserving_offsets(text, HTML_COMMENT)
    masked, code_blocks = mask_preserving_offsets(masked, FENCED_CODE)
    return masked, {"html_comments": comments, "fenced_code_blocks": code_blocks}


def input_warnings(text: str) -> list[str]:
    starts = len(PROTECT_START.findall(text))
    ends = len(PROTECT_END.findall(text))
    if starts != ends:
        return ["k-humanizer 보호 블록 시작·종료 표지 수가 맞지 않습니다. 해당 범위를 수동으로 확인하십시오."]
    return []


def sentence_run_findings(
    rule: dict[str, object],
    source_text: str,
    scan_text: str,
    protected: list[dict[str, object]],
    structure: list[dict[str, object]],
) -> list[dict[str, object]]:
    # A non-matching or protected sentence must remain a run boundary. Dropping it
    # would join matching endings across intervening prose or a protected block.
    sentences: list[tuple[int, int, str | None]] = []
    for match in re.finditer(r"[^.!?\n]+[.!?]", scan_text):
        ending = None
        if not overlaps_protected(match.start(), match.end(), protected):
            ending = re.search(r"(습니다|이다|한다|된다|있다)\.$", match.group(0).strip())
        sentences.append((match.start(), match.end(), ending.group(1) if ending else None))
    minimum = int(rule["minimum_run"])
    results: list[dict[str, object]] = []
    start = 0
    while start < len(sentences):
        if sentences[start][2] is None:
            start += 1
            continue
        end = start + 1
        while end < len(sentences) and sentences[end][2] == sentences[start][2]:
            end += 1
        if end - start >= minimum:
            first, last = sentences[start], sentences[end - 1]
            results.append(finding(str(rule["id"]), source_text, first[0], last[1], f"{first[2]} 종결 {end - start}문장 연속", structure=structure))
        start = end
    return results


def structural_findings(
    rule: dict[str, object],
    source_text: str,
    scan_text: str,
    protected: list[dict[str, object]],
    structure: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Find post-editing structural candidates; every result requires human judgment."""

    rule_id = str(rule["id"])
    kind = str(rule["structural_kind"])
    results: list[dict[str, object]] = []

    def add(start: int, end: int, evidence: str, shape: str) -> None:
        if not overlaps_protected(start, end, protected):
            results.append(finding(rule_id, source_text, start, end, evidence, structure=structure, shape=shape))

    if kind == "meta_discourse":
        patterns = (
            (re.compile(r"(?:이|이런)\s*(?:글|장|절)(?:은|에서는?)\s*[^.!?\n]{0,60}(?:장이다|이야기다|다룬다|시작한다|핵심이다|쓴다)"), "장·절 선언", "이 장은 __다."),
            (re.compile(r"(?:이제|먼저|여기서)\s+[^.!?\n]{0,48}(?:하자|두자|밝힌다|정리하자|살펴보자|이야기하자|짚고\s*가자|말해\s*두자|시작하자|긋자|듣자|들자|넘어가자)"), "메타 청유", "메타 지시: __"),
            (re.compile(r"(?:전제|기준|뜻|범위)[^.!?\n]{0,24}(?:밝힌다|정리한다|정해\s*두자)"), "논지 예고", "논지 예고: __"),
        )
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            raw = scan_text[start : int(paragraph["end"])]
            for pattern, label, shape in patterns:
                for match in pattern.finditer(raw):
                    absolute_start = start + match.start()
                    if location_metadata(structure, absolute_start)["is_paragraph_first"] and "돌아가자" not in match.group(0):
                        add(absolute_start, start + match.end(), f"{label}: {match.group(0)}", shape)
    elif kind == "return_signal":
        # Location metadata tells the reviewer whether this is a genuine chapter
        # close. A hard "last paragraph" filter misses closes followed by a note,
        # checklist, or a later inserted section; the lexical signal itself is only
        # a review candidate, never an instruction to remove the return.
        pattern = re.compile(r"(?:이제\s+)?[^.!?\n]{2,40}?(?:으로|로)\s*(?:돌아가자|마무리하자)")
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            for match in pattern.finditer(scan_text[start : int(paragraph["end"])]):
                add(start + match.start(), start + match.end(), f"장면 회귀: {match.group(0)}", "__로 돌아가자.")
    elif kind == "advance_label":
        patterns = (
            (re.compile(r"[^.!?\n]{1,48}(?:은|는|이|가|지는)\s+(?:분명하다|분명해진다)"), "자명 선언", "__는 분명하다."),
            (re.compile(r"[^.!?\n]{1,40}(?:은|는|이|가)\s*(?:하나|둘|셋|넷|다섯|한|두|세|네)\s*(?:가지|개|뿐)이다"), "열거 예고", "__는 N가지다."),
            (re.compile(r"한\s*문장으로\s*(?:하면|말하면|요약하면|정리하면|이렇다|요약된다|정한다)[^.!?\n]{0,32}"), "한 문장 예고", "한 문장으로 __"),
        )
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            raw = scan_text[start : int(paragraph["end"])]
            for pattern, label, shape in patterns:
                for match in pattern.finditer(raw):
                    add(start + match.start(), start + match.end(), f"{label}: {match.group(0)}", shape)
    elif kind == "emphasis_run":
        minimum = int(rule.get("minimum_run", 3))
        # A Markdown essay normally puts each bold lead in its own paragraph.
        # Inspecting only sentences inside one paragraph misses that visual rhythm;
        # headings and list/table lines remain outside this body-paragraph run.
        run: list[dict[str, object]] = []
        for paragraph in [*structure, None]:
            if paragraph is not None and paragraph["kind"] == "body":
                start = int(paragraph["start"])
                end = int(paragraph["end"])
                raw = scan_text[start:end].strip()
                lead = BOLD.match(raw)
                navigation_heading = bool(
                    lead
                    and re.match(
                        r"(?:제\s*)?\d+\s*(?:장|부|절)|(?:프롤로그|에필로그|부록|후기|이\s*책을\s*사용하는\s*법)",
                        lead.group(1).strip(),
                    )
                )
                if lead and not navigation_heading and len(lead.group(1).strip()) <= 52:
                    run.append({"start": start, "end": end})
                    continue
            if len(run) >= minimum:
                add(int(run[0]["start"]), int(run[-1]["end"]), f"굵은 도입 라벨 {len(run)}문단 연속", "굵은 도입 라벨 연속")
            run = []
    return results


def distributions(findings: list[dict[str, object]]) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """Summarize repeated anchors without turning their count into a quality score."""

    by_rule: dict[str, dict[str, object]] = {}
    shapes: dict[tuple[str, str], list[dict[str, object]]] = {}
    for item in findings:
        rule_id = str(item["rule_id"])
        row = by_rule.setdefault(rule_id, {"occurrences": 0, "documents": {}, "evidence": {}})
        row["occurrences"] = int(row["occurrences"]) + 1
        document_id = str(item.get("document_id", "single-input"))
        documents = dict(row["documents"])
        documents[document_id] = int(documents.get(document_id, 0)) + 1
        row["documents"] = documents
        evidence = str(item["evidence"])
        evidence_counts = dict(row["evidence"])
        evidence_counts[evidence] = int(evidence_counts.get(evidence, 0)) + 1
        row["evidence"] = evidence_counts
        shape = item.get("shape")
        if isinstance(shape, str) and shape:
            shapes.setdefault((rule_id, shape), []).append(item)
    repeats: list[dict[str, object]] = []
    for (rule_id, shape), items in sorted(shapes.items()):
        document_ids = sorted({str(item.get("document_id", "single-input")) for item in items})
        if len(document_ids) < 2:
            continue
        repeats.append(
            {
                "rule_id": rule_id,
                "shape": shape,
                "documents": len(document_ids),
                "document_ids": document_ids,
                "occurrences": len(items),
                "examples": [{key: item[key] for key in ("document_id", "line", "paragraph", "context") if key in item} for item in items[:3]],
            }
        )
    return by_rule, repeats


def scan(
    text: str,
    *,
    translation_source: bool = False,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
) -> dict[str, object]:
    if provenance not in PROVENANCES:
        raise ValueError(f"provenance must be one of: {', '.join(PROVENANCES)}")
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    protected = protected_spans(text, extra_values)
    scan_text, masked = non_prose_mask(text)
    structure = document_structure(scan_text)
    findings: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    scanned: list[str] = []
    for rule in rules:
        rule_id = str(rule["id"])
        if "translation_source" in rule.get("requires", []) and not translation_source:
            skipped.append({"rule_id": rule_id, "reason": "원문 대조가 확인되지 않아 번역투 앵커를 스캔하지 않음"})
            continue
        if "ai_edited" in rule.get("requires", []) and provenance != "ai_edited":
            skipped.append({"rule_id": rule_id, "reason": "후편집 수사·구조 후보는 ai_edited 입력에서만 스캔함"})
            continue
        scanned.append(rule_id)
        if rule["anchor_type"] == "regex":
            for match in re.finditer(str(rule["pattern"]), scan_text):
                if not overlaps_protected(match.start(), match.end(), protected):
                    findings.append(finding(rule_id, text, match.start(), match.end(), match.group(0), structure=structure))
        elif rule["anchor_type"] == "sentence_run":
            findings.extend(sentence_run_findings(rule, text, scan_text, protected, structure))
        elif rule["anchor_type"] == "structural":
            findings.extend(structural_findings(rule, text, scan_text, protected, structure))
    findings.sort(key=lambda item: (int(item["start"]), str(item["rule_id"])))
    counts: dict[str, int] = {}
    for item in findings:
        rule_id = str(item["rule_id"])
        counts[rule_id] = counts.get(rule_id, 0) + 1
    distribution, repeats = distributions(findings)
    return {
        "schema_version": "0.2",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "provenance": provenance,
        "scanned_rules": scanned,
        "skipped_rules": skipped,
        "protected_spans_excluded": len(protected),
        "non_prose_masked": masked,
        "input_warnings": input_warnings(text),
        "counts": counts,
        "counts_by_evidence": {rule_id: row["evidence"] for rule_id, row in distribution.items()},
        "rule_distribution": distribution,
        "cross_document_repeats": repeats,
        "structural_summary": {"paragraph_count": len(structure), "body_paragraph_count": sum(item["kind"] == "body" for item in structure)},
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def scan_manifest(
    manifest_path: Path,
    *,
    translation_source: bool = False,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
) -> dict[str, object]:
    """Scan included documents and retain an auditable corpus receipt."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("manifest.documents must be a non-empty list")
    document_ids: set[str] = set()
    findings: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    scanned_documents: list[dict[str, object]] = []
    excluded_documents: list[dict[str, object]] = []
    for position, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            raise ValueError(f"manifest document {position} must be an object")
        document_id = str(document.get("id", "")).strip()
        relative_path = str(document.get("path", "")).strip()
        if not document_id or not relative_path:
            raise ValueError(f"manifest document {position} requires id and path")
        if document_id in document_ids:
            raise ValueError(f"duplicate document id: {document_id}")
        document_ids.add(document_id)
        include = bool(document.get("include", True))
        receipt = {
            "document_id": document_id,
            "path": relative_path,
            "role": str(document.get("role", "prose")),
        }
        if not include:
            receipt["reason"] = str(document.get("reason", "manifest에서 제외됨"))
            excluded_documents.append(receipt)
            continue
        document_path = (manifest_path.parent / relative_path).resolve()
        if not document_path.is_file():
            raise ValueError(f"manifest document not found: {relative_path}")
        document_text = document_path.read_text(encoding="utf-8")
        result = scan(
            document_text,
            translation_source=translation_source,
            provenance=provenance,
            extra_values=extra_values,
        )
        receipt.update(
            {
                "characters": len(document_text),
                "finding_count": len(result["findings"]),
                "protected_spans_excluded": result["protected_spans_excluded"],
                "non_prose_masked": result["non_prose_masked"],
                "input_warnings": result["input_warnings"],
            }
        )
        scanned_documents.append(receipt)
        for finding_item in result["findings"]:
            item = dict(finding_item)
            item["document_id"] = document_id
            findings.append(item)
            rule_id = str(item["rule_id"])
            counts[rule_id] = counts.get(rule_id, 0) + 1
    findings.sort(key=lambda item: (str(item["document_id"]), int(item["start"]), str(item["rule_id"])))
    distribution, repeats = distributions(findings)
    return {
        "schema_version": "0.2",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "provenance": provenance,
        "manifest": str(manifest_path),
        "documents_expected": len(documents),
        "documents_scanned": scanned_documents,
        "documents_excluded": excluded_documents,
        "counts": counts,
        "counts_by_evidence": {rule_id: row["evidence"] for rule_id, row in distribution.items()},
        "rule_distribution": distribution,
        "cross_document_repeats": repeats,
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="검사할 UTF-8 텍스트 파일")
    source.add_argument("--text", help="검사할 텍스트")
    source.add_argument("--manifest", type=Path, help="다파일 검사 manifest JSON")
    parser.add_argument("--translation-source", action="store_true", help="대조할 번역 원문이 제공되었음을 표시")
    parser.add_argument("--provenance", choices=PROVENANCES, default="unknown", help="입력의 작성·편집 내력")
    parser.add_argument("--protect-file", type=Path, help="줄마다 추가 보호할 문자열")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
    if args.manifest:
        result = scan_manifest(args.manifest, translation_source=args.translation_source, provenance=args.provenance, extra_values=custom_values(args.protect_file))
    else:
        text = args.input.read_text(encoding="utf-8") if args.input else str(args.text)
        result = scan(text, translation_source=args.translation_source, provenance=args.provenance, extra_values=custom_values(args.protect_file))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
