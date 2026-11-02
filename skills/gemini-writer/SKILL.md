---
name: gemini-writer
description: 把成篇的写作任务外包给 Gemini 写初稿（默认 3.8 Flash，可选 4 Argon）、自己审校定稿。当需要产出约 300 字以上的文章、文案、报告、长文档、改写或翻译时使用；用户点名"用 gemini 写 / 用 argon 写 / 外包写作"时也使用。Delegate substantial writing tasks (articles, copy, reports, rewrites, translations, >300 Chinese characters) to Gemini (3.8 Flash by default, 4 Argon on request) for drafting, then review and finalize. 不适用于：代码注释、commit message、几句话的短回复、对话式回答。
---

# gemini-writer：写作外包工位

你是主编，Gemini 是初稿写手。成篇写作任务不要自己从零写，走下面的流程。

## 脚本位置

- Claude Code 会话：`~/.claude/skills/gemini-writer/scripts/gw.py`
- Codex 会话：`~/.codex/skills/gemini-writer/scripts/gw.py`
- 两者是同一份文件的软链，用你当前环境对应的路径。

## 工作流

1. **整理 brief**：从用户需求中提炼——目标读者、体裁、字数、风格、必须覆盖的要点。写成一段清晰的中文指令。
2. **准备素材**（如有）：长素材（参考资料、原文、数据）写入临时文件，用 `--context 文件` 传入，可重复多个。不要把大段素材塞进 brief 参数。
3. **派单**：
   ```bash
   python3 ~/.claude/skills/gemini-writer/scripts/gw.py "<brief>" --context 素材.md --out draft.md
   ```
   - 预计初稿超过 800 字：必须用 `--out`，然后读文件审校。
   - 短初稿可省略 `--out` 直接读 stdout。
   - 只走 Antigravity CLI（agy）会员额度，默认写手 gemini-3.8-flash，思考强度 high。
   - 换写手：加 `--model argon`（Gemini 4 Argon，思考强度同样默认 high）。用户点名 Argon，或稿件需要复杂论证时使用；日常初稿留在默认写手，省额度。
   - 换思考档：`--model` 写完整 slug 原样透传，如 `gemini-3.8-flash-medium`（`agy models` 可查）。
   - 超时用默认值，不要传更短的 `--timeout`：high 档 Flash 写 1500 字约 80 秒，Argon 实测 3 篇长文用了 225 秒到 300 秒以上。派 Argon 时把命令放到后台运行，或把外层命令的超时设到 10 分钟以上。
   - Codex 会话：agy 要写 `~/.gemini` 并联网，`workspace-write` 沙箱会挡住它。第一次调用就用 `sandbox_permissions: "require_escalated"`，不要先在沙箱里试。
4. **审校**：通读初稿，核对事实、修正风格、删补内容。需要大改时把修改意见写成新 brief 再派一次（可把上一稿作为 --context 传回）。
5. **交付**：给用户定稿。脚本 stderr 的 `[gw] backend=... actual_model=...` 行如实告知用户初稿由哪个模型起草。

## 出错时

脚本的报错信息自带修复步骤（装 CLI / 登录 / 沙箱提权 / 超时处理），照做或把信息转告用户即可，不要自己猜。

`actual_model=agy-default(unknown)` 表示指定模型调用失败、已退回 agy 默认模型（截至 2026-11-02 是 Argon，消耗 Argon 周额度）：把这件事告诉用户，需要时重新派单。

## 不要触发的场景

代码注释、commit message、PR 描述、几句话能答完的回复、聊天式问答——这些直接自己写。
