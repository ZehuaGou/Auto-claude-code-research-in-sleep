# ARIS Research Workflow — 快速上手

## 用户主入口：原生 ARIS 命令

用户使用原生 ARIS 命令，不需要记忆底层脚本。底层自动走 workflow 可信执行链。

| ARIS 命令 | 说明 | 对应 workflow stage |
|-----------|------|---------------------|
| `/idea-discovery "方向"` | 完整 idea 发现 pipeline | research_lit → idea_creator → novelty_check |
| `/research-contract "idea"` | 冻结研究边界和成功/失败标准 | research_contract |
| `/novelty-check "idea"` | 查新，确认想法未被发表 | novelty_check |
| `/experiment-bridge "plan"` | 把实验计划变成可运行代码 | experiment_plan → implementation_plan |
| `/status` | 查看当前 workflow 状态 | 查看 ledger / validate 状态 |

**这些是用户主入口。底层通过 workflow Controller 走 context_isolation_check → trusted_role_runner → validate_model_invocation。**

---

## 底层执行链（内部机制）

```
Native ARIS command
  ↓
tools/research_workflow.py     ← Workflow Controller，生成 context_manifest 和 prompt_file
  ↓
tools/context_isolation_check.py ← 扫描输入，禁止污染内容
  ↓
tools/trusted_role_runner.py    ← 真实调用模型（Codex MCP 或 DeepSeek API）
  ↓
tools/validate_model_invocation.py ← 验证 PASS 后才进入下一阶段
```

**用户不需要手动执行上面的脚本。原生命令是入口，workflow 组件是内部实现。**

---

## 调试用底层命令（仅开发/调试用）

以下命令仅供检查配置或手动调试，普通用户不需要使用：

```bash
# 查看有哪些阶段
python tools/research_workflow.py list-stages

# 查看阶段计划（不写文件）
python tools/research_workflow.py plan research_contract --config configs/workflows/research_default.yaml

# 干跑测试（不写文件，不调模型）
python tools/research_workflow.py run research_contract --config configs/workflows/research_default.yaml --dry-run

# 准备阶段（检查输入 → 生成 manifest → 内容扫描 → 打印命令）
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

- **正式实验代码** 必须等以下四个阶段全部验证通过后才能写：
  1. research_contract（研究边界说明）
  2. novelty_check（新颖性检查）
  3. experiment_plan（实验计划）
  4. implementation_plan（实现计划）

  提前写的实验代码不能作为可信研究成果。

---

## 流程图

```
Native ARIS command
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