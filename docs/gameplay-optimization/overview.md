# The Box 玩法深度优化方案 — 总览（优化版 v1.7）

> **版本**：v1.7
> **评审日期**：2026-05-05
> **v1.1 变更**：修复2个P0问题、6个P1问题，调整工作量估算，优化架构设计
> **v1.2 变更**：新增双模式系统（剧情模式 + 自定义模式），调整实施分期
> **v1.3 变更**：新增恐惧值系统、嫌疑人多维隐藏指标、施压/共情交互限制、每轮压力动态关系、心理侧写三级体系、行为评分维度增强
> **v1.4 变更**：全维度动态变化机制、主+副性格组合系统、反扑机制、维度边界与联动规则，详见 [`suspect-dimensions.md`](suspect-dimensions.md)
> **v1.5 变更**：统一数值基线（普通难度22 AP、初始压力20、证据基值18/12/9）、新增 `culprit_name` 真凶字段、供词进度改为反馈指标、修正反扑欺骗阈值方向、增加评分结果封顶。
> **v1.6 变更**：补充分阶段任务包、弱模型执行边界、阶段验收闸门、测试矩阵和交付物清单。
> **v1.7 变更**：明确所有玩法数值均为配置文件默认值，不允许写死在业务逻辑；新增 `config/gameplay_balance.json` 作为单一数值来源，`core/game_config.py` 仅负责加载、校验和提供只读访问器。

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
│  │  │  │    施压/共情交互限制 + 每轮压力动态          │    │  │  │
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
| 数值配置 | 外部配置文件 | 所有AP、阈值、倍率、权重、难度、经验曲线、工具消耗均来自 `config/gameplay_balance.json` |
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
| 数值基线 | 默认配置值 | 默认普通难度22 AP、初始压力20、证据基础值physical/document/testimony=18/12/9；修改配置文件即可调整 |
| 真凶来源 | `culprit_name` | 顶层字段是唯一真凶数据源，运行时如需 `is_culprit` 必须由它派生 |
| 供词进度 | 反馈指标 | `confession_progress` 只用于UI/复盘节奏，不作为升级硬门槛 |
| 评分封顶 | 按结果封顶 | win不封顶；partial最高74；fail最高59；无辜崩溃最高49 |

---

## 数值配置文件化原则

所有文档中出现的 AP、压力、阈值、倍率、扣分、经验、难度和工具次数，均表示 `config/gameplay_balance.json` 中的默认值，而不是代码常量。实现时必须遵守以下规则：

| 原则 | 要求 |
|------|------|
| 单一来源 | `config/gameplay_balance.json` 是玩法平衡数值的唯一默认来源 |
| 加载器职责 | `core/game_config.py` 只负责加载默认配置、合并用户覆盖、校验结构、提供只读访问器 |
| 禁止硬编码 | `core/interrogation.py`、`core/suspect_agent.py`、`core/scoring.py`、`core/tools/` 不得直接写入AP、阈值、倍率、权重等魔法数字 |
| 覆盖方式 | 支持通过环境变量 `THEBOX_GAMEPLAY_CONFIG` 指向调试配置；未来可扩展到用户目录配置 |
| 测试约束 | 每个涉及数值的测试都要覆盖“默认配置”和“临时配置覆盖后行为改变”两个路径 |

推荐的配置文件分区：

```json
{
  "config_version": 1,
  "action_points": {
    "difficulty_defaults": {"easy": 26, "normal": 22, "hard": 19, "nightmare": 16},
    "costs": {"chat": 1, "pressure": 2, "empathy": 2, "present_evidence": 2},
    "penalties": {"wrong_evidence": 2, "wrong_pressure": 1, "wrong_empathy": 1, "innocent_breakdown": 3}
  },
  "pressure": {
    "initial": 20,
    "segments": {"low": [0, 30], "medium": [30, 70], "high": [70, 80], "panic": [80, 100]},
    "per_turn": {"decay_rate": -1, "stable_rate": 0, "growth_rate": 1, "floor": 15}
  },
  "evidence": {
    "default_uses": 4,
    "pressure_base": {"physical": 18, "document": 12, "testimony": 9},
    "strength_multiplier": 0.1,
    "chain_bonus": 10
  },
  "confession": {
    "thresholds": {
      "0": {"pressure": 40, "min_turns": 3, "requires_evidence": false},
      "1": {"pressure": 55, "min_turns": 5, "requires_evidence": true},
      "2": {"pressure": 70, "min_turns": 7, "requires_evidence": true},
      "3": {"pressure": 85, "min_turns": 10, "requires_evidence": true}
    },
    "pressure_window": 5
  },
  "scoring": {
    "outcome_caps": {"partial": 74, "fail": 59, "innocent_breakdown": 49}
  }
}
```

代码层建议只暴露语义化访问器，例如 `get_action_cost("present_evidence")`、`get_confession_threshold(level)`、`get_difficulty_preset("normal")`。若为兼容文档或旧测试导出 `DEFAULT_TOTAL_ACTION_POINTS` 等名称，也必须在模块加载时从配置文件派生，不能在 Python 源码中重新定义数值。

---

## 实施分期

### Part A：玩法系统（原有 Phase 1-4）

| 阶段 | 主题 | 核心改动 | 优先级 | 预估工期 |
|------|------|---------|--------|----------|
| Phase 0 | 执行基线 | 测试夹具 + fake LLM + mock case + 平衡模拟脚手架 | 最高 | **2天** |
| Phase 1 | 基础重构 | 证据系统 + 供词层级 + 恐惧值 + 多维隐藏指标 + 施压/共情交互限制 | 最高 | **13天** |
| Phase 2 | 审讯深度 | 反驳机制 + 压力增强 + 证据链 + 主动开口 + 压力/恐惧每轮动态 + 错误惩罚 | 高 | **11天** |
| Phase 3a | 工具引擎 | 工具系统框架 + 4个基础工具 + 三级心理侧写 | 中 | **8天** |
| Phase 3b | 成长系统 | 玩家等级 + 数据库迁移 + 解锁规则 + 隐藏维度可见性 | 中 | **6天** |
| Phase 3c | 复杂工具 | 测谎仪、威胁、多人对质、心理崩溃等高风险工具 | 中 | **5天** |
| Phase 4 | 评分与难度 | 行为评分维度 + 错误惩罚评分 + LLM评分 + 难度分级 | 中 | **8天** |

> Part A 总工期：约 53 天。v1.6 评审认为原 37 天对弱模型执行过紧，主要缺口在 Phase 1 平衡验证、Phase 3 复杂工具拆分、Phase 4 评分回归。

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
  Phase 0 → Phase 1 → Phase 2 → Phase 3a → Phase 3b → Phase 3c → Phase 4

Part B (依赖 Part A 的 Phase 1):
  Phase 5 (可与 Phase 2+ 并行)
  Phase 6 (依赖 Phase 1 的供词系统 + Phase 5)
  Phase 7 (依赖 Phase 6)
  Phase 8 (依赖 Phase 7)
  Phase 9 (依赖 Phase 8)
```

> **推荐**：先完成 Phase 0 和 Part A Phase 1，再同时推进 Part A Phase 2+ 和 Part B Phase 5-6。

### v1.6 分期评审结论

当前方案的机制设计足够细，但如果直接交给性能较弱的 LLM 实现，阶段颗粒仍偏大。执行时必须拆成“单一职责任务包”，每个任务包只允许改一小组强相关文件，并且必须附带测试和验收标准。

| 结论 | 处理方式 |
|------|----------|
| Phase 1 过大，包含 Schema、引擎、UI、存档、数值平衡 | 拆成 1a 配置/Schema、1b 引擎核心、1c UI/事件、1d 存档/平衡测试四个闸门 |
| Phase 2 机制多且互相影响 | 拆成 2a 反驳、2b 每轮动态、2c 错误惩罚、2d 反扑、2e UI/事件 |
| Phase 3 原先把复杂工具和成长系统混在一起 | Phase 3a 只做工具框架+安全基础工具；Phase 3b 只做等级/DB；Phase 3c 再做复杂工具 |
| Phase 4 涉及评分、经验、难度、UI | 先纯规则评分，再 UI，再难度生成，最后整合经验结算 |
| Part B 可以并行，但不能早于 Phase 1 验收 | Phase 5 可在 Phase 1 后并行；Phase 6 必须依赖 `culprit_name`、ChapterResult 和供词层级稳定 |

### 弱模型任务包规则

| 规则 | 要求 |
|------|------|
| 单包范围 | 单个任务包最多修改 2-4 个文件，优先只改 `core/` 或只改 `ui/web/`，不要同时改引擎、DB、UI、测试以外的多层逻辑 |
| 单包目标 | 必须有一个清晰输出，例如“新增 `config/gameplay_balance.json` 与 `core/game_config.py` 加载器并通过配置测试”，不能写成“实现 Phase 1” |
| 输入上下文 | 每个任务包必须列出依赖章节、目标文件、不可改文件、现有测试、验收命令 |
| 测试要求 | 每个任务包至少新增或更新一个针对性测试；纯 UI 样式任务可用截图/DOM状态验收替代 |
| 交付顺序 | 先纯函数/配置/Schema，再引擎状态，再 UI 桥接，最后端到端流程 |
| 禁止事项 | 不允许弱模型同时重构 LLM prompt、胜利判定、AP扣减和 UI 事件；这些必须拆包 |

### 阶段闸门

| 闸门 | 范围 | 必须交付 | 验收命令 |
|------|------|----------|----------|
| Phase 0 | 测试基线与夹具 | mock case、fake LLM、平衡模拟入口、当前测试绿灯 | `pytest tests/ -m "not slow and not real_api" -v` |
| Phase 1a | 配置与Schema | `config/gameplay_balance.json`、`game_config.py` 加载器、`culprit_name`、证据 type/strength、维度默认值 | `pytest tests/test_game_config.py tests/test_case_schema.py -v` |
| Phase 1b | 引擎核心 | `respond_evidence`、程序化压力、AP、胜利入口、供词升级 | `pytest tests/test_evidence_rework.py tests/test_victory_conditions.py -v` |
| Phase 1c | UI与事件 | 供词/恐惧/交互限制事件和前端展示 | `pytest tests/test_web_integration.py -v` |
| Phase 1d | 存档与平衡 | 新字段序列化、旧存档兼容、42组合平衡模拟 | `pytest tests/test_save_load.py tests/test_balance.py -v` |
| Phase 2 | 审讯深度 | 反驳、证据链、主动开口、错误惩罚、反扑 | `pytest tests/test_rebuttal.py tests/test_mistakes.py tests/test_proactive.py -v` |
| Phase 3a | 工具框架 | Tool基类、注册表、基础工具、工具UI | `pytest tests/test_tools.py tests/test_tool_ui.py -v` |
| Phase 3b | 成长系统 | PlayerProfile、DB迁移、等级解锁、AP/初压奖励 | `pytest tests/test_player_profile.py tests/test_db_migrations.py -v` |
| Phase 3c | 复杂工具 | 测谎/威胁/对质/心理崩溃，且不泄露隐藏知识 | `pytest tests/test_advanced_tools.py -v` |
| Phase 4 | 评分与难度 | 评分、结果封顶、经验、难度参数、评分UI | `pytest tests/test_scoring.py tests/test_difficulty.py -v` |
| Phase 5-9 | 双模式 | GameSession、StoryEngine、剧情UI、脚本、生成器 | `pytest tests/test_story*.py tests/test_game_session.py -v` |

所有闸门还必须通过全量快速回归：`pytest tests/ -m "not slow and not real_api" -v`。

### 阶段验收标准

| 类型 | 验收标准 |
|------|----------|
| 功能正确性 | 目标任务的单元测试和相关集成测试全部通过；失败路径也有测试覆盖 |
| 存档兼容 | 新字段使用 `.get(..., default)` 恢复，旧存档 fixture 加载不崩溃 |
| UI事件 | Python事件、WebBridge信号、前端处理函数三者字段一致 |
| LLM隔离 | 测试不得依赖真实API；必须使用 fake/mock LLM 返回固定JSON |
| 数值平衡 | 普通难度42种主副性格组合胜率目标30%-80%，最难组合不低于20%，最易组合不高于90% |
| 数值可配置 | 修改临时 `gameplay_balance.json` 后，无需改代码即可影响AP、阈值、证据基值、评分封顶、难度和工具消耗 |
| 回归稳定 | 原有快速测试、lint/format检查通过；如某项暂不可跑，必须在交付说明中写明原因 |

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
| `config/gameplay_balance.json` | Phase 1 默认数值 | Phase 2 默认数值 | Phase 3a 工具数值 | Phase 3b 等级/经验数值 | Phase 4 评分/难度数值 |
| `core/game_config.py` | 配置加载/校验/访问器 | 新增Phase 2访问器 | 新增工具访问器 | 新增等级访问器 | 新增评分/难度访问器 |
| `schemas/events.py` | 新增 ConfessionUpdateEvent + FearUpdateEvent | 新增 RebuttalEvent + MistakeEvent | 新增 ToolUseEvent | — | — |
| `ui/web_main_window.py` | 处理新事件，证据次数，交互限制 | 反驳事件，主动开口异步，错误提示 | 工具事件 | 等级展示 | 评分展示 |
| `ui/web_bridge.py` | 新增信号 | 新增信号 | 新增信号 | 新增信号 | 新增信号 |
| `ui/web/js/` | 供词/证据/恐惧 JS | — | 工具 JS | 等级 JS | 评分 JS |
| `ui/web/index.html` | 供词 UI，恐惧 UI，交互限制提示 | — | 工具栏 | 等级面板 | 评分面板 |
| `ui/web/css/` | 供词/证据/恐惧样式 | 反驳样式 | 工具样式 | 等级样式 | 评分样式 |
| `tests/` | Phase 1 测试 | Phase 2 测试 | Phase 3a 测试 | Phase 3b 测试 | Phase 4 测试 |

> v1.6 执行补充：Phase 0 只允许新增/整理测试夹具、fake LLM 和 mock case，不改业务逻辑。Phase 3c 复用 Phase 3a 的工具框架，主要写入 `core/tools/`、`tests/test_advanced_tools.py` 和必要的工具配置，避免和 Phase 3b 的 DB/等级迁移混在同一任务包。

### Part A：需要新增的文件

| 文件 | 说明 |
|------|------|
| `core/player.py` | 玩家档案和等级逻辑（Phase 3b） |
| `core/scoring.py` | 评分系统逻辑（Phase 4） |
| `config/gameplay_balance.json` | 玩法平衡默认配置（按阶段添加字段） |
| `core/game_config.py` | 玩法配置加载器、校验器和访问器 |
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
→ 引擎从 gameplay_balance 配置读取数值并程序化计算:
    证据类型基础值 = pressure_base[physical/document/testimony]，默认18/12/9
    压力增量 = 证据类型基础值 × (1 + 强度 × 系数) + chain_bonus
    恐惧系数 = fear / 50
    抗压系数 = 1 / (1 + defiance × 0.01)
    软上限系数 = clamp(恐惧系数 × 抗压系数, 0.3, 1.5)
    实际压力增量 = 压力增量 × 软上限系数
→ 扣减AP: 从 difficulty_defaults 和 costs 读取；默认普通难度总AP=22，出示证据=2AP
→ 若证据与当前嫌疑人相关:
    fear += 配置值  （默认+8，恐惧上升，正向激励）
→ 若证据与当前嫌疑人无关:
    fear -= 配置值  （默认-10，恐惧下降，惩罚）
    AP -= 配置值  （默认额外-2，额外惩罚）
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
| 20 | 施压/共情无限制，可无限试错 | P0 | 混合方案：每人施压/共情各2次（第二次减半）+ 自由聊天12轮/人；证据/施压/共情不消耗自由聊天次数，但计入 `turn_count` |
| 21 | 压力静态无动态，不操作压力不变 | P1 | 压力/恐惧每轮动态：低压力(0-30)每轮-1，高压力(70+)每轮+1，中间段稳定 |
| 22 | 错误操作无惩罚 | P1 | mistake_log 机制：错误证据→恐惧-10+额外-2 AP，错误施压/共情→额外-1 AP，无辜崩溃→额外-3 AP且评分封顶 |
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

## v1.5 新增修正（数值基线统一）

| # | 问题 | 等级 | 修正措施 |
|---|------|------|----------|
| 30 | 文档间 AP 基线不一致，20 AP 对标准成功路径过紧 | P0 | 默认配置中普通难度AP为22，困难/噩梦分别19/16，简单26；代码不得硬编码这些值 |
| 31 | 证据压力基值偏低，冷静/固执型在AP模型下卡在层级3 | P0 | 默认配置中 `evidence.pressure_base` 为 physical=18、document=12、testimony=9；可通过配置调参 |
| 32 | `confession_progress` 若作为硬门槛会使12轮目标数学不可达 | P0 | 改为UI/复盘反馈指标；升级只看 pressure + turn_count + related_evidence |
| 33 | 真凶身份缺少结构化来源 | P0 | 案件Schema新增顶层 `culprit_name`，评分和错误检测不再依赖文本反推或可选 `is_culprit` |
| 34 | 高欺骗值反而降低反扑阈值，方向错误 | P1 | 反扑阈值改为 `80 + (deception_skill - 50) × 0.2`，欺骗越高越难被压制 |
| 35 | 失败局可能因行为分/LLM分偏高拿到高评级 | P1 | 评分增加结果封顶：partial≤74、fail≤59、无辜崩溃≤49 |
