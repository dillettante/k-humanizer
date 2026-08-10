# K-humanizer

> AI 문체 표지를 줄이는 근거 기반 한국어 윤문·번역 검증 스킬

독자에게 기계적으로 느껴지는 한국어 문체 표지를 진단하고, 뜻·인용·수치·용어·문체·의도한 리듬을 지키며 최소한으로 윤문합니다.

`AI 티를 줄여 달라`는 요청은 저자 판별이 아니라 독자가 읽으며 느끼는 문체의 기계적 표지를 줄이는 요청으로 처리합니다. 이 스킬은 AI 작성 여부를 판별하거나 탐지를 피하도록 돕지 않으며, 이미 충분한 문장은 `수정 없음`으로 판단합니다.

> 상태: v0.2 prototype. 결정적 안전 검사는 갖췄지만, upstream live A/B와 blind 사람 평가는 진행 중입니다.

## 무엇을 하나요

| 작업 | K-humanizer의 기준 |
| --- | --- |
| AI 문체 표지 진단 | 번역투·기계적 병렬·결산 상투구·과잉 완곡 등을 위치와 문맥에 따라 최소 수정합니다. |
| 한국어 산문 윤문 | 문제의 위치와 까닭이 확인될 때만 고칩니다. |
| 번역투 검토 | 원문이 있으면 자연스러움보다 뜻·주체·부정·양태·논리 관계를 먼저 대조합니다. |
| 사람이 다듬은 원고 검토 | 억지로 문제를 만들지 않고, 의도한 반복·호흡·형식을 보존합니다. |
| 장문 원고 | 편집 브리프와 보호 구간을 먼저 정하고, 구조 변경은 확인 요청으로 남깁니다. |
| 안전·비교 검사 | 인용·수치·날짜·조문을 보호하고, 윤문 후보는 같은 기준으로 비교합니다. |
| 문형·연구 조사 | KCI 조사 상태를 구분하고, 검증되지 않은 수치 규칙을 만들지 않습니다. |

특정 작가의 문체를 흉내 내거나, 입력에 없는 사실·예시·감정을 보태지 않습니다.

## 빠른 사용

설치 뒤 아래처럼 요청하면 됩니다.

```text
이 문단을 보수적으로 윤문해 줘. 숫자와 직접 인용은 그대로 두고,
각 수정에 짧게 이유를 붙여 줘.
```

```text
AI 티가 나는 상투적 전개·기계적 병렬·번역투만 진단해 줘.
의도한 반복과 직접 인용은 유지하고, 수정할 이유와 수정하지 않을 반례도 적어 줘.
```

번역문은 원문을 함께 주고, 원문이 없을 때에는 `자연스러움만 검토`라고 밝혀 달라고 요청하세요.

```text
원문과 번역문을 대조해 줘. 의미·주체·부정·양태·논리 관계를 먼저 확인하고,
확실한 번역투만 최소 수정해 줘.
```

## 어떻게 작동하나요

- 장르·번역 원문·보호 구간을 확인합니다.
- 문체 후보를 위치와 문맥 조건으로만 진단합니다.
- `remove`, `reshape`, `preserve`, `ask` 중 하나로 최소 편집을 결정합니다.
- 보호값과 목표 표지의 전후 차이를 검사하고, 의미·리듬 판단은 사람에게 남깁니다.

## 결정적 안전 검사

스킬에는 모델의 문맥 판단을 대체하지 않는 작은 검사기가 함께 들어 있습니다. 직접 인용·날짜·수치·조문 보존과, 지정한 문체 표지의 전후 변화를 확인할 때 씁니다.

    python3 scripts/scan_style.py --input draft.txt
    python3 scripts/verify_style_gate.py --before draft.txt --after edited.txt --target-rule KH-S02

번역 원문이 실제로 제공됐을 때만 scan_style.py에 --translation-source를 붙입니다. 전체 자작 공개 fixture는 다음으로 검증할 수 있습니다.

    python3 scripts/run_regression.py

두 윤문 후보를 비교할 때에는 다음처럼 실행합니다. 이 결과는 gate 통과 여부만 기록하며, 자연스러움의 우열은 순서를 가린 사람 검토로 판단합니다.

    python3 scripts/compare_candidates.py --before draft.txt \
      --candidate candidate-a=edited-a.txt \
      --candidate candidate-b=edited-b.txt \
      --target-rule KH-S02

## 설치

### Claude Code · Codex · Hermes

이 저장소를 한 번 내려받은 뒤 설치 스크립트를 실행합니다. 스크립트는 현재 저장소를 공통 경로 `~/.agents/skills/k-humanizer`에 연결하고, 선택한 런타임의 스킬 경로에 다시 연결합니다. 기존 `k-humanizer` 설치를 덮어쓰지 않습니다.

```bash
git clone https://github.com/dillettante/k-humanizer.git
cd k-humanizer
./install.sh
```

특정 런타임만 설치하려면 다음 중 하나를 씁니다.

```bash
./install.sh --claude
./install.sh --codex
./install.sh --hermes
```

설치 위치는 다음과 같습니다.

| 런타임 | 스킬 경로 |
| --- | --- |
| Claude Code | `~/.claude/skills/k-humanizer` |
| Codex | `~/.codex/skills/k-humanizer` |
| Hermes | `~/.hermes/skills/k-humanizer` |

새 세션에서 `K-humanizer` 또는 `$k-humanizer`를 언급하거나, 한국어 산문·번역문 최소 윤문을 자연어로 요청하세요.

### ChatGPT

ChatGPT의 **Plugins → Skills → Create → Upload**에서 이 저장소를 내려받은 폴더(또는 그 ZIP 파일)를 올려 설치합니다. ChatGPT의 개인 스킬은 데스크톱과 웹·모바일에 각각 따로 설치됩니다. 계정·워크스페이스 권한에 따라 Skills 또는 업로드 메뉴가 보이지 않을 수 있습니다.

## 근거와 공개 범위

스킬의 공개 근거 상태와 KCI 조사 방법은 [`references/evidence-status.md`](references/evidence-status.md), [`references/kci-query-manifest.json`](references/kci-query-manifest.json)를 참고하세요. AI 문체 표지의 작동 기준·안전 범위·후보 비교 절차는 [`references/ai-style-taxonomy.md`](references/ai-style-taxonomy.md), [`references/evaluation-contract.md`](references/evaluation-contract.md), [`references/comparison-protocol.md`](references/comparison-protocol.md)에 있습니다. API 응답 원문, 자격 증명, 비공개 원고·문체 규칙·스캔본은 저장소에 포함하지 않습니다.

## 경계

- 저자 판별이나 AI 탐지 회피를 하지 않습니다.
- 법률·학술 용어, 숫자, 날짜, 이름, 직접 인용, 인용 정보는 보호 구간으로 다룹니다.
- 출처 귀속, 논증 순서, 장 구성처럼 구조를 바꿀 수 있는 제안은 저자의 확인을 받습니다.
- 표절 판별, 참고문헌 검증, 책 전체의 구조 감사는 전용 도구의 범위입니다.

자세한 작업 흐름과 판단 기준은 [`SKILL.md`](SKILL.md)를 보세요.
