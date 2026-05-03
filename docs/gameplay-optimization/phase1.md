# Phase 1：基础重构 — 证据系统 + 供词层级

## 目标

解决"点完证据就赢"的核心问题，引入供词层级系统作为新的胜负判定基础。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 1.1 | 新增游戏配置模块 | `core/game_config.py` (新) | 小 |
| 1.2 | 重构证据出示链路 | `core/suspect_agent.py`, `core/interrogation.py`, `ui/web_main_window.py` | 中 |
| 1.3 | 证据使用次数限制 | `core/interrogation.py`, `ui/web/js/evidence.js` | 小 |
| 1.4 | 已出示证据 UI 标记 | `ui/web/js/evidence.js` | 小 |
| 1.5 | 供词层级系统 | `core/suspect_agent.py`, `schemas/events.py`, `core/interrogation.py` | 中 |
| 1.6 | 供词层级 UI | `ui/web/js/suspect.js`, `ui/web/index.html`, `ui/web/css/` | 中 |
| 1.7 | 修复静态系统提示词 | `core/suspect_agent.py` | 小 |
| 1.8 | 案件 Schema 扩展 | `core/case_generator.py` | 小 |
| 1.9 | 存档兼容 | `core/interrogation.py` | 小 |
| 1.10 | 测试 | `tests/` | 中 |

---

## 1.1 新增游戏配置模块

**文件**: `core/game_config.py` (新建)

**目的**: 将所有可调参数集中管理，避免硬编码，支持后续调整。

```python
"""Game configuration — all tunable parameters in one place."""

from typing import Dict, List, Any

# ──────────────────────────────────────────────
# 供词层级系统
# ──────────────────────────────────────────────

# 供词层级定义
CONFESSION_LEVELS = {
    0: {"name": "否认", "desc": "完全否认一切"},
    1: {"name": "动摇", "desc": "情绪波动，出现紧张、回避"},
    2: {"name": "部分承认", "desc": "承认部分事实，但隐瞒关键"},
    3: {"name": "关键突破", "desc": "透露动机/手段/时机之一"},
    4: {"name": "完全崩溃", "desc": "完整供述真相"},
}

# 供词层级升级阈值
# pressure: 需要达到的最低压力值
# min_turns: 需要的最低对话轮次
# requires_evidence: 是否需要出示过关联证据
# requires_semantic: 是否需要 LLM 语义判断（会增加 API 调用）
CONFESSION_THRESHOLDS: Dict[int, Dict[str, Any]] = {
    0: {"pressure": 40, "min_turns": 3, "requires_evidence": False, "requires_semantic": False},
    1: {"pressure": 60, "min_turns": 5, "requires_evidence": True, "requires_semantic": False},
    2: {"pressure": 75, "min_turns": 7, "requires_evidence": True, "requires_semantic": True},
    3: {"pressure": 90, "min_turns": 10, "requires_evidence": True, "requires_semantic": False},
}

# ──────────────────────────────────────────────
# 压力系统
# ──────────────────────────────────────────────

# 压力段定义
PRESSURE_SEGMENTS = {
    "low":    (0, 30),
    "medium": (30, 60),
    "high":   (60, 80),
    "panic":  (80, 100),
}

# 各压力段的供词进度增速（每次有效交互）
CONFESSION_PROGRESS_RATE = {
    "low":    0.02,
    "medium": 0.05,
    "high":   0.10,
    "panic":  0.15,
}

# ──────────────────────────────────────────────
# 证据系统
# ──────────────────────────────────────────────

# 默认证据出示次数（可在等级系统中覆盖）
DEFAULT_EVIDENCE_USES = 3

# 证据类型对压力的基础增量
EVIDENCE_PRESSURE_BASE = {
    "physical": 15,   # 物证：直接、难以否认
    "document": 10,   # 书证：间接但有力
    "testimony": 8,   # 证言：可反驳
}

# 证据强度系数（乘以基础增量）
EVIDENCE_STRENGTH_MULTIPLIER = 0.1  # strength 1-10，乘以 0.1 = 0.1-1.0

# ──────────────────────────────────────────────
# 经验与等级（Phase 3 完善，此处预留接口）
# ──────────────────────────────────────────────

# 经验曲线：索引=等级，值=该级所需累计经验
EXPERIENCE_CURVE: List[int] = [
    0, 50, 120, 200, 300, 450, 600, 800, 1050, 1350,
    1700, 2100, 2550, 3050, 3600, 4200, 4850, 5550, 6300, 7100,
]

# 等级解锁内容
LEVEL_UNLOCKS: Dict[int, Dict[str, Any]] = {
    1:  {"tools": [], "evidence_uses": 3, "desc": "基础审讯"},
    2:  {"tools": ["psych_profile"], "evidence_uses": 3, "desc": "心理侧写"},
    3:  {"tools": [], "evidence_uses": 4, "desc": "证据次数+1"},
    4:  {"tools": ["lie_detector"], "evidence_uses": 4, "desc": "测谎仪"},
    5:  {"tools": [], "evidence_uses": 4, "desc": "普通难度解锁"},
    6:  {"tools": ["fake_evidence"], "evidence_uses": 4, "desc": "伪造证据"},
    7:  {"tools": [], "evidence_uses": 5, "desc": "施压/共情效果+50%"},
    8:  {"tools": ["memory_recall"], "evidence_uses": 5, "desc": "记忆回溯"},
    9:  {"tools": [], "evidence_uses": 5, "desc": "证据次数+1"},
    10: {"tools": ["silent_pressure"], "evidence_uses": 5, "desc": "沉默施压，困难难度解锁"},
    11: {"tools": [], "evidence_uses": 5, "desc": "审讯时间+30秒"},
    12: {"tools": [], "evidence_uses": 6, "desc": "初始压力降低10"},
    13: {"tools": [], "evidence_uses": 6, "desc": "证据次数+1"},
    14: {"tools": ["threat"], "evidence_uses": 6, "desc": "威胁"},
    15: {"tools": ["dual_interrogation"], "evidence_uses": 6, "desc": "多人对质，噩梦难度解锁"},
    16: {"tools": [], "evidence_uses": 7, "desc": "审讯时间+30秒"},
    17: {"tools": [], "evidence_uses": 7, "desc": "证据次数+1"},
    18: {"tools": ["psych_collapse"], "evidence_uses": 7, "desc": "心理崩溃"},
    19: {"tools": [], "evidence_uses": 7, "desc": "初始压力再降10"},
    20: {"tools": [], "evidence_uses": 8, "desc": "审讯大师：所有工具次数+1"},
}

# ──────────────────────────────────────────────
# 难度分级（Phase 4 完善，此处预留接口）
# ──────────────────────────────────────────────

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "easy":      {"suspects": 2, "time": 360, "evidence_uses": 4, "keywords": 3},
    "normal":    {"suspects": "2-3", "time": 300, "evidence_uses": 3, "keywords": 2},
    "hard":      {"suspects": "3-4", "time": 240, "evidence_uses": 3, "keywords": 2},
    "nightmare": {"suspects": "4+", "time": 180, "evidence_uses": 2, "keywords": 1},
}
```

---

## 1.2 重构证据出示链路

### 问题

当前 `present_evidence` 时，`content = f"出示证据: {证据名}"`，证据名直接传入 LLM，导致 LLM 复述关键词触发胜利。

### 解决方案

**不再将证据名传入嫌疑人 prompt**，改为传入证据描述和类型。

### 1.2.1 修改 `core/suspect_agent.py` — 新增 `respond_evidence` 方法

在 `SuspectAgent` 类中新增方法，与现有 `respond()` 并列：

```python
def respond_evidence(
    self, evidence_description: str, evidence_type: str = "unknown"
) -> dict:
    """React to presented evidence without seeing the evidence name.

    Args:
        evidence_description: 证据描述（不含证据名）
        evidence_type: 证据类型 (physical/document/testimony/unknown)

    Returns:
        与 respond() 相同格式的 dict
    """
    result: Dict = {
        "reply": "",
        "pressure_change": 0,
        "secret_triggered": None,
        "rebuttal": False,
        "rebuttal_believable": None,
    }

    if not llm_client.is_initialized:
        result["reply"] = "（嫌疑人沉默不语）"
        return result

    # 构建证据专用的用户消息（不含证据名）
    evidence_prompt = (
        f"审讯员向你出示了一件{evidence_type}证据。\n"
        f"证据内容：{evidence_description}\n\n"
        "请根据你的角色和所知信息，对这件证据做出反应。"
    )

    # 使用与 respond() 相同的消息构建逻辑
    messages = [{"role": "system", "content": self._system_prompt}]
    messages.extend(self.memory[-10:])
    messages.append({"role": "user", "content": evidence_prompt})

    try:
        raw = llm_client.chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
        )
        if not raw:
            raise LLMResponseError("LLM 返回空内容")
        text = raw.strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        parsed = json.loads(text)
        result["reply"] = str(parsed.get("reply", ""))
        result["pressure_change"] = int(parsed.get("pressure_change", 0))
        result["secret_triggered"] = parsed.get("secret_triggered")
    except (NetworkError, LLMResponseError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"LLM 调用或解析失败: {exc}")
        result["reply"] = "（嫌疑人沉默不语）"

    self._postprocess(result)
    self.pressure = max(0, min(100, self.pressure + result["pressure_change"]))
    self._append_memory(evidence_prompt, result["reply"])
    self.truncate_memory()

    return result
```

**关键区别**：
- 用户消息不包含证据名称，只包含证据描述和类型
- 与 `respond()` 共用 `_system_prompt`、`_postprocess`、memory 管理
- 返回格式与 `respond()` 一致

### 1.2.2 修改 `core/interrogation.py` — 重构 `present_evidence` 分支

**当前代码** (`interrogation.py:78-92`):
```python
if action == "present_evidence":
    evidence = self._find_evidence(evidence_id)
    if evidence is None:
        # ... 错误处理
        return events
    result = suspect.respond(content)          # ← 问题：传入了证据名
    if evidence.get("related_suspect") == suspect.name:
        suspect.pressure = max(0, min(100, suspect.pressure + 20))  # ← 硬编码 +20
        self.presented_evidence_ids.add(evidence_id)
```

**改为**:
```python
if action == "present_evidence":
    evidence = self._find_evidence(evidence_id)
    if evidence is None:
        system_msg: NewMessageEvent = {
            "type": "new_message",
            "role": "system",
            "content": f"证据 {evidence_id} 不存在。",
            "suspect_name": None,
        }
        events.append(system_msg)
        return events

    # 检查证据使用次数
    if self.evidence_uses_remaining <= 0:
        system_msg: NewMessageEvent = {
            "type": "new_message",
            "role": "system",
            "content": "证据出示次数已耗尽。",
            "suspect_name": None,
        }
        events.append(system_msg)
        return events

    # 调用 respond_evidence（不传证据名，只传描述）
    evidence_desc = evidence.get("description", "")
    evidence_type = evidence.get("type", "unknown")
    result = suspect.respond_evidence(evidence_desc, evidence_type)

    # 根据证据类型和强度计算压力增量（取代硬编码 +20）
    if evidence.get("related_suspect") == suspect.name:
        from core.game_config import EVIDENCE_PRESSURE_BASE, EVIDENCE_STRENGTH_MULTIPLIER
        base = EVIDENCE_PRESSURE_BASE.get(evidence_type, 10)
        strength = evidence.get("strength", 5)
        pressure_delta = int(base * (1 + strength * EVIDENCE_STRENGTH_MULTIPLIER))
        suspect.pressure = max(0, min(100, suspect.pressure + pressure_delta))
        self.presented_evidence_ids.add(evidence_id)

    # 扣减证据使用次数
    self.evidence_uses_remaining -= 1
```

### 1.2.3 修改 `ui/web_main_window.py` — `_on_evidence_selected`

**当前代码** (L290-305):
```python
def _on_evidence_selected(self, evidence_id):
    evidence = self.engine.get_evidence(evidence_id)
    evidence_name = evidence.get("name", evidence_id) if evidence else evidence_id
    self._start_worker("present_evidence", f"出示证据: {evidence_name}", evidence_id=evidence_id)
```

**改为**:
```python
def _on_evidence_selected(self, evidence_id):
    if self.engine is None:
        return

    # 检查剩余次数
    if self.engine.evidence_uses_remaining <= 0:
        self.bridge.show_dialog.emit("提示", "证据出示次数已耗尽")
        return

    evidence = self.engine.get_evidence(evidence_id)
    # 检查是否已出示
    if evidence_id in self.engine.presented_evidence_ids:
        self.bridge.show_dialog.emit("提示", "该证据已出示过")
        return

    evidence_name = evidence.get("name", evidence_id) if evidence else evidence_id
    self._start_worker(
        "present_evidence",
        f"出示证据: {evidence_name}",
        evidence_id=evidence_id,
    )
```

---

## 1.3 证据使用次数限制

### 引擎层

**修改 `core/interrogation.py` — `__init__`**:

```python
def __init__(self, case_data: dict) -> None:
    self.case: dict = case_data
    self.suspects: List[SuspectAgent] = [
        SuspectAgent(s, case_data["title"]) for s in case_data["suspects"]
    ]
    self.current_suspect_index: int = 0
    self.presented_evidence_ids: set = set()
    self.time_left: int = case_data["interrogation_time_limit_sec"]
    self.state: str = "selecting"

    # 新增：证据使用次数
    from core.game_config import DEFAULT_EVIDENCE_USES
    self.evidence_uses_remaining: int = case_data.get(
        "evidence_uses", DEFAULT_EVIDENCE_USES
    )
```

### 前端层

**修改 `ui/web/js/evidence.js`**:

在 `EvidenceManager` 类中新增：

```javascript
// 新增属性
constructor() {
    this.listEl = document.getElementById('evidence-list');
    this.emptyEl = document.getElementById('evidence-empty');
    this.evidences = [];
    this.usesRemaining = 3;  // 新增
    this.presentedIds = new Set();  // 新增
}

// 新增方法：更新剩余次数显示
updateUsesRemaining(remaining) {
    this.usesRemaining = remaining;
    const counterEl = document.getElementById('evidence-uses-count');
    if (counterEl) {
        counterEl.textContent = `剩余次数: ${remaining}`;
        counterEl.className = 'evidence-uses-count' + (remaining <= 1 ? ' warning' : '');
    }
    // 次数耗尽时禁用所有未出示的证据卡
    if (remaining <= 0) {
        this.listEl.querySelectorAll('.evidence-card:not(.presented)').forEach(card => {
            card.classList.add('disabled');
        });
    }
}

// 新增方法：标记已出示
markPresented(evidenceId) {
    this.presentedIds.add(evidenceId);
    const card = this.listEl.querySelector(`[data-evidence-id="${evidenceId}"]`);
    if (card) {
        card.classList.add('presented');
        card.classList.remove('card-hoverable');
    }
}
```

**修改 `_onEvidenceClick`**: 在出示成功后调用 `markPresented`。

**修改 `_addEvidenceCard`**: 如果 `presentedIds` 包含该证据，添加 `presented` 类。

---

## 1.4 已出示证据 UI 标记

**修改 `ui/web/css/components.css`** (或 `style.css`):

```css
/* 已出示证据 */
.evidence-card.presented {
    opacity: 0.5;
    position: relative;
    cursor: default;
}

.evidence-card.presented::after {
    content: '✓';
    position: absolute;
    top: 8px;
    right: 8px;
    background: var(--color-success);
    color: white;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
}

/* 禁用状态（次数耗尽） */
.evidence-card.disabled {
    opacity: 0.3;
    cursor: not-allowed;
    pointer-events: none;
}

/* 次数警告 */
.evidence-uses-count.warning {
    color: var(--color-danger);
    font-weight: bold;
}
```

---

## 1.5 供词层级系统

### 1.5.1 新增事件类型

**修改 `schemas/events.py`**:

```python
class ConfessionUpdateEvent(TypedDict):
    type: Literal["confession_update"]
    suspect_index: int
    confession_level: int
    confession_progress: float
    level_name: str

# 更新 UIEvent 联合类型
UIEvent = Union[
    NewMessageEvent,
    SuspectUpdateEvent,
    StateChangeEvent,
    TimerTickEvent,
    ConfessionUpdateEvent,  # 新增
]
```

### 1.5.2 修改 `core/suspect_agent.py` — 新增供词属性

在 `__init__` 中新增:
```python
self.confession_level: int = 0       # 当前供词层级 (0-4)
self.confession_progress: float = 0.0  # 当前层级进度 (0.0-1.0)
self.turn_count: int = 0             # 对话轮次计数
```

### 1.5.3 新增供词判定方法

在 `SuspectAgent` 中新增:
```python
def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
    """检查是否满足供词升级条件，返回升级后的层级或 None。

    Args:
        has_evidence: 是否已出示过关联证据

    Returns:
        升级后的层级，或 None（不升级）
    """
    from core.game_config import CONFESSION_THRESHOLDS, CONFESSION_PROGRESS_RATE, PRESSURE_SEGMENTS

    if self.confession_level >= 4:
        return None

    next_level = self.confession_level + 1
    threshold = CONFESSION_THRESHOLDS.get(self.confession_level, {})

    # 检查压力条件
    required_pressure = threshold.get("pressure", 100)
    if self.pressure < required_pressure:
        return None

    # 检查轮次条件
    min_turns = threshold.get("min_turns", 0)
    if self.turn_count < min_turns:
        return None

    # 检查证据条件
    if threshold.get("requires_evidence", False) and not has_evidence:
        return None

    # 所有条件满足，升级
    self.confession_level = next_level
    self.confession_progress = 0.0
    return next_level

def update_confession_progress(self) -> float:
    """根据当前压力更新供词进度，返回更新后的进度值。"""
    from core.game_config import CONFESSION_PROGRESS_RATE, PRESSURE_SEGMENTS

    if self.confession_level >= 4:
        return 1.0

    # 确定当前压力段
    rate = 0.02  # 默认
    for seg_name, (low, high) in PRESSURE_SEGMENTS.items():
        if low <= self.pressure < high:
            rate = CONFESSION_PROGRESS_RATE.get(seg_name, 0.02)
            break

    self.confession_progress = min(1.0, self.confession_progress + rate)
    return self.confession_progress
```

### 1.5.4 修改 `core/interrogation.py` — 在 `submit_action` 中追踪供词

在 `submit_action` 的 `present_evidence` 和 `else` 分支之后，添加供词判定逻辑：

```python
# ── 供词进度更新 ──
suspect.turn_count += 1
has_evidence = any(
    self._find_evidence(eid).get("related_suspect") == suspect.name
    for eid in self.presented_evidence_ids
    if self._find_evidence(eid) is not None
)
old_level = suspect.confession_level
suspect.update_confession_progress()
new_level = suspect.check_confession_upgrade(has_evidence)

if new_level is not None and new_level > old_level:
    confession_event: ConfessionUpdateEvent = {
        "type": "confession_update",
        "suspect_index": self.current_suspect_index,
        "confession_level": new_level,
        "confession_progress": 0.0,
        "level_name": CONFESSION_LEVELS[new_level]["name"],
    }
    events.append(confession_event)

    # 供词层级达到 4 时触发完美胜利
    if new_level == 4:
        self.state = "breakdown"
        state_event: StateChangeEvent = {
            "type": "state_change",
            "new_state": "breakdown",
            "verdict_reason": f"{suspect.name} 完全崩溃认罪",
        }
        events.append(state_event)
```

### 1.5.5 修改 `to_dict` / `from_dict`

在 `suspects_states` 中新增字段：
```python
# to_dict 中:
{
    "name": suspect.name,
    "pressure": suspect.pressure,
    "memory": suspect.memory,
    "confession_level": suspect.confession_level,        # 新增
    "confession_progress": suspect.confession_progress,  # 新增
    "turn_count": suspect.turn_count,                    # 新增
}

# from_dict 中:
engine.suspects[i].confession_level = suspect_state.get("confession_level", 0)
engine.suspects[i].confession_progress = suspect_state.get("confession_progress", 0.0)
engine.suspects[i].turn_count = suspect_state.get("turn_count", 0)
```

新增 `evidence_uses_remaining` 的序列化：
```python
# to_dict 中:
"evidence_uses_remaining": self.evidence_uses_remaining,

# from_dict 中:
engine.evidence_uses_remaining = state.get("evidence_uses_remaining", DEFAULT_EVIDENCE_USES)
```

---

## 1.6 供词层级 UI

### 1.6.1 修改 `ui/web/index.html` — 在嫌疑人卡片中新增供词区域

在 `<div class="suspect-pressure-section">` 之后，`<div class="action-buttons">` 之前，插入：

```html
<div class="confession-section">
    <div class="confession-label">
        <span class="confession-title">供词层级</span>
        <span class="confession-level-name" id="confession-level-name">否认</span>
    </div>
    <div class="confession-bar-container">
        <div class="confession-bar" id="confession-bar" style="width: 0%;"></div>
    </div>
    <div class="confession-steps">
        <span class="confession-step active" data-level="0">否认</span>
        <span class="confession-step" data-level="1">动摇</span>
        <span class="confession-step" data-level="2">承认</span>
        <span class="confession-step" data-level="3">突破</span>
        <span class="confession-step" data-level="4">崩溃</span>
    </div>
</div>
```

### 1.6.2 新增信号

**修改 `ui/web_bridge.py`**:

```python
# Python → JS 新增信号
confession_update = Signal(int, int, float)  # suspect_index, level, progress
```

**修改 `ui/web/js/bridge.js`** — 在 `_setupSignalListeners` 中添加:
```javascript
this._qtObject.confessionUpdate.connect((suspectIndex, level, progress) => {
    this._trigger('confessionUpdate', { suspectIndex, level, progress });
});
```

### 1.6.3 修改 `ui/web/js/suspect.js` — 新增供词更新方法

```javascript
updateConfession(level, progress) {
    // 更新层级名称
    const levelNames = ['否认', '动摇', '部分承认', '关键突破', '完全崩溃'];
    const nameEl = document.getElementById('confession-level-name');
    if (nameEl) {
        nameEl.textContent = levelNames[level] || '未知';
    }

    // 更新进度条
    const barEl = document.getElementById('confession-bar');
    if (barEl) {
        // 每层 25% 的宽度，加上当前层内的进度
        const totalProgress = (level * 25) + (progress * 25);
        barEl.style.width = Math.min(100, totalProgress) + '%';
    }

    // 更新步骤指示器
    const steps = document.querySelectorAll('.confession-step');
    steps.forEach((step, i) => {
        step.classList.toggle('active', i <= level);
        step.classList.toggle('current', i === level);
    });
}
```

### 1.6.4 供词样式

**在 `ui/web/css/` 中新增样式**:

```css
.confession-section {
    padding: var(--space-3);
    border-top: 1px solid var(--color-border);
}

.confession-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
}

.confession-title {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
}

.confession-level-name {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-primary);
}

.confession-bar-container {
    height: 6px;
    background: var(--color-bg-secondary);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: var(--space-2);
}

.confession-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--color-success), var(--color-warning), var(--color-danger));
    transition: width 0.3s ease;
    border-radius: 3px;
}

.confession-steps {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--color-text-tertiary);
}

.confession-step.active {
    color: var(--color-primary);
    font-weight: 600;
}

.confession-step.current {
    color: var(--color-danger);
}
```

---

## 1.7 修复静态系统提示词

### 问题

`_build_system_prompt` 在 `__init__` 时调用一次，压力值固定为 50，后续不更新。

### 解决方案

将系统提示词中的压力值部分改为**每次 `respond()` 时动态注入**，而非在 `__init__` 时固定。

**修改 `core/suspect_agent.py`**:

1. `_build_system_prompt` 中移除压力值部分，改为占位符 `{pressure_placeholder}`
2. 在 `respond()` 和 `respond_evidence()` 中，构建 messages 时替换占位符

```python
def _build_system_prompt(self, suspect_data: dict, case_title: str) -> str:
    # ... 现有代码 ...
    prompt = (
        # ... 其他部分不变 ...
        f"## 当前压力值：{{pressure_value}}/100\n"  # ← 使用占位符
        "压力值说明：压力越高，你越慌乱，可能语无伦次、答非所问，"
        "但仍然不能直接说出禁止内容。压力低时你表现得冷静、从容。\n\n"
        # ...
    )
    return prompt

def _get_system_message(self) -> dict:
    """构建带有当前压力值的系统消息。"""
    prompt = self._system_prompt.replace("{pressure_value}", str(self.pressure))
    return {"role": "system", "content": prompt}

# 在 respond() 和 respond_evidence() 中：
# 将 messages = [{"role": "system", "content": self._system_prompt}]
# 改为 messages = [self._get_system_message()]
```

---

## 1.8 案件 Schema 扩展

**修改 `core/case_generator.py`**:

在 `CASE_SCHEMA` 的 `evidences.items.properties` 中新增字段：

```python
"evidences": {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "name", "description"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "related_suspect": {"type": ["string", "null"]},
            # 新增字段（可选，向后兼容）
            "type": {
                "type": "string",
                "enum": ["physical", "document", "testimony"],
                "default": "physical",
            },
            "strength": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
            },
        },
        "additionalProperties": False,
    },
},
```

修改生成提示词，在 evidences 部分增加：
```
"type": "字符串，证据类型：physical(物证)/document(书证)/testimony(证言)",
"strength": "整数1-10，证据强度，10为最强",
```

---

## 1.9 存档兼容

`to_dict()` / `from_dict()` 需要向后兼容旧存档（没有新字段时使用默认值）。

已在 1.5.4 中通过 `.get("field", default)` 实现。

---

## 1.10 测试计划

### 单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `tests/test_confession.py` (新) | 供词层级升级逻辑、进度更新 |
| `tests/test_evidence_rework.py` (新) | respond_evidence 不传证据名、证据次数限制 |
| `tests/test_game_config.py` (新) | 配置值正确性 |

### 集成测试

| 测试 | 说明 |
|------|------|
| 证据出示不触发自动胜利 | 出示含关键词证据后，游戏状态仍为 interrogating |
| 证据次数耗尽后无法出示 | 尝试出示应返回系统消息 |
| 供词层级递进 | 模拟高压+多轮对话，验证层级升级 |
| 存档/读档兼容 | 新字段序列化/反序列化正确 |

### 回归测试

| 测试 | 说明 |
|------|------|
| 现有 `test_engine.py` 通过 | 确保不破坏现有逻辑 |
| 现有 `test_suspect.py` 通过 | respond() 行为不变 |
| 现有 `test_web_integration.py` 通过 | UI 事件流正常 |

---

## 实施顺序建议

```
1.1 game_config.py（无依赖，先建）
    ↓
1.2 respond_evidence + 引擎重构（核心改动）
    ↓
1.7 修复静态提示词（与 1.2 同步做）
    ↓
1.3 证据次数限制（依赖 1.2）
    ↓
1.4 已出示标记（依赖 1.3）
    ↓
1.8 Schema 扩展（独立，可并行）
    ↓
1.5 供词层级系统（依赖 1.2）
    ↓
1.6 供词 UI（依赖 1.5）
    ↓
1.9 存档兼容（依赖 1.2 + 1.5）
    ↓
1.10 测试（最后）
```
