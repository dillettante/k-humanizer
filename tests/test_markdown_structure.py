#!/usr/bin/env python3
"""Smoke tests for Markdown structure verification."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from verify_markdown_structure import verify  # noqa: E402


BEFORE = """# 제목

## 핵심 요소

**강조**할 내용이다. ✅

```python
print('ok')
```
"""


def main() -> int:
    unchanged = verify(BEFORE, BEFORE)
    removed_heading = verify(BEFORE, BEFORE.replace("## 핵심 요소\n\n", ""))
    removed_bold = verify(BEFORE, BEFORE.replace("**강조**", "강조"))
    removed_emoji = verify(BEFORE, BEFORE.replace(" ✅", ""))
    if unchanged["status"] != "통과":
        raise SystemExit("unchanged Markdown should pass")
    for name, result, expected in (
        ("heading", removed_heading, "headings"),
        ("bold", removed_bold, "bold_marker_count"),
        ("emoji", removed_emoji, "emoji"),
    ):
        if result["status"] != "보류" or expected not in result["changed"]:
            raise SystemExit(f"{name} removal was not held")
    print({"status": "passed", "cases": 4})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
