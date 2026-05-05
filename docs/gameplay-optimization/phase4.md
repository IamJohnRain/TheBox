# Phase 4：评分与难度 — 行为评分维度 + 错误惩罚 + LLM 评分 + 难度分级（优化版 v1.4）

> **评审变更**：evidence_usage改为相关证据占比、best_grade数值映射、memory_summary截断、confession_depth非线性映射、难度解锁节奏说明  
> **v1.2 变更**：评分系统增加3个行为过程维度（施压精准度、证据精准度、错误惩罚），mistake_log数据联动评分  
> **v1.3 变更**：新增反扑惩罚评分（反扑触发时额外扣分），credibility变化纳入策略评分参考
> **v1.4 变更**：评分权重、评级阈值、结果封顶、经验奖励、难度参数全部配置文件化。

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


# 评分维度定义。实际值来自 config/gameplay_balance.json 的 scoring.dimensions。
SCORING_DIMENSIONS = {
    # ── 结果维度 ──
    "confession_depth": {"weight": 0.20, "desc": "供词深度：最终供词层级"},
    "ap_efficiency": {"weight": 0.10, "desc": "行动效率：剩余AP占比"},
    "evidence_usage": {"weight": 0.10, "desc": "证据利用：正确出示的相关证据占比"},
    # ── 行为过程维度（v1.2 新增） ──
    "pressure_accuracy": {"weight": 0.15, "desc": "施压精准度：对真凶施压次数 / 总施压次数"},
    "evidence_accuracy": {"weight": 0.15, "desc": "证据精准度：正确证据数 / 总出示证据数"},
    "mistake_penalty": {"weight": 0.10, "desc": "错误惩罚：根据 mistake_log 扣分，0错=100，每错-15"},
    # ── LLM 判断维度 ──
    "interrogation_strategy": {"weight": 0.10, "desc": "审讯策略：工具使用、施压共情交替"},
    "reasoning_accuracy": {"weight": 0.10, "desc": "推理准确：玩家推理与真相吻合度"},
}

# 评级阈值。实际值来自 scoring.grade_thresholds。
GRADE_THRESHOLDS = [
    ("S", 90),
    ("A", 75),
    ("B", 60),
    ("C", 40),
    ("D", 0),
]

# 评级数值映射（用于比较）
GRADE_VALUE = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}

# 评级经验系数。实际值来自 scoring.grade_exp_multiplier。
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
            - ap_remaining: 剩余行动点数
            - total_time: 总时间
            - suspect_name: 被审讯嫌疑人名

    Returns:
        包含各维度分数、总分、评级的字典
    """
    scores = {}

    # ── 规则计算的维度 ──

    # 行动效率（剩余AP/总AP）
    ap_remaining = session_data.get("ap_remaining", 0)
    total_ap = session_data.get("total_ap", 1)
    scores["ap_efficiency"] = min(100, int((ap_remaining / max(total_ap, 1)) * 100))

    # 证据利用（修正v1.2：基于正确出示的相关证据 / 可出示上限）
    correct_evidence = session_data.get("correct_evidence_count", 0)
    related_count = session_data.get("related_evidence_count", 0)
    evidence_uses = session_data.get("evidence_uses", DEFAULT_EVIDENCE_USES)
    if related_count > 0:
        max_possible = min(evidence_uses, related_count)
        scores["evidence_usage"] = min(100, int((correct_evidence / max_possible) * 100))
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

    # 错误惩罚：根据 mistake_log 计算（递减惩罚，避免线性过于严厉）
    # penalty_weights、score_floor、innocent_breakdown_extra、proactive_penalty 均从配置读取。
    from core.game_config import get_scoring_config
    scoring_config = get_scoring_config()
    mistake_log = session_data.get("mistake_log", [])
    mistake_count = len(mistake_log)
    innocent_breakdown = any(m.get("type") == "innocent_breakdown" for m in mistake_log)
    proactive_triggered = session_data.get("proactive_triggered_count", 0)
    penalty_weights = scoring_config["mistake_penalty"]["weights"]
    total_penalty = sum(penalty_weights[min(i, len(penalty_weights)-1)] for i in range(mistake_count))
    mistake_score = max(scoring_config["mistake_penalty"]["score_floor"], 100 - total_penalty)
    if innocent_breakdown:
        mistake_score = max(
            scoring_config["mistake_penalty"]["score_floor"],
            mistake_score - scoring_config["mistake_penalty"]["innocent_breakdown_extra"],
        )
    if proactive_triggered > 0:
        mistake_score = max(
            scoring_config["mistake_penalty"]["score_floor"],
            mistake_score - proactive_triggered * scoring_config["mistake_penalty"]["proactive_penalty"],
        )
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

    # 结果封顶（v1.5）：避免失败局因行为分/LLM分较高而拿到高评级。
    # win: 不封顶；partial: 最高 B；fail: 最高 C；无辜崩溃: 最高 C-。
    outcome = session_data.get("outcome", "win" if confession_level >= 4 else "fail")
    outcome_caps = scoring_config["outcome_caps"]
    if outcome == "partial":
        total = min(total, outcome_caps["partial"])
    elif outcome == "fail":
        total = min(total, outcome_caps["fail"])
    if innocent_breakdown:
        total = min(total, outcome_caps["innocent_breakdown"])

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


def _truncate_memory(memory_text: str, max_chars: Optional[int] = None) -> str:
    """截断对话摘要，控制 token 消耗。"""
    if max_chars is None:
        from core.game_config import get_scoring_config
        max_chars = get_scoring_config()["llm"]["memory_summary_max_chars"]
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
    self._countdown_timer.stop()  # 注意：AP系统下此定时器可能已不存在
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
    pressure_count = (
        PRESSURE_USES_PER_SUSPECT
        - self.engine.pressure_uses_remaining[self.engine.current_suspect_index]
    )
    wrong_pressure_count = sum(
        1 for m in self.engine.mistake_log
        if m.get("type") == "wrong_pressure" and m.get("suspect_name") == suspect.name
    )
    outcome = (
        "win" if state_event["new_state"] == "breakdown"
        else "partial" if suspect.confession_level >= 2 or total_evidence_presented > 0
        else "fail"
    )

    score_data = calculate_score({
        "truth": self.engine.case.get("truth", ""),
        "memory_summary": memory_summary,
        "presented_evidence": list(self.engine.presented_evidence_ids),
        "related_evidence_count": related_evidence_count,
        "used_tools": self.engine.used_tools,
        "confession_level": suspect.confession_level,
        "ap_remaining": self.engine.action_points_remaining,
        "total_ap": self.engine.total_action_points,
        "suspect_name": suspect.name,
        "mistake_log": self.engine.mistake_log,
        "correct_evidence_count": correct_evidence_count,
        "total_evidence_presented": total_evidence_presented,
        "pressure_count": pressure_count,
        "pressure_on_culprit": max(0, pressure_count - wrong_pressure_count),
        "outcome": outcome,
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
            <div class="dim-item" data-dim="ap_efficiency">行动效率</div>
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
from core.game_config import get_experience_reward_config
exp_config = get_experience_reward_config()
base_exp = session_data.get("confession_level", 0) * exp_config["per_confession_level"]
evidence_exp = len(self.engine.presented_evidence_ids) * exp_config["per_presented_evidence"]
completion_exp = exp_config["completion"]
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

在提示词中注入难度约束。约束文本由 `config/gameplay_balance.json` 的 `difficulty.presets` 派生，不在 `case_generator.py` 中写死：

```python
from core.game_config import get_difficulty_preset, render_difficulty_prompt

preset = get_difficulty_preset(difficulty)
difficulty_constraint = render_difficulty_prompt(preset)
```

### 难度解锁

在 `config/gameplay_balance.json` 中定义解锁等级和默认难度参数。下面 Python 片段只表示 `core.game_config` 兼容导出后的形状：

```python
# core/game_config.py — Phase 4 兼容导出，值来自 gameplay_balance.json

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "easy":      {"suspects": 2, "total_ap": 26, "evidence_uses": 4, "keywords": 3, "unlock_level": 1},
    "normal":    {"suspects": "2-3", "total_ap": 22, "evidence_uses": 4, "keywords": 2, "unlock_level": 5},
    "hard":      {"suspects": "3-4", "total_ap": 19, "evidence_uses": 4, "keywords": 2, "unlock_level": 10},
    "nightmare": {"suspects": "4+", "total_ap": 16, "evidence_uses": 3, "keywords": 1, "unlock_level": 15},
}
```

### 解锁节奏说明

- **Lv.1-4**：简单难度，熟悉基础机制（约 5-10 局，30-60分钟）
- **Lv.5-9**：普通难度，引入反驳机制（约 10-15 局，累计 1.5-2.5小时）
- **Lv.10-14**：困难难度，完整策略体验（约 15-25 局，累计 3-5小时）
- **Lv.15+**：噩梦难度，挑战极限（约 30-50 局，累计 5-8小时）

> 此节奏基于每局约5分钟、经验获取约40-65点的估算。实际节奏需根据试玩数据调整。
> 经验曲线验证（v1.5）：Lv.10约需880exp（约14-22局，1-2小时）；Lv.15约需1980exp（约30-50局，3-5小时）；Lv.20约需3580exp（约55-90局，5-8小时）。
> v1.7 配置化要求：上述局数、经验和难度AP都是默认配置推导值，调平衡时优先修改 `gameplay_balance.json`，不要改 Python 代码。

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
| 规则维度计算 | 行动效率、证据利用（相关证据）、供词深度的分数正确 |
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
| 配置覆盖 | 临时配置修改评分权重、封顶、经验奖励、难度AP后，对应评分/生成/升级行为同步变化 |

---

## 4.7 弱模型执行任务包与验收

Phase 4 应优先写纯函数评分，再接 UI 和经验结算。不要让弱模型同时修改评分公式、LLM调用、难度生成和前端面板。

### 任务包拆分

| 包 | 范围 | 允许修改 | 验收重点 |
|----|------|----------|----------|
| 4a 规则评分 | `core/scoring.py`、行为/结果/策略分数、结果封顶 | `core/scoring.py`, `tests/test_scoring.py` | 无LLM也能返回完整评分，partial/fail封顶正确 |
| 4b LLM评分降级 | LLM summary输入截断、异常降级50分 | `core/scoring.py`, `tests/test_scoring_llm.py` | 不因网络/API失败阻塞结算 |
| 4c 经验结算 | 评分转经验、PlayerProfile更新、best_grade | `core/player.py`, `core/db.py`, `tests/test_experience.py` | S>A>B>C>D比较正确，升级幂等 |
| 4d 难度系统 | 难度参数、解锁规则、case生成约束 | `config/gameplay_balance.json`, `core/game_config.py`, `core/case_generator.py`, `tests/test_difficulty.py` | 默认normal=22 AP，hard=19，nightmare=16，临时配置覆盖生效 |
| 4e 评分UI | 评分面板、分组展示、WebBridge信号 | `ui/web/`, `ui/web_bridge.py`, `ui/web_main_window.py`, `tests/test_score_ui.py` | 前端展示总分、评级、分项和封顶原因 |

### Definition of Done

| 条件 | 要求 |
|------|------|
| 纯规则可测 | 不依赖真实LLM即可完成评分 |
| 分数封顶 | win不封顶，partial≤74，fail≤59，无辜崩溃≤49 |
| 行为统计 | evidence_usage、pressure_precision、mistake_penalty 都基于正确分母 |
| 经验一致 | 经验曲线与 Phase 3b `EXPERIENCE_CURVE` 一致 |
| 数值配置 | 评分权重、封顶、经验奖励、难度AP和证据次数全部来自配置文件 |
| 难度一致 | 默认难度AP和证据次数与 v1.5 基线一致，同时支持临时配置覆盖 |
| UI可解释 | 评分面板说明每个扣分/封顶原因，便于复盘 |

### 阶段验收场景

| 场景 | 验收方式 |
|------|----------|
| 失败高行为分 | 构造fail但高证据/LLM分，最终总分仍≤59 |
| partial封顶 | confession_level=2且有证据，最终总分≤74 |
| 无辜崩溃 | mistake_log含 innocent_breakdown，最终总分≤49 |
| LLM不可用 | 模拟异常，评分返回默认LLM分且不抛出 |
| 难度生成 | easy/normal/hard/nightmare 分别生成对应AP、证据数和嫌疑人数 |
| 难度配置覆盖 | 临时配置将normal AP改为24后，生成与引擎初始化都使用24 |
| 经验升级 | 多局评分累计后正确升级并解锁难度 |

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
