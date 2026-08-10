# K-humanizer

근거에 따라 한국어 산문과 번역문을 진단하고, 뜻·인용·수치·용어·문체·의도한 리듬을 지키며 최소한으로 윤문하는 에이전트 스킬입니다.

AI가 썼는지 판별하거나 탐지를 피하도록 돕는 도구가 아닙니다. 이미 충분한 문장은 `수정 없음`으로 판단합니다.

## 무엇을 하나요

| 작업 | K-humanizer의 기준 |
| --- | --- |
| 한국어 산문 윤문 | 문제의 위치와 까닭이 확인될 때만 고칩니다. |
| 번역투 검토 | 원문이 있으면 자연스러움보다 뜻·주체·부정·양태·논리 관계를 먼저 대조합니다. |
| 사람이 다듬은 원고 검토 | 억지로 문제를 만들지 않고, 의도한 반복·호흡·형식을 보존합니다. |
| 장문 원고 | 편집 브리프와 보호 구간을 먼저 정하고, 구조 변경은 확인 요청으로 남깁니다. |
| 문형·연구 조사 | KCI 조사 상태를 구분하고, 검증되지 않은 수치 규칙을 만들지 않습니다. |

특정 작가의 문체를 흉내 내거나, 입력에 없는 사실·예시·감정을 보태지 않습니다.

## 빠른 사용

설치 뒤 아래처럼 요청하면 됩니다.

```text
이 문단을 보수적으로 윤문해 줘. 숫자와 직접 인용은 그대로 두고,
각 수정에 짧게 이유를 붙여 줘.
```

번역문은 원문을 함께 주고, 원문이 없을 때에는 `자연스러움만 검토`라고 밝혀 달라고 요청하세요.

```text
원문과 번역문을 대조해 줘. 의미·주체·부정·양태·논리 관계를 먼저 확인하고,
확실한 번역투만 최소 수정해 줘.
```

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

스킬의 공개 근거 상태와 KCI 조사 방법은 [`references/evidence-status.md`](references/evidence-status.md), [`references/kci-query-manifest.json`](references/kci-query-manifest.json)를 참고하세요. API 응답 원문, 자격 증명, 비공개 원고·문체 규칙·스캔본은 저장소에 포함하지 않습니다.

## 경계

- 저자 판별이나 AI 탐지 회피를 하지 않습니다.
- 법률·학술 용어, 숫자, 날짜, 이름, 직접 인용, 인용 정보는 보호 구간으로 다룹니다.
- 출처 귀속, 논증 순서, 장 구성처럼 구조를 바꿀 수 있는 제안은 저자의 확인을 받습니다.
- 표절 판별, 참고문헌 검증, 책 전체의 구조 감사는 전용 도구의 범위입니다.

자세한 작업 흐름과 판단 기준은 [`SKILL.md`](SKILL.md)를 보세요.
