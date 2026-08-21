#!/bin/bash
# install.sh — 把 gemini-writer skill 软链到 Claude Code 与 Codex 的 skills 目录
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/skills/gemini-writer"
TARGETS=("$HOME/.claude/skills" "$HOME/.codex/skills")

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：找不到 python3。macOS 可运行 xcode-select --install 安装。" >&2
  exit 1
fi

for dir in "${TARGETS[@]}"; do
  # 自愈：skills 目录本身是悬空软链时（如宿主应用卸载后残留），重建其目标目录
  if [ -L "$dir" ] && [ ! -e "$dir" ]; then
    tgt="$(readlink "$dir")"
    case "$tgt" in
      /*) mkdir -p "$tgt" ;;
      *)  mkdir -p "$(dirname "$dir")/$tgt" ;;
    esac
    echo "检测到悬空软链 $dir -> $tgt，已重建目标目录"
  fi
  mkdir -p "$dir"
  link="$dir/gemini-writer"
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$SRC" ]; then
    echo "已安装，跳过：$link"
    continue
  fi
  if [ -e "$link" ]; then
    mv "$link" "$link.bak"
    echo "已备份旧目录为 $link.bak"
  fi
  ln -s "$SRC" "$link"
  echo "已安装：$link -> $SRC"
done

echo ""
echo "== 后续步骤 =="
echo "会员通道（默认，走 Google AI Pro 额度）：brew install --cask antigravity-cli && agy   # 完成一次 Google 登录；需账号关联地区支持 Antigravity"
echo "API 通道（gemini-3.7-flash 直连）：https://aistudio.google.com/apikey 申请后 export GEMINI_API_KEY=你的key"
echo "验证：python3 \"$SRC/scripts/gw.py\" \"测试\" --dry-run"
