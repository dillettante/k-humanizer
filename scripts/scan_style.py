#!/usr/bin/env python3
"""Find deterministic Korean style-candidate anchors; never infer authorship."""

from __future__ import annotations

import argparse
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


def line_column(text: str, index: int) -> tuple[int, int]:
    return text.count("\n", 0, index) + 1, index - text.rfind("\n", 0, index)


def context(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 24) : min(len(text), end + 24)].split())


def finding(rule_id: str, text: str, start: int, end: int, evidence: str) -> dict[str, object]:
    line, column = line_column(text, start)
    return {"rule_id": rule_id, "start": start, "end": end, "line": line, "column": column, "evidence": evidence, "context": context(text, start, end)}


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
            results.append(finding(str(rule["id"]), source_text, first[0], last[1], f"{first[2]} 종결 {end - start}문장 연속"))
        start = end
    return results


def scan(text: str, *, translation_source: bool = False, extra_values: list[str] | None = None) -> dict[str, object]:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    protected = protected_spans(text, extra_values)
    scan_text, masked = non_prose_mask(text)
    findings: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    scanned: list[str] = []
    for rule in rules:
        rule_id = str(rule["id"])
        if "translation_source" in rule.get("requires", []) and not translation_source:
            skipped.append({"rule_id": rule_id, "reason": "원문 대조가 확인되지 않아 번역투 앵커를 스캔하지 않음"})
            continue
        scanned.append(rule_id)
        if rule["anchor_type"] == "regex":
            for match in re.finditer(str(rule["pattern"]), scan_text):
                if not overlaps_protected(match.start(), match.end(), protected):
                    findings.append(finding(rule_id, text, match.start(), match.end(), match.group(0)))
        elif rule["anchor_type"] == "sentence_run":
            findings.extend(sentence_run_findings(rule, text, scan_text, protected))
    findings.sort(key=lambda item: (int(item["start"]), str(item["rule_id"])))
    counts: dict[str, int] = {}
    for item in findings:
        rule_id = str(item["rule_id"])
        counts[rule_id] = counts.get(rule_id, 0) + 1
    return {
        "schema_version": "0.1",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "scanned_rules": scanned,
        "skipped_rules": skipped,
        "protected_spans_excluded": len(protected),
        "non_prose_masked": masked,
        "input_warnings": input_warnings(text),
        "counts": counts,
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def scan_manifest(
    manifest_path: Path,
    *,
    translation_source: bool = False,
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
    return {
        "schema_version": "0.1",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "manifest": str(manifest_path),
        "documents_expected": len(documents),
        "documents_scanned": scanned_documents,
        "documents_excluded": excluded_documents,
        "counts": counts,
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
    parser.add_argument("--protect-file", type=Path, help="줄마다 추가 보호할 문자열")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
    if args.manifest:
        result = scan_manifest(args.manifest, translation_source=args.translation_source, extra_values=custom_values(args.protect_file))
    else:
        text = args.input.read_text(encoding="utf-8") if args.input else str(args.text)
        result = scan(text, translation_source=args.translation_source, extra_values=custom_values(args.protect_file))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
