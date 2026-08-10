#!/usr/bin/env python3
"""Combine protected-value verification with before/after candidate-anchor deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from protected_spans import custom_values
from scan_style import scan
from verify_protected_spans import verify


def gate(before: str, after: str, target_rules: list[str], *, translation_source: bool, extra_values: list[str] | None) -> dict[str, object]:
    protected = verify(before, after, extra_values)
    before_scan = scan(before, translation_source=translation_source, extra_values=extra_values)
    after_scan = scan(after, translation_source=translation_source, extra_values=extra_values)
    all_rules = sorted(set(before_scan["counts"]) | set(after_scan["counts"]))
    delta = {rule_id: int(after_scan["counts"].get(rule_id, 0)) - int(before_scan["counts"].get(rule_id, 0)) for rule_id in all_rules}
    regressions = [rule_id for rule_id in target_rules if delta.get(rule_id, 0) > 0]
    status = "통과" if not protected["missing"] and not regressions else "보류"
    return {
        "schema_version": "0.1",
        "kind": "style-gate",
        "status": status,
        "target_rules": target_rules,
        "protected": protected,
        "before_counts": before_scan["counts"],
        "after_counts": after_scan["counts"],
        "delta": delta,
        "target_regressions": regressions,
        "introduced_candidates": [rule_id for rule_id, value in delta.items() if value > 0 and rule_id not in target_rules],
        "limit": "후보 앵커와 보호값만 비교한다. 의미·장르·리듬의 최종 평가는 독립 검토가 필요하다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--target-rule", action="append", default=[], help="완화가 목표인 KH-S ID; 여러 번 지정 가능")
    parser.add_argument("--translation-source", action="store_true")
    parser.add_argument("--protect-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = gate(
        args.before.read_text(encoding="utf-8"),
        args.after.read_text(encoding="utf-8"),
        args.target_rule,
        translation_source=args.translation_source,
        extra_values=custom_values(args.protect_file),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "통과" else 2


if __name__ == "__main__":
    raise SystemExit(main())
