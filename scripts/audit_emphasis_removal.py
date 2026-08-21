#!/usr/bin/env python3
"""Find short bare-label residues after an explicit Markdown bold-removal edit."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


LEADING_BOLD = re.compile(r"^\s*\*\*([^*\n]{1,24})\*\*(.*)$", re.DOTALL)
PREDICATE_END = re.compile(r"(?:다|까|자|요|죠|니다)$")


def paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def plain_markdown(text: str) -> str:
    return text.replace("**", "").strip()


def audit(before: str, after: str) -> dict[str, object]:
    before_parts = paragraphs(before)
    after_parts = paragraphs(after)
    after_by_plain: dict[str, list[int]] = defaultdict(list)
    for index, paragraph in enumerate(after_parts, start=1):
        after_by_plain[plain_markdown(paragraph)].append(index)

    consumed: set[int] = set()
    findings: list[dict[str, object]] = []
    for before_index, paragraph in enumerate(before_parts, start=1):
        match = LEADING_BOLD.match(paragraph)
        if not match:
            continue
        lead = match.group(1).strip()
        rest = match.group(2)
        target = plain_markdown(paragraph)
        after_index = next((item for item in after_by_plain.get(target, []) if item not in consumed), None)
        if after_index is None:
            continue
        consumed.add(after_index)
        after_paragraph = after_parts[after_index - 1]
        if f"**{lead}**" in after_paragraph:
            continue

        punctuated = lead.endswith((".", ":", "：")) or bool(re.match(r"^\s*(?:[.:：]|[—-])", rest))
        label = lead.rstrip(" .:：—-").strip()
        if not punctuated or not label or len(label) > 12 or PREDICATE_END.search(label):
            continue
        findings.append(
            {
                "kind": "bare-label-residue",
                "before_paragraph": before_index,
                "after_paragraph": after_index,
                "label": label,
                "context": after_paragraph[:120],
                "disposition": "contextual",
            }
        )

    indexes = sorted(int(item["after_paragraph"]) for item in findings)
    runs: list[list[int]] = []
    current: list[int] = []
    for index in indexes:
        if current and index != current[-1] + 1:
            if len(current) >= 3:
                runs.append(current)
            current = []
        current.append(index)
    if len(current) >= 3:
        runs.append(current)

    return {
        "schema_version": "0.1",
        "kind": "emphasis-removal-audit",
        "status": "사람 판정 필요" if findings else "후보 없음",
        "finding_count": len(findings),
        "findings": findings,
        "consecutive_label_runs": [{"start_paragraph": run[0], "end_paragraph": run[-1], "count": len(run)} for run in runs],
        "limit": "명시적으로 제거된 선두 볼드가 짧은 라벨꼴로 남은 위치만 찾는다. 목록 전환·문장화·보존은 사람이 판정한다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.before.read_text(encoding="utf-8"), args.after.read_text(encoding="utf-8"))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
