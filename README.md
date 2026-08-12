# K-humanizer

> AI식 한국어를 해체하고 저자 목소리를 살리는 근거 기반 윤문 스킬

독자에게 기계적으로 느껴지는 한국어를 어휘·문장·문단·리듬·서식 층에서 진단합니다. 표준 인간화에서는 상투구를 지우는 데 멈추지 않고 문단의 논리와 호흡을 다시 짭니다. 그러면서도 뜻·인용·수치·용어·저자 목소리는 보존합니다.

`AI 티를 없애 달라`, `사람이 쓴 것처럼 다듬어 달라`는 요청은 기본적으로 **표준 인간화**로 처리합니다. 진단만 하거나 표지 몇 개만 바꾸지 않고, `빼기 → 다시 짜기 → 목소리 복원`의 세 단계로 완성본을 만듭니다. 이 스킬은 AI 작성 여부를 판별하거나 탐지를 피하도록 돕지 않습니다.

> 상태: v0.3 prototype. 31개 문체 패턴, 20개 결정적 앵커, 무수정·신규 표지 gate, Markdown·DOCX 형식 프로필, 전방 비교 검증을 갖췄습니다. 독립적인 맹검 사람 평가는 계속 진행 중입니다.

## 무엇을 하나요

| 작업 | K-humanizer의 기준 |
| --- | --- |
| AI식 문투 해체 | 결산형 전개·기계적 병렬·추상 명사화·번역투·균일한 리듬을 단어가 아닌 문단 단위로 다시 씁니다. |
| 한국어 산문 윤문 | 진단·최소 윤문·표준 인간화·목소리 복원 중 작업 강도를 고릅니다. |
| 번역투 검토 | 원문이 있으면 자연스러움보다 뜻·주체·부정·양태·논리 관계를 먼저 대조합니다. |
| 사람이 다듬은 원고 검토 | 억지로 문제를 만들지 않고, 의도한 반복·호흡·형식을 보존합니다. |
| 파일 형식 보존 | Markdown의 `#`·`**`는 구조로 보존하고, DOCX의 장식성 이모지·굵은 본문·가짜 제목만 따로 진단합니다. |
| 장문 원고 | manifest와 review ledger로 실제 검사·판정 범위를 남기고, 구조 변경은 확인 요청으로 남깁니다. |
| 안전·비교 검사 | 인용·수치·날짜·조문을 보호하고, 윤문 후보는 같은 기준으로 비교합니다. |
| 문형·연구 조사 | KCI 조사 상태를 구분하고, 검증되지 않은 수치 규칙을 만들지 않습니다. |

특정 작가의 문체를 흉내 내거나, 입력에 없는 사실·예시·감정을 보태지 않습니다.

## 빠른 사용

설치 뒤 아래처럼 요청하면 됩니다.

```text
이 글의 AI식 문투를 벗겨 내고 사람이 쓴 것처럼 다듬어 줘.
상투구만 바꾸지 말고 문단의 논리와 호흡을 다시 짜되,
원문의 명제를 강화하거나 새 과정을 넣지 마.
```

`AI 티 제거`는 표준 인간화가 기본입니다. 수정 범위를 줄이고 싶으면 따로 밝힙니다.

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

- 모드·입력 내력·장르·파일 형식·번역 원문·보호 구간을 확인합니다.
- 문체 후보를 위치와 문맥 조건으로만 진단합니다.
- 표준 인간화는 `빼기 → 다시 짜기 → 목소리 복원`으로 진행합니다.
- 편집 전 문단별 의미 명세를 만들고, 윤문본의 모든 명제를 원문에 대응시킵니다.
- 보호값, 목표 표지 감소, 신규 표지, 의미·리듬을 전후 대조합니다.

## 결정적 안전 검사

스킬에는 모델의 문맥 판단을 대체하지 않는 작은 검사기가 함께 들어 있습니다. 직접 인용·날짜·수치·조문 보존과, 지정한 문체 표지의 전후 변화를 확인할 때 씁니다.

    python3 scripts/scan_style.py --input draft.txt
    python3 scripts/verify_style_gate.py --before draft.txt --after edited.txt --target-rule KH-S02

수정 대상으로 지정한 표지가 줄지 않으면 무수정본도 `보류`다. 문맥상 보존하려면 사람이 확인한 뒤 `--preserve-rule`로 명시한다. 윤문 결과에 다른 표지가 새로 생겨도 통과하지 않는다.

DOCX에서는 Markdown 기호를 문자로 찾지 않고 실제 스타일·굵은 글씨·목록·이모지를 진단한다.

    python3 scripts/scan_docx_format.py --input draft.docx

Markdown의 제목·굵은 표지·이모지·코드 펜스는 사용자가 서식 재설계를 요청하지 않았다면 그대로 남겨야 한다.

    python3 scripts/verify_markdown_structure.py --before draft.md --after edited.md

번역 원문이 실제로 제공됐을 때만 scan_style.py에 --translation-source를 붙입니다. 전체 자작 공개 fixture는 다음으로 검증할 수 있습니다.

    python3 scripts/run_regression.py

### 장문·다파일 검사 범위

장문에서 앵커를 찾았다는 사실과 모든 문맥을 읽었다는 사실은 다릅니다. 여러 파일은 manifest에 포함·제외와 이유를 먼저 적고, 스캔 뒤에는 모든 앵커의 review ledger를 만듭니다.

```json
{
  "documents": [
    {"id": "chapter-1", "path": "chapter-1.md", "role": "prose"},
    {"id": "bibliography", "path": "bibliography.md", "role": "bibliography", "include": false, "reason": "산문 검토 대상 아님"}
  ]
}
```

    python3 scripts/scan_style.py --manifest corpus.json --output scan.json
    python3 scripts/build_review_ledger.py --scan scan.json --output review-ledger.jsonl
    # review-ledger.jsonl에 실제 검토 방법·판정·이유를 기록한 뒤
    python3 scripts/verify_coverage.py --scan scan.json --ledger review-ledger.jsonl --mode sample

`sample`은 표본 경향만, `residual`은 전수 기계·규칙 분류만, `exhaustive`는 모든 앵커를 사람이 문맥 판정했을 때만 통과합니다. 따라서 결과가 “전수 문맥 검토”라고 말하려면 ledger의 모든 항목이 사람 판정이어야 합니다.

이는 전문을 처음부터 끝까지 읽었다는 주장과 다릅니다. 전문 검토를 요청받으면 [전문 검토 범위 계약](references/full-corpus-review.md)에 따라 문서의 모든 연속 구간과 구간별 독해 메모를 남깁니다. 이를 끝낼 수 없으면 `부분 검토` 또는 `전수 앵커 검토`로 범위를 낮춰 보고합니다.

Markdown 인용 블록은 기본적으로 스캔에서 제외합니다. 조문·표·인용 전문처럼 덩어리째 손대지 않을 구간은 다음 표지 사이에 둡니다.

```html
<!-- k-humanizer:protect-start -->
보호할 전문
<!-- k-humanizer:protect-end -->
```

같은 연결어가 논리 기능상 필요하지만 단조롭게 반복될 때에는 전면 치환하지 않습니다. 보존할 한 사례와 최대 2~6개의 `ask` 선택지만 제시해 저자가 결정하게 합니다.

두 윤문 후보를 비교할 때에는 다음처럼 실행합니다. 이 결과는 gate 통과 여부만 기록하며, 자연스러움의 우열은 순서를 가린 사람 검토로 판단합니다.

    python3 scripts/compare_candidates.py --before draft.txt \
      --candidate candidate-a=edited-a.txt \
      --candidate candidate-b=edited-b.txt \
      --target-rule KH-S02

## 설치

### 먼저, 내 환경 고르기

| 사용하는 제품 | 권장 경로 | 알아둘 점 |
| --- | --- | --- |
| Claude Code · Codex · Hermes | 아래의 로컬 설치 | 스크립트와 결정적 검사를 모두 사용할 수 있습니다. |
| Claude.ai | custom skill ZIP 업로드 | Code execution and file creation을 켜야 합니다. |
| ChatGPT의 Skills | skill ZIP 업로드 | 지원 플랜·워크스페이스 권한이 필요합니다. |
| Claude.ai Project · ChatGPT 맞춤 GPT | 지침·참고자료를 직접 넣기 | 대안 경로이며, 번들 스크립트의 자동 실행은 보장하지 않습니다. |

### Claude Code · Codex · Hermes (로컬 설치)

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

새 세션에서 `K-humanizer` 또는 `$k-humanizer`를 언급하거나, 한국어 산문·번역문의 진단·최소 윤문·표준 인간화·목소리 복원을 자연어로 요청하세요.

### Claude.ai (웹·데스크톱 대화형 Claude)

Claude.ai에서는 이 저장소를 custom skill로 올릴 수 있습니다. 개인 계정은 **Settings → Capabilities**에서 Code execution and file creation을 켠 뒤, **Customize → Skills → + Create skill → Upload a skill**로 들어갑니다. Team·Enterprise는 조직 관리자가 Skills와 Code execution을 먼저 켜야 할 수 있습니다. 업로드한 skill은 개인 계정에만 적용되며, Team·Enterprise에서는 별도 공유 기능을 사용할 수 있습니다. [Claude 공식 안내](https://support.claude.com/en/articles/12512180-use-skills-in-claude)를 따르세요.

업로드 파일은 `k-humanizer/` 폴더가 최상위에 있고 그 안에 `SKILL.md`가 있는 ZIP이어야 합니다. 터미널을 쓸 수 있다면 아래처럼 만듭니다.

```bash
git clone https://github.com/dillettante/k-humanizer.git
zip -r k-humanizer.zip k-humanizer -x '*/.git/*' '*/__pycache__/*'
```

터미널을 쓰지 않는다면 GitHub의 **Code → Download ZIP**으로 받은 파일을 푼 뒤, 최상위 폴더 이름을 `k-humanizer`로 바꾸고 그 폴더를 다시 ZIP으로 압축하세요. 업로드 후 Skills 목록에서 켠 다음, “K-humanizer를 사용해 이 글을 보수적으로 윤문해 줘”처럼 요청합니다.

### ChatGPT Skills (웹·모바일·데스크톱 대화형 ChatGPT)

Skills가 보이는 계정에서는 위에서 만든 같은 ZIP을 올릴 수 있습니다. **Plugins → Skills → Create → Upload**를 열어 업로드한 뒤 활성화하세요. 현재 개인 Skills는 일반적으로 ChatGPT Business·Enterprise·Healthcare·Edu에서 제공되며, Enterprise·Edu에서는 관리자가 Skills와 업로드 권한을 켜야 합니다. 개인 Skills는 데스크톱과 웹·모바일 사이에 자동 동기화되지 않으므로 사용하는 화면마다 설치합니다. [ChatGPT 공식 안내](https://help.openai.com/en/articles/20001066)를 확인하세요.

### Skills 메뉴가 없을 때: 대화형 대안

이 경로는 스킬을 설치하는 것은 아니지만, 같은 작업 원칙을 지속해서 쓰는 실용적인 방법입니다.

- **Claude.ai:** Project를 만들고 `SKILL.md`의 작업 원칙을 Project instructions에 넣습니다. 필요한 `references/*.md`만 Project knowledge에 올립니다. [Claude Projects](https://support.claude.com/en/articles/9517075-what-are-projects)는 파일과 프로젝트별 지침을 지원합니다.
- **ChatGPT:** 맞춤 GPT를 만들 수 있는 계정이라면 Instructions에 `SKILL.md`의 핵심 작업 흐름을 넣고, 필요한 `references/*.md`를 Knowledge로 올립니다. 맞춤 GPT는 지침과 업로드 자료를 지원하지만, 이 저장소의 Python 검사가 자동 실행된다고 가정하면 안 됩니다. [GPT 만들기 안내](https://help.openai.com/en/articles/8554397-use-advanced-data-analysis-in-chatgpt)를 참고하세요.
- **일반 채팅:** 원고를 첨부하고 아래 요청문을 매번 함께 보냅니다. 긴 원고는 한 번에 전문 검토를 주장하지 말고, 장·절 단위로 나눠 범위를 기록합니다.

```text
이 원고를 K-humanizer의 표준 인간화로 다듬어 줘. AI 저자 판별이나 탐지 회피는 하지 마.
상투구 치환에 멈추지 말고 번역투·기계적 병렬·결산형 전개·추상 명사화·균일한 리듬을 문단 단위로 해체해 줘.
직접 인용·수치·날짜·조문 인용 표기와 저자의 의도한 반복·호흡은 보존해 줘. 편집 전에 문단별 의미 명세를 잡고,
원문에 없던 명제·강화·인과·과정을 넣지 마. 전문을 읽지 않았다면 그 범위를 명시해 줘. 완성본을 먼저 보여 줘.
```

## 근거와 공개 범위

스킬의 공개 근거 상태와 KCI 조사 방법은 [`references/evidence-status.md`](references/evidence-status.md), [`references/kci-query-manifest.json`](references/kci-query-manifest.json)를 참고하세요. AI 문체 표지의 작동 기준·안전 범위·후보 비교 절차는 [`references/ai-style-taxonomy.md`](references/ai-style-taxonomy.md), [`references/evaluation-contract.md`](references/evaluation-contract.md), [`references/comparison-protocol.md`](references/comparison-protocol.md), [`references/repetition-alternatives.md`](references/repetition-alternatives.md)에 있습니다. API 응답 원문, 자격 증명, 비공개 원고·문체 규칙·스캔본은 저장소에 포함하지 않습니다.

## 경계

- 저자 판별이나 AI 탐지 회피를 하지 않습니다.
- 숫자, 날짜, 직접 인용, 조문 인용 표기는 기본 보호 구간으로 다룹니다. 법률·학술 용어, 이름, 법령·판결문 본문은 보호 파일 또는 명시 보호 블록으로 지정합니다.
- 출처 귀속, 논증 순서, 장 구성처럼 구조를 바꿀 수 있는 제안은 저자의 확인을 받습니다.
- 표절 판별, 참고문헌 검증, 책 전체의 구조 감사는 전용 도구의 범위입니다.

자세한 작업 흐름과 판단 기준은 [`SKILL.md`](SKILL.md)를 보세요.
