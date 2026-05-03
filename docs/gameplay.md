# The Box: Local Verdict — 玩法逻辑文档

## 游戏概述

**The Box: Local Verdict** 是一款 AI 驱动的侦探审讯游戏。玩家扮演审讯员，在限定时间内通过自由提问、施压策略和证据出示，迫使嫌疑人（由 LLM 扮演）在压力下泄露案件真相。

---

## 核心游戏循环

```
生成案件 → 选择嫌疑人 → 审讯交互 → 结局判定
                ↑_______________|
```

### 详细流程

1. **案件生成**
   - 玩家输入可选的背景故事
   - LLM 自动生成完整案件（嫌疑人、证据、真相）
   - 案件数据通过 JSON Schema 验证

2. **选择嫌疑人**
   - 从嫌疑人列表中选择审讯对象
   - 选择后启动倒计时
   - 游戏状态从 `selecting` 变为 `interrogating`

3. **审讯交互**
   - 玩家可进行三类操作：自由提问、施压/共情、出示证据
   - 嫌疑人根据压力值和人设实时回复
   - 系统检测是否触发禁忌词

4. **结局判定**
   - 胜利：真凶泄露禁忌词 → 崩溃认罪
   - 失败：时间耗尽 → 律师介入

---

## 审讯系统

### 玩家操作

| 操作 | 触发方式 | 效果 |
|------|---------|------|
| 自由提问 | 聊天框输入文本 | LLM 生成嫌疑人回复 |
| 施压 (Pressure) | 点击施压按钮 | 压力值 +10 |
| 共情 (Empathy) | 点击共情按钮 | 压力值 -5 |
| 出示证据 | 点击证据卡片 | 将证据信息注入对话，压力值可能变化 |

### 嫌疑人回复机制

**输入处理** (`core/suspect_agent.py:24-58`)

系统提示词包含：
- 角色背景与性格特征
- 该嫌疑人已知信息 (`knowledge`)
- 禁止泄露内容列表 (`forbidden_to_reveal`)
- 当前压力值状态

**输出格式要求**

嫌疑人回复必须为 JSON 格式：
```json
{
  "reply": "回复文本（1-3句话）",
  "pressure_change": 0,
  "secret_triggered": false
}
```

**后处理检查** (`core/suspect_agent.py:111-120`)

- 检测回复是否包含 `forbidden_to_reveal` 关键词
- 若触发：替换回复为"（嫌疑人略显紧张，但并没有直接回答你的问题。）"，压力值额外 +20

---

## 压力值系统

### 基础规则

| 属性 | 值 |
|------|-----|
| 初始值 | 50 |
| 范围 | 0 - 100 |
| 施压效果 | +10 |
| 共情效果 | -5 |
| 触发禁忌词 | +20 |

### 压力值影响

- **低压力 (<30%)**：嫌疑人冷静，回答谨慎
- **中压力 (30-70%)**：嫌疑人开始紧张，可能出现矛盾
- **高压力 (>70%)**：嫌疑人慌乱，可能语无伦次或泄露秘密

### 视觉反馈 (`ui/web/js/suspect.js:226-230`)

- 绿色：低压力
- 黄色：中压力
- 红色：高压力

---

## 案件生成系统

### 案件数据结构 (`core/case_generator.py:14-71`)

```json
{
  "case_id": "uuid",
  "title": "案件标题",
  "victim": "受害者姓名",
  "cause_of_death": "死因",
  "crime_scene": "犯罪现场描述",
  "truth": "案件真相（包含动机、手段、时机）",
  "suspects": [
    {
      "name": "姓名",
      "role": "与受害者关系",
      "personality": "性格描述",
      "knowledge": "该嫌疑人知道的信息",
      "forbidden_to_reveal": ["禁忌词1", "禁忌词2"]
    }
  ],
  "evidence": [
    {
      "id": "evidence_1",
      "name": "证据名称",
      "description": "证据描述",
      "related_suspect": "相关嫌疑人姓名或null"
    }
  ],
  "interrogation_time_limit_sec": 300
}
```

### 生成流程 (`core/case_generator.py:116-170`)

1. 构建系统提示词，要求 LLM 生成案件 JSON
2. 调用 LLM API（温度参数：首次 0.8，重试 0.9）
3. 使用 `jsonschema` 验证数据结构
4. 最多重试 1 次（共 2 次尝试）
5. 验证通过后返回案件对象

### 案件要素说明

| 要素 | 说明 |
|------|------|
| `truth` | 案件真相，必须包含动机、手段、时机三要素 |
| `forbidden_to_reveal` | 真凶绝不能直接承认的关键词列表，触发即破案 |
| `knowledge` | 每个嫌疑人知道的信息，用于构建对话逻辑 |
| `related_suspect` | 证据关联的嫌疑人，出示时可针对性施压 |

---

## 游戏状态机

### 状态定义 (`core/interrogation.py`)

| 状态 | 说明 |
|------|------|
| `selecting` | 选择嫌疑人阶段 |
| `interrogating` | 审讯进行中 |
| `breakdown` | 破案成功（真凶崩溃） |
| `verdict` | 审讯结束（时间耗尽或玩家判定） |

### 状态转换

```
selecting ──选择嫌疑人──> interrogating
                              │
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
         breakdown        verdict         (循环审讯)
         (触发禁忌词)      (时间耗尽)
```

---

## 胜负判定

### 胜利条件 (`core/suspect_agent.py:115-116`)

当嫌疑人回复包含 `forbidden_to_reveal` 中的关键词时：
- 游戏状态变为 `breakdown`
- 显示："破案成功！真凶已经崩溃认罪。"

### 失败条件 (`core/interrogation.py:140-147`)

当倒计时归零时：
- 游戏状态变为 `verdict`
- 显示："时间耗尽！律师介入，案件被迫终止。"

---

## 存档系统

### 数据库表结构 (`core/db.py`)

**案件表 (cases)**
```sql
CREATE TABLE cases (
    case_id TEXT PRIMARY KEY,
    title TEXT,
    victim TEXT,
    cause_of_death TEXT,
    crime_scene TEXT,
    truth TEXT,
    suspects TEXT,  -- JSON
    evidence TEXT,  -- JSON
    interrogation_time_limit_sec INTEGER,
    created_at TEXT
)
```

**会话表 (sessions)**
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    case_id TEXT,
    state TEXT,
    current_suspect_index INTEGER,
    remaining_time REAL,
    suspect_states TEXT,  -- JSON
    shown_evidence_ids TEXT,  -- JSON
    memory TEXT,  -- JSON
    created_at TEXT,
    updated_at TEXT
)
```

### 存档流程 (`ui/web_main_window.py:507-525`)

1. 生成唯一 `session_id`（UUID）
2. 调用 `engine.to_dict()` 序列化游戏状态
3. 保存到数据库：`db.save_full_session()`

### 读档流程 (`ui/web_main_window.py:527-603`)

1. 显示存档列表：`db.list_sessions()`
2. 用户选择存档
3. 加载案件数据：`db.load_case()`
4. 重建引擎状态：`InterrogationEngine.from_dict()`
5. 恢复聊天记录：遍历 `memory` 重新渲染消息

---

## UI 交互流程

### 界面布局 (`ui/web/index.html`)

```
┌─────────────────────────────────────────────────────────────┐
│  [生成案件] [存档] [读档] [设置]           顶部导航栏        │
├──────────────┬────────────────────────────┬─────────────────┤
│              │                            │                 │
│  嫌疑人选择器 │        聊天对话区          │    证据列表     │
│  嫌疑人信息卡 │        消息列表            │    证据卡片     │
│  [施压][共情] │        输入框              │                 │
│              │        倒计时              │                 │
│   左侧面板   │         中央区域           │    右侧面板     │
└──────────────┴────────────────────────────┴─────────────────┘
```

### Python-JavaScript 通信 (`ui/web_bridge.py`)

**JavaScript → Python（槽方法）**
| 方法 | 功能 |
|------|------|
| `sendMessage(text)` | 发送玩家消息 |
| `selectSuspect(index)` | 选择嫌疑人 |
| `pressureSuspect()` | 施压操作 |
| `empathySuspect()` | 共情操作 |
| `showEvidence(evidenceId)` | 出示证据 |

**Python → JavaScript（信号）**
| 信号 | 功能 |
|------|------|
| `add_message(msg)` | 添加消息到聊天区 |
| `update_suspect(data)` | 更新嫌疑人状态 |
| `state_changed(state)` | 游戏状态变更 |
| `timer_tick(remaining)` | 计时器更新 |

---

## 事件系统 (`schemas/events.py`)

### 事件类型

| 事件 | 说明 |
|------|------|
| `NewMessageEvent` | 新消息（玩家/嫌疑人/系统） |
| `SuspectUpdateEvent` | 嫌疑人状态更新 |
| `StateChangeEvent` | 游戏状态变更 |
| `TimerTickEvent` | 计时器更新 |

---

## 关键文件索引

| 文件路径 | 主要功能 |
|---------|---------|
| `core/interrogation.py` | 审讯引擎核心逻辑 |
| `core/suspect_agent.py` | 嫌疑人 AI 代理 |
| `core/case_generator.py` | 案件生成 |
| `core/db.py` | 数据库存储 |
| `ui/web_main_window.py` | 主窗口逻辑 |
| `ui/web_bridge.py` | Python-JS 桥接 |
| `ui/web/js/app.js` | 前端主逻辑 |
| `ui/web/js/bridge.js` | 前端桥接 |
| `schemas/events.py` | 事件类型定义 |

---

## 当前玩法局限与改进方向

### 已有深度
- 自由对话允许玩家设计审讯策略
- 压力博弈提供施压与共情的节奏控制
- 证据出示时机影响审讯效果

### 潜在局限
1. **胜利条件单一**：仅依赖 `forbidden_to_reveal` 关键词触发
2. **嫌疑人行为不可控**：主要靠 LLM 生成，可预测性有限
3. **缺乏推理验证**：玩家猜对真相但未触发关键词不算赢
4. **案件差异性不足**：案件结构固定，缺乏多样性
5. **无评分系统**：没有表现评价或难度分级

### 可能的改进方向
- 丰富胜利/失败条件
- 增加嫌疑人行为多样性
- 添加推理验证机制
- 引入案件难度分级
- 添加评分/评级系统
