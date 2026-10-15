# 92-gemini-flash / gemini-writer

让 Claude Code 和 Codex 把成篇写作外包给 Gemini：主 agent 当主编，Gemini Flash 当初稿写手。一份 skill，两端通用（macOS）。

## 为什么

写作是高输出 token 的活。Claude/Codex 的额度贵在推理，把初稿交给便宜快速的 Gemini Flash，主 agent 只做审校——省额度、提速度。

## 双后端

| | 会员通道（默认） | API 通道 |
|---|---|---|
| 走什么 | Antigravity CLI（`agy`，gemini CLI 的官方接班人）OAuth 登录 | `GEMINI_API_KEY` 直连 Gemini API |
| 实际模型 | `gemini-3.8-flash-medium`（可 `--model` 换 high/low 档） | `gemini-3.7-flash` |
| 费用 | 0（计入 Google AI Pro/Ultra 会员额度） | 免费限速档；付费 $0.75/1M 输入、$3.75/1M 输出（2026 介绍价） |
| 前提 | 账号关联地区支持 Antigravity（见 FAQ）；agy 的 headless 脚本化是官方文档特性 | 一个免费申请的 key |

脚本每次运行都在 stderr 如实打印实际执笔模型，绝不静默替换：

```
[gw] backend=cli actual_model=gemini-3.8-flash-medium chars=19
```

## 安装（macOS）

```bash
git clone https://github.com/toby-bridges/92-gemini-flash.git
cd 92-gemini-flash && ./install.sh
```

会员通道：`brew install --cask antigravity-cli`，终端跑 `agy` 完成一次 Google 登录。
API 通道（可选）：到 https://aistudio.google.com/apikey 申请后 `export GEMINI_API_KEY=你的key`。

Codex 侧备选安装：`$skill-installer toby-bridges/92-gemini-flash/skills/gemini-writer`

以后更新：仓库里 `git pull` 一下即可，软链让两端同时生效。

## 用法

对 Claude Code / Codex 说「用 gemini 写一篇 XX」，或让它在成篇写作任务上自动触发。手动调用：

```bash
python3 ~/.claude/skills/gemini-writer/scripts/gw.py "写作指令" --context 素材.md --out draft.md
```

常用参数：`--context 文件`（素材，可重复）、`--out 文件`（初稿落盘）、`--backend cli|api`、`--model`、`--timeout 秒`、`--dry-run`。

## ⚠️ 地区与风险披露

- Antigravity 的使用资格绑定在 **Google 账号的关联国家/地区属性**上（与 IP、代理、登录会话无关，本仓库作者逐一实验排除过）。账号地区不在开放名单会报 `Eligibility check failed: ... not currently available in your location`。
- 社区通用解法是通过 [Google 国家关联表单](https://policies.google.com/country-association-form)变更账号地区（人工审核约 0.5~24 小时），之后保持网络出口在对应地区。**是否变更、由此产生的账号与订阅风险，请自行评估承担。**
- agy 的 headless 模式（`-p`）是[官方文档特性](https://antigravity.google/docs/cli/headless)，本工具属正常脚本化使用；仍建议保持个人使用强度。

## FAQ

**Q：报 `not currently available in your location` 怎么办？**
见上面的地区披露。改完账号地区后如仍失败：重登 agy 一次（清 `~/.gemini/antigravity-cli/jetski_state.pbtxt` 后运行 `agy`）。

**Q：模型名为什么带 `-medium` 后缀？**
agy 的模型 slug 带思考强度档（`agy models` 可见 high/medium/low），API 直连则用纯模型名 `gemini-3.7-flash`。脚本已按后端自动选择默认值。

**Q：API 通道实测过吗？**
选路与参数逻辑有 22 个离线单测覆盖；真实调用留给你配 key 后自验：上面的手动命令加 `--backend api` 跑一次即可。

**Q：装完 Claude Code 侧不识别？**
若 `~/.claude/skills` 曾被其他工具改成软链且目标已删（悬空），`install.sh` 会自动重建目标目录，重跑一次即可。
