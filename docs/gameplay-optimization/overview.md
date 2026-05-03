# The Box 玩法深度优化方案 — 总览

## 核心问题诊断

| 问题 | 根因 | 位置 |
|------|------|------|
| 点完证据就赢 | 证据名直接传入 LLM prompt，LLM 自然复述触发关键词 | `interrogation.py:89` + `suspect_agent.py:75` |
| 关键词匹配太松 | 子字符串匹配，2字短语极易误触发 | `suspect_agent.py:115` |
| 没有策略深度 | 出示顺序/时机不影响结果，可重复出示 | `interrogation.py:78-92` |
| 压力系统形同虚设 | 仅通过提示词间接影响 LLM，无程序化机制 | `suspect_agent.py:47-48` |
| 胜负二元 | 触发关键词=赢，时间耗尽=输，无中间状态 | `interrogation.py:118-126` |
| 静态系统提示词 | 压力值在 `__init__` 时固定为 50，运行中不更新 | `suspect_agent.py:24` |

### 证据出示链路中的关键缺陷

```
用户点击证据 → bridge.presentEvidence(id)
→ _on_evidence_selected → content = f"出示证据: {证据名}"  ← 只有名，没有描述
→ engine.submit_action("present_evidence", content, id)
→ suspect.respond("出示证据: 沾血的锄头")  ← 嫌疑人收到证据名
→ LLM 回复自然包含 "锄头" → _postprocess 子字符串匹配 forbidden "锄头" → 胜利
```

## 方案架构

```
┌─────────────────────────────────────────────────────────┐
│                    玩家成长系统 (20级)                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │              消耗品工具箱 (6种工具)                 │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │           供词层级系统 (5层)                  │  │  │
│  │  │  ┌───────────────────────────────────────┐  │  │  │
│  │  │  │    证据系统重构 + 嫌疑人反驳机制       │  │  │  │
│  │  │  │    压力系统增强 (程序化效果)           │  │  │  │
│  │  │  └───────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                    评分系统 (S/A/B/C/D)                  │
└─────────────────────────────────────────────────────────┘
```

## 关键设计决策

| 决策 | 选择 | 说明 |
|------|------|------|
| 经验系统 | 每局独立 | Roguelike 风格，每局从零开始 |
| 工具性质 | 消耗品 | 每局有限次数，用完即止 |
| 评分系统 | LLM 判断 | 多维度评分，不同分数不同奖励 |
| 等级上限 | 20级 | 渐进式成长，经验曲线可配置 |
| 证据出示 | 限制次数 | 每局 3-7 次（根据等级和难度） |
| 嫌疑人反驳 | 引入 | 嫌疑人会主动辩解，增加审讯难度 |
| 胜利条件 | 供词层级 | 5层供词，从否认到崩溃 |

## 实施分期

| 阶段 | 主题 | 核心改动 | 优先级 |
|------|------|---------|--------|
| Phase 1 | 基础重构 | 证据系统 + 供词层级 | 最高 |
| Phase 2 | 审讯深度 | 反驳机制 + 压力增强 + 证据链 | 高 |
| Phase 3 | 工具与成长 | 消耗品工具 + 玩家等级 | 中 |
| Phase 4 | 评分与难度 | LLM 评分 + 难度分级 | 中 |

## 文件变更总览

### 需要修改的文件

| 文件 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| `core/suspect_agent.py` | 重构 respond，新增 respond_evidence | 反驳逻辑，压力效果 | — | — |
| `core/interrogation.py` | 证据次数限制，供词追踪 | 证据链，压力程序化 | 工具系统 | 评分触发 |
| `core/case_generator.py` | Schema 扩展（evidence.type/strength） | chain_with 字段 | — | 难度参数 |
| `core/db.py` | — | — | player_profile 表 | — |
| `core/player.py` | — | — | 新文件：等级逻辑 | — |
| `core/scoring.py` | — | — | — | 新文件：评分逻辑 |
| `schemas/events.py` | 新增 ConfessionUpdateEvent | 新增 RebuttalEvent | 新增 ToolUseEvent | — |
| `ui/web_main_window.py` | 处理新事件，证据次数 | 反驳事件处理 | 工具事件 | 评分展示 |
| `ui/web_bridge.py` | 新增信号 | 新增信号 | 新增信号 | 新增信号 |
| `ui/web/js/evidence.js` | 已出示标记，次数显示 | — | — | — |
| `ui/web/js/suspect.js` | 供词进度条 | — | — | — |
| `ui/web/js/app.js` | 新事件绑定 | 新事件绑定 | 工具栏逻辑 | 评分面板 |
| `ui/web/index.html` | 供词 UI，证据次数 | — | 工具栏 HTML | 评分面板 |
| `ui/web/css/` | 供词样式，证据标记 | 反驳样式 | 工具样式 | 评分样式 |
| `tests/` | Phase 1 测试 | Phase 2 测试 | Phase 3 测试 | Phase 4 测试 |

### 需要新增的文件

| 文件 | 说明 |
|------|------|
| `core/player.py` | 玩家档案和等级逻辑（Phase 3） |
| `core/scoring.py` | 评分系统逻辑（Phase 4） |
| `core/game_config.py` | 游戏配置（经验曲线、难度参数等），避免硬编码 |

## 数据流变更

### 当前流程

```
出示证据 → suspect.respond("出示证据: {name}")
→ LLM 回复可能含关键词 → _postprocess 子字符串匹配 → 胜利
```

### 目标流程（Phase 1 完成后）

```
出示证据 → 检查剩余次数 → suspect.respond_evidence(description, evidence_type)
→ LLM 返回 {reply, pressure_change, confession_progress_change}
→ 引擎更新: 压力 + 供词层级
→ 供词层级 >= 3 时触发关键词匹配作为完美胜利条件
→ 供词层级 >= 2 时可提交推理结论作为部分胜利
```

## 配置化原则

以下参数不得硬编码，统一放在 `core/game_config.py` 中：

```python
# 经验曲线（每级所需经验）
EXPERIENCE_CURVE = [0, 50, 120, 200, 300, 450, 600, 800, 1050, 1350,
                    1700, 2100, 2550, 3050, 3600, 4200, 4850, 5550, 6300, 7100]

# 等级解锁内容
LEVEL_UNLOCKS = {
    1: {"tools": [], "evidence_uses": 3, "desc": "基础审讯"},
    2: {"tools": ["psych_profile"], "evidence_uses": 3, "desc": "心理侧写"},
    # ...
}

# 难度参数
DIFFICULTY_PRESETS = {
    "easy":   {"suspects": 2, "time": 360, "evidence_uses": 4, "keywords": 3},
    "normal": {"suspects": "2-3", "time": 300, "evidence_uses": 3, "keywords": 2},
    "hard":   {"suspects": "3-4", "time": 240, "evidence_uses": 3, "keywords": 2},
    "nightmare": {"suspects": "4+", "time": 180, "evidence_uses": 2, "keywords": 1},
}

# 供词层级升级阈值
CONFESSION_THRESHOLDS = {
    0: {"pressure": 40, "min_turns": 3},
    1: {"pressure": 60, "requires_evidence": True},
    2: {"pressure": 75, "requires_semantic_match": True},
    3: {"pressure": 90, "requires_keyword_trigger": True},
}

# 压力段定义
PRESSURE_SEGMENTS = {
    "low":    (0, 30),
    "medium": (30, 60),
    "high":   (60, 80),
    "panic":  (80, 100),
}
```
