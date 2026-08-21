#!/usr/bin/env python3
"""Find deterministic Korean style-candidate anchors; never infer authorship."""

from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import re
from statistics import median
import sys
from pathlib import Path

from protected_spans import custom_values, overlaps_protected, protected_spans


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR.parent / "references" / "quick-rules.json"
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_CODE = re.compile(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$")
PROTECT_START = re.compile(r"<!--\s*k-humanizer:protect-start\s*-->", re.IGNORECASE)
PROTECT_END = re.compile(r"<!--\s*k-humanizer:protect-end\s*-->", re.IGNORECASE)
PROVENANCES = ("raw_ai", "ai_edited", "human_draft", "rule_guided_draft", "human_polished", "unknown")
ALLOW_SCOPES = ("all", "heading", "body", "first_sentence")
HEADING = re.compile(r"^[ \t]*(#{1,6})[ \t]+(.+?)\s*$")
SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+(?:\*\*)?|$)")
BOLD = re.compile(r"\*\*([^*\n]{1,72})\*\*")
BLOCKQUOTE = re.compile(r"^\s*>")
LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
HORIZONTAL_RULE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")


def document_structure(text: str) -> list[dict[str, object]]:
    """Return offset-preserving prose blocks and sentence positions for Markdown text."""

    paragraphs: list[dict[str, object]] = []
    offset = 0
    start: int | None = None
    chunks: list[str] = []

    def finish(end: int) -> None:
        nonlocal start, chunks
        if start is None:
            return
        raw = "".join(chunks)
        heading = HEADING.match(raw.strip()) if "\n" not in raw.rstrip("\n") else None
        sentences = [
            {"start": start + match.start(), "end": start + match.end()}
            for match in SENTENCE.finditer(raw)
            if match.group(0).strip()
        ]
        if not sentences:
            sentences = [{"start": start, "end": end}]
        paragraphs.append(
            {
                "start": start,
                "end": end,
                "kind": "heading" if heading else "body",
                "heading": heading.group(2).strip() if heading else "",
                "heading_level": len(heading.group(1)) if heading else 0,
                "sentences": sentences,
            }
        )
        start = None
        chunks = []

    for line in text.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = offset
            chunks.append(line)
        else:
            finish(offset)
        offset += len(line)
    finish(offset)

    heading_stack: list[str] = []
    body_indexes = [index for index, paragraph in enumerate(paragraphs) if paragraph["kind"] == "body"]
    body_tail_rank = {index: len(body_indexes) - position for position, index in enumerate(body_indexes)}
    last_body = body_indexes[-1] if body_indexes else -1
    for index, paragraph in enumerate(paragraphs):
        if paragraph["kind"] == "heading":
            level = int(paragraph["heading_level"])
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(str(paragraph["heading"]))
        paragraph["paragraph"] = index + 1
        paragraph["section_heading"] = " > ".join(heading_stack)
        paragraph["is_document_last"] = index == last_body
        paragraph["body_paragraphs_to_end"] = body_tail_rank.get(index, 0)
    return paragraphs


def location_metadata(structure: list[dict[str, object]], index: int) -> dict[str, object]:
    starts = [int(paragraph["start"]) for paragraph in structure]
    paragraph_index = bisect_right(starts, index) - 1
    if paragraph_index < 0:
        return {"paragraph": 0, "sentence_in_paragraph": 0, "is_paragraph_first": False, "is_paragraph_last": False, "paragraph_kind": "unknown", "section_heading": "", "is_document_last": False, "body_paragraphs_to_end": 0}
    paragraph = structure[paragraph_index]
    sentences = list(paragraph["sentences"])
    sentence_index = next((position for position, sentence in enumerate(sentences) if int(sentence["start"]) <= index < int(sentence["end"])), len(sentences) - 1)
    return {
        "paragraph": int(paragraph["paragraph"]),
        "sentence_in_paragraph": sentence_index + 1,
        "is_paragraph_first": sentence_index == 0,
        "is_paragraph_last": sentence_index == len(sentences) - 1,
        "paragraph_kind": str(paragraph["kind"]),
        "section_heading": str(paragraph["section_heading"]),
        "is_document_last": bool(paragraph["is_document_last"]),
        "body_paragraphs_to_end": int(paragraph["body_paragraphs_to_end"]),
    }


def line_column(text: str, index: int) -> tuple[int, int]:
    return text.count("\n", 0, index) + 1, index - text.rfind("\n", 0, index)


def context(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 24) : min(len(text), end + 24)].split())


def finding(
    rule_id: str,
    text: str,
    start: int,
    end: int,
    evidence: str,
    *,
    structure: list[dict[str, object]],
    shape: str | None = None,
) -> dict[str, object]:
    line, column = line_column(text, start)
    result = {
        "rule_id": rule_id,
        "start": start,
        "end": end,
        "line": line,
        "column": column,
        "evidence": evidence,
        "context": context(text, start, end),
        **location_metadata(structure, start),
    }
    if shape:
        result["shape"] = shape
    return result


def mask_preserving_offsets(text: str, pattern: re.Pattern[str]) -> tuple[str, int]:
    """Mask non-prose without changing offsets or line numbers."""

    matches = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal matches
        matches += 1
        return "".join("\n" if character == "\n" else " " for character in match.group(0))

    return pattern.sub(replacement, text), matches


def non_prose_mask(text: str) -> tuple[str, dict[str, int]]:
    masked, comments = mask_preserving_offsets(text, HTML_COMMENT)
    masked, code_blocks = mask_preserving_offsets(masked, FENCED_CODE)
    return masked, {"html_comments": comments, "fenced_code_blocks": code_blocks}


def input_warnings(text: str) -> list[str]:
    starts = len(PROTECT_START.findall(text))
    ends = len(PROTECT_END.findall(text))
    if starts != ends:
        return ["k-humanizer 보호 블록 시작·종료 표지 수가 맞지 않습니다. 해당 범위를 수동으로 확인하십시오."]
    return []


def validate_allow_profile(profile: dict[str, object] | None, rule_ids: set[str]) -> dict[str, object] | None:
    """Validate declarative genre exceptions before they affect reported counts."""

    if profile is None:
        return None
    if not isinstance(profile, dict):
        raise ValueError("allow profile must be a JSON object")
    genre = profile.get("genre", "")
    if not isinstance(genre, str) or not genre.strip():
        raise ValueError("allow profile requires a non-empty genre")
    entries = profile.get("allow")
    if not isinstance(entries, list):
        raise ValueError("allow profile requires an allow list")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"allow profile entry {position} must be an object")
        rule_id = entry.get("rule_id")
        scope = entry.get("scope")
        reason = entry.get("reason")
        if not isinstance(rule_id, str) or rule_id not in rule_ids:
            raise ValueError(f"allow profile entry {position} has an unknown rule_id")
        if not isinstance(scope, str) or scope not in ALLOW_SCOPES:
            raise ValueError(f"allow profile entry {position} scope must be one of: {', '.join(ALLOW_SCOPES)}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"allow profile entry {position} requires a non-empty reason")
        key = (rule_id, scope)
        if key in seen:
            raise ValueError(f"allow profile repeats rule_id and scope: {rule_id} / {scope}")
        seen.add(key)
        normalized.append({"rule_id": rule_id, "scope": scope, "reason": reason.strip()})
    return {"genre": genre.strip(), "allow": normalized}


def load_allow_profile(path: Path | None) -> dict[str, object] | None:
    """Load a JSON profile; rule IDs are checked by scan after the rule spec loads."""

    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("allow profile must be a JSON object")
    return payload


def allowance_for(item: dict[str, object], profile: dict[str, object] | None) -> dict[str, str] | None:
    """Return the first declared genre exception that fits a finding's location."""

    if profile is None:
        return None
    for entry in profile["allow"]:
        scope = str(entry["scope"])
        matches = (
            scope == "all"
            or (scope == "heading" and item["paragraph_kind"] == "heading")
            or (scope == "body" and item["paragraph_kind"] == "body")
            or (scope == "first_sentence" and item["paragraph_kind"] == "body" and bool(item["is_paragraph_first"]))
        )
        if matches and item["rule_id"] == entry["rule_id"]:
            return {"scope": scope, "reason": str(entry["reason"])}
    return None


def paragraph_rhythm(structure: list[dict[str, object]], scan_text: str) -> dict[str, object]:
    """Describe prose paragraph rhythm with an explicit, non-normative population."""

    excluded = {"heading": 0, "blockquote": 0, "list": 0, "table": 0, "horizontal_rule": 0}
    sentence_counts: list[int] = []
    for paragraph in structure:
        if paragraph["kind"] == "heading":
            excluded["heading"] += 1
            continue
        raw = scan_text[int(paragraph["start"]) : int(paragraph["end"])].strip()
        if BLOCKQUOTE.match(raw):
            excluded["blockquote"] += 1
            continue
        lines = [line for line in raw.splitlines() if line.strip()]
        if lines and all(LIST_ITEM.match(line) for line in lines):
            excluded["list"] += 1
            continue
        if lines and all(TABLE_ROW.match(line) for line in lines):
            excluded["table"] += 1
            continue
        if HORIZONTAL_RULE.match(raw):
            excluded["horizontal_rule"] += 1
            continue
        sentence_counts.append(len(paragraph["sentences"]))
    count = len(sentence_counts)
    single = sum(value == 1 for value in sentence_counts)
    return {
        "population": "Markdown body paragraphs excluding headings, blockquotes, lists, tables, and horizontal rules",
        "paragraph_count": count,
        "sentence_count": sum(sentence_counts),
        "single_sentence_paragraph_count": single,
        "single_sentence_paragraph_ratio": round(single / count, 4) if count else None,
        "mean_sentences_per_paragraph": round(sum(sentence_counts) / count, 4) if count else None,
        "median_sentences_per_paragraph": median(sentence_counts) if count else None,
        "excluded_paragraphs": excluded,
        "limit": "관찰용 리듬 지표다. 장르·문단 기능을 무시한 상한이나 통과 기준으로 쓰지 않는다.",
    }


def sentence_rule_distribution(findings: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    """Show clustering inside a sentence, not only document-wide anchor totals."""

    slots: dict[str, dict[tuple[str, int, int], int]] = {}
    for item in findings:
        rule_id = str(item["rule_id"])
        slot = (str(item.get("document_id", "single-input")), int(item["paragraph"]), int(item["sentence_in_paragraph"]))
        by_slot = slots.setdefault(rule_id, {})
        by_slot[slot] = by_slot.get(slot, 0) + 1
    return {
        rule_id: {
            "sentences_with_findings": len(counts),
            "sentences_with_2plus": sum(value >= 2 for value in counts.values()),
            "max_per_sentence": max(counts.values()),
        }
        for rule_id, counts in sorted(slots.items())
    }


def sentence_run_findings(
    rule: dict[str, object],
    source_text: str,
    scan_text: str,
    protected: list[dict[str, object]],
    structure: list[dict[str, object]],
) -> list[dict[str, object]]:
    # A non-matching or protected sentence must remain a run boundary. Dropping it
    # would join matching endings across intervening prose or a protected block.
    sentences: list[tuple[int, int, str | None]] = []
    for match in re.finditer(r"[^.!?\n]+[.!?]", scan_text):
        ending = None
        if not overlaps_protected(match.start(), match.end(), protected):
            ending = re.search(r"(습니다|이다|한다|된다|있다)\.$", match.group(0).strip())
        sentences.append((match.start(), match.end(), ending.group(1) if ending else None))
    minimum = int(rule["minimum_run"])
    results: list[dict[str, object]] = []
    start = 0
    while start < len(sentences):
        if sentences[start][2] is None:
            start += 1
            continue
        end = start + 1
        while end < len(sentences) and sentences[end][2] == sentences[start][2]:
            end += 1
        if end - start >= minimum:
            first, last = sentences[start], sentences[end - 1]
            results.append(finding(str(rule["id"]), source_text, first[0], last[1], f"{first[2]} 종결 {end - start}문장 연속", structure=structure))
        start = end
    return results


def triadic_chain_findings(
    rule: dict[str, object],
    source_text: str,
    scan_text: str,
    protected: list[dict[str, object]],
    structure: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Collect three-part predicate chains; semantic redundancy remains a human decision."""

    connector = r"(?:(?<![다라냐자])고|(?<![다라냐자])며)(?:\s*,\s*|\s+)"
    pattern = re.compile(
        rf"[^.!?\n,]{{1,36}}?{connector}"
        rf"[^.!?\n,]{{1,28}}?{connector}"
        r"[^.!?\n]{1,40}(?=[.!?])"
    )
    results: list[dict[str, object]] = []
    for match in pattern.finditer(scan_text):
        if overlaps_protected(match.start(), match.end(), protected):
            continue
        results.append(
            finding(
                str(rule["id"]),
                source_text,
                match.start(),
                match.end(),
                f"삼항 병렬 후보—세 항목의 의미 기여도 확인: {match.group(0).strip()}",
                structure=structure,
                shape="삼항 병렬: -고/-며",
            )
        )
    return results


def structural_findings(
    rule: dict[str, object],
    source_text: str,
    scan_text: str,
    protected: list[dict[str, object]],
    structure: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Find post-editing structural candidates; every result requires human judgment."""

    rule_id = str(rule["id"])
    kind = str(rule["structural_kind"])
    results: list[dict[str, object]] = []

    def add(start: int, end: int, evidence: str, shape: str) -> None:
        if not overlaps_protected(start, end, protected):
            results.append(finding(rule_id, source_text, start, end, evidence, structure=structure, shape=shape))

    if kind == "meta_discourse":
        patterns = (
            (re.compile(r"(?:이|이런)\s*(?:글|장|절)(?:은|에서는?)\s*[^.!?\n]{0,60}(?:장이다|이야기다|다룬다|시작한다|핵심이다|쓴다)"), "장·절 선언", "이 장은 __다."),
            (re.compile(r"(?:이제|먼저|여기서)\s+[^.!?\n]{0,48}(?:하자|두자|정리하자|살펴보자|이야기하자|짚고\s*가자|말해\s*두자|시작하자|긋자|듣자|들자|넘어가자)"), "메타 청유형 도입", "메타 청유: __"),
            (re.compile(r"(?:이제|먼저|여기서)\s+[^.!?\n]{0,48}밝힌다"), "메타 평서", "메타 지시: __"),
            (re.compile(r"(?:전제|기준|뜻|범위)[^.!?\n]{0,24}(?:밝힌다|정리한다|정해\s*두자)"), "논지 예고", "논지 예고: __"),
        )
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            raw = scan_text[start : int(paragraph["end"])]
            for pattern, label, shape in patterns:
                for match in pattern.finditer(raw):
                    absolute_start = start + match.start()
                    if location_metadata(structure, absolute_start)["is_paragraph_first"] and "돌아가자" not in match.group(0):
                        add(absolute_start, start + match.end(), f"{label}: {match.group(0)}", shape)
    elif kind == "return_signal":
        # Location metadata tells the reviewer whether this is a genuine chapter
        # close. A hard "last paragraph" filter misses closes followed by a note,
        # checklist, or a later inserted section; the lexical signal itself is only
        # a review candidate, never an instruction to remove the return.
        pattern = re.compile(r"(?:이제\s+)?[^.!?\n]{2,40}?(?:으로|로)\s*(?:돌아가자|마무리하자)")
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            for match in pattern.finditer(scan_text[start : int(paragraph["end"])]):
                add(start + match.start(), start + match.end(), f"장면 회귀: {match.group(0)}", "__로 돌아가자.")
    elif kind == "advance_label":
        patterns = (
            (re.compile(r"[^.!?\n]{1,48}(?:은|는|이|가|지는)\s+(?:분명하다|분명해진다)"), "자명 선언", "__는 분명하다."),
            (re.compile(r"[^.!?\n]{1,40}(?:은|는|이|가)\s*(?:하나|둘|셋|넷|다섯|한|두|세|네)\s*(?:가지|개|뿐)이다"), "열거 예고", "__는 N가지다."),
            (re.compile(r"한\s*문장으로\s*(?:하면|말하면|요약하면|정리하면|이렇다|요약된다|정한다)[^.!?\n]{0,32}"), "한 문장 예고", "한 문장으로 __"),
        )
        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            raw = scan_text[start : int(paragraph["end"])]
            for pattern, label, shape in patterns:
                for match in pattern.finditer(raw):
                    add(start + match.start(), start + match.end(), f"{label}: {match.group(0)}", shape)
    elif kind == "nominalization_echo":
        # 용언으로 쓴 것을 바로 뒤에서 「그 + 명사형(-ㅁ)」으로 되받는 자리다.
        # 「안목은 자라고 … 그 자람에」·「내가 틀린 것 … 그 틀림이」.
        #
        # 왜 정규식 하나로 안 되는가 — 결함의 조건이 「낱말의 꼴」이 아니라
        # 「앞에 같은 어간의 용언이 있었는가」라는 관계이기 때문이다. 그래서
        # ① 「그 X + 조사」로 후보를 모으고 ② X의 어간을 만들어 ③ 같은 문장 안에서 찾는다.
        #
        # 어간 만들기: 한글 음절은 (초성×21 + 중성)×28 + 종성으로 짜여 있다.
        # 종성만 0으로 돌리면 「람」→「라」가 된다(28로 나눈 나머지를 뺀다).
        # 그리고 「틀리」는 「틀린」과 글자가 달라 그대로는 못 찾으므로,
        # 마지막 음절을 「종성만 다른 28자」의 범위로 열어 둔다 — 그 28자가
        # 코드포인트 상 연속이라 정규식 문자 범위 하나로 표현된다.
        # 널리 정착한 명사는 단순한 형태 일치만으로 후보가 되면 안 된다. 이 목록은
        # 사전이 아니라 흔한 오탐을 막는 보수적 차단 목록이며, 나머지도 자동 수정하지 않는다.
        settled = {"사람", "마음", "다음", "처음", "이름", "때문", "삶", "다짐", "믿음",
                   "죽음", "웃음", "울음", "걸음", "도움", "쓰임", "살림", "즐거움", "아쉬움",
                   "다름", "부끄러움", "어려움", "두려움", "그리움", "느낌", "생각"}
        josa = r"(?:이|가|은|는|을|를|에|에서|으로|로|도|만|과|와|까지|부터|조차)"
        pattern = re.compile(rf"그\s+([가-힣]{{2,6}})\s*{josa}(?![가-힣])")

        def stem_pattern(noun: str) -> str | None:
            """명사형에서 종성 ㅁ을 떼어 어간을 만들고, 마지막 음절을 종성 무관으로 연다."""
            last = noun[-1]
            if not ("가" <= last <= "힣") or (ord(last) - 0xAC00) % 28 != 16:
                return None                                  # ㅁ 받침이 아니면 명사형이 아니다
            base = ord(last) - (ord(last) - 0xAC00) % 28     # 「람」 → 「라」
            head = noun[:-1]
            if not head:
                return None
            return re.escape(head) + f"[{chr(base)}-{chr(base + 27)}]"

        for paragraph in structure:
            if paragraph["kind"] != "body":
                continue
            start = int(paragraph["start"])
            for match in pattern.finditer(scan_text[start : int(paragraph["end"])]):
                noun = match.group(1)
                if noun in settled:
                    continue
                probe = stem_pattern(noun)
                if probe is None:
                    continue
                absolute = start + match.start()
                # 멀리 떨어진 동형어는 대개 다른 논점이다. 같은 문장 안의 가까운
                # 되받기만 위치 후보로 남겨 과도한 전역 어간 일치를 피한다.
                sentence_start = max(scan_text.rfind(marker, 0, absolute) for marker in ".!?\n") + 1
                window = scan_text[max(sentence_start, absolute - 64) : absolute]
                echo = re.search(probe, window)
                if echo:
                    add(absolute, start + match.end(),
                        f"명사형 되받기: 「{echo.group(0)}…」 → 「{match.group(0)}」",
                        "…Vㅁ … 그 Vㅁ")
    elif kind == "emphasis_run":
        minimum = int(rule.get("minimum_run", 3))
        # A Markdown essay normally puts each bold lead in its own paragraph.
        # Inspecting only sentences inside one paragraph misses that visual rhythm;
        # headings and list/table lines remain outside this body-paragraph run.
        run: list[dict[str, object]] = []
        for paragraph in [*structure, None]:
            if paragraph is not None and paragraph["kind"] == "body":
                start = int(paragraph["start"])
                end = int(paragraph["end"])
                raw = scan_text[start:end].strip()
                lead = BOLD.match(raw)
                navigation_heading = bool(
                    lead
                    and re.match(
                        r"(?:제\s*)?\d+\s*(?:장|부|절)|(?:프롤로그|에필로그|부록|후기|이\s*책을\s*사용하는\s*법)",
                        lead.group(1).strip(),
                    )
                )
                if lead and not navigation_heading and len(lead.group(1).strip()) <= 52:
                    run.append({"start": start, "end": end})
                    continue
            if len(run) >= minimum:
                add(int(run[0]["start"]), int(run[-1]["end"]), f"굵은 도입 라벨 {len(run)}문단 연속", "굵은 도입 라벨 연속")
            run = []
    return results


def distributions(findings: list[dict[str, object]]) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """Summarize repeated anchors without turning their count into a quality score."""

    by_rule: dict[str, dict[str, object]] = {}
    shapes: dict[tuple[str, str], list[dict[str, object]]] = {}
    for item in findings:
        rule_id = str(item["rule_id"])
        row = by_rule.setdefault(rule_id, {"occurrences": 0, "documents": {}, "evidence": {}})
        row["occurrences"] = int(row["occurrences"]) + 1
        document_id = str(item.get("document_id", "single-input"))
        documents = dict(row["documents"])
        documents[document_id] = int(documents.get(document_id, 0)) + 1
        row["documents"] = documents
        evidence = str(item["evidence"])
        evidence_counts = dict(row["evidence"])
        evidence_counts[evidence] = int(evidence_counts.get(evidence, 0)) + 1
        row["evidence"] = evidence_counts
        shape = item.get("shape")
        if isinstance(shape, str) and shape:
            shapes.setdefault((rule_id, shape), []).append(item)
    repeats: list[dict[str, object]] = []
    for (rule_id, shape), items in sorted(shapes.items()):
        document_ids = sorted({str(item.get("document_id", "single-input")) for item in items})
        if len(document_ids) < 2:
            continue
        repeats.append(
            {
                "rule_id": rule_id,
                "shape": shape,
                "documents": len(document_ids),
                "document_ids": document_ids,
                "occurrences": len(items),
                "examples": [{key: item[key] for key in ("document_id", "line", "paragraph", "context") if key in item} for item in items[:3]],
            }
        )
    return by_rule, repeats


def scan(
    text: str,
    *,
    translation_source: bool = False,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
    allow_profile: dict[str, object] | None = None,
) -> dict[str, object]:
    if provenance not in PROVENANCES:
        raise ValueError(f"provenance must be one of: {', '.join(PROVENANCES)}")
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
    profile = validate_allow_profile(allow_profile, {str(rule["id"]) for rule in rules})
    protected = protected_spans(text, extra_values)
    scan_text, masked = non_prose_mask(text)
    structure = document_structure(scan_text)
    findings: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    scanned: list[str] = []
    for rule in rules:
        rule_id = str(rule["id"])
        if "translation_source" in rule.get("requires", []) and not translation_source:
            skipped.append({"rule_id": rule_id, "reason": "원문 대조가 확인되지 않아 번역투 앵커를 스캔하지 않음"})
            continue
        if "ai_edited" in rule.get("requires", []) and provenance not in {"ai_edited", "rule_guided_draft"}:
            skipped.append({"rule_id": rule_id, "reason": "후편집 수사·구조 후보는 ai_edited 또는 rule_guided_draft 입력에서만 스캔함"})
            continue
        scanned.append(rule_id)
        if rule["anchor_type"] == "regex":
            for match in re.finditer(str(rule["pattern"]), scan_text):
                if not overlaps_protected(match.start(), match.end(), protected):
                    findings.append(finding(rule_id, text, match.start(), match.end(), match.group(0), structure=structure))
        elif rule["anchor_type"] == "sentence_run":
            findings.extend(sentence_run_findings(rule, text, scan_text, protected, structure))
        elif rule["anchor_type"] == "triadic_chain":
            findings.extend(triadic_chain_findings(rule, text, scan_text, protected, structure))
        elif rule["anchor_type"] == "structural":
            findings.extend(structural_findings(rule, text, scan_text, protected, structure))
    findings.sort(key=lambda item: (int(item["start"]), str(item["rule_id"])))
    active_findings: list[dict[str, object]] = []
    allowed_findings: list[dict[str, object]] = []
    for item in findings:
        allowance = allowance_for(item, profile)
        if allowance is None:
            item["allowed"] = False
            active_findings.append(item)
            continue
        item.update({"allowed": True, "allow_scope": allowance["scope"], "allow_reason": allowance["reason"]})
        allowed_findings.append(item)
    counts: dict[str, int] = {}
    allowed_counts: dict[str, int] = {}
    all_counts: dict[str, int] = {}
    for item in active_findings:
        rule_id = str(item["rule_id"])
        counts[rule_id] = counts.get(rule_id, 0) + 1
    for item in allowed_findings:
        rule_id = str(item["rule_id"])
        allowed_counts[rule_id] = allowed_counts.get(rule_id, 0) + 1
    for item in findings:
        rule_id = str(item["rule_id"])
        all_counts[rule_id] = all_counts.get(rule_id, 0) + 1
    distribution, repeats = distributions(active_findings)
    allowed_distribution, allowed_repeats = distributions(allowed_findings)
    scope_warnings = []
    if skipped:
        skipped_ids = ", ".join(item["rule_id"] for item in skipped)
        scope_warnings.append(f"{len(skipped)}개 규칙을 스캔하지 않았습니다 ({skipped_ids}). 이 결과는 해당 규칙군의 전수 진단이 아닙니다.")
    return {
        "schema_version": "0.3",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "provenance": provenance,
        "scanned_rules": scanned,
        "skipped_rules": skipped,
        "scope_warnings": scope_warnings,
        "protected_spans_excluded": len(protected),
        "non_prose_masked": masked,
        "input_warnings": input_warnings(text),
        "counts": counts,
        "allowed_counts": allowed_counts,
        "all_counts": all_counts,
        "counts_by_evidence": {rule_id: row["evidence"] for rule_id, row in distribution.items()},
        "rule_distribution": distribution,
        "allowed_rule_distribution": allowed_distribution,
        "cross_document_repeats": repeats,
        "allowed_cross_document_repeats": allowed_repeats,
        "per_sentence_rule_distribution": sentence_rule_distribution(active_findings),
        "structural_summary": {
            "paragraph_count": len(structure),
            "body_paragraph_count": sum(item["kind"] == "body" for item in structure),
            "paragraph_rhythm": paragraph_rhythm(structure, scan_text),
        },
        "allow_profile": None if profile is None else {"genre": profile["genre"], "entry_count": len(profile["allow"])},
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def scan_manifest(
    manifest_path: Path,
    *,
    translation_source: bool = False,
    provenance: str = "unknown",
    extra_values: list[str] | None = None,
    allow_profile: dict[str, object] | None = None,
) -> dict[str, object]:
    """Scan included documents and retain an auditable corpus receipt."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("manifest.documents must be a non-empty list")
    document_ids: set[str] = set()
    findings: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    allowed_counts: dict[str, int] = {}
    all_counts: dict[str, int] = {}
    scanned_documents: list[dict[str, object]] = []
    excluded_documents: list[dict[str, object]] = []
    for position, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            raise ValueError(f"manifest document {position} must be an object")
        document_id = str(document.get("id", "")).strip()
        relative_path = str(document.get("path", "")).strip()
        if not document_id or not relative_path:
            raise ValueError(f"manifest document {position} requires id and path")
        if document_id in document_ids:
            raise ValueError(f"duplicate document id: {document_id}")
        document_ids.add(document_id)
        include = bool(document.get("include", True))
        receipt = {
            "document_id": document_id,
            "path": relative_path,
            "role": str(document.get("role", "prose")),
        }
        if not include:
            receipt["reason"] = str(document.get("reason", "manifest에서 제외됨"))
            excluded_documents.append(receipt)
            continue
        document_path = (manifest_path.parent / relative_path).resolve()
        if not document_path.is_file():
            raise ValueError(f"manifest document not found: {relative_path}")
        document_text = document_path.read_text(encoding="utf-8")
        result = scan(
            document_text,
            translation_source=translation_source,
            provenance=provenance,
            extra_values=extra_values,
            allow_profile=allow_profile,
        )
        receipt.update(
            {
                "characters": len(document_text),
                "finding_count": len(result["findings"]),
                "candidate_finding_count": sum(result["counts"].values()),
                "allowed_finding_count": sum(result["allowed_counts"].values()),
                "protected_spans_excluded": result["protected_spans_excluded"],
                "non_prose_masked": result["non_prose_masked"],
                "input_warnings": result["input_warnings"],
                "scope_warnings": result["scope_warnings"],
                "paragraph_rhythm": result["structural_summary"]["paragraph_rhythm"],
            }
        )
        scanned_documents.append(receipt)
        for finding_item in result["findings"]:
            item = dict(finding_item)
            item["document_id"] = document_id
            findings.append(item)
            rule_id = str(item["rule_id"])
            all_counts[rule_id] = all_counts.get(rule_id, 0) + 1
            if bool(item.get("allowed")):
                allowed_counts[rule_id] = allowed_counts.get(rule_id, 0) + 1
            else:
                counts[rule_id] = counts.get(rule_id, 0) + 1
    findings.sort(key=lambda item: (str(item["document_id"]), int(item["start"]), str(item["rule_id"])))
    active_findings = [item for item in findings if not bool(item.get("allowed"))]
    allowed_findings = [item for item in findings if bool(item.get("allowed"))]
    distribution, repeats = distributions(active_findings)
    allowed_distribution, allowed_repeats = distributions(allowed_findings)
    scope_warnings = [
        {"document_id": item["document_id"], "warnings": item["scope_warnings"]}
        for item in scanned_documents
        if item.get("scope_warnings")
    ]
    return {
        "schema_version": "0.3",
        "kind": "style-candidate-scan",
        "translation_source": translation_source,
        "provenance": provenance,
        "manifest": str(manifest_path),
        "documents_expected": len(documents),
        "documents_scanned": scanned_documents,
        "documents_excluded": excluded_documents,
        "counts": counts,
        "allowed_counts": allowed_counts,
        "all_counts": all_counts,
        "counts_by_evidence": {rule_id: row["evidence"] for rule_id, row in distribution.items()},
        "rule_distribution": distribution,
        "allowed_rule_distribution": allowed_distribution,
        "cross_document_repeats": repeats,
        "allowed_cross_document_repeats": allowed_repeats,
        "per_sentence_rule_distribution": sentence_rule_distribution(active_findings),
        "scope_warnings": scope_warnings,
        "allow_profile": None if allow_profile is None else {"genre": str(allow_profile.get("genre", "")), "entry_count": len(allow_profile.get("allow", []))},
        "findings": findings,
        "limit": "결정적 앵커의 위치 후보일 뿐, 저자 판별·품질 점수·자동 수정 지시가 아님",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="검사할 UTF-8 텍스트 파일")
    source.add_argument("--text", help="검사할 텍스트")
    source.add_argument("--manifest", type=Path, help="다파일 검사 manifest JSON")
    parser.add_argument("--translation-source", action="store_true", help="대조할 번역 원문이 제공되었음을 표시")
    parser.add_argument("--provenance", choices=PROVENANCES, default="unknown", help="입력의 작성·편집 내력")
    parser.add_argument("--protect-file", type=Path, help="줄마다 추가 보호할 문자열")
    parser.add_argument("--allow-profile", type=Path, help="규칙별 장르 예외를 선언한 JSON 파일")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
    if args.manifest:
        result = scan_manifest(args.manifest, translation_source=args.translation_source, provenance=args.provenance, extra_values=custom_values(args.protect_file), allow_profile=load_allow_profile(args.allow_profile))
    else:
        text = args.input.read_text(encoding="utf-8") if args.input else str(args.text)
        result = scan(text, translation_source=args.translation_source, provenance=args.provenance, extra_values=custom_values(args.protect_file), allow_profile=load_allow_profile(args.allow_profile))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
