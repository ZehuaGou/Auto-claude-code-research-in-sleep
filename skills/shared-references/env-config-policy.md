# Env Config Policy

## 1. Scope

本文件规定 ARIS 内部 LLM / reviewer / fallback / Feishu 配置如何读取。

## 2. Key Principles

- 项目根目录 `.env` 是 DeepSeek、LLM Chat、Feishu 等密钥和模型参数的唯一来源。
- 不允许任何 skill、tool、yaml、markdown 写入真实 API Key。
- 不允许覆盖用户现有 `.env`。
- 不允许修改、清空、重写用户现有 LLM_API_KEY。
- `.env.example` 可以更新，但真实 `.env` 只能检查和提示。
- model-routing 只写角色和环境变量名，不写密钥。
- Codex 不通过 `.env` 调用。Codex 走现有 Codex MCP / Codex CLI。
- DeepSeek / LLM Chat 通过 OpenAI-compatible API 调用，从 `.env` 读取。
- 外层 Claud Agent 的模型和思考档位不属于 ARIS 内部配置。

## 3. Existing Variables to Preserve

继续沿用 ARIS 现有 llm-chat 变量：
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_FALLBACK_MODEL`
- `LLM_SERVER_NAME`

不要改成 DEEPSEEK_API_KEY、DEEPSEEK_PRO_MODEL、DEEPSEEK_FLASH_MODEL 作为主配置。

## 4. Role Variables

角色级模型变量可以新增，但必须：
- 以 `LLM_` 开头
- 按角色命名
- 不加 `ARIS_` 前缀
- 不存 API Key

示例：
- `LLM_IDEA_REVIEWER_PRIMARY`
- `LLM_IDEA_REVIEWER_FALLBACK_MODEL`
- `LLM_RESULT_JUDGE_PRIMARY`
- `LLM_FINAL_AUDITOR_FALLBACK_MODEL`

## 5. Codex Rule

- Codex 用于关键审查。
- Codex 不走 `.env`。
- Codex 失败、超时、额度不足、权限失败、无响应时，必须 fallback 到对应 `LLM_*_FALLBACK_MODEL`。
- fallback 必须显式标记，不允许 silent fallback。

## 6. Security

- 不打印完整 API Key。
- config-check 只能显示 masked key，例如 `sk-****abcd`。
- IMPLEMENTATION_REPORT.md 中不得包含任何真实密钥。
