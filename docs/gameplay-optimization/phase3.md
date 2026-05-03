# Phase 3：工具与成长 — 消耗品工具 + 玩家等级

## 前置依赖

Phase 1、Phase 2 完成。

## 目标

引入消耗品审讯工具和玩家等级系统，增加长期可玩性和每局的策略选择。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 3.1 | 工具系统引擎 | `core/interrogation.py`, `core/game_config.py` | 中 |
| 3.2 | 各工具实现 | `core/suspect_agent.py`, `core/interrogation.py` | 大 |
| 3.3 | 工具 UI | `ui/web/js/`, `ui/web/index.html`, `ui/web/css/` | 中 |
| 3.4 | 玩家等级引擎 | `core/player.py` (新), `core/db.py` | 中 |
| 3.5 | 等级 UI | `ui/web/` | 小 |
| 3.6 | 测试 | `tests/` | 中 |

---

## 3.1 工具系统引擎

### 引擎状态

在 `InterrogationEngine.__init__` 中新增：

```python
# 工具系统
from core.game_config import LEVEL_UNLOCKS
self.available_tools: Dict[str, int] = {}  # tool_name -> remaining_uses
self.used_tools: List[str] = []  # 本局使用过的工具记录
```

### 工具配置

在 `core/game_config.py` 中定义工具参数：

```python
TOOL_DEFINITIONS = {
    "psych_profile": {
        "name": "心理侧写",
        "desc": "查看嫌疑人性格弱点标签",
        "max_uses": 1,
        "unlock_level": 2,
        "cost_time": 0,  # 不消耗时间
    },
    "lie_detector": {
        "name": "测谎仪",
        "desc": "输入一句话，判断嫌疑人回复的真假",
        "max_uses": 2,
        "unlock_level": 4,
        "cost_time": 0,
    },
    "fake_evidence": {
        "name": "伪造证据",
        "desc": "输入虚假证据描述，观察嫌疑人反应",
        "max_uses": 1,
        "unlock_level": 6,
        "cost_time": 10,  # 消耗 10 秒
    },
    "memory_recall": {
        "name": "记忆回溯",
        "desc": "系统总结嫌疑人对话中的矛盾点",
        "max_uses": 1,
        "unlock_level": 8,
        "cost_time": 0,
    },
    "silent_pressure": {
        "name": "沉默施压",
        "desc": "不说话，压力+15",
        "max_uses": 2,
        "unlock_level": 10,
        "cost_time": 5,
    },
    "dual_interrogation": {
        "name": "多人对质",
        "desc": "两名嫌疑人同时审讯，压力效果翻倍",
        "max_uses": 1,
        "unlock_level": 15,
        "cost_time": 30,
    },
    "threat": {
        "name": "威胁",
        "desc": "压力+20，但可能触发嫌疑人沉默",
        "max_uses": 1,
        "unlock_level": 14,
        "cost_time": 0,
    },
    "psych_collapse": {
        "name": "心理崩溃",
        "desc": "供词直接+1级，但时间-60秒",
        "max_uses": 1,
        "unlock_level": 18,
        "cost_time": 60,
    },
}
```

### 工具初始化

在 `InterrogationEngine` 中新增方法：

```python
def init_tools(self, player_level: int = 1):
    """根据玩家等级初始化可用工具。"""
    from core.game_config import TOOL_DEFINITIONS, LEVEL_UNLOCKS
    self.available_tools = {}
    for level, unlock in LEVEL_UNLOCKS.items():
        if level <= player_level:
            for tool_name in unlock.get("tools", []):
                if tool_name in TOOL_DEFINITIONS:
                    tool_def = TOOL_DEFINITIONS[tool_name]
                    max_uses = tool_def["max_uses"]
                    # 20级大师：所有工具次数+1
                    if player_level >= 20:
                        max_uses += 1
                    self.available_tools[tool_name] = max_uses
```

### 工具使用入口

在 `submit_action` 中新增 `elif` 分支：

```python
elif action.startswith("tool_"):
    tool_name = action[5:]  # 去掉 "tool_" 前缀
    result = self._use_tool(tool_name, content)
    events.extend(result)
    return events
```

新增 `_use_tool` 方法：

```python
def _use_tool(self, tool_name: str, content: str) -> List[UIEvent]:
    """执行工具使用逻辑。"""
    from core.game_config import TOOL_DEFINITIONS

    events = []

    # 检查工具是否可用
    if tool_name not in self.available_tools:
        events.append(self._system_message("该工具不可用"))
        return events
    if self.available_tools[tool_name] <= 0:
        events.append(self._system_message(f"{TOOL_DEFINITIONS[tool_name]['name']}次数已耗尽"))
        return events

    # 扣减次数
    self.available_tools[tool_name] -= 1
    self.used_tools.append(tool_name)

    # 扣减时间
    cost_time = TOOL_DEFINITIONS[tool_name].get("cost_time", 0)
    if cost_time > 0:
        self.time_left = max(0, self.time_left - cost_time)

    # 分发到具体工具逻辑
    suspect = self.suspects[self.current_suspect_index]
    tool_events = self._execute_tool(tool_name, suspect, content)
    events.extend(tool_events)

    return events
```

---

## 3.2 各工具实现

### `_execute_tool` 分发方法

```python
def _execute_tool(self, tool_name: str, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """分发到具体工具的实现。"""
    handlers = {
        "psych_profile": self._tool_psych_profile,
        "lie_detector": self._tool_lie_detector,
        "fake_evidence": self._tool_fake_evidence,
        "memory_recall": self._tool_memory_recall,
        "silent_pressure": self._tool_silent_pressure,
        "dual_interrogation": self._tool_dual_interrogation,
        "threat": self._tool_threat,
        "psych_collapse": self._tool_psych_collapse,
    }
    handler = handlers.get(tool_name)
    if handler:
        return handler(suspect, content)
    return [self._system_message(f"未知工具: {tool_name}")]
```

### 心理侧写

```python
def _tool_psych_profile(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """显示嫌疑人性格弱点。"""
    personality = suspect._suspect_data.get("personality", "未知")
    role = suspect._suspect_data.get("role", "未知")
    msg = f"【心理侧写】\n角色: {role}\n性格: {personality}\n弱点: 根据性格特征，该嫌疑人可能对情感诉求或逻辑矛盾较为敏感。"
    return [
        NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None),
        ToolUseEvent(type="tool_use", tool_name="psych_profile", result=msg),
    ]
```

### 测谎仪

```python
def _tool_lie_detector(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """让 LLM 判断嫌疑人上一句话的真假。"""
    # 获取嫌疑人最后一条回复
    last_reply = ""
    for msg in reversed(suspect.memory):
        if msg["role"] == "assistant":
            last_reply = msg["content"]
            break

    if not last_reply:
        return [self._system_message("没有可分析的回复")]

    # 调用 LLM 判断真假
    from core.llm_client import llm_client
    judge_prompt = f"""你是一个测谎专家。请分析以下嫌疑人回复是否可能是谎言。

嫌疑人的性格: {suspect._suspect_data.get('personality', '未知')}
嫌疑人知道的信息: {suspect._suspect_data.get('knowledge', '未知')}
嫌疑人的回复: "{last_reply}"

请以 JSON 格式输出：
- "result": "truthful"/"deceptive"/"uncertain"
- "confidence": 0-100 的置信度
- "reason": 简短的判断理由"""

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "system", "content": judge_prompt}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        result_map = {"truthful": "疑似真实", "deceptive": "疑似虚假", "uncertain": "无法判断"}
        display = result_map.get(parsed.get("result", "uncertain"), "无法判断")
        reason = parsed.get("reason", "")
        msg = f"【测谎仪】{display}（置信度: {parsed.get('confidence', 50)}%）\n理由: {reason}"
    except Exception:
        msg = "【测谎仪】分析失败，无法得出结论"

    return [self._system_message(msg)]
```

### 伪造证据

```python
def _tool_fake_evidence(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """用伪造的证据试探嫌疑人反应。"""
    # content 是玩家输入的伪造证据描述
    fake_prompt = f"审讯员声称掌握了以下证据：{content}"
    result = suspect.respond(fake_prompt)
    return [
        NewMessageEvent(type="new_message", role="player", content=f"[伪造证据] {content}", suspect_name=None),
        NewMessageEvent(type="new_message", role="suspect", content=result["reply"], suspect_name=suspect.name),
    ]
```

### 记忆回溯

```python
def _tool_memory_recall(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """总结嫌疑人对话中的矛盾点。"""
    from core.llm_client import llm_client

    memory_text = "\n".join(
        f"{'审讯员' if m['role'] == 'user' else '嫌疑人'}: {m['content']}"
        for m in suspect.memory
    )

    recall_prompt = f"""分析以下审讯对话，找出嫌疑人回复中的矛盾点和可疑之处。

对话记录：
{memory_text}

请以 JSON 格式输出：
- "contradictions": 矛盾点列表（字符串数组）
- "suspicious": 可疑之处列表（字符串数组）
- "summary": 简短总结"""

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "system", "content": recall_prompt}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        lines = ["【记忆回溯 — 矛盾分析】"]
        for c in parsed.get("contradictions", []):
            lines.append(f"⚠ 矛盾: {c}")
        for s in parsed.get("suspicious", []):
            lines.append(f"🔍 可疑: {s}")
        if parsed.get("summary"):
            lines.append(f"\n总结: {parsed['summary']}")
        msg = "\n".join(lines)
    except Exception:
        msg = "【记忆回溯】分析失败"

    return [self._system_message(msg)]
```

### 沉默施压

```python
def _tool_silent_pressure(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """沉默施压，压力+15。"""
    suspect.pressure = max(0, min(100, suspect.pressure + 15))
    # 触发嫌疑人主动开口
    result = suspect.respond("（审讯员沉默地看着你，一言不发...）")
    return [
        NewMessageEvent(type="new_message", role="player", content="[沉默施压]", suspect_name=None),
        NewMessageEvent(type="new_message", role="suspect", content=result["reply"], suspect_name=suspect.name),
        SuspectUpdateEvent(type="suspect_update", suspect_index=self.current_suspect_index,
                          pressure=suspect.pressure, secret_triggered=result.get("secret_triggered")),
    ]
```

### 威胁

```python
def _tool_threat(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """威胁，压力+20，但可能触发嫌疑人沉默。"""
    suspect.pressure = max(0, min(100, suspect.pressure + 20))
    # 30% 概率嫌疑人沉默不语
    import random
    if random.random() < 0.3:
        reply = "（嫌疑人沉默不语，拒绝回答）"
    else:
        result = suspect.respond(f"审讯员威胁道: {content}")
        reply = result["reply"]
    return [
        NewMessageEvent(type="new_message", role="player", content=f"[威胁] {content}", suspect_name=None),
        NewMessageEvent(type="new_message", role="suspect", content=reply, suspect_name=suspect.name),
    ]
```

### 心理崩溃

```python
def _tool_psych_collapse(self, suspect: SuspectAgent, content: str) -> List[UIEvent]:
    """供词直接+1级，但时间-60秒。"""
    old_level = suspect.confession_level
    if suspect.confession_level < 4:
        suspect.confession_level += 1
        suspect.confession_progress = 0.0
    return [
        self._system_message(f"【心理崩溃】{suspect.name} 的供词层级提升至 {suspect.confession_level}！（时间 -60秒）"),
        ConfessionUpdateEvent(
            type="confession_update",
            suspect_index=self.current_suspect_index,
            confession_level=suspect.confession_level,
            confession_progress=0.0,
            level_name=CONFESSION_LEVELS[suspect.confession_level]["name"],
        ),
    ]
```

---

## 3.3 工具 UI

### HTML 结构

在左侧面板的 `<div class="action-buttons">` 之后新增：

```html
<div class="tools-section">
    <h3 class="tools-title">工具箱</h3>
    <div class="tools-list" id="tools-list">
        <!-- 动态生成 -->
    </div>
</div>
```

### 工具栏 JS 模块

新增 `ui/web/js/tools.js`:

```javascript
class ToolManager {
    constructor() {
        this.listEl = document.getElementById('tools-list');
        this.tools = {};
    }

    loadTools(tools) {
        // tools = {"psych_profile": 1, "lie_detector": 2, ...}
        this.tools = tools;
        this.render();
    }

    render() {
        if (!this.listEl) return;
        this.listEl.innerHTML = '';
        for (const [name, remaining] of Object.entries(this.tools)) {
            const btn = document.createElement('button');
            btn.className = 'tool-btn' + (remaining <= 0 ? ' disabled' : '');
            btn.dataset.tool = name;
            btn.innerHTML = `
                <span class="tool-name">${this._getDisplayName(name)}</span>
                <span class="tool-count">${remaining}</span>
            `;
            btn.addEventListener('click', () => this._onToolClick(name));
            this.listEl.appendChild(btn);
        }
    }

    _onToolClick(toolName) {
        if (this.tools[toolName] <= 0) return;
        // 某些工具需要额外输入
        if (['fake_evidence', 'threat'].includes(toolName)) {
            const input = prompt(`请输入${this._getDisplayName(toolName)}的内容:`);
            if (input) window.bridge.useTool(toolName, input);
        } else {
            window.bridge.useTool(toolName, '');
        }
    }

    _getDisplayName(name) {
        const names = {
            psych_profile: '心理侧写', lie_detector: '测谎仪',
            fake_evidence: '伪造证据', memory_recall: '记忆回溯',
            silent_pressure: '沉默施压', dual_interrogation: '多人对质',
            threat: '威胁', psych_collapse: '心理崩溃',
        };
        return names[name] || name;
    }
}
```

### 新增信号

```python
# web_bridge.py
use_tool = Signal(str, str)  # tool_name, content
```

---

## 3.4 玩家等级引擎

### 新建 `core/player.py`

```python
"""Player profile and level system."""

import json
import logging
from typing import Optional, Dict, Any
from core.db import get_connection
from core.game_config import EXPERIENCE_CURVE, LEVEL_UNLOCKS

logger = logging.getLogger(__name__)


class PlayerProfile:
    """玩家档案，管理等级和经验。"""

    def __init__(self):
        self.level: int = 1
        self.experience: int = 0
        self.total_sessions: int = 0
        self.successful_sessions: int = 0
        self.best_grade: str = "D"
        self._load()

    def _load(self):
        """从数据库加载。"""
        conn = get_connection()
        row = conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
        if row:
            self.level = row["level"]
            self.experience = row["experience"]
            self.total_sessions = row["total_sessions"]
            self.successful_sessions = row["successful_sessions"]
            self.best_grade = row["best_grade"]
        conn.close()

    def save(self):
        """保存到数据库。"""
        conn = get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO player_profile
            (id, level, experience, total_sessions, successful_sessions, best_grade, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (self.level, self.experience, self.total_sessions,
              self.successful_sessions, self.best_grade))
        conn.commit()
        conn.close()

    def add_experience(self, amount: int):
        """添加经验并检查升级。"""
        self.experience += amount
        leveled_up = False
        while self.level < len(EXPERIENCE_CURVE) - 1:
            next_threshold = EXPERIENCE_CURVE[self.level]
            if self.experience >= next_threshold:
                self.level += 1
                leveled_up = True
                logger.info(f"玩家升级到 {self.level} 级！")
            else:
                break
        self.save()
        return leveled_up

    def get_evidence_uses(self) -> int:
        """获取当前等级的证据使用次数。"""
        return LEVEL_UNLOCKS.get(self.level, {}).get("evidence_uses", 3)

    def get_available_tools(self) -> list:
        """获取当前等级可用的工具列表。"""
        tools = []
        for level, unlock in LEVEL_UNLOCKS.items():
            if level <= self.level:
                tools.extend(unlock.get("tools", []))
        return tools
```

### 数据库表

在 `core/db.py` 的 `init_db` 中新增：

```sql
CREATE TABLE IF NOT EXISTS player_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    successful_sessions INTEGER DEFAULT 0,
    best_grade TEXT DEFAULT 'D',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 审讯历史表

```sql
CREATE TABLE IF NOT EXISTS interrogation_history (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    score_data TEXT,  -- JSON
    grade TEXT,
    experience_gained INTEGER,
    verdict TEXT,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3.5 等级 UI

在顶部导航栏或案件生成模态框中显示当前等级和经验：

```html
<div class="player-level">
    <span class="level-badge" id="player-level">Lv.1</span>
    <div class="exp-bar-container">
        <div class="exp-bar" id="player-exp-bar" style="width: 0%;"></div>
    </div>
    <span class="exp-text" id="player-exp-text">0/50</span>
</div>
```

---

## 3.6 测试计划

| 测试 | 说明 |
|------|------|
| 工具次数扣减 | 使用工具后次数正确减少 |
| 工具次数耗尽 | 次数为 0 时无法使用 |
| 各工具效果 | 每个工具的核心逻辑正确 |
| 等级经验计算 | 经验达到阈值时正确升级 |
| 等级解锁 | 不同等级解锁对应工具 |
| 存档兼容 | 工具状态和等级数据正确序列化/反序列化 |
