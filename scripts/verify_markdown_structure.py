#!/usr/bin/env python3
"""Verify that protected Markdown presentation markers survive an edit."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$", re.MULTILINE)
FENCE = re.compile(r"^[ \t]*(```+|~~~+)([^\n]*)$", re.MULTILINE)
EMOJI = re.compile("[\\U0001F300-\\U0001FAFF\\u2600-\\u27BF]")


def signature(text: str) -> dict[str, object]:
    return {
        "headings": [(len(mark), title) for mark, title in HEADING.findall(text)],
        "bold_marker_count": text.count("**"),
        "emoji": EMOJI.findall(text),
        "fences": [(mark, info.strip()) for mark, info in FENCE.findall(text)],
    }


def verify(before: str, after: str) -> dict[str, object]:
    before_signature = signature(before)
    after_signature = signature(after)
    changed = [key for key in before_signature if before_signature[key] != after_signature[key]]
    return {
        "schema_version": "0.1",
        "kind": "markdown-structure-verification",
        "status": "통과" if not changed else "보류",
        "changed": changed,
        "before": before_signature,
        "after": after_signature,
        "limit": "제목·굵은 표지·이모지·코드 펜스만 exact 비교한다. 문서 의미와 다른 Markdown 구조는 별도 검토가 필요하다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(
        args.before.read_text(encoding="utf-8"),
        args.after.read_text(encoding="utf-8"),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "통과" else 2


if __name__ == "__main__":
    raise SystemExit(main())
