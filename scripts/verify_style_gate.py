#!/usr/bin/env python3
"""Combine protected-value verification with before/after candidate-anchor deltas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from protected_spans import custom_values
from scan_style import PROVENANCES, scan
from verify_protected_spans import verify


def gate(
    before: str,
    after: str,
    target_rules: list[str],
    *,
    translation_source: bool,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
    preserved_rules: list[str] | None = None,
) -> dict[str, object]:
    protected = verify(before, after, extra_values)
    before_scan = scan(before, translation_source=translation_source, provenance=provenance, extra_values=extra_values)
    after_scan = scan(after, translation_source=translation_source, provenance=provenance, extra_values=extra_values)
    all_rules = sorted(set(before_scan["counts"]) | set(after_scan["counts"]))
    delta = {rule_id: int(after_scan["counts"].get(rule_id, 0)) - int(before_scan["counts"].get(rule_id, 0)) for rule_id in all_rules}
    preserved = set(preserved_rules or [])
    regressions = [rule_id for rule_id in target_rules if delta.get(rule_id, 0) > 0]
    reduced = [rule_id for rule_id in target_rules if delta.get(rule_id, 0) < 0]
    unverifiable = [rule_id for rule_id in target_rules if int(before_scan["counts"].get(rule_id, 0)) == 0]
    valid_preserved = {
        rule_id
        for rule_id in preserved.intersection(target_rules)
        if int(before_scan["counts"].get(rule_id, 0)) > 0
    }
    invalid_preserved = sorted(preserved - valid_preserved)
    unresolved = [
        rule_id
        for rule_id in target_rules
        if rule_id not in valid_preserved and delta.get(rule_id, 0) >= 0
    ]
    introduced = [rule_id for rule_id, value in delta.items() if value > 0 and rule_id not in target_rules]
    status = "통과" if not protected["missing"] and not unresolved and not introduced and not invalid_preserved else "보류"
    return {
        "schema_version": "0.3",
        "kind": "style-gate",
        "status": status,
        "target_rules": target_rules,
        "provenance": provenance,
        "protected": protected,
        "before_counts": before_scan["counts"],
        "after_counts": after_scan["counts"],
        "delta": delta,
        "target_reduced": reduced,
        "target_preserved": sorted(valid_preserved),
        "invalid_preserved_rules": invalid_preserved,
        "target_unverifiable": unverifiable,
        "target_unresolved": unresolved,
        "target_regressions": regressions,
        "introduced_candidates": introduced,
        "limit": "목표 앵커의 실제 감소 또는 명시적 보존 판정과 보호값만 검사한다. 의미·장르·리듬의 최종 평가는 독립 검토가 필요하다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--target-rule", action="append", default=[], help="완화가 목표인 KH-S ID; 여러 번 지정 가능")
    parser.add_argument("--preserve-rule", action="append", default=[], help="사람이 문맥을 확인해 보존하기로 한 목표 KH-S ID")
    parser.add_argument("--translation-source", action="store_true")
    parser.add_argument("--provenance", choices=PROVENANCES, default="unknown")
    parser.add_argument("--protect-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = gate(
        args.before.read_text(encoding="utf-8"),
        args.after.read_text(encoding="utf-8"),
        args.target_rule,
        translation_source=args.translation_source,
        provenance=args.provenance,
        extra_values=custom_values(args.protect_file),
        preserved_rules=args.preserve_rule,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "통과" else 2


if __name__ == "__main__":
    raise SystemExit(main())
