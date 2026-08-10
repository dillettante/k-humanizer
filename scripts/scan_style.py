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


def line_column(text: str, index: int) -> tuple[int, int]:
    return text.count("\n", 0, index) + 1, index - text.rfind("\n", 0, index)


def context(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 24) : min(len(text), end + 24)].split())


def finding(rule_id: str, text: str, start: int, end: int, evidence: str) -> dict[str, object]:
    line, column = line_column(text, start)
    return {"rule_id": rule_id, "start": start, "end": end, "line": line, "column": column, "evidence": evidence, "context": context(text, start, end)}


def sentence_run_findings(rule: dict[str, object], text: str, protected: list[dict[str, object]]) -> list[dict[str, object]]:
    sentences: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^.!?\n]+[.!?]", text):
        if not overlaps_protected(match.start(), match.end(), protected):
            ending = re.search(r"(습니다|이다|한다|된다|있다)\.$", match.group(0).strip())
            if ending:
                sentences.append((match.start(), match.end(), ending.group(1)))
    minimum = int(rule["minimum_run"])
    results: list[dict[str, object]] = []
    start = 0
    while start < len(sentences):
        end = start + 1
        while end < len(sentences) and sentences[end][2] == sentences[start][2]:
            end += 1
        if end - start >= minimum:
            first, last = sentences[start], sentences[end - 1]
            results.append(finding(str(rule["id"]), text, first[0], last[1], f"{first[2]} 종결 {end - start}문장 연속"))
        start = end
    return results


def scan(text: str, *, translation_source: bool = False, extra_values: list[str] | None = None) -> dict[str, object]:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    protected = protected_spans(text, extra_values)
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
            for match in re.finditer(str(rule["pattern"]), text):
                if not overlaps_protected(match.start(), match.end(), protected):
                    findings.append(finding(rule_id, text, match.start(), match.end(), match.group(0)))
        elif rule["anchor_type"] == "sentence_run":
            findings.extend(sentence_run_findings(rule, text, protected))
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
        "counts": counts,
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="검사할 UTF-8 텍스트 파일")
    source.add_argument("--text", help="검사할 텍스트")
    parser.add_argument("--translation-source", action="store_true", help="대조할 번역 원문이 제공되었음을 표시")
    parser.add_argument("--protect-file", type=Path, help="줄마다 추가 보호할 문자열")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
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
