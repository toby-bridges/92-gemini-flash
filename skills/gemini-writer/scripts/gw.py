#!/usr/bin/env python3
"""gw.py — 把写作任务外包给 Gemini。

双后端：
  cli — Antigravity CLI（agy，gemini CLI 的官方接班人；OAuth 走 Google AI Pro 会员额度）
  api — GEMINI_API_KEY 直连 generateContent（真·gemini-3.7-flash）
零第三方依赖，python3 标准库实现。
"""
import shutil
from pathlib import Path

DEFAULT_MODEL = "gemini-3.7-flash"
# agy 的模型 slug 带思考档后缀（2026-10-15 agy 1.3.5 实测 agy models：gemini-3.8-flash-high|medium|low）
CLI_DEFAULT_MODEL = "gemini-3.8-flash-medium"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# agy 登录后的本地痕迹（Task 5 按真实登录结果校准）
CLI_AUTH_MARKER = Path.home() / ".gemini" / "antigravity-cli"

FIX_CLI = "修复：brew install --cask antigravity-cli，然后在终端运行 agy 完成一次 Google 登录"
FIX_API = "修复：到 https://aistudio.google.com/apikey 免费申请 key，然后 export GEMINI_API_KEY=你的key"

SYSTEM_INSTRUCTION = (
    "你是一位专业写手。只输出正文本身：不要解释写作过程，"
    "不要加前言后语，不要输出标题之外的元信息，不要使用任何工具。"
)


def cli_available() -> bool:
    return shutil.which("agy") is not None and CLI_AUTH_MARKER.exists()


def select_backend(requested, env_backend, cli_ok, key_ok):
    """选后端。优先级：--backend 显式指定 > GW_BACKEND 环境变量 > 自动。

    返回 (backend, error)：backend ∈ {"cli", "api", None}；出错时 backend 为 None。
    """
    choice = requested if requested not in (None, "auto") else (env_backend or None)
    if choice == "cli":
        return ("cli", None) if cli_ok else (None, "Antigravity CLI (agy) 不可用（未安装或未登录）。" + FIX_CLI)
    if choice == "api":
        return ("api", None) if key_ok else (None, "缺少 GEMINI_API_KEY 环境变量。" + FIX_API)
    if cli_ok:
        return ("cli", None)
    if key_ok:
        return ("api", None)
    return (None, "两个后端都不可用。\n  会员通道 — " + FIX_CLI + "\n  API 通道 — " + FIX_API)


def build_prompt(brief, context_files):
    parts = [SYSTEM_INSTRUCTION, "", "【写作要求】", brief]
    for i, fp in enumerate(context_files, 1):
        p = Path(fp)
        parts += ["", f"【素材 {i}：{p.name}】", p.read_text(encoding="utf-8")]
    return "\n".join(parts)


def clamp_timeout(seconds):
    return max(1, min(int(seconds), 600))


def resolve_model(explicit, backend):
    """显式指定则原样使用；否则按后端给默认：cli 用带思考档的 slug，api 用纯模型名。"""
    if explicit:
        return explicit
    return CLI_DEFAULT_MODEL if backend == "cli" else DEFAULT_MODEL


import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def die(msg):
    print("[gw] 错误：" + msg, file=sys.stderr)
    sys.exit(1)


def run_cli(prompt, model, timeout):
    """调 Antigravity CLI (agy) headless 模式。返回 (正文, actual_model)。

    agy 对未知模型会硬报错（不静默替换），因此显式 --model 成功即代表实际模型；
    显式失败则退回 agy 默认模型重试一次，并把 actual_model 标为 agy-default(unknown)。
    """
    def invoke(with_model):
        cmd = ["agy", "--output-format", "json", "--disable-slash-commands"]
        if with_model:
            cmd += ["--model", model]
        cmd += ["-p", prompt]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    used_model = model
    try:
        proc = invoke(True)
        if proc.returncode != 0:
            used_model = "agy-default(unknown)"
            proc = invoke(False)
    except subprocess.TimeoutExpired:
        die(f"agy 超时（{timeout}s）。建议减少素材量，或用 --timeout 调大（上限 600）")
    except FileNotFoundError:
        die("找不到 agy 命令。" + FIX_CLI)
    if proc.returncode != 0:
        die("agy 调用失败：" + (proc.stderr or proc.stdout).strip()[:500] + "\n" + FIX_CLI)
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


def run_api(prompt, model, timeout, api_key):
    """直连 generateContent。返回 (正文, actual_model)。"""
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(
        API_URL.format(model=model),
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 429:
            die("触发限速（429）：免费档有每分钟/每天配额。稍等再试，或不带 GEMINI_API_KEY 改走会员通道。\n" + detail)
        die(f"API 调用失败（HTTP {e.code}）：{detail}\n" + FIX_API)
    except TimeoutError:
        die(f"API 超时（{timeout}s）。建议减少素材量，或用 --timeout 调大（上限 600）")
    except urllib.error.URLError as e:
        die(f"网络错误：{e.reason}")
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    actual = data.get("modelVersion", "unknown")
    if not text:
        die("API 返回了空正文，原始响应片段：" + json.dumps(data, ensure_ascii=False)[:300])
    return text, actual


def main(argv=None):
    ap = argparse.ArgumentParser(description="把写作任务外包给 Gemini（cli=会员额度 / api=GEMINI_API_KEY 直连）")
    ap.add_argument("brief", help="写作指令：要写什么、体裁、字数、风格、要点")
    ap.add_argument("--context", action="append", default=[], metavar="FILE", help="素材文件，可重复")
    ap.add_argument("--out", metavar="FILE", help="初稿写入文件（默认打印到 stdout）")
    ap.add_argument("--backend", choices=["auto", "cli", "api"], default="auto")
    ap.add_argument("--model", default=None, help=f"默认按后端选择：cli={CLI_DEFAULT_MODEL}，api={DEFAULT_MODEL}")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="只打印选路结果，不联网")
    args = ap.parse_args(argv)

    for fp in args.context:
        if not os.path.isfile(fp):
            die("素材文件不存在：" + fp)

    timeout = clamp_timeout(args.timeout)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    backend, err = select_backend(args.backend, os.environ.get("GW_BACKEND", "").strip() or None,
                                  cli_available(), bool(key))
    if err:
        die(err)

    model = resolve_model(args.model, backend)
    if args.dry_run:
        print(f"[gw] dry-run backend={backend} model={model} timeout={timeout} "
              f"brief_chars={len(args.brief)} context_files={len(args.context)}")
        return

    prompt = build_prompt(args.brief, args.context)
    if backend == "cli":
        text, actual = run_cli(prompt, model, timeout)
    else:
        text, actual = run_api(prompt, model, timeout, key)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[gw] 初稿已写入 {args.out}")
    else:
        print(text)
    print(f"[gw] backend={backend} actual_model={actual} chars={len(text)}", file=sys.stderr)


if __name__ == "__main__":
    main()
