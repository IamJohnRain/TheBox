# Phase 1：基础重构 — 证据系统 + 供词层级（优化版 v1.1）

> **评审变更**：修复P0 `_postprocess`冲突、抽取`_call_llm()`、统一胜利入口`_check_victory()`、压力程序化计算、移除`requires_semantic`、game_config分阶段配置

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
| 1.9 | 存档兼容 | `core/interrogation.py`, `core/suspect_agent.py` | 小 |
| 1.10 | 测试 | `tests/` | 中 |

---

## 1.1 新增游戏配置模块

**文件**: `core/game_config.py` (新建)

**目的**: 将所有可调参数集中管理，避免硬编码，支持后续调整。**Phase 1 只放置 Phase 1 需要的配置**，后续 Phase 配置按阶段添加。

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
CONFESSION_THRESHOLDS: Dict[int, Dict[str, Any]] = {
    0: {"pressure": 40, "min_turns": 3, "requires_evidence": False},
    1: {"pressure": 60, "min_turns": 5, "requires_evidence": True},
    2: {"pressure": 75, "min_turns": 7, "requires_evidence": True},
    3: {"pressure": 90, "min_turns": 10, "requires_evidence": True},
}
# NOTE: requires_semantic 标志在 Phase 1 中暂不实现，Phase 2 再引入语义匹配

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
# Phase 2+ 配置预留（此处声明类型，值在对应 Phase 添加）
# ──────────────────────────────────────────────

# REBUTTAL_DECAY_CONFIG: Dict[str, Any] = {}  # Phase 2
# CHAIN_BONUS: int = 10  # Phase 2
# TOOL_DEFINITIONS: Dict[str, Dict] = {}  # Phase 3a
# LEVEL_UNLOCKS: Dict[int, Dict] = {}  # Phase 3b
# EXPERIENCE_CURVE: List[int] = []  # Phase 3b
# DIFFICULTY_PRESETS: Dict[str, Dict] = {}  # Phase 4
```

---

## 1.2 重构证据出示链路

### 问题

当前 `present_evidence` 时，`content = f"出示证据: {证据名}"`，证据名直接传入 LLM，导致 LLM 复述关键词触发胜利。

### 解决方案

**不再将证据名传入嫌疑人 prompt**，改为传入证据描述和类型。压力增量由引擎**程序化计算**，LLM 不再返回 `pressure_change`。

### 1.2.1 修改 `core/suspect_agent.py` — 抽取公共 LLM 调用方法

**新增 `_call_llm` 方法**，消除 `respond()` 与 `respond_evidence()` 的代码重复：

```python
def _call_llm(self, user_prompt: str) -> dict:
    """调用 LLM 并解析 JSON 回复。

    Args:
        user_prompt: 用户消息内容

    Returns:
        包含 reply, secret_triggered 的字典
    """
    result = {
        "reply": "",
        "secret_triggered": None,
    }

    if not llm_client.is_initialized:
        result["reply"] = "（嫌疑人沉默不语）"
        return result

    messages = [self._get_system_message()]
    messages.extend(self.memory[-10:])
    messages.append({"role": "user", "content": user_prompt})

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
        result["secret_triggered"] = parsed.get("secret_triggered")
    except (NetworkError, LLMResponseError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"LLM 调用或解析失败: {exc}")
        result["reply"] = "（嫌疑人沉默不语）"

    return result
```

### 1.2.2 修改 `core/suspect_agent.py` — 改造 `respond()`

```python
def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
    """Process player input and return a reply with secret status."""
    result = self._call_llm(player_input)

    # 压力变化由引擎程序化计算，此处不再处理 pressure_change
    self._postprocess(result)
    self._append_memory(player_input, result["reply"])
    self.truncate_memory()

    logger.debug(
        f"嫌疑人[{self.name}]回复: {result['reply'][:100]}, secret_triggered={result.get('secret_triggered')}"
    )
    return result
```

### 1.2.3 修改 `core/suspect_agent.py` — 新增 `respond_evidence` 方法

```python
def respond_evidence(
    self, evidence_description: str, evidence_type: str = "unknown"
) -> dict:
    """React to presented evidence without seeing the evidence name.

    Args:
        evidence_description: 证据描述（不含证据名）
        evidence_type: 证据类型 (physical/document/testimony/unknown)

    Returns:
        包含 reply, secret_triggered 的字典
        （注意：不再返回 pressure_change，压力由引擎程序化计算）
    """
    evidence_prompt = (
        f"审讯员向你出示了一件{evidence_type}证据。\n"
        f"证据内容：{evidence_description}\n\n"
        "请根据你的角色和所知信息，对这件证据做出反应。"
    )

    result = self._call_llm(evidence_prompt)
    self._postprocess(result)
    self._append_memory(evidence_prompt, result["reply"])
    self.truncate_memory()

    return result
```

**关键区别**：
- 用户消息不包含证据名称，只包含证据描述和类型
- 共用 `_call_llm`、`_postprocess`、memory 管理
- **不再返回 `pressure_change`**，压力增量完全由引擎程序化计算
- 返回格式为 `{"reply": str, "secret_triggered": Optional[str]}`

### 1.2.4 修改 `core/suspect_agent.py` — 改造 `_postprocess`

**关键修改**：`_postprocess` 与供词系统联动，低供词层级时不触发胜利。

```python
def _postprocess(self, result: dict) -> None:
    """Check reply for forbidden substrings and sanitize if matched.

    与供词系统联动：
    - 供词层级 < 3：替换回复但不触发胜利（仅增加压力）
    - 供词层级 >= 3：允许触发胜利（完美胜利条件）
    """
    reply_lower = result["reply"].lower()
    for item in self._forbidden_to_reveal:
        if item.lower() in reply_lower:
            if self.confession_level >= 3:
                # 高供词层级：允许触发完整胜利
                logger.info(f"角色 [{self.name}] 高供词层级下泄露禁止内容: {item}")
                result["secret_triggered"] = item
                result["pressure_change"] = 20
            else:
                # 低供词层级：替换回复但不触发胜利
                logger.info(f"角色 [{self.name}] 低供词层级下提及禁止内容，已拦截: {item}")
                result["reply"] = "（对方略显紧张，但并没有直接回答你的问题。）"
                result["pressure_change"] = 10
                result["secret_triggered"] = None
            return
```

### 1.2.5 修改 `core/interrogation.py` — 重构 `present_evidence` 分支

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

    # 压力增量由引擎程序化计算（取代硬编码 +20 和 LLM 返回的 pressure_change）
    pressure_delta = 0
    if evidence.get("related_suspect") == suspect.name:
        from core.game_config import EVIDENCE_PRESSURE_BASE, EVIDENCE_STRENGTH_MULTIPLIER
        base = EVIDENCE_PRESSURE_BASE.get(evidence_type, 10)
        strength = evidence.get("strength", 5)
        pressure_delta = int(base * (1 + strength * EVIDENCE_STRENGTH_MULTIPLIER))
        self.presented_evidence_ids.add(evidence_id)

    old_pressure = suspect.pressure
    suspect.pressure = max(0, min(100, suspect.pressure + pressure_delta))
    actual_pressure_change = suspect.pressure - old_pressure

    # 扣减证据使用次数
    self.evidence_uses_remaining -= 1
```

### 1.2.6 修改 `core/interrogation.py` — 统一胜利判定入口

**新增 `_check_victory` 方法**：

```python
def _check_victory(self, suspect, result: dict) -> Optional[StateChangeEvent]:
    """统一检查所有胜利条件。

    胜利条件优先级：
    1. 供词层级达到 4：完全崩溃（主要胜利条件）
    2. secret_triggered 且供词层级 >= 3：完美胜利（关键词触发）
    3. 时间耗尽：失败

    Returns:
        StateChangeEvent 或 None
    """
    # 条件1：供词层级 4
    if suspect.confession_level >= 4 and self.state != "breakdown":
        self.state = "breakdown"
        return StateChangeEvent(
            type="state_change",
            new_state="breakdown",
            verdict_reason=f"{suspect.name} 完全崩溃认罪",
        )

    # 条件2：secret_triggered + 高供词层级
    if result.get("secret_triggered") and suspect.confession_level >= 3:
        self.state = "breakdown"
        return StateChangeEvent(
            type="state_change",
            new_state="breakdown",
            verdict_reason=f"{suspect.name} 泄露了秘密: {result['secret_triggered']}",
        )

    return None
```

在 `submit_action` 末尾调用 `_check_victory` 替代原有的分散判定。

### 1.2.7 修改 `ui/web_main_window.py` — `_on_evidence_selected`

**当前代码** (L332-347):
```python
def _on_evidence_selected(self, evidence_id):
    evidence = self.engine.get_evidence(evidence_id)
    evidence_name = evidence.get("name", evidence_id) if evidence else evidence_id
    self._start_worker("present_evidence", f"出示证据: {evidence_name}", evidence_id=evidence_id)
```

**改为**:
```python
def _on_evidence_selected(self, evidence_id):
    logger.debug(f"用户出示证据: {evidence_id}")
    if self.engine is None:
        return

    # 检查剩余次数
    if self.engine.evidence_uses_remaining <= 0:
        self.bridge.show_dialog.emit("提示", "证据出示次数已耗尽")
        return

    # 检查是否已出示
    if evidence_id in self.engine.presented_evidence_ids:
        self.bridge.show_dialog.emit("提示", "该证据已出示过")
        return

    evidence = self.engine.get_evidence(evidence_id)
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
    from core.game_config import CONFESSION_THRESHOLDS

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
    from core.game_config import CONFESSION_LEVELS
    confession_event: ConfessionUpdateEvent = {
        "type": "confession_update",
        "suspect_index": self.current_suspect_index,
        "confession_level": new_level,
        "confession_progress": 0.0,
        "level_name": CONFESSION_LEVELS[new_level]["name"],
    }
    events.append(confession_event)

# ── 统一胜利判定 ──
victory_event = self._check_victory(suspect, result)
if victory_event:
    events.append(victory_event)
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
        // 每层 20% 的宽度，加上当前层内的进度
        const totalProgress = (level * 20) + (progress * 20);
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

将系统提示词中的压力值部分改为**每次调用时动态注入**，而非在 `__init__` 时固定。

**修改 `core/suspect_agent.py`**:

1. `_build_system_prompt` 中移除压力值部分，改为占位符 `{pressure_value}`
2. 在 `_get_system_message()` 中替换占位符

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
```

`_call_llm` 中已经使用 `self._get_system_message()`，无需额外修改。

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

已在 1.5.5 中通过 `.get("field", default)` 实现。

**特别注意**：
- `SuspectAgent.__init__` 中的新字段（`confession_level`, `confession_progress`, `turn_count`）已设置默认值
- `InterrogationEngine.__init__` 中的 `evidence_uses_remaining` 已使用 `case_data.get("evidence_uses", DEFAULT_EVIDENCE_USES)`
- 旧存档加载时，缺失的新字段会自动使用默认值

---

## 1.10 测试计划

### 单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `tests/test_confession.py` (新) | 供词层级升级逻辑、进度更新、阈值边界条件 |
| `tests/test_evidence_rework.py` (新) | respond_evidence 不传证据名、证据次数限制、压力程序化计算 |
| `tests/test_game_config.py` (新) | 配置值正确性、默认值 |
| `tests/test_victory_conditions.py` (新) | `_check_victory` 各条件优先级、低供词层级拦截、高供词层级触发 |

### 集成测试

| 测试 | 说明 |
|------|------|
| 证据出示不触发自动胜利 | 出示含关键词证据后，`_postprocess` 应拦截（低供词层级） |
| 证据次数耗尽后无法出示 | 尝试出示应返回系统消息 |
| 供词层级递进 | 模拟高压+多轮对话，验证层级升级 |
| 存档/读档兼容 | 新字段序列化/反序列化正确，旧存档加载不崩溃 |
| 压力动态更新 | 验证 `_get_system_message` 使用当前压力值 |

### 回归测试

| 测试 | 说明 |
|------|------|
| 现有 `test_engine.py` 通过 | 确保不破坏现有逻辑 |
| 现有 `test_suspect.py` 通过 | `respond()` 行为不变（除 pressure_change 不再返回） |
| 现有 `test_web_integration.py` 通过 | UI 事件流正常 |

---

## 实施顺序建议

```
1.1  game_config.py（无依赖，先建，只放Phase 1配置）
    ↓
1.2  _call_llm 抽取 + _get_system_message 动态化（基础改造）
    ↓
1.7  修复静态提示词（与 1.2 同步做）
    ↓
1.2  respond_evidence + 引擎重构（核心改动）
    ↓
1.2  _postprocess 联动改造 + _check_victory 统一入口（P0修复）
    ↓
1.3  证据次数限制（依赖 1.2）
    ↓
1.4  已出示标记（依赖 1.3）
    ↓
1.8  Schema 扩展（独立，可并行）
    ↓
1.5  供词层级系统（依赖 1.2 + _check_victory）
    ↓
1.6  供词 UI（依赖 1.5）
    ↓
1.9  存档兼容（依赖 1.2 + 1.5）
    ↓
1.10 测试（最后）
```

---

## Phase 1 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.1 优化方案 | 原因 |
|--------|------------|--------------|------|
| `_postprocess` | 原样保留，触发即胜利 | 低供词层级拦截，>=3才触发 | P0：防止绕过供词系统 |
| 压力来源 | LLM返回`pressure_change`+引擎硬编码+20 | 引擎程序化计算，LLM不返回 | P1：避免双重计算 |
| `respond()`/`respond_evidence()` | 各30行重复代码 | 抽取`_call_llm()`公共方法 | P1：消除代码重复 |
| 胜利判定 | 分散在`submit_action`中 | 统一`_check_victory()`入口 | P1：避免双重判定 |
| `requires_semantic` | 定义在阈值中但无实现 | Phase 1移除，Phase 2实现 | P1：避免未完成的功能 |
| `game_config.py` | 包含Phase 1-4所有配置 | 仅Phase 1配置，后续分阶段添加 | P2：减少早期测试负担 |

(End of file - total 643 lines)
