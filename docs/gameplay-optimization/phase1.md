# Phase 1：基础重构 — 证据系统 + 供词层级 + 恐惧值 + 多维隐藏指标 + 交互限制（优化版 v1.4）

> **评审变更**：修复P0 `_postprocess`冲突、抽取`_call_llm()`、统一胜利入口`_check_victory()`、压力程序化计算、移除`requires_semantic`、game_config分阶段配置  
> **v1.2 变更**：新增恐惧值系统、嫌疑人5维隐藏指标、施压/共情交互限制（混合方案）、聊天轮次限制  
> **v1.3 变更**：全维度动态变化机制、主+副性格组合、反扑机制、维度边界与联动规则，详见 [`suspect-dimensions.md`](suspect-dimensions.md)
> **v1.4 变更**：所有数值改为配置文件默认值，新增 `config/gameplay_balance.json`；`core/game_config.py` 只做加载、校验和访问器，不在业务逻辑硬编码数值。

## 目标

解决"点完证据就赢"的核心问题，引入供词层级系统作为新的胜负判定基础，同时引入恐惧值和嫌疑人多维隐藏指标，增加个体差异和策略深度。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 1.1 | 新增玩法配置文件与加载器 | `config/gameplay_balance.json` (新), `core/game_config.py` (新) | 中 |
| 1.2 | 重构证据出示链路 | `core/suspect_agent.py`, `core/interrogation.py`, `ui/web_main_window.py` | 中 |
| 1.3 | 证据使用次数限制 | `core/interrogation.py`, `ui/web/js/evidence.js` | 小 |
| 1.4 | 已出示证据 UI 标记 | `ui/web/js/evidence.js` | 小 |
| 1.5 | 供词层级系统 | `core/suspect_agent.py`, `schemas/events.py`, `core/interrogation.py` | 中 |
| 1.6 | 供词层级 UI | `ui/web/js/suspect.js`, `ui/web/index.html`, `ui/web/css/` | 中 |
| 1.7 | 修复静态系统提示词 | `core/suspect_agent.py` | 小 |
| 1.8 | 案件 Schema 扩展 | `core/case_generator.py` | 小 |
| 1.9 | 恐惧值系统 | `core/suspect_agent.py`, `core/interrogation.py`, `schemas/events.py` | 中 |
| 1.10 | 嫌疑人多维隐藏指标 | `core/suspect_agent.py`, `core/case_generator.py`, `config/gameplay_balance.json`, `core/game_config.py` | 中 |
| 1.11 | 施压/共情交互限制 | `core/interrogation.py`, `ui/web/js/`, `ui/web/index.html` | 中 |
| 1.12 | 存档兼容 | `core/interrogation.py`, `core/suspect_agent.py` | 小 |
| 1.13 | 测试 | `tests/` | 中 |

---

## 1.1 新增玩法配置文件与加载器

**文件**: `config/gameplay_balance.json` (新建), `core/game_config.py` (新建)

**目的**: 将所有可调数值放入配置文件，支持后续通过改配置调参。**Phase 1 只放置 Phase 1 需要的配置字段**，后续 Phase 按阶段追加字段。`core/game_config.py` 不保存业务数值，只负责加载、校验、合并覆盖和提供只读访问器。

### 配置文件优先原则

| 规则 | 要求 |
|------|------|
| 默认配置 | 仓库内新增 `config/gameplay_balance.json`，保存默认玩法数值 |
| 调试覆盖 | 支持 `THEBOX_GAMEPLAY_CONFIG` 指向临时配置文件，方便测试和平衡调参 |
| 业务读取 | 引擎、嫌疑人、评分、工具系统只能通过 `core.game_config` 访问器读取数值 |
| 禁止硬编码 | 不允许在 `submit_action`、`respond_evidence`、评分和工具逻辑里直接写 `22`、`18`、`0.1`、`85` 等平衡数值 |
| 兼容导出 | 如果保留 `DEFAULT_TOTAL_ACTION_POINTS` 等名称，只能作为从 JSON 读取后的只读别名，不能在 Python 中重新定义默认值 |

### Phase 1 配置文件示例

```json
{
  "config_version": 1,
  "confession": {
    "levels": {
      "0": {"name": "否认", "desc": "完全否认一切"},
      "1": {"name": "动摇", "desc": "情绪波动，出现紧张、回避"},
      "2": {"name": "部分承认", "desc": "承认部分事实，但隐瞒关键"},
      "3": {"name": "关键突破", "desc": "透露动机/手段/时机之一"},
      "4": {"name": "完全崩溃", "desc": "完整供述真相"}
    },
    "thresholds": {
      "0": {"pressure": 40, "min_turns": 3, "requires_evidence": false},
      "1": {"pressure": 55, "min_turns": 5, "requires_evidence": true},
      "2": {"pressure": 70, "min_turns": 7, "requires_evidence": true},
      "3": {"pressure": 85, "min_turns": 10, "requires_evidence": true}
    },
    "pressure_window": 5,
    "progress_rate": {"low": 0.02, "medium": 0.05, "high": 0.10, "panic": 0.15}
  },
  "pressure": {
    "initial": 20,
    "segments": {"low": [0, 30], "medium": [30, 60], "high": [60, 80], "panic": [80, 100]},
    "soft_factor": {"min": 0.3, "max": 1.5},
    "per_turn": {"decay_zone": [0, 30], "decay_rate": -1, "stable_zone": [30, 70], "stable_rate": 0, "growth_zone": [70, 100], "growth_rate": 1, "floor": 15}
  },
  "evidence": {
    "default_uses": 4,
    "pressure_base": {"physical": 18, "document": 12, "testimony": 9},
    "strength_multiplier": 0.1,
    "fear_delta": {"correct": 8, "wrong": -10}
  },
  "fear": {
    "default": 50,
    "neutral": 50,
    "per_turn_decay": -1,
    "provocation_threshold": 15
  },
  "dimensions": {
    "bounds": {
      "fear": {"min": 0, "max": 100},
      "defiance": {"min": 5, "max": 100},
      "empathy_susceptibility": {"min": 0, "max": 95},
      "deception_skill": {"min": 5, "max": 100},
      "loyalty": {"min": 0, "max": 100},
      "credibility": {"min": 0, "max": 100}
    },
    "personality_weights": {"primary": 0.7, "secondary": 0.3}
  },
  "interaction_limits": {
    "chat_turns_per_suspect": 12,
    "pressure_uses_per_suspect": 2,
    "empathy_uses_per_suspect": 2,
    "second_use_multiplier": 0.5
  },
  "action_points": {
    "default_total": 22,
    "costs": {"chat": 1, "pressure": 2, "empathy": 2, "present_evidence": 2},
    "penalties": {"wrong_evidence": 2, "wrong_pressure": 1, "wrong_empathy": 1, "innocent_breakdown": 3}
  }
}
```

### `core/game_config.py` 访问器示例

以下 Python 片段只描述加载器形态。文档后续为了简洁仍会引用 `DEFAULT_TOTAL_ACTION_POINTS`、`EVIDENCE_PRESSURE_BASE` 等名字，但这些名字都必须由配置文件派生。

```python
"""Gameplay configuration loader.

All tunable values come from config/gameplay_balance.json.
Business logic should import accessors from this module instead of hardcoding numbers.
"""

from typing import Dict, Any

GAMEPLAY_CONFIG = load_gameplay_config()


def get_action_cost(action_type: str) -> int:
    return GAMEPLAY_CONFIG["action_points"]["costs"][action_type]


def get_ap_penalty(penalty_type: str) -> int:
    return GAMEPLAY_CONFIG["action_points"]["penalties"][penalty_type]


def get_evidence_pressure_base(evidence_type: str) -> int:
    return GAMEPLAY_CONFIG["evidence"]["pressure_base"].get(evidence_type, 0)


def get_confession_threshold(level: int) -> Dict[str, Any]:
    return GAMEPLAY_CONFIG["confession"]["thresholds"][str(level)]


def get_dimension_bounds(name: str) -> Dict[str, int]:
    return GAMEPLAY_CONFIG["dimensions"]["bounds"][name]


# Optional compatibility aliases. Values are derived from GAMEPLAY_CONFIG at import time.
DEFAULT_TOTAL_ACTION_POINTS = GAMEPLAY_CONFIG["action_points"]["default_total"]
DEFAULT_INITIAL_PRESSURE = GAMEPLAY_CONFIG["pressure"]["initial"]
DEFAULT_EVIDENCE_USES = GAMEPLAY_CONFIG["evidence"]["default_uses"]
EVIDENCE_PRESSURE_BASE = GAMEPLAY_CONFIG["evidence"]["pressure_base"]
EVIDENCE_STRENGTH_MULTIPLIER = GAMEPLAY_CONFIG["evidence"]["strength_multiplier"]
AP_PENALTY = GAMEPLAY_CONFIG["action_points"]["penalties"]
```

### 默认配置字段参考

以下常量形态仅用于说明默认值和字段命名，实际实现应写入 `config/gameplay_balance.json`，再由 `core/game_config.py` 暴露。

```python
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
    1: {"pressure": 55, "min_turns": 5, "requires_evidence": True},
    2: {"pressure": 70, "min_turns": 7, "requires_evidence": True},
    3: {"pressure": 85, "min_turns": 10, "requires_evidence": True},
}
# 持续判定窗口：pressure >= 阈值后，在接下来 5 轮内均视为满足条件
# （允许 pressure 因时间动态短暂回落，增加容错）
CONFESSION_PRESSURE_WINDOW = 5
# NOTE: requires_semantic 标志在 Phase 1 中暂不实现，Phase 2 再引入语义匹配

# ──────────────────────────────────────────────
# 压力系统
# ──────────────────────────────────────────────

# 压力段定义
DEFAULT_INITIAL_PRESSURE = 20  # 新局初始压力，替代当前实现中的 50

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
DEFAULT_EVIDENCE_USES = 4

# 证据类型对压力的基础增量
# v1.5 调整：在 AP/每轮制下，原 15/10/8 会让冷静+固执型在 12 轮内停在层级3。
# 18/12/9 可让最难型在 12 轮左右可达，但仍明显慢于胆小型。
EVIDENCE_PRESSURE_BASE = {
    "physical": 18,   # 物证：直接、难以否认
    "document": 12,   # 书证：间接但有力
    "testimony": 9,   # 证言：可反驳
}

# 证据强度系数（乘以基础增量）
EVIDENCE_STRENGTH_MULTIPLIER = 0.1  # strength 1-10，乘以 0.1 = 0.1-1.0

# ──────────────────────────────────────────────
# 恐惧值系统
# ──────────────────────────────────────────────

# 恐惧值默认
DEFAULT_FEAR = 50  # 0-100

# 恐惧对施压效果的影响系数
# 实际压力增量 = 基础压力增量 × soft_factor
# soft_factor = clamp((fear / FEAR_NEUTRAL) × (1 / (1 + defiance × 0.01)), 0.3, 1.5)
FEAR_NEUTRAL = 50  # fear=50时效果正常

# 压力综合系数软上限（防止极端性格差距过大）
PRESSURE_SOFT_FACTOR_MIN = 0.3
PRESSURE_SOFT_FACTOR_MAX = 1.5

# 恐惧自然冷却（每轮 -1，在 submit_action 末尾结算）
FEAR_PER_TURN_DECAY = -1

# 反扑：恐惧极低阈值（固定值，嫌疑人维度文档中定义动态化方案）
FEAR_PROVOCATION_THRESHOLD = 15  # fear<15 触发挑衅态度

# 出示错误证据的恐惧惩罚
FEAR_PENALTY_WRONG_EVIDENCE = 10

# ──────────────────────────────────────────────
# 嫌疑人多维隐藏指标
# ──────────────────────────────────────────────

# 维度边界
DIMENSION_BOUNDS = {
    "fear":                  {"min": 0,   "max": 100},
    "defiance":              {"min": 5,   "max": 100},  # 最低5，不归零
    "empathy_susceptibility": {"min": 0,   "max": 95},   # 最高95，保留一点抵抗
    "deception_skill":       {"min": 5,   "max": 100},  # 最低5，保留基础撒谎能力
    "loyalty":               {"min": 0,   "max": 100},
    "credibility":           {"min": 0,   "max": 100},
}

# 性格维度映射（7种性格，v1.3新增忠诚/孤僻）
PERSONALITY_DIMENSIONS = {
    "冷静":  {"fear": 30, "defiance": 70, "empathy_susceptibility": 30, "deception_skill": 60, "loyalty": 50},
    "暴躁":  {"fear": 60, "defiance": 30, "empathy_susceptibility": 50, "deception_skill": 20, "loyalty": 40},
    "狡猾":  {"fear": 40, "defiance": 50, "empathy_susceptibility": 20, "deception_skill": 80, "loyalty": 30},
    "胆小":  {"fear": 80, "defiance": 20, "empathy_susceptibility": 70, "deception_skill": 10, "loyalty": 60},
    "固执":  {"fear": 35, "defiance": 80, "empathy_susceptibility": 15, "deception_skill": 30, "loyalty": 70},
    "忠诚":  {"fear": 40, "defiance": 40, "empathy_susceptibility": 60, "deception_skill": 20, "loyalty": 90},
    "孤僻":  {"fear": 45, "defiance": 60, "empathy_susceptibility": 10, "deception_skill": 50, "loyalty": 20},
}

# 性格组合权重
PERSONALITY_PRIMARY_WEIGHT = 0.7
PERSONALITY_SECONDARY_WEIGHT = 0.3

# 每轮维度联动（在 submit_action 末尾执行）
DIMENSION_PER_TURN_EFFECTS = {
    "pressure_gt_60": {"defiance": -1},
    "pressure_lt_30": {"defiance": +1},
    "pressure_gt_70": {"deception_skill": -2},
    "fear_gt_70":     {"defiance": -2, "deception_skill": -3, "loyalty": -2},
    "fear_gt_60":     {"empathy_susceptibility": +1},
    "fear_lt_15":     {"defiance": +2},  # 挑衅反扑
    "defiance_gt_70": {"empathy_susceptibility": -1},
}

# 反扑触发条件
PROACTIVE_TRIGGERS = {
    "counter_attack": {"condition": "consecutive_rebuttal_success >= 2",
                       "effects": {"fear": +10, "defiance": +3}},
    "gloat":          {"condition": "rebuttal_believable == True",
                       "effects": {"fear": -5, "deception_skill": +1, "confession_progress": -0.05}},
    "provocation":    {"condition": "fear < 15",
                       "effects_per_turn": {"pressure": -2, "defiance": +2}},
    "probe":          {"condition": "pressure > 40 and fear < 20",
                       "effects_on_fail": {"fear": -10}},
    "recover":        {"condition": "consecutive_idle_turns >= 3",
                       "effects": {"defiance": +3, "fear": -5, "deception_skill": +2}},
}

# 可见性等级（玩家等级 → 可见维度）
DIMENSION_VISIBILITY = {
    1:  ["pressure", "confession_level"],                                    # Lv.1-4: 基础可见
    2:  ["pressure", "confession_level", "personality", "fear"],             # Lv.2+: 心理侧写(初级)
    10: ["pressure", "confession_level", "personality", "fear",
         "defiance", "empathy_susceptibility"],                              # Lv.10+: 高级侧写
    15: ["pressure", "confession_level", "personality", "fear",
         "defiance", "empathy_susceptibility", "deception_skill", "loyalty"], # Lv.15+: 大师侧写
}

# ──────────────────────────────────────────────
# 交互限制
# ──────────────────────────────────────────────

# 每个嫌疑人的自由聊天上限；证据/施压/共情不消耗该次数，但都会计入 turn_count
CHAT_TURNS_PER_SUSPECT = 12

# 每个嫌疑人的施压次数上限（第二次效果减半）
PRESSURE_USES_PER_SUSPECT = 2

# 每个嫌疑人的共情次数上限（第二次效果减半）
EMPATHY_USES_PER_SUSPECT = 2

# ──────────────────────────────────────────────
# 行动点数（AP）系统
# ──────────────────────────────────────────────

# 默认总行动点数（普通难度基准）
# v1.5 调整：22 AP 给标准成功路径留下约 2-4 AP 容错，避免一次误点直接崩盘。
DEFAULT_TOTAL_ACTION_POINTS = 22

# 各操作的行动点数消耗
ACTION_AP_COST = {
    "chat": 1,              # 对话：最基础操作
    "pressure": 2,          # 施压：强力操作
    "empathy": 2,           # 共情：与施压等价
    "present_evidence": 2,  # 出示证据：关键操作
}

# 错误操作的AP惩罚（额外扣减，不包含操作本身的AP消耗）
AP_PENALTY = {
    "wrong_evidence": 2,      # 出示错误证据：严重浪费
    "wrong_pressure": 1,      # 施压失误：轻度浪费
    "wrong_empathy": 1,       # 共情失误：轻度浪费
    "innocent_breakdown": 3,  # 无辜崩溃：严重后果
}

# 压力/恐惧每轮动态（每次操作后结算，取代原基于秒的时间动态）
PRESSURE_PER_TURN_DYNAMICS = {
    "decay_zone": (0, 30),    # 低压力自然衰减区间
    "decay_rate": -1,         # 每轮压力变化（低段衰减）
    "stable_zone": (30, 70),  # 稳定区间
    "stable_rate": 0,         # 稳定区不变化
    "growth_zone": (70, 100), # 高压力自然增长区间
    "growth_rate": 1,         # 每轮压力变化（高段增长）
    "pressure_floor": 15,     # 最低压力保护
}

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
        from core.game_config import (
            EVIDENCE_PRESSURE_BASE, EVIDENCE_STRENGTH_MULTIPLIER,
            FEAR_NEUTRAL, PRESSURE_SOFT_FACTOR_MIN, PRESSURE_SOFT_FACTOR_MAX,
        )
        base = EVIDENCE_PRESSURE_BASE.get(evidence_type, 10)
        strength = evidence.get("strength", 5)
        pressure_delta = int(base * (1 + strength * EVIDENCE_STRENGTH_MULTIPLIER))
        # 恐惧值和抗压性综合影响施压效果（带软上限，防止极端差距）
        fear_factor = suspect.fear / FEAR_NEUTRAL
        defiance_factor = 1.0 / (1.0 + suspect.defiance * 0.01)
        raw_factor = fear_factor * defiance_factor
        soft_factor = max(PRESSURE_SOFT_FACTOR_MIN, min(PRESSURE_SOFT_FACTOR_MAX, raw_factor))
        pressure_delta = int(pressure_delta * soft_factor)
        # 出示正确证据 → 恐惧上升（+8，与错误-10形成正向激励）
        suspect.fear = min(100, suspect.fear + 8)
        self.presented_evidence_ids.add(evidence_id)
    else:
        # 出示错误证据 → 恐惧下降 + 记录错误
        from core.game_config import FEAR_PENALTY_WRONG_EVIDENCE
        suspect.fear = max(0, suspect.fear - FEAR_PENALTY_WRONG_EVIDENCE)
        self.mistake_log.append({
            "type": "wrong_evidence",
            "evidence_id": evidence_id,
            "suspect_name": suspect.name,
            "turn": suspect.turn_count,
        })

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
    # 条件1：供词层级 4 → 完全崩溃（主要胜利条件）
    if suspect.confession_level >= 4 and self.state != "breakdown":
        self.state = "breakdown"
        return StateChangeEvent(
            type="state_change",
            new_state="breakdown",
            verdict_reason=f"{suspect.name} 完全崩溃认罪",
        )

    # 条件2：secret_triggered + 高供词层级 → 完美胜利（彩蛋，不纳入平衡基准）
    if result.get("secret_triggered") and suspect.confession_level >= 3:
        self.state = "breakdown"
        return StateChangeEvent(
            type="state_change",
            new_state="breakdown",
            verdict_reason=f"{suspect.name} 泄露了秘密: {result['secret_triggered']}",
        )

    # 条件3：部分突破（供词层级>=2 + pressure>=60）→ 不结束游戏，但解锁额外信息
    if suspect.confession_level >= 2 and suspect.pressure >= 60 and self.state == "interrogating":
        # 部分胜利不返回 StateChangeEvent，而是发送系统提示
        # 由调用方决定是否继续审讯或切换嫌疑人
        pass  # 部分突破状态由 UI 层展示，不强制结束

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
    self.action_points_remaining: int = case_data.get(
        "total_action_points", DEFAULT_TOTAL_ACTION_POINTS
    )
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
    ActionPointUpdateEvent,
    ConfessionUpdateEvent,
]
```

### 1.5.2 修改 `core/suspect_agent.py` — 新增供词属性

在 `__init__` 中新增:
```python
self.confession_level: int = 0       # 当前供词层级 (0-4)
self.confession_progress: float = 0.0  # 当前层级反馈进度 (0.0-1.0)，不作为硬升级门槛
self.turn_count: int = 0             # 行动轮次计数：chat / pressure / empathy / present_evidence 都计入
```

> v1.5 口径：`confession_progress` 是反馈指标和 UI 节奏条，不是升级硬门槛。真正的升级判定以 `pressure + turn_count + related_evidence` 为准。原因是按当前 `0.02/0.05/0.10/0.15` 速率，若强制要求进度到 1.0，12 轮目标会数学上不可达。若未来想把进度改为硬门槛，必须重新调高进度速率并重新跑平衡模拟。

### 1.5.3 新增供词判定方法

在 `SuspectAgent` 中新增:
```python
def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
    """检查是否满足供词升级条件，返回升级后的层级或 None。

    v1.5: confession_progress 不参与硬判定，仅用于 UI 反馈。

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

    # 所有条件满足，升级。升级瞬间视为当前层进度已完成，然后重置下一层进度。
    self.confession_progress = 1.0
    self.confession_level = next_level
    self.confession_progress = 0.0
    return next_level

def update_confession_progress(self) -> float:
    """根据当前压力更新供词反馈进度，返回更新后的进度值。

    注意：该进度只用于 UI/复盘反馈，不阻塞 check_confession_upgrade。
    """
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

新增 `action_points_remaining` 的序列化：
```python
# to_dict 中:
"action_points_remaining": self.action_points_remaining,

# from_dict 中:
engine.action_points_remaining = state.get("action_points_remaining", DEFAULT_TOTAL_ACTION_POINTS)
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

### 1.8.0 新增真凶字段（评分与错误惩罚的前置依赖）

在 `CASE_SCHEMA.required` 与顶层 `properties` 中新增：

```python
"required": [
    "case_id",
    "title",
    "victim",
    "cause_of_death",
    "crime_scene",
    "truth",
    "culprit_name",
    "suspects",
    "evidences",
    "interrogation_time_limit_sec",
],
"properties": {
    # ... 现有字段 ...
    "culprit_name": {"type": "string"},  # 真凶姓名，必须匹配 suspects[].name 中的一项
}
```

新增业务校验：

```python
suspect_names = {s["name"] for s in case_dict.get("suspects", [])}
if case_dict.get("culprit_name") not in suspect_names:
    raise ValidationError("culprit_name 必须匹配某个 suspects[].name")
```

> v1.5 口径：`culprit_name` 是真凶的唯一数据源。不要依赖 LLM 在 `truth` 文本里反推真凶，也不要用可选的 `is_culprit` 做评分依据。运行时如需 `is_culprit`，由 `culprit_name` 派生。

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

在 `CASE_SCHEMA` 的 `suspects.items.properties` 中新增隐藏维度字段：

```python
"suspects": {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["name", "role", "personality", "knowledge", "forbidden_to_reveal"],
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string"},
            "personality": {"type": "string"},
            "knowledge": {"type": "string"},
            "forbidden_to_reveal": {"type": "array", "items": {"type": "string"}},
            "personality_secondary": {"type": "string"},  # v1.3: 主+副性格组合
            # 新增隐藏维度（可选，向后兼容）
            "fear": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
            "defiance": {"type": "integer", "minimum": 5, "maximum": 100, "default": 50},
            "empathy_susceptibility": {"type": "integer", "minimum": 0, "maximum": 95, "default": 50},
            "deception_skill": {"type": "integer", "minimum": 5, "maximum": 100, "default": 50},
            "loyalty": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
        },
        "additionalProperties": False,
    },
},
```

修改生成提示词，在顶层字段增加：
```
"culprit_name": "字符串，真凶姓名，必须等于 suspects 中某个 name。全案只能有一个真凶。",
```

修改生成提示词，在 evidences 部分增加：
```
"type": "字符串，证据类型：physical(物证)/document(书证)/testimony(证言)",
"strength": "整数1-10，证据强度，10为最强",
```

修改生成提示词，在 suspects 部分增加：
```
"personality_secondary": "字符串，副性格类型（可选）：冷静/暴躁/狡猾/胆小/固执/忠诚/孤僻。与主性格组合形成更丰富的心理画像。如果缺失则按主性格100%计算。",
"fear": "整数0-100，恐惧值，胆小性格80+，冷静性格20-40",
"defiance": "整数5-100，抗压性，固执性格80+，胆小性格20-30。最低5不归零",
"empathy_susceptibility": "整数0-95，共情易感性，胆小/暴躁性格50+，狡猾性格20-30。最高95保留一点抵抗",
"deception_skill": "整数5-100，欺骗技巧，狡猾性格80+，胆小/暴躁性格10-30。最低5保留基础撒谎能力",
"loyalty": "整数0-100，对同伙的忠诚度，固执/忠诚性格70+，狡猾性格20-40",
```

---

## 1.9 恐惧值系统

### 设计

恐惧值(fear)是嫌疑人对审讯员的畏惧感指标，与压力值交互：
- **恐惧影响施压效果**：实际压力增量 = 基础压力增量 × (fear / 50) × defiance系数
- **恐惧过低时施压效果极弱**：fear=10 时施压效果仅为正常的20%
- **恐惧极低触发反扑**：fear<15 时嫌疑人转为挑衅态度（pressure每轮-2, defiance每轮+2）
- **恐惧动态变化**：恐惧不是静态值，随操作和状态持续变化

完整恐惧值定义和触发器详见 [`suspect-dimensions.md`](suspect-dimensions.md) §3。

### 修改 `core/suspect_agent.py` — 新增恐惧值属性

在 `__init__` 中新增:

```python
self.fear: int = suspect_data.get("fear", 50)
```

### 修改 `core/interrogation.py` — 恐惧值动态变化

在 `submit_action` 中实现恐惧值的完整触发逻辑：

```python
from core.game_config import FEAR_NEUTRAL, DIMENSION_BOUNDS

# 出示正确证据 → fear+8（与错误-10形成正向净效应）
if evidence.get("related_suspect") == suspect.name:
    suspect.fear = min(DIMENSION_BOUNDS["fear"]["max"], suspect.fear + 8)

# 出示错误证据 → fear-10
else:
    suspect.fear = max(DIMENSION_BOUNDS["fear"]["min"], suspect.fear - 10)
    self.mistake_log.append({...})

# 施压成功(对真凶) → fear+5
# 施压失败(对无辜者) → fear-5
# 共情 → fear -10 × (empathy/50)
# 对真凶共情(错误) → fear+5
# 反驳成功 → fear-5
# 反扑:反击质问 → fear+10
# 被同伴出卖 → fear+10
```

恐惧自然冷却在 `submit_action` 末尾实现（每轮 -1）。

### 新增事件类型

**修改 `schemas/events.py`**:

```python
class FearUpdateEvent(TypedDict):
    type: Literal["fear_update"]
    suspect_index: int
    fear: int
    reason: str  # "wrong_evidence" / "pressure_success" / "natural_decay"

# 更新 UIEvent 联合类型
UIEvent = Union[
    NewMessageEvent,
    SuspectUpdateEvent,
    StateChangeEvent,
    ActionPointUpdateEvent,
    ConfessionUpdateEvent,
    FearUpdateEvent,
]
```

### 在 `submit_action` 中发送恐惧事件

```python
if old_fear != suspect.fear:
    fear_event: FearUpdateEvent = {
        "type": "fear_update",
        "suspect_index": self.current_suspect_index,
        "fear": suspect.fear,
        "reason": "wrong_evidence" if suspect.fear < old_fear else "pressure_success",
    }
    events.append(fear_event)
```

### 新增 `InterrogationEngine` 属性

在 `__init__` 中新增:

```python
self.mistake_log: List[dict] = []  # 错误操作记录
```

### 恐惧值 UI

在嫌疑人卡片的压力条下方新增恐惧值显示：

```html
<div class="fear-section">
    <div class="fear-label">
        <span class="fear-title">恐惧值</span>
        <span class="fear-value" id="fear-value">50</span>
    </div>
    <div class="fear-bar-container">
        <div class="fear-bar" id="fear-bar" style="width: 50%;"></div>
    </div>
</div>
```

恐惧值条颜色：低恐惧(0-30)蓝色（冷静），中恐惧(30-70)黄色，高恐惧(70-100)红色。

### 新增信号

```python
# web_bridge.py
fear_update = Signal(int, int, str)  # suspect_index, fear_value, reason
```

---

## 1.10 嫌疑人多维隐藏指标

### 设计

每个嫌疑人拥有6个隐藏心理维度（+2个可见维度 = 8指标）：
- **全部动态变化**：所有隐藏维度随审讯过程动态变化，不是初始化后不变的死值
- **维度间联动**：维度之间互相影响，形成正/负反馈循环
- **默认不可见**：玩家只能看到 pressure 和 confession_level
- **按等级解锁可见**：使用心理侧写技能可逐步解锁（详见 Phase 3a 三级侧写体系）
- **有边界约束**：各维度有 min/max 边界，不会无限增长或归零

完整维度定义、触发器和联动规则详见 [`suspect-dimensions.md`](suspect-dimensions.md)。

### 8个指标总览

| 指标 | 可见性 | 值域 | 初始值 | 动态性 |
|------|--------|------|--------|--------|
| pressure | 始终可见 | 0-100 | 20（固定） | 高度动态 |
| confession_level | 始终可见 | 0-4 | 0 | 阶梯升级 |
| fear | Lv.2+ | 0-100 | 性格计算 | 高度动态 |
| defiance | Lv.10+ | 5-100 | 性格计算 | 中度动态 |
| empathy_susceptibility | Lv.10+ | 0-95 | 性格计算 | 中度动态 |
| deception_skill | Lv.15+ | 5-100 | 性格计算 | 中度动态 |
| loyalty | Lv.15+ | 0-100 | 性格计算 | 中度动态 |
| credibility | 不可见 | 0-100 | 50 | 低度动态 |

### 修改 `core/suspect_agent.py` — 新增隐藏维度属性

在 `__init__` 中新增:

```python
self.pressure: int = DEFAULT_INITIAL_PRESSURE
self.fear: int = suspect_data.get("fear", DEFAULT_FEAR)
self.defiance: int = suspect_data.get("defiance", 50)
self.empathy_susceptibility: int = suspect_data.get("empathy_susceptibility", 50)
self.deception_skill: int = suspect_data.get("deception_skill", 50)
self.loyalty: int = suspect_data.get("loyalty", 50)
self.credibility: int = 50  # 不可见，固定初始值
```

如果 `suspect_data` 中没有提供维度值，根据主+副性格字段从 `PERSONALITY_DIMENSIONS` 查找并加权计算：

```python
from core.game_config import (
    PERSONALITY_DIMENSIONS,
    PERSONALITY_PRIMARY_WEIGHT,
    PERSONALITY_SECONDARY_WEIGHT,
)

primary = suspect_data.get("personality", "")
secondary = suspect_data.get("personality_secondary", "")
primary_dims = PERSONALITY_DIMENSIONS.get(primary, {})
secondary_dims = PERSONALITY_DIMENSIONS.get(secondary, {})

if primary_dims and secondary_dims:
    # 主+副性格加权
    for dim in ["fear", "defiance", "empathy_susceptibility", "deception_skill", "loyalty"]:
        calculated = primary_dims.get(dim, 50) * PERSONALITY_PRIMARY_WEIGHT + \
                     secondary_dims.get(dim, 50) * PERSONALITY_SECONDARY_WEIGHT
        setattr(self, dim, suspect_data.get(dim, int(calculated)))
elif primary_dims:
    # 仅主性格
    for dim in primary_dims:
        setattr(self, dim, suspect_data.get(dim, primary_dims[dim]))
```

### 修改 `core/interrogation.py` — 每轮维度联动

在 `submit_action` 末尾新增每轮维度联动检查：

```python
def _apply_dimension_per_turn_effects(self, suspect) -> List[UIEvent]:
    """每轮维度联动效果。"""
    from core.game_config import DIMENSION_PER_TURN_EFFECTS, DIMENSION_BOUNDS
    
    changes = {}
    
    if suspect.pressure > 60:
        changes["defiance"] = changes.get("defiance", 0) - 1
    if suspect.pressure < 30:
        changes["defiance"] = changes.get("defiance", 0) + 1
    if suspect.pressure > 70:
        changes["deception_skill"] = changes.get("deception_skill", 0) - 2
    if suspect.fear > 70:
        changes["defiance"] = changes.get("defiance", 0) - 2
        changes["deception_skill"] = changes.get("deception_skill", 0) - 3
        changes["loyalty"] = changes.get("loyalty", 0) - 2
    if suspect.fear > 60:
        changes["empathy_susceptibility"] = changes.get("empathy_susceptibility", 0) + 1
    if suspect.fear < 15:
        changes["defiance"] = changes.get("defiance", 0) + 2
    if suspect.defiance > 70:
        changes["empathy_susceptibility"] = changes.get("empathy_susceptibility", 0) - 1
    
    # 应用变化（受边界约束）
    for dim, delta in changes.items():
        if delta == 0:
            continue
        old_val = getattr(suspect, dim)
        bounds = DIMENSION_BOUNDS.get(dim, {"min": 0, "max": 100})
        new_val = max(bounds["min"], min(bounds["max"], old_val + delta))
        setattr(suspect, dim, new_val)
    
    return []  # 维度变化事件可选发送
```

### 序列化

```python
# to_dict 中:
{
    "name": suspect.name,
    "pressure": suspect.pressure,
    "memory": suspect.memory,
    "confession_level": suspect.confession_level,
    "confession_progress": suspect.confession_progress,
    "turn_count": suspect.turn_count,
    "fear": suspect.fear,
    "defiance": suspect.defiance,
    "empathy_susceptibility": suspect.empathy_susceptibility,
    "deception_skill": suspect.deception_skill,
    "loyalty": suspect.loyalty,
    "credibility": suspect.credibility,
}

# from_dict 中:
engine.suspects[i].fear = suspect_state.get("fear", 50)
engine.suspects[i].defiance = suspect_state.get("defiance", 50)
engine.suspects[i].empathy_susceptibility = suspect_state.get("empathy_susceptibility", 50)
engine.suspects[i].deception_skill = suspect_state.get("deception_skill", 50)
engine.suspects[i].loyalty = suspect_state.get("loyalty", 50)
engine.suspects[i].credibility = suspect_state.get("credibility", 50)
```

---

## 1.11 施压/共情交互限制

### 设计（混合方案）

- **聊天轮次限制**：每个嫌疑人最多12轮对话，超过后该嫌疑人"拒绝再说话"
- **施压限制**：每个嫌疑人可施压2次，第二次效果减半（如+15→+8）
- **共情限制**：每个嫌疑人可共情2次，第二次效果减半（如fear-10→fear-5）

### 修改 `core/interrogation.py` — 新增交互追踪

在 `__init__` 中新增:

```python
from core.game_config import CHAT_TURNS_PER_SUSPECT, PRESSURE_USES_PER_SUSPECT, EMPATHY_USES_PER_SUSPECT

# 每个嫌疑人的交互使用次数
self.chat_turns_remaining: List[int] = [CHAT_TURNS_PER_SUSPECT] * len(self.suspects)
self.pressure_uses_remaining: List[int] = [PRESSURE_USES_PER_SUSPECT] * len(self.suspects)
self.empathy_uses_remaining: List[int] = [EMPATHY_USES_PER_SUSPECT] * len(self.suspects)
```

### 在 `submit_action` 中检查交互限制

```python
# 检查聊天轮次
if self.chat_turns_remaining[self.current_suspect_index] <= 0:
    events.append(self._system_message(
        f"{suspect.name} 拒绝再和你说话了。"
    ))
    return events

    # 检查行动点数
    from core.game_config import ACTION_AP_COST
    ap_cost = ACTION_AP_COST.get(action, 1)
    if self.action_points_remaining < ap_cost:
        events.append(self._system_message(
            f"行动点数不足（需要{ap_cost}AP，剩余{self.action_points_remaining}AP）。"
        ))
        return events

    # 根据操作类型扣减对应次数
    if action == "pressure":
        if self.pressure_uses_remaining[self.current_suspect_index] <= 0:
            events.append(self._system_message(
                f"你已经对 {suspect.name} 施压过了。"
            ))
            return events
        # 第二次施压效果减半标记
        self._pressure_half_effect = self.pressure_uses_remaining[self.current_suspect_index] <= 1
        self.pressure_uses_remaining[self.current_suspect_index] -= 1
    elif action == "empathy":
        if self.empathy_uses_remaining[self.current_suspect_index] <= 0:
            events.append(self._system_message(
                f"你已经对 {suspect.name} 共情过了。"
            ))
            return events
        # 第二次共情效果减半标记
        self._empathy_half_effect = self.empathy_uses_remaining[self.current_suspect_index] <= 1
        self.empathy_uses_remaining[self.current_suspect_index] -= 1

    # 扣减行动点数
    self.action_points_remaining -= ap_cost
```

### 交互限制 UI

在嫌疑人卡片中显示剩余交互次数：

```html
<div class="interaction-limits">
    <span class="limit-badge" id="chat-remaining">💬 12</span>
    <span class="limit-badge" id="pressure-remaining">👊 2</span>
    <span class="limit-badge" id="empathy-remaining">🤝 2</span>
</div>
```

当某个限制接近耗尽时（聊天剩余 ≤ 2），高亮警告。

### 新增信号

```python
# web_bridge.py
interaction_limits_update = Signal(int, int, int, int)  # suspect_index, chat, pressure, empathy
```

---

## 1.12 存档兼容

`to_dict()` / `from_dict()` 需要向后兼容旧存档（没有新字段时使用默认值）。

已在 1.5.5 中通过 `.get("field", default)` 实现，1.10 中新增了隐藏维度的序列化。

**特别注意**：
- `SuspectAgent.__init__` 中的新字段（`confession_level`, `confession_progress`, `turn_count`, `fear`, `defiance`, `empathy_susceptibility`, `deception_skill`, `loyalty`）已设置默认值
- `InterrogationEngine.__init__` 中的 `evidence_uses_remaining` 已使用 `case_data.get("evidence_uses", DEFAULT_EVIDENCE_USES)`
- 旧存档加载时，缺失的新字段会自动使用默认值
- 交互限制字段（`chat_turns_remaining`, `pressure_uses_remaining`, `empathy_uses_remaining`）存档时需序列化，读档时恢复

**新增序列化**：

```python
# to_dict 中:
"chat_turns_remaining": self.chat_turns_remaining,
"pressure_uses_remaining": self.pressure_uses_remaining,
"empathy_uses_remaining": self.empathy_uses_remaining,
"mistake_log": self.mistake_log,

# from_dict 中:
engine.chat_turns_remaining = state.get("chat_turns_remaining",
    [CHAT_TURNS_PER_SUSPECT] * len(engine.suspects))
engine.pressure_uses_remaining = state.get("pressure_uses_remaining",
    [PRESSURE_USES_PER_SUSPECT] * len(engine.suspects))
engine.empathy_uses_remaining = state.get("empathy_uses_remaining",
    [EMPATHY_USES_PER_SUSPECT] * len(engine.suspects))
engine.mistake_log = state.get("mistake_log", [])
```

---

## 1.13 测试计划

### 单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `tests/test_confession.py` (新) | 供词层级升级逻辑、进度更新、阈值边界条件 |
| `tests/test_evidence_rework.py` (新) | respond_evidence 不传证据名、证据次数限制、压力程序化计算、恐惧系数 |
| `tests/test_game_config.py` (新) | 默认配置加载、临时配置覆盖、非法配置校验、PERSONALITY_DIMENSIONS 映射 |
| `tests/test_victory_conditions.py` (新) | `_check_victory` 各条件优先级、低供词层级拦截、高供词层级触发 |
| `tests/test_fear_system.py` (新) | 恐惧值初始值、错误证据恐惧下降、恐惧系数影响施压效果 |
| `tests/test_hidden_dimensions.py` (新) | 隐藏维度默认值、性格映射、综合压力公式 |
| `tests/test_interaction_limits.py` (新) | 聊天轮次限制、施压/共情次数限制、耗尽后拒绝交互 |

### 集成测试

| 测试 | 说明 |
|------|------|
| 证据出示不触发自动胜利 | 出示含关键词证据后，`_postprocess` 应拦截（低供词层级） |
| 证据次数耗尽后无法出示 | 尝试出示应返回系统消息 |
| 供词层级递进 | 模拟高压+多轮对话，验证层级升级 |
| 存档/读档兼容 | 新字段序列化/反序列化正确，旧存档加载不崩溃 |
| 压力动态更新 | 验证 `_get_system_message` 使用当前压力值 |
| 恐惧-压力交互 | 出示错误证据→恐惧下降→后续施压效果减弱 |
| 多维指标综合计算 | 验证 fear × defiance 综合影响压力增量 |
| 交互限制耗尽 | 自由聊天12轮后嫌疑人拒绝，施压/共情各2次后不可再使用；第二次效果减半 |
| 配置覆盖生效 | 使用临时 `gameplay_balance.json` 修改AP/证据基值/阈值后，引擎行为随配置变化 |

### 回归测试

| 测试 | 说明 |
|------|------|
| 现有 `test_engine.py` 通过 | 确保不破坏现有逻辑 |
| 现有 `test_suspect.py` 通过 | `respond()` 行为不变（除 pressure_change 不再返回） |
| 现有 `test_web_integration.py` 通过 | UI 事件流正常 |

---

## 1.14 弱模型执行任务包与验收

Phase 1 是后续所有阶段的地基，不建议一次性交给弱模型完整实现。必须拆成以下任务包，每包独立提交、独立测试。

### 任务包拆分

| 包 | 范围 | 允许修改 | 不允许修改 | 验收重点 |
|----|------|----------|------------|----------|
| 1a 配置与Schema | 新增 `gameplay_balance.json`、加载器、`culprit_name`、证据字段、维度默认值 | `config/gameplay_balance.json`, `core/game_config.py`, `core/case_generator.py`, `tests/test_game_config.py`, `tests/test_case_schema.py` | 不改 `submit_action`、不改 UI | 默认值、覆盖配置、Schema校验、旧mock case兼容 |
| 1b LLM调用隔离 | 抽取 `_call_llm`、动态系统提示词、fake LLM测试入口 | `core/suspect_agent.py`, `tests/test_suspect_agent.py` | 不改胜利判定、不改前端 | pressure 使用当前值，LLM不返回 `pressure_change` |
| 1c 证据与胜利入口 | `respond_evidence`、程序化压力、`_check_victory`、低层级拦截 | `core/interrogation.py`, `core/suspect_agent.py`, `tests/test_evidence_rework.py`, `tests/test_victory_conditions.py` | 不改 UI 样式、不加工具系统 | 出示证据不自动胜利，层级>=3才可触发秘密胜利 |
| 1d AP与交互限制 | AP扣减、证据次数、聊天/施压/共情次数 | `core/interrogation.py`, `tests/test_interaction_limits.py` | 不改 LLM prompt | 普通22 AP路径可用，错误证据额外-2 AP |
| 1e 维度与存档 | fear/defiance等维度、每轮联动、序列化兼容 | `core/suspect_agent.py`, `core/interrogation.py`, `tests/test_hidden_dimensions.py`, `tests/test_save_load.py` | 不改 UI | 旧存档可加载，新字段可恢复 |
| 1f UI事件 | 供词、恐惧、证据状态、交互限制前端展示 | `schemas/events.py`, `ui/web_bridge.py`, `ui/web_main_window.py`, `ui/web/js/`, `ui/web/css/`, `tests/test_web_integration.py` | 不改核心公式 | 事件字段一致，前端状态更新正确 |
| 1g 平衡验证 | 42组合模拟、最难/最易边界测试 | `tests/test_balance.py`, `tests/fixtures/` | 不改业务逻辑 | 胜率与AP目标落在v1.5范围 |

### Definition of Ready

| 条件 | 要求 |
|------|------|
| 测试夹具 | 已有 mock case 覆盖 `culprit_name`、2-3个嫌疑人、3类证据、至少1条错误证据路径 |
| LLM隔离 | fake LLM 能返回固定 `{reply, secret_triggered, rebuttal_believable}` |
| 基线测试 | 修改前 `pytest tests/ -m "not slow and not real_api" -v` 可运行，若失败需记录已有失败 |
| 任务边界 | 每个任务包有明确目标文件和验收命令，不跨包顺手重构 |
| 配置边界 | 已明确本包新增的配置字段路径和默认值，禁止把数值直接写进业务文件 |

### Definition of Done

| 条件 | 要求 |
|------|------|
| 单包测试 | 对应任务包测试全部通过 |
| 快速回归 | `pytest tests/ -m "not slow and not real_api" -v` 通过 |
| 数值配置 | 默认配置断言覆盖普通AP=22、初始压力20、证据基值18/12/9、阈值40/55/70/85；临时配置覆盖后行为同步变化 |
| 存档兼容 | 旧状态缺字段时使用默认值，不抛异常 |
| UI一致 | 新增事件在 `schemas/events.py`、WebBridge、前端处理函数中字段名一致 |
| 无真实API | 测试不调用真实LLM，不要求API key |

### 阶段验收场景

| 场景 | 验收方式 |
|------|----------|
| 关键词证据不秒赢 | fake LLM 回复包含 forbidden 关键词，但供词层级<3时不进入胜利 |
| 正确证据推进 | 出示相关物证后 fear+8、pressure按18基值和soft_factor变化 |
| 错误证据惩罚 | 出示无关证据后 fear-10、AP额外-2、mistake_log记录 |
| 供词层级升级 | pressure/turn/evidence满足条件时逐层升级，`confession_progress` 不阻塞升级 |
| 交互耗尽 | 自由聊天12轮后拒绝；施压/共情各2次后拒绝，第二次效果减半 |
| 旧存档兼容 | 旧fixture不含新字段仍可加载，并补齐默认值 |
| 平衡模拟 | 普通难度42组合胜率30%-80%，最难组合不低于20%，最易组合不高于90% |
| 调参无改码 | 将普通AP改为24或物证基值改为20后，只改配置文件即可让测试观察到差异 |

---

## 实施顺序建议

```
1.1  gameplay_balance.json + game_config.py（无依赖，先建配置文件、加载器和校验器，含恐惧、隐藏维度、交互限制配置）
    ↓
1.2  _call_llm 抽取 + _get_system_message 动态化（基础改造）
    ↓
1.7  修复静态提示词（与 1.2 同步做）
    ↓
1.10 嫌疑人多维隐藏指标（SuspectAgent 新属性，独立于 1.2）
    ↓
1.2  respond_evidence + 引擎重构（核心改动，含恐惧系数）
    ↓
1.2  _postprocess 联动改造 + _check_victory 统一入口（P0修复）
    ↓
1.9  恐惧值系统（依赖 1.2 + 1.10）
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
1.11 施压/共情交互限制（依赖 1.10 + 引擎改造）
    ↓
1.12 存档兼容（依赖 1.2 + 1.5 + 1.9 + 1.10 + 1.11）
    ↓
1.13 测试（最后）
```

---

## Phase 1 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.3 优化方案 | 原因 |
|--------|------------|--------------|------|
| `_postprocess` | 原样保留，触发即胜利 | 低供词层级拦截，>=3才触发 | P0：防止绕过供词系统 |
| 压力来源 | LLM返回`pressure_change`+引擎硬编码+20 | 引擎程序化计算并从配置读取默认基值，LLM不返回 | P1：避免双重计算 |
| `respond()`/`respond_evidence()` | 各30行重复代码 | 抽取`_call_llm()`公共方法 | P1：消除代码重复 |
| 胜利判定 | 分散在`submit_action`中 | 统一`_check_victory()`入口 | P1：避免双重判定 |
| `requires_semantic` | 定义在阈值中但无实现 | Phase 1移除，Phase 2实现 | P1：避免未完成的功能 |
| 配置文件 | Python常量或一次性包含Phase 1-4所有配置 | `config/gameplay_balance.json` 按阶段追加字段，`game_config.py` 仅加载/校验/提供访问器 | P2：减少早期测试负担，并支持调参 |
| 嫌疑人维度 | 仅 pressure/confession | 8指标(2可见+6隐藏) | P0：增加个体差异和策略深度 |
| 施压效果 | 固定公式计算 | fear × defiance 综合系数 | P0：恐惧影响施压，错误操作有惩罚 |
| 交互限制 | 无限制 | 默认自由聊天12轮/人 + 施压2次/人 + 共情2次/人（第二次减半），均从配置读取 | P0：避免无限试错，同时保留基本容错 |
| 错误操作 | 无惩罚 | fear-10 + mistake_log 记录 | P1：增加策略博弈 |
| 隐藏维度 | 初始化后不变 | 全维度动态变化+维度联动 | P0：维度间正/负反馈循环 |
| 性格系统 | 5种离散类型 | 7种+主副组合(0.7+0.3加权) | P1：更丰富心理画像 |
| 维度边界 | 无 | 各维度min/max约束 | P1：defiance最低5等 |
| 反扑机制 | 无 | 5种反扑行为 | P0：嫌疑人主动博弈 |
| credibility | 无 | 新增不可见属性，影响反驳判定 | 增强：辅助程序化判定 |

(End of file - total 643 lines)
