#!/usr/bin/env python3
"""Report deterministic edit size metrics without treating them as quality scores."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


def sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]


def measure(before: str, after: str) -> dict[str, object]:
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    unchanged = sum(i2 - i1 for tag, i1, i2, _, _ in matcher.get_opcodes() if tag == "equal")
    denominator = max(len(before), len(after), 1)
    before_sentences, after_sentences = sentences(before), sentences(after)
    sentence_matcher = difflib.SequenceMatcher(a=before_sentences, b=after_sentences, autojunk=False)
    changed_sentence_slots = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in sentence_matcher.get_opcodes()
        if tag != "equal"
    )
    return {
        "schema_version": "0.1",
        "kind": "edit-measurement",
        "before_characters": len(before),
        "after_characters": len(after),
        "changed_character_ratio": round(1 - unchanged / denominator, 6),
        "before_sentence_count": len(before_sentences),
        "after_sentence_count": len(after_sentences),
        "changed_sentence_slots": changed_sentence_slots,
        "limit": "변경률은 경보용 보조 지표다. 낮은 변경률도 의미·귀속·부정 변경을 보증하지 않는다.",
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
