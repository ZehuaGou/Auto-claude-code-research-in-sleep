# 纲领

> Branch: `recovery/upstream-first-minimal-patch-plan`  
> Base: upstream `wanshuiyin/Auto-claude-code-research-in-sleep@745f856a255a194cf704cd50c225eb8af86a16a3`  
> Purpose: 以原版 ARIS 为主体，只做能明显提升科研创新点质量的目的驱动补丁。

---

## 0. 第一原则：目的第一

```text
提高科研创新点质量是第一目标。
改动大小、实现形式、是否工具化都是第二位。
```

本分支不是为了“小改”而小改，也不是为了“大改”而大改。

如果修改一句 Skill 就能达到目标，就只修改一句 Skill。  
如果 Skill 不够，再考虑模板。  
如果模板仍不够，并且出现了可重复的具体失败，再考虑最小工具。  
不允许为了架构好看、流程完整、或者复用旧 fork 心血而添加无必要机制。

任何后续改动都必须回答：

1. 它服务哪个具体目标？
2. 原版 ARIS 为什么还不够？
3. 它是不是达到目标的最轻机制？
4. 怎么判断它真的提升了创新点质量？

回答不清楚，就不做。

---

## 1. 当前总路线

以原版 ARIS 工作流为主体。

```text
原版 ARIS
+ 创新点质量增强 Skill 补丁
+ 必要时的轻量模板
+ 只有在真实失败反复出现时，才加最小工具
```

不继续当前 heavy fork 主线。

默认不迁移：

- 六阶段自定义 workflow；
- slash command adapter 作为主控流程；
- workflow_state 中央状态机；
- IDEA_BANK / CANONICAL_IDEAS 工具化系统；
- run isolation 工具；
- candidate selection 工具；
- lightweight experiment scaffold；
- 大量 roadmap / audit 文档。

这些不是绝对永远不能做，而是目前没有足够证据说明它们值得加入。

---

## 2. 核心目标：让创新点更强

本项目最重要的阶段是创新点发现与创新点验证。

实验、写论文、结果包装都在后面。  
如果 idea 本身弱，后面很难救回来。  
如果 idea 本身强，后面的实验只是验证和完善。

所以当前补丁只围绕三件事：

1. 迁移式创新不要停留在 `apply X to Y`。
2. 多个中等创新点必须形成 coherent contribution chain，而不是 patchwork。
3. 查新/验证不能把证据不足、直接迁移、已有工作包装成强创新。

---

## 3. 迁移式创新规则

迁移式创新不是垃圾创新。  
垃圾的是简单套壳。

弱迁移：

```text
把 A 领域的方法 X 用到 B 领域。
```

强迁移：

```text
X 在 A 领域成立，是因为假设 P。
B 领域存在条件 Q，使 P 不再完全成立。
直接迁移 X 会暴露失败模式 R。
我们提出适配机制 S 来解决 Q/R。
通过 direct-transfer baseline 和 ablation 证明 S 有必要。
```

每个迁移式 idea 至少要写清楚：

1. source-domain mature method；
2. source method 为什么在原领域有效；
3. target-domain opportunity；
4. direct-transfer baseline；
5. target-domain mismatch；
6. adaptation mechanism；
7. adaptation 为什么解决 mismatch；
8. required ablation；
9. closest prior work risk；
10. reviewer attack point。

缺少 direct-transfer baseline 或 target-domain mismatch 的迁移 idea，不应推荐进入 pilot。

---

## 4. Contribution chain 规则

两三个中等创新点可以组成一篇论文，但前提是它们服务同一个 shared core claim。

有效 contribution chain：

```text
Core claim: target-domain structure matters for the method.
Contribution 1: 修改核心方法以适配 target-domain structure。
Contribution 2: 基于这个修改，进一步提供检测/定位/解释能力。
Ablation 分别证明每个 component 都服务同一个 core claim。
```

无效 patchwork：

```text
加 trick A，trick B，trick C，因为它们看起来都可能有用。
```

每个 contribution chain 必须写清楚：

1. shared core claim；
2. main contribution；
3. auxiliary contribution(s)；
4. 每个 component 如何支撑同一个 claim；
5. 为什么不是 patchwork；
6. 每个 component 的 ablation；
7. 最小 pilot 如何验证 shared claim。

缺少 shared core claim 的组合 idea，不应推荐进入 pilot。

---

## 5. 创新点验证规则

旧 heavy fork 中真正值得保留的，不是整套 workflow，而是一个原则：

```text
证据质量必须限制 novelty verdict 的强度。
```

也就是说：

- `insufficient_evidence` 不能升级成 `confirmed_novel`；
- 弱文献证据不能支撑强 novelty claim；
- `already_done` 必须 stop 或 pivot；
- `direct_transfer_only` 不能推荐进入 pilot；
- contribution chain 必须检查是否 patchwork；
- transfer idea 必须检查是否已有同类迁移工作。

Novelty check 必须回答：

1. source method 是否已经被迁移到 target domain？
2. target-domain mismatch 是否真实存在？
3. adaptation 是否已经有人提出过？
4. 当前 idea 是否只是 direct transfer？
5. contribution chain 是否有 shared core claim？
6. 还缺什么 evidence 才能进入 pilot？

这部分可以先写进 `skills/novelty-check/SKILL.md` 和 `skills/idea-creator/SKILL.md`。  
不要先写 Python validator。

---

## 6. 用户把关原则

系统可以不推荐某个 idea 进入 pilot，但不能把候选 idea 直接藏起来。

如果没有强推荐，应输出：

```text
No current pilot recommendation.
```

同时仍然展示：

- 所有候选 idea；
- 不推荐的理由；
- 缺少的 evidence；
- 用户是否要 override；
- 下一步是补文献、改 idea，还是换方向。

不要设计成系统直接替用户丢弃潜在 idea。

---

## 7. 候选审查的轻量隔离原则

原版 ARIS 已有 reviewer-independence 协议。这里不再重做隔离系统。

只补一条 idea 场景下的轻量原则：

```text
审查某个 candidate 时，只提供 candidate 本身和直接相关的文献/gap evidence。
不要提供完整 brainstorming trace、旧分数、旧夸奖、用户偏好、其他候选 idea。
```

这只是 Skill 规则，不引入 IDEA_BANK 工具，不引入 central state，不引入 Python runner。

---

## 8. 工具化原则

默认不工具化。

以下情况才考虑工具化：

- Skill 修改后，系统仍反复缺 direct-transfer baseline；
- 系统仍把 direct-transfer-only 推荐进入 pilot；
- 系统仍把 evidence insufficient 写成 confirmed novel；
- 系统仍把无 shared core claim 的 patchwork 当成 contribution chain。

即使工具化，也只做最小检查器，例如检查 idea card 是否缺字段或是否出现 forbidden verdict upgrade。

不做：

- 新 workflow engine；
- 大型状态机；
- IDEA_BANK 数据库化；
- 自动 candidate selection 系统；
- 替代原版 ARIS 的实验流程。

---

## 9. 原版已有能力，不重复建设

原版 ARIS 已经有：

- cross-model review；
- reviewer independence；
- idea generation / filtering / deep validation / pilot / ranked report；
- novelty check；
- experiment bridge；
- paper / citation / claim audit；
- paper verification。

所以本分支不重复建设这些主流程。

我们只补：

```text
迁移式创新质量规则
+ contribution chain 质量规则
+ novelty verdict guardrails
+ 轻量 candidate 审查输入规则
```

---

## 10. 近期实施范围

下一步只改 Skill，不改 Python。

优先文件：

1. `skills/idea-creator/SKILL.md`
2. `skills/novelty-check/SKILL.md`
3. `skills/experiment-plan/SKILL.md`

可选文件：

4. `skills/exec-review/SKILL.md`

本轮不新增模板。  
本轮不新增工具。  
本轮不改 workflow。  
本轮不运行实验。  
本轮不调用模型。

---

## 11. 暂无其他高置信新增方法

除上述内容外，目前没有发现另一个“原版明显没想到、且高收益低复杂度”的创新点质量增强方法。

如果后续实际运行发现新的稳定失败模式，再基于失败模式补最小机制。不要预先编造功能。
