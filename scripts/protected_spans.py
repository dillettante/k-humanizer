"""Shared extraction for values that a conservative edit must preserve exactly."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("protected_block", re.compile(r"<!--\s*k-humanizer:protect-start\s*-->.*?<!--\s*k-humanizer:protect-end\s*-->", re.DOTALL | re.IGNORECASE)),
    ("blockquote", re.compile(r"(?m)(?:^>[^\n]*(?:\n|$))+")),
    ("quotation", re.compile(r'"[^"\n]{1,500}"|“[^”\n]{1,500}”|「[^」\n]{1,500}」|『[^』\n]{1,500}』')),
    ("date", re.compile(r"\b\d{4}[.-]\d{1,2}[.-]\d{1,2}\b|\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?")),
    ("statute", re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*항)?")),
    ("number", re.compile(r"(?<![\d가-힣])\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:%|명|개|원|회|쪽|년|월|일|조|항|호))?")),
)


def custom_values(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def protected_spans(text: str, extra_values: list[str] | None = None) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    seen: set[tuple[int, int, str]] = set()
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            if kind == "number" and any(match.start() < int(span["end"]) and match.end() > int(span["start"]) for span in spans):
                continue
            key = (match.start(), match.end(), kind)
            if key not in seen:
                spans.append({"kind": kind, "start": match.start(), "end": match.end(), "value": match.group(0)})
                seen.add(key)
    for value in extra_values or []:
        for match in re.finditer(re.escape(value), text):
            key = (match.start(), match.end(), "user")
            if key not in seen:
                spans.append({"kind": "user", "start": match.start(), "end": match.end(), "value": value})
                seen.add(key)
    return sorted(spans, key=lambda item: (int(item["start"]), int(item["end"])))


def overlaps_protected(start: int, end: int, spans: list[dict[str, object]]) -> bool:
    return any(start < int(span["end"]) and end > int(span["start"]) for span in spans)


def missing_values(before: str, after: str, extra_values: list[str] | None = None) -> list[dict[str, object]]:
    values = Counter(str(span["value"]) for span in protected_spans(before, extra_values))
    after_counts = Counter(str(span["value"]) for span in protected_spans(after, extra_values))
    return [
        {"value": value, "expected": expected, "actual": after_counts[value]}
        for value, expected in sorted(values.items())
        if after_counts[value] < expected
    ]
