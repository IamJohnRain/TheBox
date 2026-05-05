# The Box 玩法深度优化方案 — 总览（优化版 v1.3）

> **版本**：v1.3  
> **评审日期**：2026-05-04  
> **v1.1 变更**：修复2个P0问题、6个P1问题，调整工作量估算，优化架构设计  
> **v1.2 变更**：新增双模式系统（剧情模式 + 自定义模式），调整实施分期  
> **v1.3 变更**：新增恐惧值系统、嫌疑人多维隐藏指标、施压/共情交互限制、时间-压力动态关系、心理侧写三级体系、行为评分维度增强  
> **v1.4 变更**：全维度动态变化机制、主+副性格组合系统、反扑机制、维度边界与联动规则，详见 [`suspect-dimensions.md`](suspect-dimensions.md)

---

## 核心问题诊断

| 问题 | 根因 | 位置 |
|------|------|------|
| 点完证据就赢 | 证据名直接传入 LLM prompt，LLM 自然复述触发关键词 | `interrogation.py:89` + `suspect_agent.py:115` |
| 关键词匹配太松 | 子字符串匹配，2字短语极易误触发 | `suspect_agent.py:115` |
| 没有策略深度 | 出示顺序/时机不影响结果，可重复出示 | `interrogation.py:78-92` |
| 压力系统形同虚设 | 仅通过提示词间接影响 LLM，无程序化机制 | `suspect_agent.py:47-48` |
| 胜负二元 | AP耗尽=输，无中间状态 | `interrogation.py:118-126` |
| 静态系统提示词 | 压力值在 `__init__` 时固定为 50，运行中不更新 | `suspect_agent.py:24` |
| 缺乏长期目标 | 单局独立，无成长线和叙事驱动 | 架构层面 |
| 无叙事深度 | 案件间无关联，无法形成沉浸式体验 | 架构层面 |
| 嫌疑人维度单一 | 仅有 pressure/confession，缺少恐惧、抗压等心理维度 | `suspect_agent.py` 架构层面 |
| 交互无限制 | 施压/共情/聊天无次数限制，可无限试错 | `interrogation.py` 架构层面 |
| 压力静态无动态 | 压力只靠玩家操作改变，无自然衰减/增长 | `interrogation.py:submit_action()` |
| 复盘维度不足 | 评分偏结果导向，缺少行为过程统计 | `scoring.py` 设计层面 |
| 心理侧写过浅 | psych_profile 只显示 personality，无层级深度 | `tools/psych_profile.py` |
| 隐藏维度静态 | defiance/empathy/deception/loyalty 初始化后不变，与"动态指标"设计矛盾 | `suspect_agent.py` 架构层面 |
| 嫌疑人无反扑 | 嫌疑人被动挨打，缺少主动博弈行为 | `interrogation.py` 架构层面 |
| 性格类型过粗 | 5种离散性格，无混合型，变化不够丰富 | `case_generator.py` Schema层面 |

### 证据出示链路中的关键缺陷

```
用户点击证据 → bridge.presentEvidence(id)
→ _on_evidence_selected → content = f"出示证据: {证据名}"  ← 只有名，没有描述
→ engine.submit_action("present_evidence", content, id)
→ suspect.respond("出示证据: 沾血的锄头")  ← 嫌疑人收到证据名
→ LLM 回复自然包含 "锄头" → _postprocess 子字符串匹配 forbidden "锄头" → 胜利
```

---

## 方案架构

### 整体架构（v1.2 新增双模式层）

```
┌──────────────────────────────────────────────────────────────────┐
│                         主菜单 (模式选择)                         │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                     ┌──────┴──────┐
                     │ GameSession │  ← 游戏会话协调器
                     └──┬───────┬──┘
                        │       │
             ┌──────────┘       └──────────┐
             │                             │
      ┌──────┴──────┐              ┌───────┴──────┐
      │  剧情模式    │              │  自定义模式   │
      │ StoryEngine  │              │  现有流程     │
      │  + 章节系统   │              │              │
      └──────┬──────┘              └───────┬──────┘
             │                             │
             └───────────┬─────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                    玩家成长系统 (20级)                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │         三级心理侧写系统 (初级/高级/大师)                    │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           消耗品工具箱 (8种工具)                      │  │  │
│  │  │  ┌─────────────────────────────────────────────┐    │  │  │
│  │  │  │    供词层级系统 (5层)                          │    │  │  │
│  │  │  │  ┌─────────────────────────────────────┐    │    │  │  │
│  │  │  │  │  嫌疑人多维隐藏指标系统               │    │    │  │  │
│  │  │  │  │  fear/defiance/empathy/deception/   │    │    │  │  │
│  │  │  │  │  loyalty + 可见性等级控制             │    │    │  │  │
│  │  │  │  └─────────────────────────────────────┘    │    │  │  │
│  │  │  │    证据系统重构 + 嫌疑人反驳机制               │    │  │  │
│  │  │  │    施压/共情交互限制 + 时间-压力动态          │    │  │  │
│  │  │  └─────────────────────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                    评分系统 (S/A/B/C/D)                          │
│              行为评分维度 + 错误惩罚机制                          │
└─────────────────────────────────────────────────────────────────┘
```

### 双模式设计

| 模式 | 说明 | 案件来源 | 进度 |
|------|------|----------|------|
| **剧情模式** | 15+章长篇主线（如"寻找失踪父亲"），悬疑叙事，分支+3-4结局 | 关键转折固定剧本 + 填充章节LLM约束生成 | 章节进度，分支影响走向 |
| **自定义模式** | 保持现有流程，玩家自由设定案件背景 | LLM 自由生成 | 单局独立 |

**进度共享规则**：

| 属性 | 共享策略 | 说明 |
|------|----------|------|
| `level` / `experience` | ✅ 共享 | 两种模式经验通用 |
| `story_progress` | ❌ 独立 | 每个剧情独立进度 |
| `story_tools_unlocked` | ❌ 独立 | 剧情模式按章节进度解锁 |
| `custom_tools_unlocked` | ❌ 独立 | 自定义模式按等级解锁 |

> 双模式系统详细设计见 [`dual-mode.md`](dual-mode.md)

---

## 关键设计决策

| 决策 | 选择 | 说明 |
|------|------|------|
| 游戏模式 | 双模式（剧情 + 自定义） | 剧情模式提供叙事驱动，自定义模式保持自由度 |
| 经验系统 | 每局独立（局内）+ 跨局成长（等级） | Roguelike 单局 + RPG 长期成长 |
| 工具性质 | 消耗品 | 每局有限次数，用完即止 |
| 评分系统 | LLM 判断 + 行为统计 | 多维度评分+行为过程统计，不同分数不同奖励 |
| 等级上限 | 20级 | 渐进式成长，经验曲线可配置 |
| 证据出示 | 限制次数 | 每局 4-8 次（根据等级和难度） |
| 嫌疑人反驳 | 引入 | 嫌疑人会主动辩解，增加审讯难度 |
| 胜利条件 | 供词层级 | 5层供词，从否认到崩溃 |
| 压力来源 | 引擎计算 | 程序化计算优先，LLM 不返回 pressure_change |
| 剧情案件来源 | 混合（固定剧本 + LLM约束生成） | 关键转折手写保证质量，填充章节LLM降低成本 |
| 剧情分支策略 | 漏斗式收敛 | 分支后1-2章内回归主线，3-4个结局 |
| 剧情脚本格式 | JSON 文件 | 与项目现有 Schema 体系一致 |
| 分支条件格式 | 声明式结构 | 防代码注入，安全解析 |
| 会话管理 | GameSession 协调器 | 避免WebMainWindow职责膨胀 |
| 恐惧值系统 | 独立指标 | 与压力值交互：恐惧影响施压效果增益，错误证据导致恐惧下降 |
| 嫌疑人多维指标 | 8指标(2可见+6隐藏) + 可见性等级 | pressure/confession可见 + fear/defiance/empathy/deception/loyalty/credibility隐藏，按等级解锁可见 |
| 维度动态变化 | 全维度动态 | 所有5个隐藏心理维度随审讯过程动态变化，维度间联动形成正/负反馈循环 |
| 施压/共情限制 | 混合方案 | 每人每类2次（第二次效果减半）+ 聊天轮次限制（12轮/人） |
| 压力/恐惧动态 | 每轮结算 | 低压力每轮-1自然衰减、高压力每轮+1自然增长，中间段稳定，floor=15 |
| 心理侧写 | 三级体系 | 初级(Lv.2)/高级(Lv.10)/大师(Lv.15)，对应不同隐藏维度可见 |
| 错误惩罚 | mistake_log + AP扣减 | 错误证据/施压/崩溃导致恐惧下降、AP扣减、评分递减扣分 |
| 反扑机制 | 5种反扑行为 | 反击质问/得意回应/挑衅态度/试探玩家/恢复镇定 |
| 性格系统 | 主+副性格组合 | 7种性格，主0.7+副0.3加权，维度初始值由组合计算 |

---

## 实施分期

### Part A：玩法系统（原有 Phase 1-4）

| 阶段 | 主题 | 核心改动 | 优先级 | 预估工期 |
|------|------|---------|--------|----------|
| Phase 1 | 基础重构 | 证据系统 + 供词层级 + 恐惧值 + 多维隐藏指标 + 施压/共情交互限制 | 最高 | **10天** |
| Phase 2 | 审讯深度 | 反驳机制 + 压力增强 + 证据链 + 主动开口 + 压力/恐惧每轮动态 + 错误惩罚 | 高 | **9天** |
| Phase 3a | 工具引擎 | 工具系统框架 + 4个基础工具 + 三级心理侧写 | 中 | **7天** |
| Phase 3b | 成长系统 | 4个复杂工具 + 玩家等级 + 数据库 + 隐藏维度可见性 | 中 | **5天** |
| Phase 4 | 评分与难度 | 行为评分维度 + 错误惩罚评分 + LLM评分 + 难度分级 | 中 | **6天** |

> Part A 总工期：约 37 天

### Part B：双模式系统（新增）

| 阶段 | 主题 | 核心改动 | 优先级 | 预估工期 |
|------|------|---------|--------|----------|
| Phase 5 | 主菜单 + 会话管理 | 主菜单UI + GameSession协调器 + 模式选择 | 高 | **4天** |
| Phase 6 | 剧情引擎核心 | StoryEngine + 章节JSON Schema + StoryLoader + 分支系统 | 高 | **5天** |
| Phase 7 | 剧情模式UI | 叙事过场 + 章节进度 + 分支提示 + 存档扩展 | 中 | **4天** |
| Phase 8 | MVP剧情脚本 | 5章"寻找失踪父亲"脚本编写 + 测试 | 中 | **5天** |
| Phase 9 | 约束式生成器 | generated章节支持 + case_constraints + 扩展至15章 | 低 | **6天** |

> Part B 总工期：约 24 天（MVP 5章），扩展至15章另需约 5天

### 依赖关系

```
Part A:
  Phase 1 → Phase 2 → Phase 3a → Phase 3b → Phase 4

Part B (依赖 Part A 的 Phase 1):
  Phase 5 (可与 Phase 2+ 并行)
  Phase 6 (依赖 Phase 1 的供词系统 + Phase 5)
  Phase 7 (依赖 Phase 6)
  Phase 8 (依赖 Phase 7)
  Phase 9 (依赖 Phase 8)
```

> **推荐**：先完成 Part A Phase 1，再同时推进 Part A Phase 2+ 和 Part B Phase 5-6。

---

## 文件变更总览

### Part A：需要修改的文件

| 文件 | Phase 1 | Phase 2 | Phase 3a | Phase 3b | Phase 4 |
|------|---------|---------|----------|----------|---------|
| `core/suspect_agent.py` | 重构 respond，新增 respond_evidence，恐惧值，多维隐藏指标 | 反驳逻辑，压力效果，压力/恐惧每轮动态 | — | — | — |
| `core/interrogation.py` | 证据次数限制，供词追踪，统一胜利入口，交互限制，mistake_log | 证据链，压力程序化，错误惩罚 | 工具引擎框架 | 工具实现 | 评分触发 |
| `core/case_generator.py` | Schema 扩展（evidence.type/strength + suspect dimensions） | chain_with 字段 | — | — | 难度参数 |
| `core/db.py` | — | — | — | player_profile 表，迁移机制 | — |
| `core/player.py` | — | — | — | 新文件：等级逻辑+可见性 | — |
| `core/scoring.py` | — | — | — | — | 新文件：行为评分逻辑 |
| `core/game_config.py` | Phase 1 配置 | Phase 2 配置 | Phase 3a 配置 | Phase 3b 配置 | Phase 4 配置 |
| `schemas/events.py` | 新增 ConfessionUpdateEvent + FearUpdateEvent | 新增 RebuttalEvent + MistakeEvent | 新增 ToolUseEvent | — | — |
| `ui/web_main_window.py` | 处理新事件，证据次数，交互限制 | 反驳事件，主动开口异步，错误提示 | 工具事件 | 等级展示 | 评分展示 |
| `ui/web_bridge.py` | 新增信号 | 新增信号 | 新增信号 | 新增信号 | 新增信号 |
| `ui/web/js/` | 供词/证据/恐惧 JS | — | 工具 JS | 等级 JS | 评分 JS |
| `ui/web/index.html` | 供词 UI，恐惧 UI，交互限制提示 | — | 工具栏 | 等级面板 | 评分面板 |
| `ui/web/css/` | 供词/证据/恐惧样式 | 反驳样式 | 工具样式 | 等级样式 | 评分样式 |
| `tests/` | Phase 1 测试 | Phase 2 测试 | Phase 3a 测试 | Phase 3b 测试 | Phase 4 测试 |

### Part A：需要新增的文件

| 文件 | 说明 |
|------|------|
| `core/player.py` | 玩家档案和等级逻辑（Phase 3b） |
| `core/scoring.py` | 评分系统逻辑（Phase 4） |
| `core/game_config.py` | 游戏配置（按阶段添加） |
| `core/tools/` | 工具实现目录（Phase 3a 预留接口，Phase 3b 填充） |

### Part B：需要修改的文件

| 文件 | Phase 5 | Phase 6 | Phase 7 | Phase 8 | Phase 9 |
|------|---------|---------|---------|---------|---------|
| `ui/web_main_window.py` | GameSession 集成，模式分发 | StoryEngine 事件处理 | 叙事过场，章节UI | — | — |
| `ui/web_bridge.py` | 主菜单信号 | 剧情信号 | 章节进度信号 | — | — |
| `ui/web/index.html` | 主菜单页面 | — | 叙事UI，章节进度 | — | — |
| `core/case_generator.py` | — | — | — | — | 约束式生成 |
| `core/db.py` | — | — | 存档扩展（mode字段） | — | — |
| `core/player.py` | — | — | 剧情进度持久化 | — | — |
| `tests/` | Phase 5 测试 | Phase 6 测试 | Phase 7 测试 | Phase 8 测试 | Phase 9 测试 |

### Part B：需要新增的文件

| 文件 | 说明 |
|------|------|
| `core/game_session.py` | 游戏会话协调器（Phase 5） |
| `core/story_engine.py` | 剧情引擎：章节流转、分支判定、状态管理（Phase 6） |
| `core/story_loader.py` | 剧情脚本加载与验证（Phase 6） |
| `schemas/story.py` | 章节、剧情进度、审讯结果数据结构（Phase 6） |
| `stories/` | 剧情脚本目录（Phase 8） |
| `stories/missing_father.json` | "寻找失踪父亲"剧情脚本（Phase 8） |
| `ui/web/js/story.js` | 剧情模式前端模块（Phase 7） |
| `ui/web/js/menu.js` | 主菜单前端模块（Phase 5） |

---

## 数据流变更

### 当前流程

```
出示证据 → suspect.respond("出示证据: {name}")
→ LLM 回复可能含关键词 → _postprocess 子字符串匹配 → 胜利
```

### 目标流程（Phase 1 完成后）

```
出示证据 → 检查剩余AP(2AP) → suspect.respond_evidence(description, evidence_type)
→ LLM 返回 {reply, secret_triggered}  （不再返回 pressure_change）
→ 引擎程序化计算:
    压力增量 = 证据类型基础值 × (1 + 强度 × 系数) + chain_bonus
    恐惧系数 = fear / 50
    抗压系数 = 1 / (1 + defiance × 0.01)
    软上限系数 = clamp(恐惧系数 × 抗压系数, 0.3, 1.5)
    实际压力增量 = 压力增量 × 软上限系数
→ 扣减AP: 出示证据=2AP
→ 若证据与当前嫌疑人相关:
    fear += 8  （恐惧上升，正向激励）
→ 若证据与当前嫌疑人无关:
    fear -= 10  （恐惧下降，惩罚）
    AP -= 2  （额外惩罚）
    mistake_log 记录错误
→ 每轮维度联动 + 压力/恐惧每轮动态结算:
    pressure<30 → pressure-1/轮, pressure>=70 → pressure+1/轮
    fear每轮-1（自然冷却）
    pressure>60 → defiance-1, pressure>70 → deception-2
    fear>70 → defiance-2/deception-3/loyalty-2
    fear>60 → empathy+1, defiance>70 → empathy-1
→ 检查反扑条件: 连续反驳成功/fear<15/连续空闲
→ _postprocess: 低供词层级时替换回复但不触发胜利；>=3 时才触发
→ _check_victory() 统一判定所有胜利条件
→ AP<=0 且未胜利 → 判定失败（律师介入）
```

### 剧情模式流程（Phase 6 完成后）

```
主菜单 → 选择剧情模式 → GameSession.start_story(story_id)
→ StoryEngine.start_chapter() → 返回 case_data
→ InterrogationEngine(case_data) → 审讯交互
→ 审讯结束 → GameSession.evaluate_chapter() → ChapterResult
→ StoryEngine.complete_chapter(result) → 评估分支 → 下一章节
→ 叙事过场 → 新章节开始 → ... → 到达结局
```

---

## 评审后关键修正（相比 v1.0）

| # | 问题 | 等级 | 修正措施 |
|---|------|------|----------|
| 1 | `_postprocess` 与供词系统冲突 | P0 | 低供词层级替换回复但不触发胜利，>=3 才触发 |
| 2 | `tick()` 主动开口阻塞 UI | P0 | 改为基于轮次触发，WebWorker 异步执行 |
| 3 | `respond()`/`respond_evidence()` 代码重复 | P1 | 抽取 `_call_llm()` 公共方法 |
| 4 | 胜利判定逻辑分散 | P1 | 统一 `_check_victory()` 入口 |
| 5 | 压力变化双重计算 | P1 | 程序化计算优先，LLM 不再返回 `pressure_change` |
| 6 | `rebuttal_believable` 完全依赖 LLM 自评 | P1 | 增加程序化兜底（pressure>80 强制衰减） |
| 7 | `requires_semantic` 无实现 | P1 | Phase 1 移除，Phase 2 实现 |
| 8 | 工具系统与引擎耦合 | P1 | Phase 3 预留策略模式接口 |
| 9 | 数据库无迁移机制 | P1 | Phase 3b 引入版本号和增量迁移 |
| 10 | `game_config.py` 过早包含后期配置 | P2 | 按阶段分步添加配置 |
| 11 | 信号数量持续增长 | P2 | 可选合并低频信号 |
| 12 | Phase 3 工作量被低估 | P1 | 拆分为 3a + 3b |

## v1.2 新增修正（双模式系统）

| # | 问题 | 等级 | 修正措施 |
|---|------|------|----------|
| 13 | 无长期叙事驱动 | — | 新增剧情模式（15+章，分支+结局） |
| 14 | 缺少会话协调层 | P1 | 新增 GameSession 协调器，避免 WebMainWindow 膨胀 |
| 15 | 分支条件代码注入风险 | P0 | 使用声明式条件结构，非 Python 表达式 |
| 16 | 审讯结果缺少量化评估 | P0 | 新增 ChapterResult（win/partial/fail + 供词层级） |
| 17 | 跨章节状态传递机制缺失 | P1 | story_variables + carry_evidence + merge_to 声明 |
| 18 | 存档设计冗余 | P1 | 统一 sessions 表 + mode 字段，不新增 story_saves 表 |

## v1.3 新增修正（审讯机制深化）

| # | 问题 | 等级 | 修正措施 |
|---|------|------|----------|
| 19 | 嫌疑人维度单一，压力/供词无法体现个体差异 | P0 | 新增恐惧值(fear) + 5维隐藏指标(defiance/empathy_susceptibility/deception_skill/loyalty) + credibility，各维度动态变化并相互影响，详见 [`suspect-dimensions.md`](suspect-dimensions.md) |
| 20 | 施压/共情无限制，可无限试错 | P0 | 混合方案：每人每类1次 + 聊天轮次限制(10轮/人) |
| 21 | 压力静态无动态，不操作压力不变 | P1 | 压力/恐惧每轮动态：低压力(0-30)每轮-1，高压力(70+)每轮+1，中间段稳定 |
| 22 | 错误操作无惩罚 | P1 | mistake_log 机制：错误证据→恐惧-10+时间-15s，错误施压→时间-10s，无辜崩溃→评分-20 |
| 23 | 心理侧写过浅，只显示 personality | P1 | 三级侧写体系：初级(Lv.2)→personality+fear，高级(Lv.10)→+defiance/empathy，大师(Lv.15)→全部可见 |
| 24 | 复盘维度不足，缺少行为过程统计 | P2 | 评分新增3个行为维度：施压精准度、证据精准度、错误惩罚 |

## v1.4 新增修正（维度动态化与反扑机制）

| # | 问题 | 等级 | 修正措施 |
|---|------|------|----------|
| 25 | 隐藏维度初始化后不变，与"动态指标"设计矛盾 | P0 | 全维度动态变化机制：每轮联动效果 + 操作触发变化，详见 [`suspect-dimensions.md`](suspect-dimensions.md) |
| 26 | 嫌疑人被动挨打，缺少主动博弈 | P0 | 反扑机制：5种反扑行为（反击质问/得意回应/挑衅/试探/恢复） |
| 27 | 性格类型过粗，5种离散类型无变化 | P1 | 主+副性格组合(0.7+0.3加权)，新增忠诚/孤僻2种性格 |
| 28 | 维度边界未定义，defiance可归零使施压无限放大 | P1 | 各维度定义min/max边界：defiance最低5，empathy最高95等 |
| 29 | 维度间缺少联动，fear/defiance独立计算 | P1 | 维度联动规则：fear>70瓦解defiance/deception/loyalty，pressure>60瓦解defiance等 |
