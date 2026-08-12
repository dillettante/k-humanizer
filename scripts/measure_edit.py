#!/usr/bin/env python3
"""Report deterministic edit size metrics without treating them as quality scores."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


CHARACTER_SEQUENCE_LIMIT = 100_000
LINE_SEQUENCE_LIMIT = 20_000


def sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]


def sequence_ratio(before: list[str], after: list[str]) -> tuple[float, int]:
    """Return an aligned unchanged ratio and changed slots for bounded sequences."""

    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=True)
    unchanged = sum(i2 - i1 for tag, i1, i2, _, _ in matcher.get_opcodes() if tag == "equal")
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")
    return unchanged / max(len(before), len(after), 1), changed


def measure(before: str, after: str) -> dict[str, object]:
    """Measure edit size without allowing book-length character diff to dominate runtime.

    Exact character comparison is useful for short excerpts. For larger inputs, an
    aligned line comparison is intentionally reported as an estimate; it must not
    be described as an exact changed-character ratio.
    """

    before_characters = len(before)
    after_characters = len(after)
    if before == after:
        return {
            "schema_version": "0.2",
            "kind": "edit-measurement",
            "before_characters": before_characters,
            "after_characters": after_characters,
            "comparison_method": "exact-equality",
            "changed_character_ratio": 0.0,
            "changed_line_ratio": 0.0,
            "before_sentence_count": len(sentences(before)),
            "after_sentence_count": len(sentences(after)),
            "changed_sentence_slots": 0,
            "sentence_measurement_method": "exact-equality",
            "limit": "동일 본문은 해시·문자열 동등성으로 확인했다. 의미·귀속·부정 변경은 판정하지 않는다.",
        }

    if max(before_characters, after_characters) <= CHARACTER_SEQUENCE_LIMIT:
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        unchanged = sum(i2 - i1 for tag, i1, i2, _, _ in matcher.get_opcodes() if tag == "equal")
        changed_character_ratio: float | None = round(1 - unchanged / max(before_characters, after_characters, 1), 6)
        comparison_method = "character-sequence"
    else:
        changed_character_ratio = None
        comparison_method = "line-sequence"

    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if max(len(before_lines), len(after_lines)) <= LINE_SEQUENCE_LIMIT:
        unchanged_line_ratio, changed_line_slots = sequence_ratio(before_lines, after_lines)
        changed_line_ratio: float | None = round(1 - unchanged_line_ratio, 6)
        line_measurement_method = "line-sequence"
    else:
        # The final fallback is linear and deliberately coarse. It keeps an
        # iteration receipt available instead of hanging on pathological corpora.
        compared = max(len(before_lines), len(after_lines), 1)
        changed_line_slots = sum(
            1
            for index in range(compared)
            if (before_lines[index] if index < len(before_lines) else None)
            != (after_lines[index] if index < len(after_lines) else None)
        )
        changed_line_ratio = round(changed_line_slots / compared, 6)
        line_measurement_method = "positional-line-fallback"

    if max(before_characters, after_characters) <= CHARACTER_SEQUENCE_LIMIT:
        before_sentences, after_sentences = sentences(before), sentences(after)
        _, changed_sentence_slots = sequence_ratio(before_sentences, after_sentences)
        sentence_measurement_method = "sentence-sequence"
    else:
        before_sentences, after_sentences = [], []
        changed_sentence_slots = None
        sentence_measurement_method = "not-run-large-input"
    return {
        "schema_version": "0.2",
        "kind": "edit-measurement",
        "before_characters": before_characters,
        "after_characters": after_characters,
        "comparison_method": comparison_method,
        "changed_character_ratio": changed_character_ratio,
        "changed_line_ratio": changed_line_ratio,
        "line_measurement_method": line_measurement_method,
        "before_sentence_count": len(before_sentences),
        "after_sentence_count": len(after_sentences),
        "changed_sentence_slots": changed_sentence_slots,
        "sentence_measurement_method": sentence_measurement_method,
        "limit": "변경률은 경보용 보조 지표다. 장문 line-sequence의 changed_line_ratio는 변경 문자 비율이 아니다. 낮은 변경률도 의미·귀속·부정 변경을 보증하지 않는다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(args.before.read_text(encoding="utf-8"), args.after.read_text(encoding="utf-8"))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
