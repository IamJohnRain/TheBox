# Phase 2：审讯深度 — 反驳机制 + 压力增强 + 证据链

## 前置依赖

Phase 1 完成（供词层级、证据系统重构）。

## 目标

增加审讯的策略深度：嫌疑人会主动反驳证据，压力值产生程序化效果，证据之间可以形成证据链。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 2.1 | 嫌疑人反驳机制 | `core/suspect_agent.py` | 中 |
| 2.2 | 反驳事件与 UI | `schemas/events.py`, `ui/web_bridge.py`, `ui/web/js/`, `ui/web_main_window.py` | 中 |
| 2.3 | 压力程序化效果 | `core/suspect_agent.py`, `core/interrogation.py` | 中 |
| 2.4 | 证据链机制 | `core/interrogation.py`, `core/case_generator.py` | 小 |
| 2.5 | 嫌疑人主动开口 | `core/interrogation.py`, `ui/web_main_window.py` | 中 |
| 2.6 | 测试 | `tests/` | 中 |

---

## 2.1 嫌疑人反驳机制

### 设计

出示证据时，嫌疑人会尝试用 `knowledge` 中的信息进行反驳。反驳是否可信由 LLM 判断。

### 修改 `core/suspect_agent.py` — `respond_evidence` 返回值扩展

在 Phase 1 的 `respond_evidence` 基础上，修改 LLM 的 JSON 输出要求：

**系统提示词中新增（在 respond_evidence 的 user prompt 中）**：
```
请以 JSON 格式回复：
- "reply": 你的回复文本（1-3句话）
- "pressure_change": 整数，压力变化
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

### 反驳结果处理

在 `InterrogationEngine.submit_action` 的 `present_evidence` 分支中：

```python
result = suspect.respond_evidence(evidence_desc, evidence_type)

# 反驳机制处理
if result.get("rebuttal"):
    if result.get("rebuttal_believable"):
        # 反驳成功：压力不增加（覆盖证据带来的压力增量），嫌疑人可信度上升
        suspect.credibility = min(100, suspect.credibility + 10)
        # 不执行后续的证据压力增量
    else:
        # 反驳失败：压力按证据强度增加，供词进度额外提升
        suspect.credibility = max(0, suspect.credibility - 5)
        # 正常执行证据压力增量（Phase 1 已实现的逻辑）
```

### 新增属性

在 `SuspectAgent.__init__` 中新增：
```python
self.credibility: int = 50  # 嫌疑人可信度，影响后续反驳成功率
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

### 2.3.2 供词进度增速（已在 Phase 1 的 game_config.py 中定义）

在 `SuspectAgent.update_confession_progress` 中使用 `CONFESSION_PROGRESS_RATE`。

### 2.3.3 反驳成功率（已在 2.1 中通过提示词实现）

不使用硬编码概率，完全由 LLM 根据提示词中的压力描述自行判断。

---

## 2.4 证据链机制

### 设计

当出示的证据与之前出示的证据存在逻辑关联时，触发"证据链"效果。

### Schema 扩展

在 Phase 1 的 Schema 基础上，`evidences` 中新增 `chain_with` 字段（已在 Phase 1 的 Schema 中预留）：

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
# 检查证据链
chain_bonus = 0
for prev_id in self.presented_evidence_ids:
    prev_evidence = self._find_evidence(prev_id)
    if prev_evidence and evidence_id in prev_evidence.get("chain_with", []):
        chain_bonus = 10
        break
    if prev_evidence and prev_id in evidence.get("chain_with", []):
        chain_bonus = 10
        break

if chain_bonus > 0:
    suspect.pressure = max(0, min(100, suspect.pressure + chain_bonus))
    # 发送系统消息
    chain_msg: NewMessageEvent = {
        "type": "new_message",
        "role": "system",
        "content": "证据链形成！两件证据相互印证，压力额外增加。",
        "suspect_name": None,
    }
    events.append(chain_msg)
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

### 实现

在 `InterrogationEngine.tick()` 中新增逻辑：

```python
def tick(self, seconds_elapsed: int = 1) -> List[UIEvent]:
    # ... 现有的倒计时逻辑 ...

    # 新增：高压时嫌疑人主动开口
    suspect = self.suspects[self.current_suspect_index]
    if suspect.pressure > 70 and self.state == "interrogating":
        import random
        if random.random() < 0.02:  # 每秒约 2% 概率
            # 构建主动开口的 prompt
            result = suspect.respond(
                "（审讯员沉默了片刻，你感到压力越来越大，忍不住想说些什么...）"
            )
            # 构造事件...
            proactive_msg: NewMessageEvent = {
                "type": "new_message",
                "role": "suspect",
                "content": f"[主动开口] {result['reply']}",
                "suspect_name": suspect.name,
            }
            events.append(proactive_msg)
```

**注意**：主动开口的内容可能暴露信息（增加策略深度），也可能只是无意义的辩解。

---

## 2.6 测试计划

| 测试 | 说明 |
|------|------|
| 反驳成功不增加压力 | 模拟 believable=True 的反驳，验证压力不变 |
| 反驳失败正常增加压力 | 模拟 believable=False 的反驳，验证压力增加 |
| 证据链触发 | 出示两个 chain_with 关联的证据，验证额外压力 |
| 高压主动开口 | 模拟压力>70，验证 tick 中的主动开口逻辑 |
| 动态提示词 | 验证不同压力下系统提示词内容不同 |
