---
name: config-check
description: Check ARIS .env, LLM Chat, Codex, Feishu, and model routing configuration.
argument-hint: [optional: --fix-suggestions]
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# Config Check

## Purpose

检查 ARIS 当前配置能否支撑 Codex + LLM Chat + DeepSeek fallback + Feishu 通知。它不修改 `.env`，只检查和提示。

## When to Use

- 第一次配置 ARIS 后。
- 修改 `.env` 后。
- Codex / LLM Chat 调用失败后。
- 跑 research-pipeline 前。

## Inputs

- `.env`
- `.env.example`
- `mcp-servers/llm-chat/server.py`
- `config/status.json`，如存在
- shell 中 codex 命令可用性
- Feishu 相关变量

## Outputs

- `config/status.json`
- `config/CONFIG_CHECK.md`

## Workflow

1. 定位项目根目录。
2. 调用 `tools/config_check.py`。
3. 读取生成的 `config/status.json`。
4. 输出中文总结。
5. 如果发现缺失变量，只提示用户手动追加，不修改 `.env`。
6. 如果 Codex 不可用，说明关键审查将 fallback 到 LLM。
8. 如果 `LLM_FALLBACK_MODEL` 缺失，提示补 `LLM_FALLBACK_MODEL=deepseek-v4-flash`。

## Hard Rules

- 不修改 `.env`。
- 不打印完整 API Key。
- 不覆盖用户配置。
- 不执行真实模型调用，只做配置检查。

## Failure Handling

- 如果 `.env` 不存在，输出 missing 并建议复制 `.env.example`。
- 如果 `config_check.py` 失败，输出错误并保留已有 `config/status.json`。
- 如果 Codex 状态无法判断，标记 unknown，不要假装 available。

## Integration

和以下组件衔接：
- `tools/env_loader.py` — 统一读取 .env
- `tools/config_check.py` — 执行检查
- `skills/status/SKILL.md` — 读取 status.json 展示状态
- `skills/shared-references/env-config-policy.md` — 配置策略

## Example Invocation

```
/config-check
```

## Expected Artifacts

- `config/status.json`
- `config/CONFIG_CHECK.md`

## Failure Example

如果 `.env` 不存在：
- config/config.md 输出缺失提示
- status.json 标记 env.exists=false
- 建议复制 `.env.example`

## Recovery Step

按 `CONFIG_CHECK.md` 中的 missing variables 手动补 `.env`。

## Status / Ledger

本 skill 只检查配置，不调用模型，不写入 ledger。
