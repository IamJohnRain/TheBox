# Phase 4：评分与难度 — LLM 评分 + 难度分级

## 前置依赖

Phase 1-3 完成。

## 目标

引入 LLM 驱动的多维评分系统和案件难度分级，完善游戏循环的反馈和长期目标。

## 任务清单

| # | 任务 | 涉及文件 | 预估工作量 |
|---|------|---------|-----------|
| 4.1 | 评分系统引擎 | `core/scoring.py` (新) | 中 |
| 4.2 | 评分结果 UI | `ui/web/` | 中 |
| 4.3 | 经验结算 | `core/player.py`, `ui/web_main_window.py` | 小 |
| 4.4 | 难度分级系统 | `core/case_generator.py`, `core/game_config.py` | 小 |
| 4.5 | 难度选择 UI | `ui/web/` | 小 |
| 4.6 | 测试 | `tests/` | 中 |

---

## 4.1 评分系统引擎

### 新建 `core/scoring.py`

```python
"""LLM-based scoring system for interrogation sessions."""

import json
import logging
from typing import Dict, Any, Optional
from core.llm_client import llm_client, NetworkError, LLMResponseError

logger = logging.getLogger(__name__)


# 评分维度定义
SCORING_DIMENSIONS = {
    "confession_depth": {"weight": 0.30, "desc": "供词深度：最终供词层级"},
    "time_efficiency": {"weight": 0.20, "desc": "时间效率：剩余时间占比"},
    "evidence_usage": {"weight": 0.20, "desc": "证据利用：正确出示的证据占比"},
    "interrogation_strategy": {"weight": 0.15, "desc": "审讯策略：工具使用、施压共情交替"},
    "reasoning_accuracy": {"weight": 0.15, "desc": "推理准确：玩家推理与真相吻合度"},
}

# 评级阈值
GRADE_THRESHOLDS = [
    ("S", 90),
    ("A", 75),
    ("B", 60),
    ("C", 40),
    ("D", 0),
]

# 评级经验系数
GRADE_EXP_MULTIPLIER = {
    "S": 1.5,
    "A": 1.2,
    "B": 1.0,
    "C": 0.8,
    "D": 0.5,
}


def calculate_score(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算审讯评分。

    Args:
        session_data: 包含以下字段的字典:
            - truth: 案件真相
            - memory_summary: 对话摘要
            - presented_evidence: 已出示证据列表
            - used_tools: 已使用工具列表
            - confession_level: 最终供词层级
            - time_left: 剩余时间
            - total_time: 总时间
            - total_evidence: 总证据数
            - suspect_name: 被审讯嫌疑人名

    Returns:
        包含各维度分数、总分、评级的字典
    """
    scores = {}

    # ── 规则计算的维度 ──

    # 时间效率
    time_left = session_data.get("time_left", 0)
    total_time = session_data.get("total_time", 1)
    scores["time_efficiency"] = min(100, int((time_left / max(total_time, 1)) * 100))

    # 证据利用
    presented = len(session_data.get("presented_evidence", []))
    total_ev = session_data.get("total_evidence", 1)
    scores["evidence_usage"] = min(100, int((presented / max(total_ev, 1)) * 100))

    # 供词深度
    confession_level = session_data.get("confession_level", 0)
    scores["confession_depth"] = min(100, confession_level * 25)

    # ── LLM 判断的维度 ──

    # 审讯策略和推理准确度由 LLM 评分
    llm_scores = _llm_score(session_data)
    scores["interrogation_strategy"] = llm_scores.get("interrogation_strategy", 50)
    scores["reasoning_accuracy"] = llm_scores.get("reasoning_accuracy", 50)

    # ── 加权总分 ──
    total = 0
    for dim, config in SCORING_DIMENSIONS.items():
        total += scores.get(dim, 0) * config["weight"]
    total = int(total)

    # ── 评级 ──
    grade = "D"
    for g, threshold in GRADE_THRESHOLDS:
        if total >= threshold:
            grade = g
            break

    return {
        "dimensions": scores,
        "total_score": total,
        "grade": grade,
        "exp_multiplier": GRADE_EXP_MULTIPLIER.get(grade, 1.0),
        "detail": llm_scores.get("detail", ""),
    }


def _llm_score(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 进行审讯策略和推理准确度评分。"""
    if not llm_client.is_initialized:
        return {"interrogation_strategy": 50, "reasoning_accuracy": 50, "detail": "LLM 未初始化"}

    truth = session_data.get("truth", "")
    memory = session_data.get("memory_summary", "")
    tools = session_data.get("used_tools", [])

    prompt = f"""你是一个游戏评分专家。请对以下审讯表现进行评分。

案件真相: {truth}

审讯对话摘要:
{memory}

使用过的工具: {', '.join(tools) if tools else '无'}

请从以下两个维度评分（0-100分）：

1. 审讯策略（interrogation_strategy）：玩家是否合理使用了施压/共情交替、工具使用时机、审讯节奏等
2. 推理准确（reasoning_accuracy）：玩家的提问和推理是否接近案件真相

请以 JSON 格式输出：
{{
    "interrogation_strategy": 分数,
    "reasoning_accuracy": 分数,
    "detail": "简短的评语（50字以内）"
}}"""

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
        )
        if not raw:
            raise LLMResponseError("LLM 返回空内容")
        text = raw.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except (NetworkError, LLMResponseError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"LLM 评分失败: {exc}")
        return {"interrogation_strategy": 50, "reasoning_accuracy": 50, "detail": "评分失败"}
```

---

## 4.2 评分结果 UI

### 结局面板扩展

修改 `_handle_ending` 方法，在结局对话框中展示评分：

```python
def _handle_ending(self, event):
    # ... 现有逻辑 ...

    # 计算评分
    from core.scoring import calculate_score
    score_data = calculate_score({
        "truth": self.engine.case.get("truth", ""),
        "memory_summary": self._get_memory_summary(),
        "presented_evidence": list(self.engine.presented_evidence_ids),
        "used_tools": self.engine.used_tools,
        "confession_level": suspect.confession_level,
        "time_left": self.engine.time_left,
        "total_time": self.engine.case.get("interrogation_time_limit_sec", 300),
        "total_evidence": len(self.engine.case.get("evidences", [])),
        "suspect_name": suspect.name,
    })

    # 发送评分数据到前端
    self.bridge.show_score_panel.emit(json.dumps(score_data))
```

### 评分面板 HTML

```html
<div class="score-panel" id="score-panel" style="display: none;">
    <h2 class="score-title">审讯报告</h2>
    <div class="score-grade" id="score-grade">B</div>
    <div class="score-total" id="score-total">72分</div>
    <div class="score-dimensions">
        <!-- 各维度分数条 -->
    </div>
    <div class="score-detail" id="score-detail"></div>
    <div class="score-exp">
        <span>获得经验: </span><span id="score-exp">+72</span>
    </div>
    <button class="btn-primary" id="btn-continue">继续</button>
</div>
```

### 新增信号

```python
# web_bridge.py
show_score_panel = Signal(str)  # score_data JSON
```

---

## 4.3 经验结算

在 `_handle_ending` 中，评分计算后进行经验结算：

```python
# 经验结算
from core.game_config import EXPERIENCE_CURVE
base_exp = session_data.get("confession_level", 0) * 10  # 供词层级经验
evidence_exp = len(self.engine.presented_evidence_ids) * 5  # 证据经验
completion_exp = 20  # 完成一局
grade_multiplier = score_data.get("exp_multiplier", 1.0)
total_exp = int((base_exp + evidence_exp + completion_exp) * grade_multiplier)

# 更新玩家档案
self.player.add_experience(total_exp)
self.player.total_sessions += 1
if event.get("new_state") == "breakdown":
    self.player.successful_sessions += 1
if score_data["grade"] < self.player.best_grade:
    self.player.best_grade = score_data["grade"]
self.player.save()
```

---

## 4.4 难度分级系统

### 案件生成时传入难度参数

修改 `generate_case` 函数签名：

```python
def generate_case(background: str, difficulty: str = "easy", max_retries: int = 1) -> Dict:
```

在提示词中注入难度约束：

```python
difficulty_constraints = {
    "easy": "生成2个嫌疑人，3-4个证据，3个以上forbidden_to_reveal关键词，审讯时限360秒。",
    "normal": "生成2-3个嫌疑人，3-4个证据，2个forbidden_to_reveal关键词，审讯时限300秒。",
    "hard": "生成3-4个嫌疑人，4-5个证据，1-2个forbidden_to_reveal关键词，审讯时限240秒。嫌疑人的反驳能力更强。",
    "nightmare": "生成4个以上嫌疑人，5-6个证据，仅1个forbidden_to_reveal关键词，审讯时限180秒。嫌疑人非常善于隐瞒。",
}
```

### 难度解锁

在 `game_config.py` 中定义解锁等级（已在 Phase 1 预留）。

---

## 4.5 难度选择 UI

在案件生成模态框中新增难度选择：

```html
<div class="difficulty-selector">
    <label>难度:</label>
    <select id="difficulty-select">
        <option value="easy">简单</option>
        <option value="normal" disabled>普通 (Lv.5 解锁)</option>
        <option value="hard" disabled>困难 (Lv.10 解锁)</option>
        <option value="nightmare" disabled>噩梦 (Lv.15 解锁)</option>
    </select>
</div>
```

根据玩家等级动态启用/禁用选项。

---

## 4.6 测试计划

| 测试 | 说明 |
|------|------|
| 规则维度计算 | 时间效率、证据利用、供词深度的分数正确 |
| LLM 评分降级 | LLM 不可用时使用默认分数 |
| 评级阈值 | 各分数段对应正确评级 |
| 经验结算 | 经验计算和等级提升正确 |
| 难度参数传递 | 不同难度生成不同参数的案件 |
| 难度解锁 | 等级不足时难度选项不可选 |
