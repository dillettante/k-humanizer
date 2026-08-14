#!/usr/bin/env python3
"""Validate the public quick-rule specification and print its deterministic inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_RULES = Path(__file__).resolve().parent.parent / "references" / "quick-rules.json"


def build(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("rules must be a non-empty list")
    ids = [item.get("id") for item in rules if isinstance(item, dict)]
    if len(ids) != len(rules) or len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.startswith("KH-S") for item in ids):
        raise ValueError("each rule requires a unique KH-S id")
    for rule in rules:
        anchor_type = rule.get("anchor_type")
        if anchor_type == "regex":
            import re

            re.compile(str(rule.get("pattern", "")))
        elif anchor_type == "sentence_run" and int(rule.get("minimum_run", 0)) < 2:
            raise ValueError(f"{rule['id']} requires minimum_run >= 2")
        elif anchor_type == "structural":
            kind = rule.get("structural_kind")
            if kind not in {"meta_discourse", "return_signal", "advance_label", "emphasis_run"}:
                raise ValueError(f"{rule['id']} requires a supported structural_kind")
            if kind == "emphasis_run" and int(rule.get("minimum_run", 0)) < 2:
                raise ValueError(f"{rule['id']} requires minimum_run >= 2")
        elif anchor_type == "triadic_chain":
            pass
        else:
            if anchor_type not in {"regex", "sentence_run", "structural", "triadic_chain"}:
                raise ValueError(f"unsupported anchor type: {anchor_type}")
    return {"schema_version": payload.get("schema_version"), "rule_count": len(rules), "rule_ids": ids, "status": "valid"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = build(args.rules)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"quick-rules build failed: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
