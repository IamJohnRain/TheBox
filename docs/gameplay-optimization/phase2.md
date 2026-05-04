# Phase 2：审讯深度 — 反驳机制 + 压力增强 + 证据链（优化版 v1.1）

> **评审变更**：修复P0主动开口线程阻塞（改为轮次触发+异步）、反驳增加程序化兜底、证据链奖励配置化、高压行为指令动态注入

## 前置依赖

Phase 1 完成（供词层级、证据系统重构、统一胜利入口 `_check_victory`）。

## 目标

增加审讯的策略深度：嫌疑人会主动反驳证据，压力值产生程序化效果，证据之间可以形成证据链。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 2.1 | 嫌疑人反驳机制 | `core/suspect_agent.py` | 中 |
| 2.2 | 反驳事件与 UI | `schemas/events.py`, `ui/web_bridge.py`, `ui/web/js/`, `ui/web_main_window.py` | 中 |
| 2.3 | 压力程序化效果 | `core/suspect_agent.py`, `core/interrogation.py` | 中 |
| 2.4 | 证据链机制 | `core/interrogation.py`, `core/case_generator.py`, `core/game_config.py` | 小 |
| 2.5 | 嫌疑人主动开口 | `core/interrogation.py`, `ui/web_main_window.py` | 中 |
| 2.6 | 测试 | `tests/` | 中 |

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
    if suspect.pressure > 80:
        # 压力>80时，即使LLM认为可信，程序也判定为不可信
        rebuttal_believable = False
        logger.debug(f"[{suspect.name}] 压力{suspect.pressure}>80，反驳可信度被程序覆盖为False")
    elif suspect.pressure > 60:
        # 压力60-80时，可信度减半（视为不可信）
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

不使用硬编码概率，由 LLM 根据提示词中的压力描述自行判断 + 程序化兜底（见 2.1）。

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

## 2.6 测试计划

| 测试 | 说明 |
|------|------|
| 反驳成功不增加压力 | 模拟 believable=True 的反驳，验证压力不变 |
| 反驳失败正常增加压力 | 模拟 believable=False 的反驳，验证压力增加 |
| 反驳程序化兜底 | 模拟 pressure=85 + believable=True，验证程序覆盖为 False |
| 证据链触发 | 出示两个 chain_with 关联的证据，验证额外压力 |
| 主动开口轮次触发 | 验证每5轮检查一次，非每秒检查 |
| 主动开口异步执行 | 验证主动开口不阻塞 UI 线程 |
| 动态提示词 | 验证不同压力下系统提示词内容不同 |
| credibility 序列化 | 验证存档/读档后可信度正确恢复 |

---

## Phase 2 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.1 优化方案 | 原因 |
|--------|------------|--------------|------|
| 主动开口触发 | `tick()` 中每秒2%概率 | `submit_action` 中每5轮检查 | P0：避免阻塞UI线程 |
| 反驳可信度 | 完全依赖LLM自评 | LLM判断+程序化兜底 | P1：增加可靠性 |
| 证据链奖励 | 硬编码`chain_bonus=10` | `game_config.CHAIN_BONUS` | P2：配置化 |
| 压力行为指令 | 通用描述 | 4段压力段动态注入 | 增强：细化LLM行为 |

(End of file - total 310 lines)
