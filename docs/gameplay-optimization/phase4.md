# Phase 4：评分与难度 — 行为评分维度 + 错误惩罚 + LLM 评分 + 难度分级（优化版 v1.3）

> **评审变更**：evidence_usage改为相关证据占比、best_grade数值映射、memory_summary截断、confession_depth非线性映射、难度解锁节奏说明  
> **v1.2 变更**：评分系统增加3个行为过程维度（施压精准度、证据精准度、错误惩罚），mistake_log数据联动评分  
> **v1.3 变更**：新增反扑惩罚评分（反扑触发时额外扣分），credibility变化纳入策略评分参考

## 前置依赖

Phase 1-3 完成。

## 目标

引入 LLM 驱动的多维评分系统（含行为过程统计）和案件难度分级，完善游戏循环的反馈和长期目标。

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
    # ── 结果维度 ──
    "confession_depth": {"weight": 0.20, "desc": "供词深度：最终供词层级"},
    "time_efficiency": {"weight": 0.10, "desc": "时间效率：剩余时间占比"},
    "evidence_usage": {"weight": 0.10, "desc": "证据利用：正确出示的相关证据占比"},
    # ── 行为过程维度（v1.2 新增） ──
    "pressure_accuracy": {"weight": 0.15, "desc": "施压精准度：对真凶施压次数 / 总施压次数"},
    "evidence_accuracy": {"weight": 0.15, "desc": "证据精准度：正确证据数 / 总出示证据数"},
    "mistake_penalty": {"weight": 0.10, "desc": "错误惩罚：根据 mistake_log 扣分，0错=100，每错-15"},
    # ── LLM 判断维度 ──
    "interrogation_strategy": {"weight": 0.10, "desc": "审讯策略：工具使用、施压共情交替"},
    "reasoning_accuracy": {"weight": 0.10, "desc": "推理准确：玩家推理与真相吻合度"},
}

# 评级阈值
GRADE_THRESHOLDS = [
    ("S", 90),
    ("A", 75),
    ("B", 60),
    ("C", 40),
    ("D", 0),
]

# 评级数值映射（用于比较）
GRADE_VALUE = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}

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
            - memory_summary: 对话摘要（已截断）
            - presented_evidence: 已出示证据列表
            - related_evidence_count: 与当前嫌疑人相关的证据总数
            - used_tools: 已使用工具列表
            - confession_level: 最终供词层级
            - time_left: 剩余时间
            - total_time: 总时间
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

    # 证据利用（修正v1.1：基于相关证据而非总证据）
    presented = len(session_data.get("presented_evidence", []))
    related_count = session_data.get("related_evidence_count", 0)
    if related_count > 0:
        scores["evidence_usage"] = min(100, int((presented / related_count) * 100))
    else:
        scores["evidence_usage"] = 0

    # 供词深度（非线性映射：层级4=100，层级3=85，层级2=65，层级1=40，层级0=15）
    confession_level = session_data.get("confession_level", 0)
    confession_score_map = {0: 15, 1: 40, 2: 65, 3: 85, 4: 100}
    scores["confession_depth"] = confession_score_map.get(confession_level, 0)

    # ── 行为过程维度（v1.2 新增） ──

    # 施压精准度：对真凶施压次数 / 总施压次数
    pressure_count = session_data.get("pressure_count", 0)
    pressure_on_culprit = session_data.get("pressure_on_culprit", 0)
    if pressure_count > 0:
        scores["pressure_accuracy"] = min(100, int((pressure_on_culprit / pressure_count) * 100))
    else:
        scores["pressure_accuracy"] = 50  # 没有施压不加分也不扣分

    # 证据精准度：正确证据数 / 总出示证据数
    correct_evidence = session_data.get("correct_evidence_count", 0)
    total_evidence_presented = session_data.get("total_evidence_presented", 0)
    if total_evidence_presented > 0:
        scores["evidence_accuracy"] = min(100, int((correct_evidence / total_evidence_presented) * 100))
    else:
        scores["evidence_accuracy"] = 50

    # 错误惩罚：根据 mistake_log 计算
    mistake_log = session_data.get("mistake_log", [])
    mistake_count = len(mistake_log)
    innocent_breakdown = any(m.get("type") == "innocent_breakdown" for m in mistake_log)
    proactive_triggered = session_data.get("proactive_triggered_count", 0)
    mistake_score = max(0, 100 - mistake_count * 15)
    if innocent_breakdown:
        mistake_score = max(0, mistake_score - 30)  # 无辜崩溃额外扣30
    if proactive_triggered > 0:
        mistake_score = max(0, mistake_score - proactive_triggered * 5)  # 反扑触发扣5/次
    scores["mistake_penalty"] = mistake_score

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
        "grade_value": GRADE_VALUE[grade],
        "exp_multiplier": GRADE_EXP_MULTIPLIER.get(grade, 1.0),
        "detail": llm_scores.get("detail", ""),
    }


def _truncate_memory(memory_text: str, max_chars: int = 2000) -> str:
    """截断对话摘要，控制 token 消耗。"""
    if len(memory_text) <= max_chars:
        return memory_text
    return memory_text[:max_chars] + "\n...（对话记录已截断）"


def _llm_score(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """调用 LLM 进行审讯策略和推理准确度评分。"""
    if not llm_client.is_initialized:
        return {"interrogation_strategy": 50, "reasoning_accuracy": 50, "detail": "LLM 未初始化"}

    truth = session_data.get("truth", "")
    memory = _truncate_memory(session_data.get("memory_summary", ""))
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
def _handle_ending(self, state_event):
    self._countdown_timer.stop()
    self.bridge.set_game_interactive.emit(False)

    # 计算评分
    from core.scoring import calculate_score
    suspect = self.engine.suspects[self.engine.current_suspect_index]

    # 计算相关证据数
    related_evidence_count = sum(
        1 for e in self.engine.case.get("evidences", [])
        if e.get("related_suspect") == suspect.name
    )

    # 构建对话摘要（从 suspect.memory 提取）
    memory_summary = "\n".join(
        f"{'审讯员' if m['role'] == 'user' else suspect.name}: {m['content']}"
        for m in suspect.memory
    )

    # 计算行为过程数据（v1.2 新增）
    correct_evidence_count = sum(
        1 for eid in self.engine.presented_evidence_ids
        if self.engine._find_evidence(eid) and
           self.engine._find_evidence(eid).get("related_suspect") == suspect.name
    )
    total_evidence_presented = len(self.engine.presented_evidence_ids)

    score_data = calculate_score({
        "truth": self.engine.case.get("truth", ""),
        "memory_summary": memory_summary,
        "presented_evidence": list(self.engine.presented_evidence_ids),
        "related_evidence_count": related_evidence_count,
        "used_tools": self.engine.used_tools,
        "confession_level": suspect.confession_level,
        "time_left": self.engine.time_left,
        "total_time": self.engine.case.get("interrogation_time_limit_sec", 300),
        "suspect_name": suspect.name,
        "mistake_log": self.engine.mistake_log,
        "correct_evidence_count": correct_evidence_count,
        "total_evidence_presented": total_evidence_presented,
        "pressure_count": self.engine.pressure_uses_remaining and
            (PRESSURE_USES_PER_SUSPECT - self.engine.pressure_uses_remaining[self.engine.current_suspect_index]),
        "pressure_on_culprit": 0,  # 需要从mistake_log反算
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
        <div class="dim-group">
            <h4>结果评估</h4>
            <div class="dim-item" data-dim="confession_depth">供词深度</div>
            <div class="dim-item" data-dim="time_efficiency">时间效率</div>
            <div class="dim-item" data-dim="evidence_usage">证据利用</div>
        </div>
        <div class="dim-group">
            <h4>行为评估</h4>
            <div class="dim-item" data-dim="pressure_accuracy">施压精准度</div>
            <div class="dim-item" data-dim="evidence_accuracy">证据精准度</div>
            <div class="dim-item" data-dim="mistake_penalty">失误控制</div>
        </div>
        <div class="dim-group">
            <h4>策略评估</h4>
            <div class="dim-item" data-dim="interrogation_strategy">审讯策略</div>
            <div class="dim-item" data-dim="reasoning_accuracy">推理准确</div>
        </div>
    </div>
    <div class="score-detail" id="score-detail"></div>
    <div class="score-mistakes" id="score-mistakes"></div>
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
if state_event.get("new_state") == "breakdown":
    self.player.successful_sessions += 1

# 使用数值映射比较评级（修正v1.1）
if score_data["grade_value"] > GRADE_VALUE.get(self.player.best_grade, 0):
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

在 `game_config.py` 中定义解锁等级：

```python
# core/game_config.py — Phase 4 添加

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "easy":      {"suspects": 2, "time": 360, "evidence_uses": 4, "keywords": 3, "unlock_level": 1},
    "normal":    {"suspects": "2-3", "time": 300, "evidence_uses": 3, "keywords": 2, "unlock_level": 5},
    "hard":      {"suspects": "3-4", "time": 240, "evidence_uses": 3, "keywords": 2, "unlock_level": 10},
    "nightmare": {"suspects": "4+", "time": 180, "evidence_uses": 2, "keywords": 1, "unlock_level": 15},
}
```

### 解锁节奏说明

- **Lv.1-4**：简单难度，熟悉基础机制（约 5-10 局，30-60分钟）
- **Lv.5-9**：普通难度，引入反驳机制（约 10-15 局，累计 1.5-2小时）
- **Lv.10-14**：困难难度，完整策略体验（约 15-20 局，累计 3-4小时）
- **Lv.15+**：噩梦难度，挑战极限

> 此节奏基于每局约5分钟、经验获取约30-50点的估算。实际节奏需根据试玩数据调整。

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

根据玩家等级动态启用/禁用选项：

```javascript
function updateDifficultyOptions(playerLevel) {
    const presets = {
        easy: 1, normal: 5, hard: 10, nightmare: 15
    };
    document.querySelectorAll('#difficulty-select option').forEach(opt => {
        const required = presets[opt.value];
        opt.disabled = playerLevel < required;
    });
}
```

---

## 4.6 测试计划

| 测试 | 说明 |
|------|------|
| 规则维度计算 | 时间效率、证据利用（相关证据）、供词深度的分数正确 |
| 证据利用基于相关证据 | 验证出示无关证据不计入分子 |
| 施压精准度 | 对真凶施压 vs 对无辜施压，正确计算比例 |
| 证据精准度 | 正确证据 vs 错误证据比例 |
| 错误惩罚计算 | 0错=100，1错=85，2错=70，无辜崩溃额外-30 |
| LLM 评分降级 | LLM 不可用时使用默认分数 50 |
| 评级阈值 | 各分数段对应正确评级 |
| 经验结算 | 经验计算和等级提升正确 |
| best_grade 数值比较 | 验证 S > A > B > C > D |
| 难度参数传递 | 不同难度生成不同参数的案件 |
| 难度解锁 | 等级不足时难度选项不可选 |
| memory_summary 截断 | 验证超长对话正确截断 |
| 行为维度权重 | 验证8个维度权重之和为1.0 |
| mistake_log 联动 | 验证 mistake_log 数据正确传入评分 |

---

## Phase 4 评审后关键变更对照表

| 变更项 | v1.0 原方案 | v1.3 优化方案 | 原因 |
|--------|------------|--------------|------|
| `evidence_usage` | 出示数/总证据数 | 出示数/相关证据数 | P1：更准确反映策略 |
| `confession_depth` | `level * 25`（线性） | 非线性映射（0=15,1=40,2=65,3=85,4=100） | P2：缩小层级间差距 |
| `best_grade` | 字符串比较 | 数值映射比较 | P2：支持未来扩展（SS等） |
| `memory_summary` | 完整传入 | 截断至2000字符 | P2：控制token消耗 |
| 难度解锁节奏 | 未说明 | 明确各阶段预计局数和时间 | 增强：帮助设计验证 |
| 评分维度 | 5维（纯结果+LLM） | 8维（结果3+行为3+LLM2） | P0：增加行为过程统计 |
| 错误惩罚 | 无 | mistake_log 联动评分 | P1：错误操作有后果 |
| 反扑惩罚 | 无 | 反扑触发次数扣5/次 | P1：反扑是操作失误的信号 |
| 评分面板 | 简单列表 | 分组展示（结果/行为/策略） | 增强：复盘信息更丰富 |

(End of file - total 324 lines)
