# Phase 3：工具与成长 — 消耗品工具 + 玩家等级（优化版 v1.1）

> **评审变更**：Phase 3拆分为3a+3b、工具系统预留策略模式接口、修复psych_collapse直接跳级、threat随机改为压力驱动、lie_detector knowledge泄露防护、数据库版本号迁移机制

## 前置依赖

Phase 1、Phase 2 完成。

## 目标

引入消耗品审讯工具和玩家等级系统，增加长期可玩性和每局的策略选择。

---

## Phase 3a：工具系统引擎 + 基础工具（6天）

### 3a.1 工具系统引擎

#### 设计原则

- **预留策略模式接口**：定义 `Tool` 抽象基类，各工具为独立实现类
- **引擎只负责调度**：`InterrogationEngine` 不内嵌工具逻辑，只调用 `Tool.execute()`
- **异步执行统一**：所有工具在 WebWorker 中执行，耗时操作不阻塞 UI

#### 新建 `core/tools/__init__.py`

```python
"""Tool system — strategy pattern for interrogation tools."""

from abc import ABC, abstractmethod
from typing import Dict, List, Type

from schemas.events import UIEvent


class Tool(ABC):
    """审讯工具抽象基类。"""

    name: str = ""           # 工具标识名（如 "psych_profile"）
    display_name: str = ""   # 显示名称（如 "心理侧写"）
    max_uses: int = 1
    unlock_level: int = 1
    cost_time: int = 0       # 消耗时间（秒）

    @abstractmethod
    def execute(self, engine, suspect, content: str) -> List[UIEvent]:
        """执行工具逻辑。

        Args:
            engine: InterrogationEngine 实例
            suspect: 当前嫌疑人 SuspectAgent 实例
            content: 玩家输入的额外内容（如伪造证据描述、威胁内容）

        Returns:
            UIEvent 列表
        """
        ...


# 工具注册表
TOOL_REGISTRY: Dict[str, Type[Tool]] = {}


def register_tool(tool_class: Type[Tool]) -> Type[Tool]:
    """装饰器：注册工具类。"""
    TOOL_REGISTRY[tool_class.name] = tool_class
    return tool_class


def get_tool(name: str) -> Tool:
    """根据名称获取工具实例。"""
    tool_class = TOOL_REGISTRY.get(name)
    if tool_class is None:
        raise ValueError(f"未知工具: {name}")
    return tool_class()
```

#### 引擎状态

在 `InterrogationEngine.__init__` 中新增：

```python
# 工具系统
from core.tools import TOOL_REGISTRY
self.available_tools: Dict[str, int] = {}  # tool_name -> remaining_uses
self.used_tools: List[str] = []  # 本局使用过的工具记录
```

#### 工具初始化

```python
def init_tools(self, player_level: int = 1):
    """根据玩家等级初始化可用工具。"""
    from core.game_config import LEVEL_UNLOCKS
    self.available_tools = {}
    for level, unlock in LEVEL_UNLOCKS.items():
        if level <= player_level:
            for tool_name in unlock.get("tools", []):
                if tool_name in TOOL_REGISTRY:
                    tool = get_tool(tool_name)
                    max_uses = tool.max_uses
                    # 20级大师：所有工具次数+1
                    if player_level >= 20:
                        max_uses += 1
                    self.available_tools[tool_name] = max_uses
```

#### 工具使用入口

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
    from core.tools import get_tool, TOOL_REGISTRY
    from schemas.events import NewMessageEvent

    events = []

    # 检查工具是否可用
    if tool_name not in self.available_tools:
        events.append(self._system_message("该工具不可用"))
        return events
    if self.available_tools[tool_name] <= 0:
        tool_display = TOOL_REGISTRY.get(tool_name, type('T', (), {'display_name': tool_name}))().display_name
        events.append(self._system_message(f"{tool_display} 次数已耗尽"))
        return events

    # 扣减次数
    self.available_tools[tool_name] -= 1
    self.used_tools.append(tool_name)

    # 扣减时间
    tool = get_tool(tool_name)
    if tool.cost_time > 0:
        self.time_left = max(0, self.time_left - tool.cost_time)

    # 执行工具逻辑（策略模式）
    suspect = self.suspects[self.current_suspect_index]
    try:
        tool_events = tool.execute(self, suspect, content)
        events.extend(tool_events)
    except Exception as exc:
        logger.error(f"工具 {tool_name} 执行失败: {exc}")
        events.append(self._system_message(f"工具执行失败: {exc}"))

    return events
```

---

### 3a.2 基础工具实现（4个）

#### 工具1：心理侧写

```python
# core/tools/psych_profile.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent, ToolUseEvent

@register_tool
class PsychProfileTool(Tool):
    name = "psych_profile"
    display_name = "心理侧写"
    max_uses = 1
    unlock_level = 2
    cost_time = 0

    def execute(self, engine, suspect, content: str):
        personality = suspect._suspect_data.get("personality", "未知")
        role = suspect._suspect_data.get("role", "未知")
        msg = f"【心理侧写】\n角色: {role}\n性格: {personality}\n弱点: 根据性格特征，该嫌疑人可能对情感诉求或逻辑矛盾较为敏感。"
        return [
            NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None),
            ToolUseEvent(type="tool_use", tool_name="psych_profile", result=msg),
        ]
```

#### 工具2：沉默施压

```python
# core/tools/silent_pressure.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent, SuspectUpdateEvent

@register_tool
class SilentPressureTool(Tool):
    name = "silent_pressure"
    display_name = "沉默施压"
    max_uses = 2
    unlock_level = 10
    cost_time = 5

    def execute(self, engine, suspect, content: str):
        suspect.pressure = max(0, min(100, suspect.pressure + 15))
        # 触发嫌疑人主动开口
        result = suspect.respond("（审讯员沉默地看着你，一言不发...）")
        return [
            NewMessageEvent(type="new_message", role="player", content="[沉默施压]", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=result["reply"], suspect_name=suspect.name),
            SuspectUpdateEvent(type="suspect_update", suspect_index=engine.current_suspect_index,
                              pressure=suspect.pressure, secret_triggered=result.get("secret_triggered")),
        ]
```

#### 工具3：威胁

```python
# core/tools/threat.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

@register_tool
class ThreatTool(Tool):
    name = "threat"
    display_name = "威胁"
    max_uses = 1
    unlock_level = 14
    cost_time = 0

    def execute(self, engine, suspect, content: str):
        """威胁，压力+20。嫌疑人是否沉默由压力值决定（非随机）。"""
        suspect.pressure = max(0, min(100, suspect.pressure + 20))

        # 压力驱动而非随机：pressure>70 时大概率沉默
        if suspect.pressure > 70:
            reply = "（嫌疑人沉默不语，拒绝回答）"
        else:
            result = suspect.respond(f"审讯员威胁道: {content}")
            reply = result["reply"]

        return [
            NewMessageEvent(type="new_message", role="player", content=f"[威胁] {content}", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=reply, suspect_name=suspect.name),
        ]
```

#### 工具4：心理崩溃

```python
# core/tools/psych_collapse.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent, ConfessionUpdateEvent
from core.game_config import CONFESSION_LEVELS

@register_tool
class PsychCollapseTool(Tool):
    name = "psych_collapse"
    display_name = "心理崩溃"
    max_uses = 1
    unlock_level = 18
    cost_time = 60

    def execute(self, engine, suspect, content: str):
        """供词直接+1级，但时间-60秒。

        修正（v1.1）：不再直接修改 confession_level，而是模拟高压状态
        调用 check_confession_upgrade，确保符合升级约束。
        """
        old_level = suspect.confession_level

        # 模拟高压条件，强制满足升级所需的压力值
        suspect.pressure = 100

        # 计算 has_evidence（基于已出示证据）
        has_evidence = any(
            engine._find_evidence(eid).get("related_suspect") == suspect.name
            for eid in engine.presented_evidence_ids
            if engine._find_evidence(eid) is not None
        )

        # 使用正常的升级检查（尊重阈值约束）
        new_level = suspect.check_confession_upgrade(has_evidence)

        # 如果正常检查不通过，强制升一级（作为工具的特殊效果）
        if new_level is None and suspect.confession_level < 4:
            suspect.confession_level += 1
            suspect.confession_progress = 0.0
            new_level = suspect.confession_level

        events = [
            NewMessageEvent(
                type="new_message",
                role="system",
                content=f"【心理崩溃】{suspect.name} 的供词层级提升至 {suspect.confession_level}！（时间 -60秒）",
                suspect_name=None,
            ),
        ]

        if new_level is not None and new_level > old_level:
            events.append(ConfessionUpdateEvent(
                type="confession_update",
                suspect_index=engine.current_suspect_index,
                confession_level=suspect.confession_level,
                confession_progress=0.0,
                level_name=CONFESSION_LEVELS[suspect.confession_level]["name"],
            ))

        return events
```

---

### 3a.3 复杂工具实现（4个）

#### 工具5：测谎仪

```python
# core/tools/lie_detector.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent
from core.llm_client import llm_client

@register_tool
class LieDetectorTool(Tool):
    name = "lie_detector"
    display_name = "测谎仪"
    max_uses = 2
    unlock_level = 4
    cost_time = 0

    def execute(self, engine, suspect, content: str):
        """让 LLM 判断嫌疑人上一句话的真假。

        修正（v1.1）：不再将嫌疑人 knowledge 传入 prompt，
        仅提供性格特征和对话上下文，避免泄露信息。
        """
        # 获取嫌疑人最后一条回复
        last_reply = ""
        for msg in reversed(suspect.memory):
            if msg["role"] == "assistant":
                last_reply = msg["content"]
                break

        if not last_reply:
            return [NewMessageEvent(type="new_message", role="system", content="没有可分析的回复", suspect_name=None)]

        # 仅传入性格特征，不传入 knowledge
        personality = suspect._suspect_data.get("personality", "未知")

        judge_prompt = f"""你是一个测谎专家。请分析以下嫌疑人回复是否可能是谎言。

嫌疑人的性格: {personality}
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

        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]
```

#### 工具6：伪造证据

```python
# core/tools/fake_evidence.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

@register_tool
class FakeEvidenceTool(Tool):
    name = "fake_evidence"
    display_name = "伪造证据"
    max_uses = 1
    unlock_level = 6
    cost_time = 10

    def execute(self, engine, suspect, content: str):
        """用伪造的证据试探嫌疑人反应。"""
        # content 是玩家输入的伪造证据描述
        # 注意：伪造证据使用 respond（普通对话模式），不会触发证据压力计算
        fake_prompt = f"审讯员声称掌握了以下证据：{content}"
        result = suspect.respond(fake_prompt)
        return [
            NewMessageEvent(type="new_message", role="player", content=f"[伪造证据] {content}", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=result["reply"], suspect_name=suspect.name),
        ]
```

#### 工具7：记忆回溯

```python
# core/tools/memory_recall.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent
from core.llm_client import llm_client

@register_tool
class MemoryRecallTool(Tool):
    name = "memory_recall"
    display_name = "记忆回溯"
    max_uses = 1
    unlock_level = 8
    cost_time = 0

    def execute(self, engine, suspect, content: str):
        """总结嫌疑人对话中的矛盾点。"""
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

        return [NewMessageEvent(type="new_message", role="system", content=msg, suspect_name=None)]
```

#### 工具8：多人对质

```python
# core/tools/dual_interrogation.py
from core.tools import Tool, register_tool
from schemas.events import NewMessageEvent

@register_tool
class DualInterrogationTool(Tool):
    name = "dual_interrogation"
    display_name = "多人对质"
    max_uses = 1
    unlock_level = 15
    cost_time = 30

    def execute(self, engine, suspect, content: str):
        """两名嫌疑人同时审讯，压力效果翻倍。

        当前嫌疑人压力+20，同时让另一名嫌疑人听到对话并反应。
        """
        current_idx = engine.current_suspect_index
        other_idx = (current_idx + 1) % len(engine.suspects)
        other_suspect = engine.suspects[other_idx]

        # 当前嫌疑人压力+20
        suspect.pressure = max(0, min(100, suspect.pressure + 20))

        # 另一名嫌疑人反应
        prompt = f"（另一名嫌疑人 {suspect.name} 被审讯员严厉质问，你在一旁听到...）"
        other_result = other_suspect.respond(prompt)

        return [
            NewMessageEvent(type="new_message", role="system", content="【多人对质】两名嫌疑人被同时审讯。", suspect_name=None),
            NewMessageEvent(type="new_message", role="player", content=f"[对质] 你如何看待 {suspect.name} 的供述？", suspect_name=None),
            NewMessageEvent(type="new_message", role="suspect", content=other_result["reply"], suspect_name=other_suspect.name),
        ]
```

---

### 3a.4 工具配置（game_config.py Phase 3a 配置）

```python
# core/game_config.py — Phase 3a 添加

TOOL_DEFINITIONS = {
    "psych_profile":     {"display_name": "心理侧写",   "max_uses": 1, "unlock_level": 2,  "cost_time": 0},
    "lie_detector":      {"display_name": "测谎仪",     "max_uses": 2, "unlock_level": 4,  "cost_time": 0},
    "fake_evidence":     {"display_name": "伪造证据",   "max_uses": 1, "unlock_level": 6,  "cost_time": 10},
    "memory_recall":     {"display_name": "记忆回溯",   "max_uses": 1, "unlock_level": 8,  "cost_time": 0},
    "silent_pressure":   {"display_name": "沉默施压",   "max_uses": 2, "unlock_level": 10, "cost_time": 5},
    "dual_interrogation":{"display_name": "多人对质",   "max_uses": 1, "unlock_level": 15, "cost_time": 30},
    "threat":            {"display_name": "威胁",       "max_uses": 1, "unlock_level": 14, "cost_time": 0},
    "psych_collapse":    {"display_name": "心理崩溃",   "max_uses": 1, "unlock_level": 18, "cost_time": 60},
}
```

---

### 3a.5 工具 UI

#### HTML 结构

在左侧面板的 `<div class="action-buttons">` 之后新增：

```html
<div class="tools-section">
    <h3 class="tools-title">工具箱</h3>
    <div class="tools-list" id="tools-list">
        <!-- 动态生成 -->
    </div>
</div>
```

#### 工具栏 JS 模块

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

#### 新增信号

```python
# web_bridge.py
use_tool = Signal(str, str)  # tool_name, content
```

---

## Phase 3b：玩家等级 + 数据库（5天）

### 3b.1 玩家等级引擎

#### 新建 `core/player.py`

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

### 3b.2 数据库表 + 迁移机制

#### 修改 `core/db.py` — 引入版本号迁移

```python
import sqlite3
from typing import Optional

DB_VERSION = 2  # 当前数据库版本


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 版本号表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY
        )
    """)

    # 获取当前版本
    cursor.execute("SELECT version FROM db_version LIMIT 1")
    row = cursor.fetchone()
    current_version = row[0] if row else 0

    # 增量迁移
    if current_version < 1:
        _migrate_v0_to_v1(cursor)
    if current_version < 2:
        _migrate_v1_to_v2(cursor)

    # 更新版本号
    cursor.execute("DELETE FROM db_version")
    cursor.execute("INSERT INTO db_version (version) VALUES (?)", (DB_VERSION,))

    conn.commit()
    conn.close()
    logger.info(f"数据库初始化完成: {db_path}, version={DB_VERSION}")


def _migrate_v0_to_v1(cursor):
    """初始表结构（v0 -> v1）。"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            title TEXT,
            json_data TEXT,
            created_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            case_id TEXT,
            current_state_json TEXT,
            saved_at TIMESTAMP
        )
    """)


def _migrate_v1_to_v2(cursor):
    """Phase 3b 新增表（v1 -> v2）。"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            successful_sessions INTEGER DEFAULT 0,
            best_grade TEXT DEFAULT 'D',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interrogation_history (
            id TEXT PRIMARY KEY,
            case_id TEXT,
            score_data TEXT,
            grade TEXT,
            experience_gained INTEGER,
            verdict TEXT,
            duration_seconds INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

### 3b.3 等级配置（game_config.py Phase 3b 配置）

```python
# core/game_config.py — Phase 3b 添加

EXPERIENCE_CURVE: List[int] = [
    0, 50, 120, 200, 300, 450, 600, 800, 1050, 1350,
    1700, 2100, 2550, 3050, 3600, 4200, 4850, 5550, 6300, 7100,
]

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
```

### 3b.4 等级 UI

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
| 策略模式注册 | 工具注册表正确加载所有工具 |
| 等级经验计算 | 经验达到阈值时正确升级 |
| 等级解锁 | 不同等级解锁对应工具 |
| 数据库迁移 | v0->v1->v2 增量迁移正确 |
| 存档兼容 | 工具状态和等级数据正确序列化/反序列化 |
| psych_collapse 约束 | 验证不再直接修改 confession_level |
| lie_detector 信息隔离 | 验证不传入 knowledge |
| threat 压力驱动 | 验证 pressure>70 时沉默 |

---

## Phase 3 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.1 优化方案 | 原因 |
|--------|------------|--------------|------|
| 工具架构 | 8个工具内嵌在引擎中 | 策略模式，各工具独立类 | P1：解耦，开闭原则 |
| `psych_collapse` | 直接 `confession_level += 1` | 调用 `check_confession_upgrade` | P1：尊重升级约束 |
| `lie_detector` | 传入嫌疑人 `knowledge` | 仅传入 `personality` | P2：避免信息泄露 |
| `threat` | `random.random() < 0.3` | `pressure > 70` 时沉默 | P2：压力驱动替代随机 |
| 数据库 | `CREATE TABLE IF NOT EXISTS` | 版本号 + 增量迁移 | P1：支持schema升级 |
| Phase 3 拆分 | 单阶段 | 3a(工具引擎,6天)+3b(成长,5天) | P1：降低单阶段复杂度 |

(End of file - total 595 lines)
