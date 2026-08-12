#!/usr/bin/env python3
"""Record comparable deterministic checks for two or more candidate edits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from measure_edit import measure
from protected_spans import custom_values
from scan_style import PROVENANCES
from verify_style_gate import gate


def compare(
    before: str,
    candidates: dict[str, str],
    target_rules: list[str],
    *,
    translation_source: bool,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for name, after in candidates.items():
        style_gate = gate(before, after, target_rules, translation_source=translation_source, provenance=provenance, extra_values=extra_values)
        results.append(
            {
                "candidate": name,
                "eligibility": "비교 가능" if style_gate["status"] == "통과" else "비교 제외",
                "style_gate": style_gate,
                "edit_measurement": measure(before, after),
            }
        )
    eligible = [item["candidate"] for item in results if item["eligibility"] == "비교 가능"]
    return {
        "schema_version": "0.2",
        "kind": "candidate-comparison",
        "target_rules": target_rules,
        "provenance": provenance,
        "candidates": results,
        "eligible_candidates": eligible,
        "next_step": "순서를 가린 사람 검토" if eligible else "보호·표지 gate 실패를 먼저 해결",
        "limit": "이 도구는 품질 순위나 저자·생성 방식 판정을 내리지 않는다.",
    }


def parse_candidate(specification: str) -> tuple[str, Path]:
    if "=" not in specification:
        raise ValueError("--candidate must use NAME=PATH")
    name, raw_path = specification.split("=", 1)
    if not name or not raw_path:
        raise ValueError("--candidate must use non-empty NAME=PATH")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--candidate", action="append", required=True, help="NAME=PATH; repeat for each candidate")
    parser.add_argument("--target-rule", action="append", default=[])
    parser.add_argument("--translation-source", action="store_true")
    parser.add_argument("--provenance", choices=PROVENANCES, default="unknown")
    parser.add_argument("--protect-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        candidate_paths = dict(parse_candidate(item) for item in args.candidate)
    except ValueError as error:
        parser.error(str(error))
    if len(candidate_paths) < 2:
        parser.error("at least two distinct --candidate values are required")
    before = args.before.read_text(encoding="utf-8")
    candidates = {name: path.read_text(encoding="utf-8") for name, path in candidate_paths.items()}
    result = compare(
        before,
        candidates,
        args.target_rule,
        translation_source=args.translation_source,
        provenance=args.provenance,
        extra_values=custom_values(args.protect_file),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["eligible_candidates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
