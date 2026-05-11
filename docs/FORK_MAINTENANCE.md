# Fork Maintenance / 上游同步与合并指南

本文件说明本 fork 后续如何同步原作者 ARIS 的更新，并尽量减少冲突。

## 1. 基本原则

本 fork 基于上游 ARIS 项目，但包含个人修改。因此后续更新时应遵守：

1. 不要直接覆盖本 fork 的新增机制。
2. 不要把本 fork 的实验数据、runtime、`.env`、模型权重提交到 Git。
3. 上游 README 主体尽量保持原样，本 fork 只在顶部保留一个短 Fork Notice。
4. 本 fork 的详细说明放在 `docs/FORK_CHANGES.md`，避免污染上游 README 主体。
5. 遇到冲突时，优先保留上游通用功能，同时重新应用本 fork 的可靠性和模型路由相关修改。

## 2. 推荐远端配置

检查远端：

`git remote -v`

如果没有 upstream，添加：

`git remote add upstream https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep.git`

然后执行：

`git fetch upstream`

## 3. 推荐同步流程

不要直接在 main 上冒险合并。建议每次同步上游前新建分支：

`git checkout main`

`git pull origin main`

`git fetch upstream`

`git checkout -b sync-upstream-YYYYMMDD`

`git merge upstream/main`

如果没有冲突，运行检查：

`python tools/verify_agentic_reliability.py`

`python tools/register_slash_commands.py --check-only`

`git status --short`

确认后：

`git checkout main`

`git merge sync-upstream-YYYYMMDD`

`git push origin main`

## 4. README 冲突处理策略

README 是最容易和上游冲突的文件。

本 fork 在 README 顶部使用 marker：

`<!-- FORK_NOTICE_START -->`

和：

`<!-- FORK_NOTICE_END -->`

如果合并上游时 README 冲突：

1. 优先保留上游 README 主体。
2. 保留或重新插入本 fork 的 Fork Notice marker block。
3. 不要把 `docs/FORK_CHANGES.md` 的详细内容塞进 README。
4. 中文 README_CN.md 同理。

## 5. 本 fork 应优先保留的文件和机制

遇到冲突时，以下文件或机制通常代表本 fork 的关键修改，应谨慎处理：

- `.env.example`
- `tools/model_route.py`
- `docs/MODEL_ROUTING_OVERVIEW.md`
- `docs/FORK_CHANGES.md`
- `docs/FORK_MAINTENANCE.md`
- `tools/verify_agentic_reliability.py`
- `tools/resume_stage_state.py`
- `tools/validate_idea_stage_state.py`
- `tools/register_slash_commands.py`
- `.claude/commands/`
- `skills/idea-bank/SKILL.md`
- `skills/experiment-bridge/SKILL.md`
- `skills/status/SKILL.md`

## 6. 不应提交的内容

以下内容应保持 ignored，不要提交：

- `.env`
- `.aris/`
- `external_data/`
- `experiments/*/data/`
- `experiments/*/reports/`
- 模型权重：`*.bin`, `*.safetensors`, `*.pt`, `*.pth`, `*.ckpt`
- 大型缓存文件：`*.arrow`, `*.parquet`
- 临时调试脚本和运行产物

同步上游前后都建议执行：

`git status --short`

`git check-ignore -v external_data/ || true`

## 7. 冲突解决建议

如果是上游新增 skill：

1. 保留上游 skill。
2. 运行：

`python tools/register_slash_commands.py`

`python tools/register_slash_commands.py --check-only`

3. 确认对应 `.claude/commands/<skill>.md` 存在。

如果是模型路由相关冲突：

1. 不要重新引入硬编码模型。
2. 优先使用 `.env` + `tools/model_route.py`。
3. 不允许 silent fallback。
4. Critical gate 必须记录 `codex_used`, `fallback_used`, `actual_backend`, `actual_model`。

如果是实验项目相关冲突：

1. 不要把 synthetic / weak-label smoke 当作正式实验结果。
2. 不要绕过 data validation。
3. 不要绕过 sample-grouped split。
4. 不要绕过 baseline gate。
5. 不要提交数据和模型权重。

## 8. 同步后的最低检查

每次同步上游后，至少运行：

`python tools/verify_agentic_reliability.py`

`python tools/register_slash_commands.py --check-only`

`python tools/model_route.py final_selector`

`python tools/model_route.py experiment_code_reviewer`

## 9. 推荐 commit message

同步上游时建议使用清晰 commit：

`git commit -m "sync upstream ARIS updates"`

修复本 fork 冲突时：

`git commit -m "preserve fork-specific routing and reliability safeguards"`

不要在 commit message 中加入：

- Claude
- Claude Code
- Co-authored-by
- Generated with
- Happy
- 🤖