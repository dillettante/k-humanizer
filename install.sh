#!/usr/bin/env bash
# K-humanizer를 공통 스킬 경로와 선택한 런타임에 안전하게 연결한다.
set -euo pipefail

usage() {
  cat <<'EOF'
사용법: ./install.sh [--claude] [--codex] [--hermes] [--all]

옵션을 생략하거나 --all을 주면 Claude Code, Codex, Hermes에 모두 설치합니다.
기존 k-humanizer 설치가 다른 위치를 가리키면 덮어쓰지 않고 중단합니다.
EOF
}

install_claude=false
install_codex=false
install_hermes=false

if [ "$#" -eq 0 ]; then
  install_claude=true
  install_codex=true
  install_hermes=true
fi

for argument in "$@"; do
  case "$argument" in
    --claude) install_claude=true ;;
    --codex) install_codex=true ;;
    --hermes) install_hermes=true ;;
    --all)
      install_claude=true
      install_codex=true
      install_hermes=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

source_dir="$(cd "$(dirname "$0")" && pwd -P)"
common_dir="$HOME/.agents/skills"
common_skill="$common_dir/k-humanizer"

same_location() {
  [ -e "$1" ] && [ "$(cd "$1" && pwd -P)" = "$2" ]
}

mkdir -p "$common_dir"
if [ -e "$common_skill" ] || [ -L "$common_skill" ]; then
  if ! same_location "$common_skill" "$source_dir"; then
    printf '기존 설치를 덮어쓰지 않았습니다: %s\n' "$common_skill" >&2
    printf '현재 위치: %s\n' "$(cd "$common_skill" && pwd -P)" >&2
    exit 1
  fi
else
  ln -sfn "$source_dir" "$common_skill"
fi

link_runtime() {
  runtime_dir="$1"
  runtime_name="$2"
  runtime_skill="$HOME/$runtime_dir/skills/k-humanizer"
  relative_common='../../.agents/skills/k-humanizer'

  mkdir -p "$HOME/$runtime_dir/skills"
  if [ -e "$runtime_skill" ] || [ -L "$runtime_skill" ]; then
    if ! same_location "$runtime_skill" "$source_dir"; then
      printf '기존 %s 설치를 덮어쓰지 않았습니다: %s\n' "$runtime_name" "$runtime_skill" >&2
      return 1
    fi
  else
    (cd "$HOME/$runtime_dir/skills" && ln -sfn "$relative_common" k-humanizer)
  fi
  printf '%s 설치 확인: %s\n' "$runtime_name" "$runtime_skill"
}

if "$install_claude"; then link_runtime '.claude' 'Claude Code'; fi
if "$install_codex"; then link_runtime '.codex' 'Codex'; fi
if "$install_hermes"; then link_runtime '.hermes' 'Hermes'; fi

printf 'K-humanizer 공통 경로: %s\n' "$common_skill"
