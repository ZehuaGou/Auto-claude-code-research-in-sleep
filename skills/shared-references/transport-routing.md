# Transport Routing

## 1. Principle

MCP 可以保留，但不作为所有事情的唯一方案。

## 2. MCP Suitable For

- Zotero / Obsidian 等数据源。
- Codex 关键审查。
- 已经稳定的 llm-chat 调用。
- 轻量工具桥接。

## 3. MCP Not Ideal For

- 长时间无状态可见的调用。
- 多轮 reviewer 协作。
- 需要持续上下文的辩论。
- 需要用户知道当前卡在哪里的长流程。
- 容易出现 "Calling codex..." 但没有状态输出的流程。

## 4. exec-review Suitable For

- 一次性独立审查。
- 单个 idea card review。
- contract review。
- paper relevance review。
- result snapshot review。

## 5. panel-review Suitable For

- 多轮复杂审查。
- 持续上下文辩论。
- 方法漏洞追问。
- 实验异常定位。
- reviewer 需要记住上轮怀疑点的情况。

## 6. Required Observability

所有外部调用必须：
- 写 `.aris/calls/current_call.json`
- 完成后写 `.aris/calls/llm_calls.jsonl`
- fallback 时显式标记
- status 能读到当前状态

## 7. No Silent Stuck Rule

不允许：
- 调用 Codex 后只有 "Calling codex..." 而没有状态文件。
- reviewer 卡住但 status 看不到。
- fallback 发生但用户不知道。
