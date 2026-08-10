#!/usr/bin/env python3
"""Verify that baseline protected values survive an edit exactly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from protected_spans import custom_values, missing_values, protected_spans


def verify(before: str, after: str, extra_values: list[str] | None = None) -> dict[str, object]:
    missing = missing_values(before, after, extra_values)
    return {
        "schema_version": "0.1",
        "kind": "protected-span-verification",
        "status": "통과" if not missing else "보류",
        "before_protected_span_count": len(protected_spans(before, extra_values)),
        "missing": missing,
        "limit": "값의 정확한 보존만 검사한다. 위치, 의미, 새로 삽입한 사실은 별도 검토 대상이다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="윤문 전 UTF-8 파일")
    parser.add_argument("--after", type=Path, required=True, help="윤문 후 UTF-8 파일")
    parser.add_argument("--protect-file", type=Path, help="줄마다 추가 보호할 문자열")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
    result = verify(args.before.read_text(encoding="utf-8"), args.after.read_text(encoding="utf-8"), custom_values(args.protect_file))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if not result["missing"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
