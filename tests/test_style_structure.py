from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from scan_style import scan, scan_manifest


POST_EDITED_SAMPLE = """이 장은 그 경계선을 긋는 장이다.

이제 경계선을 긋자. 전제부터 분명히 한다.

**읽기 전에는 정찰이다.** 읽기 전에 길을 살핀다.

**읽는 중에는 좌표 확인이다.** 읽는 동안 현재 자리를 확인한다.

**읽은 뒤에는 대조다.** 기록과 기억을 대조한다.

이 어긋남이 왜 위험한지는 분명하다.

첫머리의 세 요약으로 돌아가자.
"""


def test_post_editing_structural_candidates_have_location_metadata() -> None:
    result = scan(POST_EDITED_SAMPLE, provenance="ai_edited")

    assert result["counts"] == {"KH-S34": 2, "KH-S35": 1, "KH-S36": 1, "KH-S37": 1}
    assert result["structural_summary"] == {"paragraph_count": 7, "body_paragraph_count": 7}
    meta = result["findings"][0]
    assert {"paragraph", "sentence_in_paragraph", "is_paragraph_first", "is_paragraph_last", "paragraph_kind", "section_heading", "is_document_last"} <= set(meta)
    assert meta["paragraph"] == 1
    assert meta["is_paragraph_first"] is True


def test_post_editing_candidates_do_not_run_without_ai_edited_provenance() -> None:
    result = scan(POST_EDITED_SAMPLE)

    assert not result["counts"]
    skipped = {item["rule_id"] for item in result["skipped_rules"]}
    assert {"KH-S34", "KH-S35", "KH-S36", "KH-S37"} <= skipped


def test_manifest_reports_cross_document_structural_repeats(tmp_path: Path) -> None:
    (tmp_path / "chapter-1.md").write_text("이 장은 첫 구분을 하는 장이다.\n\n첫머리의 질문으로 돌아가자.\n", encoding="utf-8")
    (tmp_path / "chapter-2.md").write_text("이 장은 둘째 구분을 하는 장이다.\n\n첫머리의 장면으로 돌아가자.\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"documents": [{"id": "chapter-1", "path": "chapter-1.md"}, {"id": "chapter-2", "path": "chapter-2.md"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = scan_manifest(manifest, provenance="ai_edited")

    assert result["counts"]["KH-S34"] == 2
    assert result["counts"]["KH-S35"] == 2
    repeats = {(item["rule_id"], item["shape"]): item for item in result["cross_document_repeats"]}
    assert repeats[("KH-S34", "이 장은 __다.")]["documents"] == 2
    assert repeats[("KH-S35", "__로 돌아가자.")]["occurrences"] == 2


def test_markdown_non_prose_does_not_create_structural_candidates() -> None:
    result = scan("```text\n이 장은 그 경계선을 긋는 장이다.\n첫머리로 돌아가자.\n```\n<!-- 이제 경계선을 긋자. -->\n", provenance="ai_edited")

    assert not result["counts"]


def test_return_signal_is_not_limited_to_the_last_paragraph() -> None:
    result = scan("첫머리의 질문으로 돌아가자.\n\n이제 다음 논의를 시작한다.\n", provenance="ai_edited")

    finding = next(item for item in result["findings"] if item["rule_id"] == "KH-S35")
    assert finding["body_paragraphs_to_end"] == 2


def test_bold_navigation_labels_do_not_count_as_emphasis_run() -> None:
    result = scan("**제1장 출발**\n\n**제2장 전개**\n\n**부록 자료**\n", provenance="ai_edited")

    assert "KH-S37" not in result["counts"]


def test_triadic_chain_is_collected_without_semantic_verdict() -> None:
    redundant = scan("그의 마음은 무너졌고 흩어졌으며 소멸했다.")
    procedural = scan("자료를 모으고 분류하며 검증했다.")

    assert redundant["counts"]["KH-S40"] == 1
    assert procedural["counts"]["KH-S40"] == 1
    assert "의미 기여도 확인" in redundant["findings"][0]["evidence"]
    assert redundant["findings"][0]["shape"] == "삼항 병렬: -고/-며"


def test_triadic_chain_in_quote_or_protected_block_is_not_collected() -> None:
    text = """> 그의 마음은 무너졌고 흩어졌으며 소멸했다.

<!-- k-humanizer:protect-start -->
중요하고 핵심적이며 필수적이다.
<!-- k-humanizer:protect-end -->
"""

    result = scan(text)

    assert "KH-S40" not in result["counts"]


def test_triadic_chain_does_not_split_words_or_quotative_endings() -> None:
    text = "알고리즘은 내가 좋아할 것을 주고, 도구는 원하는 답을 준다. 그는 사실이라고 믿는다고 썼다."

    result = scan(text)

    assert "KH-S40" not in result["counts"]
