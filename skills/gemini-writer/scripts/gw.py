#!/usr/bin/env python3
"""gw.py — 把写作任务外包给 Gemini。

只走 Antigravity CLI（agy，gemini CLI 的官方接班人；OAuth 走 Google AI Pro 会员额度）。
写手见 WRITERS，默认思考强度 high。
零第三方依赖，python3 标准库实现。
"""
import shutil
from pathlib import Path

# 写手简称 → 模型名，增加模型只改这张表（agy 的 slug 是 模型名-思考档）
WRITERS = {"flash": "gemini-3.8-flash", "argon": "gemini-4-argon"}
DEFAULT_WRITER = "flash"
# 官方默认是 medium（2026-11-02 核对文档与 agy 1.4.12），这里统一拉到 high
DEFAULT_THINKING = "high"
# agy 登录后的本地痕迹（Task 5 按真实登录结果校准）
CLI_AUTH_MARKER = Path.home() / ".gemini" / "antigravity-cli"

FIX_CLI = "修复：brew install --cask antigravity-cli，然后在终端运行 agy 完成一次 Google 登录"
FIX_SANDBOX = "修复：agy 要写 ~/.gemini 并联网，宿主沙箱挡住了。Codex 里用 sandbox_permissions=require_escalated 重跑"
FIX_TIMEOUT = "建议减少素材量，或换回 flash 写手（--timeout 默认已是上限 600）"

SYSTEM_INSTRUCTION = (
    "你是一位专业写手。只输出正文本身：不要解释写作过程，"
    "不要加前言后语，不要输出标题之外的元信息，不要使用任何工具。"
)


def cli_available() -> bool:
    return shutil.which("agy") is not None and CLI_AUTH_MARKER.exists()


def build_prompt(brief, context_files):
    parts = [SYSTEM_INSTRUCTION, "", "【写作要求】", brief]
    for i, fp in enumerate(context_files, 1):
        p = Path(fp)
        parts += ["", f"【素材 {i}：{p.name}】", p.read_text(encoding="utf-8")]
    return "\n".join(parts)


def clamp_timeout(seconds):
    return max(1, min(int(seconds), 600))


def resolve_model(explicit):
    """简称、留空或内置模型名走写手表并拼默认思考档；其他显式值原样使用。"""
    model = WRITERS.get(explicit or DEFAULT_WRITER, explicit)
    return f"{model}-{DEFAULT_THINKING}" if model in WRITERS.values() else model


import argparse
import json
import os
import subprocess
import sys


def die(msg):
    print("[gw] 错误：" + msg, file=sys.stderr)
    sys.exit(1)


def agy_env():
    """去掉 GEMINI_API_KEY：agy 支持 key 会话，这里保证只走会员 OAuth。"""
    return {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}


def run_cli(prompt, model, timeout):
    """调 Antigravity CLI (agy) headless 模式。返回 (正文, actual_model)。

    agy 对未知模型会硬报错（不静默替换），因此显式 --model 成功即代表实际模型；
    显式失败则退回 agy 默认模型重试一次（仍用默认思考档），并把 actual_model 标为 agy-default(unknown)。
    """
    def invoke(with_model):
        cmd = ["agy", "--output-format", "json", "--disable-slash-commands"]
        cmd += ["--model", model] if with_model else ["--effort", DEFAULT_THINKING]
        cmd += ["-p", prompt]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=agy_env())

    used_model = model
    try:
        proc = invoke(True)
        if proc.returncode != 0:
            used_model = "agy-default(unknown)"
            proc = invoke(False)
    except subprocess.TimeoutExpired:
        die(f"agy 超时（{timeout}s）。" + FIX_TIMEOUT)
    except FileNotFoundError:
        die("找不到 agy 命令。" + FIX_CLI)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        die("agy 调用失败：" + detail[:500] + "\n" + (FIX_SANDBOX if "operation not permitted" in detail else FIX_CLI))
    try:
        data = json.loads(proc.stdout)
        if data.get("error"):
            die("agy 报错：" + str(data["error"])[:300])
        text = data.get("response") or ""
        actual = used_model
        if not text:
            text, actual = proc.stdout, "unknown"
    except (json.JSONDecodeError, AttributeError):
        text, actual = proc.stdout, "unknown"
    return text, actual


def main(argv=None):
    ap = argparse.ArgumentParser(description="把写作任务外包给 Gemini（走 Antigravity CLI 会员额度）")
    ap.add_argument("brief", help="写作指令：要写什么、体裁、字数、风格、要点")
    ap.add_argument("--context", action="append", default=[], metavar="FILE", help="素材文件，可重复")
    ap.add_argument("--out", metavar="FILE", help="初稿写入文件（默认打印到 stdout）")
    # 只为兼容宿主的旧调用习惯（--backend cli），没有其他通道
    ap.add_argument("--backend", choices=["auto", "cli"], default="cli", help=argparse.SUPPRESS)
    ap.add_argument("--model", default=None,
                    help=f"写手简称（{' / '.join(WRITERS)}）或完整模型名；默认 {DEFAULT_WRITER}，思考强度 {DEFAULT_THINKING}")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true", help="只打印选路结果，不联网")
    args = ap.parse_args(argv)

    for fp in args.context:
        if not os.path.isfile(fp):
            die("素材文件不存在：" + fp)

    timeout = clamp_timeout(args.timeout)
    if not cli_available():
        die("Antigravity CLI (agy) 不可用（未安装或未登录）。" + FIX_CLI)

    model = resolve_model(args.model)
    if args.dry_run:
        print(f"[gw] dry-run backend=cli model={model} timeout={timeout} "
              f"brief_chars={len(args.brief)} context_files={len(args.context)}")
        return

    prompt = build_prompt(args.brief, args.context)
    text, actual = run_cli(prompt, model, timeout)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[gw] 初稿已写入 {args.out}")
    else:
        print(text)
    print(f"[gw] backend=cli actual_model={actual} chars={len(text)}", file=sys.stderr)


if __name__ == "__main__":
    main()
