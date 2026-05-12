# ARIS Research Workflow — 快速上手

## 这套流程的目标

ARIS 研究流程通过分层设计，确保每个阶段都由专门的组件负责，防止外部 Agent（External Agent）绕过控制流程直接产出"可信"结论。

| 组件 | 职责 |
|------|------|
| **External Agent**（外部 Agent） | 只负责调度，不自己组织 prompt，不选模型，不产出可信结论 |
| **Workflow Controller**（流程控制器） | 统一管理流程，生成 context manifest 和标准 prompt file |
| **Context Isolation Check**（上下文内容检查） | 扫描输入文件，拦截 forbidden context 污染 |
| **Trusted Runner**（可信执行脚本） | 真实调用模型，记录 ledger，保留完整路由元数据 |
| **Validator**（验证器） | 在 ledger 中核对路由、backend、context 字段，PASS 才放行 |

---

## 标准使用顺序（四步）

```bash
# 第 1 步：查看有哪些阶段
python tools/research_workflow.py list-stages

# 第 2 步：查看阶段计划（不写文件）
python tools/research_workflow.py plan research_contract --config configs/workflows/research_default.yaml

# 第 3 步：干跑测试（不写文件，不调模型）
python tools/research_workflow.py run research_contract --config configs/workflows/research_default.yaml --dry-run

# 第 4 步：准备阶段（检查输入 → 生成 manifest → 内容扫描 → 打印命令）
python tools/research_workflow.py prepare research_contract --config configs/workflows/research_default.yaml
```

只有 `prepare` 会写文件，其他命令都是只读检查。

---

## Codex/mcp 阶段（Codex 角色）的完整流程

`contract_reviewer`、`novelty_checker`、`experiment_auditor` 等角色走 Codex MCP backend。

`prepare` 执行后会输出类似：

```
TRUSTED_ROLE_RUNNER COMMAND:
  python tools/trusted_role_runner.py --role contract_reviewer --input ... --output ... --context-manifest ... --prepare-external-mcp --require-codex-thread
```

外部 Agent 必须**原样执行这个命令**，不能修改参数。完整流程：

```
1. trusted_role_runner.py --prepare-external-mcp     → 写入 ledger，输出 prompt_file
2. mcp__codex__codex 调用 Codex                     → 拿到真实 threadId
3. trusted_role_runner.py --complete-external-mcp    → 写入 threadId，更新 ledger
4. validate_model_invocation.py --role <role>        → 核对 PASS 后才进入下一阶段
```

**没有真实 codex_thread_id 的完成记录是无效的。**

---

## DeepSeek / MiniMax / OpenAI 阶段（API 角色）的完整流程

`experiment_implementer`、`paper_writer` 等角色走 OpenAI-compatible API backend。

同样通过 `prepare` 拿到标准命令，然后由外部 Agent 执行：

```
1. trusted_role_runner.py                          → 直接调用 API，写入 ledger
2. validate_model_invocation.py --role <role>      → 核对 PASS 后才进入下一阶段
```

不需要 threadId，但必须记录 `actual_backend` 和 `actual_model`。

---

## 明确禁止

| 禁止项 | 原因 |
|--------|------|
| 外部 Agent 自己组织 prompt | 绕过 Workflow Controller 的标准化 |
| 外部 Agent 自己选择模型 | 绕过 MODEL_/ROLE_ 路由配置 |
| 跳过 context_isolation_check | 允许污染内容进入模型输入 |
| 跳过 validate_model_invocation | 允许错误路由或 fallback 偷偷进入下一阶段 |
| 提交 .env / .aris / tmp / runtime / external_data / experiments/TokenTR / research/current | 运行时产物不是源码 |
| dry-run / mock 产物作为真实研究证据 | 演练产物不是实验结果 |

---

## 当前边界

- **context_isolation_check** 是硬规则扫描（hard-rule scanning）。它能拦截 "old conclusion"、"unverified experiment result" 等明显标记，但不能做语义理解。有意规避仍可能漏过。

- **run 真实自动执行** 还没有完全实现。当前标准流程是：`prepare` 生成标准命令，再由外部 Agent 执行该命令，然后手动 `validate_model_invocation`。

- **正式实验代码** 必须等以下四个阶段全部验证通过后才能写：
  1. research_contract（研究边界说明）
  2. novelty_check（新颖性检查）
  3. experiment_plan（实验计划）
  4. implementation_plan（实现计划）

  提前写的实验代码不能作为可信研究成果。

---

## 流程图

```
External Agent
     │
     ▼
research_workflow.py prepare <stage>
     │
     ├── 输入文件存在性检查
     ├── 生成 context_manifest.json
     ├── 生成 input.md（只含 allowed_input_files）
     ├── context_isolation_check.py 扫描
     │        ├── PASS → contamination_scan_status=checked
     │        │        打印 trusted_role_runner 命令
     │        └── FAIL → contamination_scan_status=failed
     │                 停止，不调用模型
     │
     ▼
External Agent 执行 trusted_role_runner 命令
     │
     ├── Codex/mcp 角色 → mcp__codex__codex → --complete-external-mcp
     └── API 角色      → 直接 API 调用
     │
     ▼
validate_model_invocation.py --role <role>
     │
     ├── PASS + allowed_next_stage=true → 进入下一阶段
     └── FAIL 或 allowed_next_stage=false → 停止
```