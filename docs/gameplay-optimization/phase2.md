# Phase 2：审讯深度 — 反驳机制 + 压力增强 + 证据链 + 时间-压力动态 + 错误惩罚（优化版 v1.2）

> **评审变更**：修复P0主动开口线程阻塞（改为轮次触发+异步）、反驳增加程序化兜底、证据链奖励配置化、高压行为指令动态注入  
> **v1.2 变更**：新增时间-压力双向动态关系、错误惩罚机制（mistake_log评分联动）、维度指标对反驳/共情的影响

## 前置依赖

Phase 1 完成（供词层级、证据系统重构、统一胜利入口 `_check_victory`）。

## 目标

增加审讯的策略深度：嫌疑人会主动反驳证据，压力值产生程序化效果，证据之间可以形成证据链，时间与压力双向动态关系，错误操作有惩罚。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 2.1 | 嫌疑人反驳机制 | `core/suspect_agent.py` | 中 |
| 2.2 | 反驳事件与 UI | `schemas/events.py`, `ui/web_bridge.py`, `ui/web/js/`, `ui/web_main_window.py` | 中 |
| 2.3 | 压力程序化效果 | `core/suspect_agent.py`, `core/interrogation.py` | 中 |
| 2.4 | 证据链机制 | `core/interrogation.py`, `core/case_generator.py`, `core/game_config.py` | 小 |
| 2.5 | 嫌疑人主动开口 | `core/interrogation.py`, `ui/web_main_window.py` | 中 |
| 2.6 | 时间-压力双向动态 | `core/interrogation.py`, `core/game_config.py` | 中 |
| 2.7 | 错误惩罚机制 | `core/interrogation.py`, `schemas/events.py`, `ui/web/` | 中 |
| 2.8 | 测试 | `tests/` | 中 |

---

## 2.1 嫌疑人反驳机制

### 设计

出示证据时，嫌疑人会尝试用 `knowledge` 中的信息进行反驳。反驳是否可信由 LLM 判断 + 程序化兜底。

### 修改 `core/suspect_agent.py` — `respond_evidence` 返回值扩展

在 Phase 1 的 `respond_evidence` 基础上，修改 LLM 的 JSON 输出要求：

**系统提示词中新增（在 respond_evidence 的 user prompt 中）**：
```
请以 JSON 格式回复：
- "reply": 你的回复文本（1-3句话）
- "secret_triggered": 如提到禁止内容则填写，否则为null
- "rebuttal": true/false，你是否尝试反驳这件证据
- "rebuttal_believable": true/false，如果你在反驳，你认为你的反驳是否可信
```

**反驳可信度受压力影响** — 在 prompt 中注入：
```
注意：你当前的压力值是 {pressure}/100。
- 压力低于30时，你可以从容反驳
- 压力在30-60时，你的反驳可能有漏洞
- 压力高于60时，你的反驳难以令人信服
- 压力高于80时，你几乎无法有效反驳
```

### 反驳结果处理（增加程序化兜底）

在 `InterrogationEngine.submit_action` 的 `present_evidence` 分支中：

```python
result = suspect.respond_evidence(evidence_desc, evidence_type)

# 反驳机制处理（LLM判断 + 程序化兜底）
rebuttal = result.get("rebuttal", False)
rebuttal_believable = result.get("rebuttal_believable", False)

# 程序化兜底：高压时反驳可信度强制衰减
if rebuttal and rebuttal_believable:
    # deception_skill 影响反驳阈值：欺骗技巧高的人更难被程序化否决
    effective_hard_threshold = REBUTTAL_DECAY_CONFIG["pressure_threshold_hard"] - int(suspect.deception_skill * 0.2)
    effective_soft_threshold = REBUTTAL_DECAY_CONFIG["pressure_threshold_soft"] - int(suspect.deception_skill * 0.1)

    if suspect.pressure > effective_hard_threshold:
        rebuttal_believable = False
        logger.debug(f"[{suspect.name}] 压力{suspect.pressure}>{effective_hard_threshold}，反驳可信度被程序覆盖为False")
    elif suspect.pressure > effective_soft_threshold:
        rebuttal_believable = False

if rebuttal:
    if rebuttal_believable:
        # 反驳成功：压力不增加（覆盖证据带来的压力增量），嫌疑人可信度上升
        suspect.credibility = min(100, suspect.credibility + 10)
        pressure_delta = 0  # 抵消证据压力增量
        rebuttal_event: RebuttalEvent = {
            "type": "rebuttal",
            "suspect_index": self.current_suspect_index,
            "rebuttal_text": result["reply"],
            "believable": True,
            "credibility_change": +10,
        }
        events.append(rebuttal_event)
    else:
        # 反驳失败：压力按证据强度增加，供词进度额外提升
        suspect.credibility = max(0, suspect.credibility - 5)
        # pressure_delta 保持证据原本的计算值（Phase 1 已实现的逻辑）
        rebuttal_event: RebuttalEvent = {
            "type": "rebuttal",
            "suspect_index": self.current_suspect_index,
            "rebuttal_text": result["reply"],
            "believable": False,
            "credibility_change": -5,
        }
        events.append(rebuttal_event)
```

### 新增属性

在 `SuspectAgent.__init__` 中新增：
```python
self.credibility: int = 50  # 嫌疑人可信度，影响后续反驳成功率
```

**并在 `to_dict`/`from_dict` 中序列化**：
```python
# to_dict:
"credibility": suspect.credibility,

# from_dict:
engine.suspects[i].credibility = suspect_state.get("credibility", 50)
```

---

## 2.2 反驳事件与 UI

### 新增事件类型

**修改 `schemas/events.py`**:
```python
class RebuttalEvent(TypedDict):
    type: Literal["rebuttal"]
    suspect_index: int
    rebuttal_text: str
    believable: bool
    credibility_change: int
```

### UI 展示

- 反驳成功时，聊天区以特殊样式显示嫌疑人反驳内容（如带"反驳"标签的气泡）
- 反驳失败时，显示嫌疑人慌乱回应（带"破绽"标签）

### 新增信号

**修改 `ui/web_bridge.py`**:
```python
rebuttal_result = Signal(int, str, bool)  # suspect_index, text, believable
```

### 可信度显示

在嫌疑人卡片中新增可信度指示器（可选，也可以作为隐藏属性不显示）。

---

## 2.3 压力程序化效果

### 2.3.1 动态系统提示词（增强版）

在 Phase 1 修复的动态提示词基础上，根据压力段注入更详细的行为指令：

```python
def _get_pressure_instruction(self) -> str:
    """根据当前压力返回行为指令。"""
    if self.pressure < 30:
        return (
            "你表现冷静、从容，回答滴水不漏。"
            "你会主动质疑审讯员的指控。"
        )
    elif self.pressure < 60:
        return (
            "你有些紧张，偶尔会多说几句不必要的话。"
            "你的回答开始出现细微的前后不一致。"
        )
    elif self.pressure < 80:
        return (
            "你很慌乱，说话前后矛盾，可能会说漏嘴。"
            "你试图辩解但逻辑混乱。"
        )
    else:
        return (
            "你接近崩溃，语无伦次，难以自圆其说。"
            "你可能会不自觉地提到一些你本不该说的事情。"
        )
```

将此方法的返回值注入到系统提示词中，替换原有的通用压力描述。

**修改 `_build_system_prompt`**：
```python
def _build_system_prompt(self, suspect_data: dict, case_title: str) -> str:
    # ... 其他部分不变 ...
    prompt = (
        # ...
        f"## 当前压力值：{{pressure_value}}/100\n"
        "{{pressure_instruction}}\n"  # ← 新增占位符
        # ...
    )
    return prompt

def _get_system_message(self) -> dict:
    """构建带有当前压力值和行为指令的系统消息。"""
    prompt = self._system_prompt.replace("{pressure_value}", str(self.pressure))
    prompt = prompt.replace("{pressure_instruction}", self._get_pressure_instruction())
    return {"role": "system", "content": prompt}
```

### 2.3.2 供词进度增速

在 `SuspectAgent.update_confession_progress` 中使用 `CONFESSION_PROGRESS_RATE`（已在 Phase 1 的 game_config.py 中定义）。

### 2.3.3 反驳成功率

不使用硬编码概率，由 LLM 根据提示词中的压力描述自行判断 + 程序化兜底（见 2.1）。`deception_skill` 影响反驳阈值的计算。

### 2.3.4 共情机制

新增"共情"操作类型，与"施压"对应：
- **施压**：增加压力，效果受 `fear` 和 `defiance` 影响
- **共情**：降低嫌疑人戒备，效果受 `empathy_susceptibility` 影响

共情效果：
```python
# 共情操作在 submit_action 中
elif action == "empathy":
    # 共情降低恐惧但提升供词进度
    from core.game_config import FEAR_NEUTRAL
    empathy_effect = suspect.empathy_susceptibility / FEAR_NEUTRAL
    suspect.fear = max(0, suspect.fear - int(10 * empathy_effect))
    # 共情增加供词进度（而非压力）
    suspect.confession_progress = min(1.0, suspect.confession_progress + 0.1 * empathy_effect)
    result = suspect.respond(content)
```

共情不增加压力，但增加供词进度和降低恐惧值——适用于"高压力但低供词"的情况，帮助突破供词瓶颈。

---

## 2.4 证据链机制

### 设计

当出示的证据与之前出示的证据存在逻辑关联时，触发"证据链"效果。

### Schema 扩展

在 Phase 1 的 Schema 基础上，`evidences` 中新增 `chain_with` 字段：

```json
{
  "id": "e1",
  "name": "沾血的锄头",
  "description": "锄头上有血迹和指纹",
  "type": "physical",
  "strength": 8,
  "related_suspect": "李四",
  "chain_with": ["e2"]
}
```

### 引擎逻辑

在 `submit_action` 的 `present_evidence` 分支中：

```python
# 检查证据链（在计算 pressure_delta 之前）
from core.game_config import CHAIN_BONUS
chain_bonus = 0
for prev_id in self.presented_evidence_ids:
    prev_evidence = self._find_evidence(prev_id)
    if prev_evidence and evidence_id in prev_evidence.get("chain_with", []):
        chain_bonus = CHAIN_BONUS
        break
    if prev_evidence and prev_id in evidence.get("chain_with", []):
        chain_bonus = CHAIN_BONUS
        break

# 压力增量 = 证据基础值 + 证据链奖励
if evidence.get("related_suspect") == suspect.name:
    from core.game_config import EVIDENCE_PRESSURE_BASE, EVIDENCE_STRENGTH_MULTIPLIER
    base = EVIDENCE_PRESSURE_BASE.get(evidence_type, 10)
    strength = evidence.get("strength", 5)
    pressure_delta = int(base * (1 + strength * EVIDENCE_STRENGTH_MULTIPLIER)) + chain_bonus
    # ... 其余逻辑不变 ...

if chain_bonus > 0:
    chain_msg: NewMessageEvent = {
        "type": "new_message",
        "role": "system",
        "content": "证据链形成！两件证据相互印证，压力额外增加。",
        "suspect_name": None,
    }
    events.append(chain_msg)
```

### game_config.py 新增（Phase 2 配置）

```python
# 证据链奖励值
CHAIN_BONUS: int = 10

# 反驳可信度程序化兜底配置
REBUTTAL_DECAY_CONFIG = {
    "pressure_threshold_hard": 80,   # 压力超过此值强制判定为不可信
    "pressure_threshold_soft": 60,   # 压力超过此值可信度减半
    "credibility_bonus_success": 10,
    "credibility_penalty_fail": 5,
}
```

### 生成提示词修改

在案件生成提示词中增加：
```
"chain_with": "字符串数组，与该证据可以组成证据链的其他证据ID。证据链意味着两件证据相互印证，对嫌疑人形成更强的压力。可以为空数组。"
```

---

## 2.5 嫌疑人主动开口

### 设计

高压时嫌疑人可能主动辩解，不等玩家提问。

### 关键修正（v1.1）

**v1.0 原方案的问题**：在 `tick()` 中直接调用 `suspect.respond()`，阻塞 Qt 主线程。

**v1.1 优化方案**：改为基于**轮次触发**（非秒），在 `submit_action` 末尾检查条件，通过 WebWorker 异步执行。

### 实现

**修改 `core/interrogation.py` — 新增主动开口检查**：

```python
def _check_proactive_speech(self, suspect) -> Optional[dict]:
    """检查嫌疑人是否应该主动开口。

    触发条件：
    - 压力 > 70
    - 每 5 轮对话检查一次（而非每秒）
    - 概率基于压力值（pressure/200，即 35%-50%）

    Returns:
        respond 结果字典，或 None（不触发）
    """
    if suspect.pressure <= 70:
        return None
    if suspect.turn_count % 5 != 0:
        return None

    import random
    probability = suspect.pressure / 200  # 35% - 50%
    if random.random() >= probability:
        return None

    # 构建主动开口的 prompt
    result = suspect.respond(
        "（审讯员沉默了片刻，你感到压力越来越大，忍不住想说些什么...）"
    )
    return result
```

**在 `submit_action` 末尾调用**（供词进度更新之后）：

```python
# ── 嫌疑人主动开口检查 ──
proactive_result = self._check_proactive_speech(suspect)
if proactive_result:
    proactive_msg: NewMessageEvent = {
        "type": "new_message",
        "role": "suspect",
        "content": f"[主动开口] {proactive_result['reply']}",
        "suspect_name": suspect.name,
    }
    events.append(proactive_msg)

    # 主动开口也可能触发胜利条件
    victory_event = self._check_victory(suspect, proactive_result)
    if victory_event:
        events.append(victory_event)
```

**注意**：主动开口的内容可能暴露信息（增加策略深度），也可能只是无意义的辩解。由于 `_check_proactive_speech` 在 `submit_action` 中调用，而 `submit_action` 已在 WebWorker 中执行，因此主动开口也是异步的，不会阻塞 UI。

---

## 2.6 时间-压力双向动态

### 设计

压力值随时间自然变化，创造博弈空间：
- **低压力段（0-40）**：自然衰减，每秒 -0.5 压力（嫌疑人逐渐恢复冷静）
- **高压力段（60+）**：自然增长，每秒 +0.3 压力（审讯室压迫感 + 心理防线崩溃）
- **中间段（40-60）**：稳定区，不增不减

这创造了一个有趣的博弈：**低压力时必须主动出击**，否则压力会自行回落；**高压力时可以适当等待**，压力会自行推高。

### game_config.py Phase 2 配置新增

```python
# 时间-压力动态配置
PRESSURE_TIME_DYNAMICS = {
    "decay_zone": (0, 40),       # 低压力自然衰减区间
    "decay_rate": -0.5,          # 每秒压力变化（负值=衰减）
    "stable_zone": (40, 60),     # 稳定区间
    "stable_rate": 0.0,          # 稳定区不变化
    "growth_zone": (60, 100),    # 高压力自然增长区间
    "growth_rate": 0.3,          # 每秒压力变化（正值=增长）
}
```

### 修改 `core/interrogation.py` — tick 中压力自然变化

```python
def _apply_pressure_dynamics(self, dt_seconds: float) -> List[UIEvent]:
    """每 tick 应用时间-压力动态变化。

    Args:
        dt_seconds: 距上次 tick 的秒数

    Returns:
        压力变化事件列表（仅变化时才产生事件）
    """
    from core.game_config import PRESSURE_TIME_DYNAMICS

    events = []
    dynamics = PRESSURE_TIME_DYNAMICS

    for i, suspect in enumerate(self.suspects):
        if i == self.current_suspect_index:
            # 当前正在审讯的嫌疑人，压力动态生效
            old_pressure = suspect.pressure

            if suspect.pressure < dynamics["decay_zone"][1]:
                # 低压力衰减
                suspect.pressure = max(0, suspect.pressure + dynamics["decay_rate"] * dt_seconds)
            elif suspect.pressure >= dynamics["growth_zone"][0]:
                # 高压力增长
                suspect.pressure = min(100, suspect.pressure + dynamics["growth_rate"] * dt_seconds)

            # 压力变化超过 2 点时发送事件（避免频繁更新 UI）
            if abs(suspect.pressure - old_pressure) >= 2:
                suspect.pressure = int(suspect.pressure)
                events.append(SuspectUpdateEvent(
                    type="suspect_update",
                    suspect_index=i,
                    pressure=suspect.pressure,
                    secret_triggered=None,
                ))

    return events
```

在 `tick()` 方法中调用（每秒1次）：

```python
def tick(self):
    if self.state != "interrogating":
        return []
    self.time_left -= 1
    events = [TimerTickEvent(type="timer_tick", time_left=self.time_left)]
    # 时间-压力动态
    dynamics_events = self._apply_pressure_dynamics(1.0)
    events.extend(dynamics_events)
    return events
```

---

## 2.7 错误惩罚机制

### 设计

在 Phase 1 的 `mistake_log` 基础上，增加更多错误场景和对应惩罚：

| 错误类型 | 触发条件 | 恐惧惩罚 | 时间惩罚 | 评分惩罚 |
|---------|---------|---------|---------|---------|
| `wrong_evidence` | 出示与当前嫌疑人无关的证据 | fear -10 | time -15s | -5分 |
| `wrong_pressure` | 对错误嫌疑人施压（无相关证据时施压） | fear -5 | time -10s | -3分 |
| `wrong_empathy` | 对真凶共情（共情后真凶恐惧下降） | fear +5（真凶恐惧反而上升，因为觉得你在套话） | time -5s | -3分 |
| `innocent_breakdown` | 无辜嫌疑人达到崩溃（confession_level=4 但非真凶） | — | time -30s | -20分 |

### 修改 `core/interrogation.py` — 错误检测

```python
def _check_mistake(self, action: str, suspect, result: dict) -> Optional[dict]:
    """检查操作是否为错误操作，返回错误记录或 None。"""
    is_culprit = suspect.name in [
        s.get("name") for s in self.case.get("suspects", [])
        if s.get("is_culprit", False)
    ]

    if action == "present_evidence":
        # 出示错误证据（Phase 1 已实现部分，此处补充时间惩罚）
        if not any(
            self._find_evidence(eid).get("related_suspect") == suspect.name
            for eid in self.presented_evidence_ids
        ):
            self.time_left = max(0, self.time_left - 15)
            return {"type": "wrong_evidence", "suspect_name": suspect.name}

    elif action == "pressure":
        if not is_culprit:
            suspect.fear = max(0, suspect.fear - 5)
            self.time_left = max(0, self.time_left - 10)
            return {"type": "wrong_pressure", "suspect_name": suspect.name}

    elif action == "empathy":
        if is_culprit:
            # 对真凶共情：真凶恐惧反而上升（觉得你在套话）
            suspect.fear = min(100, suspect.fear + 5)
            self.time_left = max(0, self.time_left - 5)
            return {"type": "wrong_empathy", "suspect_name": suspect.name}

    # 无辜崩溃检查
    if suspect.confession_level >= 4 and not is_culprit:
        self.time_left = max(0, self.time_left - 30)
        return {"type": "innocent_breakdown", "suspect_name": suspect.name}

    return None
```

### 新增事件类型

```python
class MistakeEvent(TypedDict):
    type: Literal["mistake"]
    mistake_type: str  # "wrong_evidence" / "wrong_pressure" / "wrong_empathy" / "innocent_breakdown"
    suspect_index: int
    description: str
    time_penalty: int
```

### 错误提示 UI

错误操作时在聊天区显示红色警告：

```
⚠ 错误证据！该证据与当前嫌疑人无关。恐惧值-10，时间-15秒。
⚠ 施压失误！你对无辜者施压了。恐惧值-5，时间-10秒。
⚠ 共情失误！真凶不为所动，反而提高了警惕。恐惧值+5，时间-5秒。
🚨 无辜者崩溃！你逼供了无辜的人。时间-30秒，评分严重扣分。
```

---

## 2.8 测试计划

| 测试 | 说明 |
|------|------|
| 反驳成功不增加压力 | 模拟 believable=True 的反驳，验证压力不变 |
| 反驳失败正常增加压力 | 模拟 believable=False 的反驳，验证压力增加 |
| 反驳程序化兜底 | 模拟 pressure=85 + believable=True，验证程序覆盖为 False |
| deception_skill 影响反驳 | 模拟 deception_skill=80，验证反驳阈值降低 |
| 证据链触发 | 出示两个 chain_with 关联的证据，验证额外压力 |
| 主动开口轮次触发 | 验证每5轮检查一次，非每秒检查 |
| 主动开口异步执行 | 验证主动开口不阻塞 UI 线程 |
| 动态提示词 | 验证不同压力下系统提示词内容不同 |
| credibility 序列化 | 验证存档/读档后可信度正确恢复 |
| 时间-压力低段衰减 | 压力=30，等待5秒，验证压力下降约2.5 |
| 时间-压力高段增长 | 压力=80，等待5秒，验证压力增长约1.5 |
| 时间-压力中间段稳定 | 压力=50，等待5秒，验证压力不变 |
| 共情效果 | 共情操作后恐惧下降、供词进度增加 |
| 错误证据惩罚 | 出示错误证据→恐惧-10、时间-15s、mistake_log记录 |
| 无辜崩溃惩罚 | 无辜者confession_level=4→时间-30s、评分-20 |

---

## Phase 2 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.2 优化方案 | 原因 |
|--------|------------|--------------|------|
| 主动开口触发 | `tick()` 中每秒2%概率 | `submit_action` 中每5轮检查 | P0：避免阻塞UI线程 |
| 反驳可信度 | 完全依赖LLM自评 | LLM判断+程序化兜底 | P1：增加可靠性 |
| 反驳阈值 | 固定 80/60 | 受 deception_skill 动态调整 | P1：维度指标参与机制 |
| 证据链奖励 | 硬编码`chain_bonus=10` | `game_config.CHAIN_BONUS` | P2：配置化 |
| 压力行为指令 | 通用描述 | 4段压力段动态注入 | 增强：细化LLM行为 |
| 压力动态 | 静态，不操作不变 | 低压力衰减+高压力增长+中间稳定 | P1：增加博弈深度 |
| 错误操作 | 无惩罚 | mistake_log + 恐惧/时间/评分惩罚 | P1：增加策略博弈 |
| 共情操作 | 无 | 新增共情类型，受 empathy_susceptibility 影响 | 增强：增加策略选择 |

(End of file - total 310 lines)
