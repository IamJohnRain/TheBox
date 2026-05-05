# 双模式系统设计 — 剧情模式 + 自定义模式

> **版本**：v1.1  
> **依赖**：Phase 1（供词层级系统）已完成  
> **状态**：待评审  
> **v1.1 变更**：剧情模式不直接硬编码AP、经验、难度等平衡数值；章节脚本只声明难度或剧情覆盖意图，最终数值由 `config/gameplay_balance.json` 派生。

---

## 1. 需求概述

### 1.1 两种游戏模式

| 模式 | 说明 | 案件来源 | 进度 | 目标用户 |
|------|------|----------|------|----------|
| **剧情模式** | 15+章长篇主线，悬疑叙事，分支+3-4结局 | 关键转折固定剧本 + 填充章节LLM约束生成 | 章节进度，分支影响走向 | 叙事驱动型玩家 |
| **自定义模式** | 保持现有流程，玩家自由设定案件背景 | LLM 自由生成 | 单局独立 | 自由探索型玩家 |

### 1.2 剧情模式示例

**主线**：「寻找失踪父亲」

玩家扮演一名新入职的警探，在调查一系列看似无关的案件时，逐渐发现这些案件都指向同一个真相——自己失踪多年的父亲。每一章是一个独立的审讯案件，但线索相互交织，最终揭示一个跨越二十年的秘密。

**章节节奏**：
- 第1-3章：入门案件，学习基础审讯技巧，初步接触线索
- 第4-6章：案件复杂度上升，引入反驳/证据链机制，线索开始串联
- 第7-9章：关键转折点，多分支，玩家选择影响后续走向
- 第10-12章：真相逼近，高压审讯，工具全面解锁
- 第13-15章：终章，根据前期分支走向不同结局

**结局**：
1. **真相大白**：找到父亲，揭露幕后黑手
2. **暗影重重**：部分真相被掩盖，父亲下落不明
3. **牺牲之路**：为保护重要之人，选择隐瞒真相

---

## 2. 架构设计

### 2.1 分层架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         主菜单 (模式选择)                         │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                     ┌──────┴──────┐
                     │ GameSession │  ← 新增：游戏会话协调器
                     └──┬───────┬──┘
                        │       │
             ┌──────────┘       └──────────┐
             │                             │
      ┌──────┴──────┐              ┌───────┴──────┐
      │  剧情模式    │              │  自定义模式   │
      │ StoryEngine  │              │  现有流程     │
      │  + 章节系统   │              │              │
      └──────┬──────┘              └───────┬──────┘
             │                             │
             └───────────┬─────────────────┘
                         │
                 ┌───────┴───────┐
                 │Interrogation  │  ← 复用，不修改
                 │   Engine      │
                 └───────────────┘
```

**关键原则**：
- **组合优于继承**：StoryEngine 持有 InterrogationEngine 实例，非继承
- **不修改底层**：InterrogationEngine 接口不变，StoryEngine 在上层编排
- **协调器模式**：GameSession 统一管理双模式会话，避免 WebMainWindow 膨胀
- **数值配置化**：剧情章节不写死AP/经验/工具次数，统一通过 `core.game_config` 根据难度和等级读取

### 2.2 GameSession 协调器

**文件**：`core/game_session.py`（新建）

```python
class GameSession:
    """游戏会话协调器，管理双模式切换。"""

    mode: Literal["story", "custom"]           # 当前模式
    story_engine: Optional[StoryEngine]         # 剧情引擎（剧情模式）
    engine: Optional[InterrogationEngine]       # 审讯引擎（两种模式共用）
    player: PlayerProfile                       # 玩家档案（共享）

    # ── 模式启动 ──

    def start_story(self, story_id: str) -> None:
        """启动剧情模式。"""

    def start_custom(self, case_data: dict) -> None:
        """启动自定义模式（现有流程）。"""

    # ── 剧情模式章节管理 ──

    def start_chapter(self) -> dict:
        """开始当前章节，返回 case_data。"""

    def evaluate_chapter(self) -> ChapterResult:
        """评估当前章节审讯结果。"""

    def complete_chapter(self, result: ChapterResult) -> Optional[str]:
        """完成章节，推进剧情。返回下一章 narrative 或 None（结局）。"""

    def get_narrative(self, result: ChapterResult) -> str:
        """获取章节叙事文本。"""

    # ── 审讯结果处理 ──

    def on_interrogation_ending(self, state_event: dict) -> None:
        """审讯结束时统一调度。剧情模式推进章节，自定义模式直接结束。"""
```

**WebMainWindow 集成**：

```python
# 改前
self.engine: Optional[InterrogationEngine] = None

# 改后
self.session: Optional[GameSession] = None

# 访问引擎
@property
def engine(self) -> Optional[InterrogationEngine]:
    return self.session.engine if self.session else None
```

---

## 3. StoryEngine 剧情引擎

**文件**：`core/story_engine.py`（新建）

### 3.1 核心状态

```python
class StoryEngine:
    """剧情引擎：管理章节流转、分支判定、叙事状态。"""

    def __init__(self, story_data: dict):
        self.story: dict = story_data
        self.current_chapter_id: str = story_data["chapters"][0]["chapter_id"]
        self.completed_chapters: List[str] = []
        self.story_variables: Dict[str, Any] = {}      # 跨章节叙事变量
        self.carried_evidence: List[dict] = []           # 跨章节携带证据
        self.interrogation_engine: Optional[InterrogationEngine] = None
```

### 3.2 章节流转

```python
def start_chapter(self) -> dict:
    """开始当前章节，返回符合 CASE_SCHEMA 的 case_data。"""
    chapter = self._get_current_chapter()

    if chapter["type"] == "scripted":
        # 固定剧本：直接返回 case_data（已通过 StoryLoader 校验符合 CASE_SCHEMA）
        case_data = chapter["case_data"]
    elif chapter["type"] == "generated":
        # LLM 约束生成：在 case_constraints 框架内生成
        case_data = generate_case_with_constraints(
            constraints=chapter["case_constraints"],
            story_variables=self.story_variables,
        )
    else:
        raise ValueError(f"未知章节类型: {chapter['type']}")

    # 合并跨章节携带证据到 case_data.evidences
    if self.carried_evidence:
        case_data["evidences"] = list(case_data.get("evidences", []))
        for ev in self.carried_evidence:
            if ev["id"] not in [e["id"] for e in case_data["evidences"]]:
                case_data["evidences"].append(ev)

    return case_data
```

### 3.3 章节完成与分支判定

```python
def complete_chapter(self, result: ChapterResult) -> Optional[str]:
    """完成当前章节，评估分支，返回下一章 chapter_id 或结局 id。"""
    chapter = self._get_current_chapter()
    self.completed_chapters.append(self.current_chapter_id)

    # 更新叙事状态变量
    self._apply_story_variables(chapter)

    # 评估分支
    next_id = self._evaluate_branch(chapter["branch"], result)

    # 检查是否到达结局
    ending = self._find_ending(next_id)
    if ending:
        self.current_chapter_id = next_id
        return next_id  # 结局 ID

    self.current_chapter_id = next_id
    return next_id


def _evaluate_branch(self, branch: dict, result: ChapterResult) -> str:
    """评估分支条件，返回下一章/结局 ID。

    使用声明式条件，不使用 eval()。
    """
    for condition in branch["conditions"]:
        if self._match_condition(condition, result):
            return condition["next"]
    # 兜底：最后一个条件（应为 else 条件）
    return branch["conditions"][-1]["next"]


def _match_condition(self, condition: dict, result: ChapterResult) -> bool:
    """匹配单个声明式条件。"""
    # 条件1：result 匹配
    if "result" in condition:
        if condition["result"] != result.result:
            return False

    # 条件2：最低供词层级
    if "min_confession" in condition:
        if result.confession_level < condition["min_confession"]:
            return False

    # 条件3：最低证据数
    if "min_evidence" in condition:
        if result.evidence_count < condition["min_evidence"]:
            return False

    return True
```

### 3.4 叙事状态管理

```python
def _apply_story_variables(self, chapter: dict) -> None:
    """应用章节的叙事状态变量。"""
    variables = chapter.get("story_variables", {})

    # 设置变量
    for key, value in variables.get("set", {}).items():
        self.story_variables[key] = value

    # 收集携带证据
    for ev_id in variables.get("carry_evidence", []):
        # 从当前引擎中找到该证据并携带
        if self.interrogation_engine:
            ev = self.interrogation_engine.get_evidence(ev_id)
            if ev and ev not in self.carried_evidence:
                self.carried_evidence.append(ev)


def get_narrative(self, result: ChapterResult) -> str:
    """根据审讯结果质量返回对应的叙事文本。"""
    chapter = self._get_current_chapter()
    narrative = chapter.get("narrative", {})
    return narrative.get(f"closing_{result.result}", narrative.get("closing_fail", ""))
```

---

## 4. 章节系统

### 4.1 章节 JSON Schema

**文件**：`schemas/story.py`（新建）

剧情脚本完整 JSON 结构：

```json
{
  "story_id": "missing_father",
  "title": "寻找失踪父亲",
  "desc": "一段跨越二十年的悬疑故事...",
  "cover_image": null,
  "chapters": [
    {
      "chapter_id": "ch01",
      "seq": 1,
      "title": "初入警局",
      "type": "scripted",
      "narrative": {
        "opening": "你是一名新入职的警探，第一天报到就被派去审讯一名嫌疑人...",
        "closing_win": "嫌疑人供出了关键线索，你在笔记本上记下了重要信息...",
        "closing_partial": "虽然未能完全突破，但你从嫌疑人的反应中察觉到了一些端倪...",
        "closing_fail": "审讯陷入僵局，嫌疑人始终保持沉默..."
      },
      "case_data": {
        "case_id": "ch01_case",
        "title": "工厂失窃案",
        "victim": "...",
        "cause_of_death": "...",
        "crime_scene": "...",
        "truth": "...",
        "culprit_name": "张某",
        "suspects": [...],
        "evidences": [...],
        "difficulty": "normal"
      },
      "merge_to": null,
      "branch": {
        "conditions": [
          {"result": "win", "min_confession": 3, "next": "ch02a"},
          {"result": "partial", "next": "ch02b"},
          {"next": "ch02c"}
        ]
      },
      "story_variables": {
        "set": {"met_informant": true, "first_case_success": true},
        "carry_evidence": ["e_ch01_key"]
      }
    },
    {
      "chapter_id": "ch02a",
      "seq": 2,
      "title": "暗流涌动",
      "type": "scripted",
      "merge_to": "ch03",
      "narrative": {...},
      "case_data": {...},
      "branch": {
        "conditions": [
          {"result": "win", "next": "ch03"},
          {"next": "ch03"}
        ]
      },
      "story_variables": {}
    }
  ],
  "endings": [
    {
      "id": "ending_truth",
      "title": "真相大白",
      "desc": "你终于找到了父亲，揭露了幕后黑手的罪行...",
      "narrative": "阳光透过审讯室的窗户..."
    },
    {
      "id": "ending_shadow",
      "title": "暗影重重",
      "desc": "部分真相被掩盖，父亲下落仍是个谜...",
      "narrative": "雨夜中，你独自走出警局..."
    },
    {
      "id": "ending_sacrifice",
      "title": "牺牲之路",
      "desc": "为了保护重要之人，你选择将真相永远埋藏...",
      "narrative": "你合上了卷宗，轻轻叹了口气..."
    }
  ]
}
```

章节脚本如需特殊调参，优先使用声明式覆盖字段并通过 `StoryLoader` 校验，例如 `"balance_profile": "tutorial"` 或 `"difficulty": "normal"`；不建议在 `case_data` 内直接写 `total_action_points`。若确有剧情关卡需要固定数值，也必须引用 `gameplay_balance.json` 中预定义的 profile，而不是在脚本里写裸数字。

### 4.2 分支条件格式（声明式）

```json
"conditions": [
  {"result": "win", "min_confession": 3, "min_evidence": 2, "next": "ch02a"},
  {"result": "partial", "min_confession": 1, "next": "ch02b"},
  {"next": "ch02c"}
]
```

**字段说明**：

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `result` | `"win"` / `"partial"` / `"fail"` | 否 | 审讯结果匹配 |
| `min_confession` | `int` | 否 | 最低供词层级 |
| `min_evidence` | `int` | 否 | 最低已出示证据数 |
| `next` | `string` | **是** | 下一章 chapter_id 或结局 id |

**匹配规则**：按数组顺序逐一匹配，第一个满足条件的生效。最后一个条件通常只有 `next`（兜底/else）。

### 4.3 漏斗式收敛

通过 `merge_to` 字段声明收敛点：

```json
{"chapter_id": "ch02a", "merge_to": "ch03", ...},
{"chapter_id": "ch02b", "merge_to": "ch03", ...},
{"chapter_id": "ch02c", "merge_to": "ch03_alt", ...}
```

`StoryLoader` 加载时校验：
1. 所有 `merge_to` 指向的章节在脚本 `chapters` 中存在
2. 分支路径在 1-2 步内收敛到同一个 `merge_to` 目标（否则发出警告）

### 4.4 跨章节状态传递

| 机制 | 说明 | 示例 |
|------|------|------|
| `story_variables.set` | 章节完成时设置叙事变量 | `{"met_informant": true}` |
| `carry_evidence` | 章节完成时携带证据到下一章 | `["e_ch01_key"]` |
| `case_constraints.require_variables` | generated章节生成时注入叙事变量约束 | `{"must_mention": "informant"}` |

**跨章节证据机制**：
- `start_chapter()` 时将 `carried_evidence` 合并到 `case_data.evidences`
- 跨章节证据在 UI 中标记为"旧线索"（样式区分）
- 跨章节证据不出现在当前案件的 `forbidden_to_reveal` 中（不触发胜利）

---

## 5. 审讯结果评估

### 5.1 ChapterResult 结构

**文件**：`schemas/story.py`

```python
from typing import Literal, TypedDict

class ChapterResult(TypedDict):
    """章节完成后的审讯结果评估。"""
    result: Literal["win", "partial", "fail"]
    confession_level: int       # 来自 Phase 1 供词系统
    evidence_count: int         # 已出示证据数
    ap_remaining_pct: float     # 剩余行动点数百分比
    suspect_name: str
    culprit_name: str           # 来自 case_data.culprit_name，作为真凶唯一来源
    verdict_reason: str
```

### 5.2 评估逻辑

```python
def evaluate_chapter(engine: InterrogationEngine) -> ChapterResult:
    """基于引擎状态评估审讯结果。"""
    suspect = engine.suspects[engine.current_suspect_index]
    total_ap = engine.total_action_points
    culprit_name = engine.case.get("culprit_name", "")
    is_culprit = suspect.name == culprit_name

    # 三级判定：只有真凶达到崩溃/层级4才算win；无辜者崩溃不能推进为胜利分支。
    if is_culprit and (engine.state == "breakdown" or suspect.confession_level >= 4):
        result = "win"
    elif suspect.confession_level >= 2 or (
        engine.state == "verdict" and len(engine.presented_evidence_ids) > 0
    ):
        result = "partial"
    else:
        result = "fail"

    return ChapterResult(
        result=result,
        confession_level=suspect.confession_level,
        evidence_count=len(engine.presented_evidence_ids),
        ap_remaining_pct=round(engine.action_points_remaining / max(total_ap, 1), 2),
        suspect_name=suspect.name,
        culprit_name=culprit_name,
        verdict_reason=f"供词层级{suspect.confession_level}，状态{engine.state}",
    )
```

**评判标准**：

| 结果 | 条件 | 叙事 |
|------|------|------|
| `win` | `culprit_name` 对应真凶达到 `breakdown` 或供词层级 >= 4 | `closing_win` |
| `partial` | 供词层级 >= 2，或超时但有出示过证据 | `closing_partial` |
| `fail` | 超时且无证据出示，供词层级 < 2 | `closing_fail` |

---

## 6. StoryLoader 剧情脚本加载器

**文件**：`core/story_loader.py`（新建）

### 6.1 加载与校验

```python
import json
import jsonschema
from typing import Dict, List

STORY_SCHEMA = {
    "type": "object",
    "required": ["story_id", "title", "chapters", "endings"],
    "properties": {
        "story_id": {"type": "string"},
        "title": {"type": "string"},
        "desc": {"type": "string"},
        "chapters": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["chapter_id", "seq", "title", "type", "narrative", "branch"],
                "properties": {
                    "chapter_id": {"type": "string"},
                    "seq": {"type": "integer"},
                    "title": {"type": "string"},
                    "type": {"type": "string", "enum": ["scripted", "generated"]},
                    "narrative": {"type": "object"},
                    "case_data": {"type": "object"},
                    "case_constraints": {"type": "object"},
                    "merge_to": {"type": "string"},
                    "branch": {"type": "object"},
                    "story_variables": {"type": "object"},
                },
            },
        },
        "endings": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "title"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "desc": {"type": "string"},
                    "narrative": {"type": "string"},
                },
            },
        },
    },
}


def load_story(story_path: str) -> dict:
    """加载并校验剧情脚本。

    Args:
        story_path: JSON 文件路径

    Returns:
        校验通过的剧情数据字典

    Raises:
        ValidationError: JSON 格式或 Schema 不合规
        ValueError: 业务规则校验失败（收敛性、引用完整性等）
    """
    with open(story_path, "r", encoding="utf-8") as f:
        story_data = json.load(f)

    # 1. Schema 校验
    jsonschema.validate(instance=story_data, schema=STORY_SCHEMA)

    # 2. 业务规则校验
    _validate_story_integrity(story_data)

    return story_data


def _validate_story_integrity(story_data: dict) -> None:
    """校验剧情脚本的引用完整性和收敛性。"""
    chapter_ids = {ch["chapter_id"] for ch in story_data["chapters"]}
    ending_ids = {e["id"] for e in story_data["endings"]}
    all_valid_ids = chapter_ids | ending_ids

    errors = []

    for chapter in story_data["chapters"]:
        # 校验 scripted 章节的 case_data 符合 CASE_SCHEMA
        if chapter["type"] == "scripted" and "case_data" in chapter:
            try:
                from core.case_generator import CASE_SCHEMA
                jsonschema.validate(instance=chapter["case_data"], schema=CASE_SCHEMA)
            except jsonschema.ValidationError as e:
                errors.append(
                    f"章节 {chapter['chapter_id']} 的 case_data 不符合 CASE_SCHEMA: {e.message}"
                )

        # 校验 generated 章节有 case_constraints
        if chapter["type"] == "generated" and "case_constraints" not in chapter:
            errors.append(
                f"章节 {chapter['chapter_id']} 类型为 generated 但缺少 case_constraints"
            )

        # 校验分支条件的 next 指向有效 ID
        for condition in chapter.get("branch", {}).get("conditions", []):
            next_id = condition.get("next", "")
            if next_id not in all_valid_ids:
                errors.append(
                    f"章节 {chapter['chapter_id']} 的分支条件 next='{next_id}' 不存在"
                )

        # 校验 merge_to 指向有效 ID
        merge_to = chapter.get("merge_to")
        if merge_to and merge_to not in chapter_ids:
            errors.append(
                f"章节 {chapter['chapter_id']} 的 merge_to='{merge_to}' 不存在"
            )

        # 校验 carry_evidence 引用的证据在 case_data 中存在
        carry = chapter.get("story_variables", {}).get("carry_evidence", [])
        if carry and chapter["type"] == "scripted":
            ev_ids = {e["id"] for e in chapter.get("case_data", {}).get("evidences", [])}
            for ev_id in carry:
                if ev_id not in ev_ids:
                    errors.append(
                        f"章节 {chapter['chapter_id']} 的 carry_evidence '{ev_id}' 不在 case_data.evidences 中"
                    )

    if errors:
        raise ValueError("剧情脚本校验失败:\n" + "\n".join(f"  - {e}" for e in errors))


def list_available_stories(stories_dir: str = "stories") -> List[Dict]:
    """列出所有可用的剧情脚本。"""
    import os
    stories = []
    if not os.path.isdir(stories_dir):
        return stories
    for filename in sorted(os.listdir(stories_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(stories_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                stories.append({
                    "story_id": data.get("story_id", filename),
                    "title": data.get("title", filename),
                    "desc": data.get("desc", ""),
                    "chapter_count": len(data.get("chapters", [])),
                    "ending_count": len(data.get("endings", [])),
                    "filename": filename,
                })
            except Exception:
                pass
    return stories
```

---

## 7. 约束式案件生成器

### 7.1 设计

为 `generated` 类型章节提供 LLM 约束生成功能。在现有 `generate_case()` 基础上增加结构化约束注入。

```python
def generate_case_with_constraints(
    constraints: dict,
    story_variables: dict = None,
    max_retries: int = 1,
) -> dict:
    """在约束框架内生成案件。

    Args:
        constraints: 章节定义的 case_constraints
            - theme: 主题/背景
            - suspect_count: 嫌疑人数量
            - must_include: 必须包含的元素列表
            - difficulty: 难度
        story_variables: 当前叙事状态变量（注入到生成提示词）
        max_retries: 最大重试次数

    Returns:
        符合 CASE_SCHEMA 的案件数据
    """
    # 构建约束式系统提示词
    constraint_block = _build_constraint_block(constraints, story_variables)
    # 复用现有 generate_case 逻辑，但注入约束
    ...
```

**注意**：约束式生成器在 Phase 9 才实现。Phase 5-8 全部使用 `scripted` 类型章节。

---

## 8. 进度共享与持久化

### 8.1 PlayerProfile 扩展

```python
class PlayerProfile:
    # ── 共享字段 ──
    level: int                    # 全局等级
    experience: int               # 全局经验

    # ── 剧情模式独立 ──
    story_progress: Dict[str, dict]  # {story_id: {current_chapter_id, completed_chapters, ...}}
    story_tools_unlocked: Dict[str, List[str]]  # {story_id: ["psych_profile", ...]}

    # ── 自定义模式独立 ──
    custom_tools_unlocked: List[str]  # 基于等级解锁
```

### 8.2 经验获取规则

| 来源 | 经验值 | 说明 |
|------|--------|------|
| 剧情模式每章完成 | 配置基础经验 × 评级系数 | 默认基础20 exp；win/partial/fail系数来自 `gameplay_balance.json` |
| 自定义模式每局完成 | 沿用 Phase 4 评分系统 | 供词深度 + 行动效率 + 证据利用 + LLM评分 |

### 8.3 存档扩展

**sessions 表新增字段**：
- `mode TEXT DEFAULT 'custom'` — `"story"` 或 `"custom"`
- `story_progress_json TEXT` — 剧情模式专用进度 JSON

```sql
-- 增量迁移（DB_VERSION = 3）
ALTER TABLE sessions ADD COLUMN mode TEXT DEFAULT 'custom';
ALTER TABLE sessions ADD COLUMN story_progress_json TEXT;
```

**story_progress_json 结构**：
```json
{
  "story_id": "missing_father",
  "current_chapter_id": "ch05",
  "completed_chapters": ["ch01", "ch02a", "ch03", "ch04", "ch05"],
  "story_variables": {"met_informant": true, "first_case_success": true},
  "carried_evidence": [{"id": "e_ch01_key", "name": "...", "description": "..."}],
  "story_tools_unlocked": ["psych_profile", "lie_detector"]
}
```

---

## 9. UI 设计

### 9.1 主菜单

启动应用后显示主菜单（替代当前直接进入审讯室）：

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                    T H E   B O X                       │
│                Local Verdict                           │
│                                                         │
│         ┌───────────────────┐  ┌───────────────────┐   │
│         │   📖  剧情模式     │  │   🎮  自定义模式   │   │
│         │                   │  │                   │   │
│         │  体验完整的悬疑    │  │  自由设定案件     │   │
│         │  审讯故事线        │  │  背景进行审讯     │   │
│         │                   │  │                   │   │
│         │  [选择剧情 ▸]     │  │  [开始 ▸]         │   │
│         └───────────────────┘  └───────────────────┘   │
│                                                         │
│              ⚙ 设置    📂 读档                          │
│                                                         │
│              Lv.3  ████░░░░  120/200 exp               │
└─────────────────────────────────────────────────────────┘
```

### 9.2 剧情选择界面

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回                                                 │
│                                                         │
│  选择剧情                                                │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  📖 寻找失踪父亲                                 │   │
│  │  一段跨越二十年的悬疑故事...                      │   │
│  │  15章 · 3个结局                                  │   │
│  │  进度: 第3章/15章 ████░░░░░░░░                   │   │
│  │                                [继续 ▸]           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  📖 （更多剧情待添加...）                          │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 9.3 叙事过场

章节开始/结束时显示叙事文本（全屏覆盖，带淡入淡出动画）：

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                                                         │
│           第一章 · 初入警局                              │
│                                                         │
│     你是一名新入职的警探，第一天报到                      │
│     就被派去审讯一名嫌疑人...                            │
│                                                         │
│                                                         │
│                     [开始审讯 ▸]                         │
│                                                         │
│           第1章/15章  ● ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○   │
└─────────────────────────────────────────────────────────┘
```

### 9.4 WebBridge 新增信号

| 信号 | 参数 | 用途 | Phase |
|------|------|------|-------|
| `show_main_menu` | `` | 显示主菜单 | 5 |
| `mode_selected` | `str` | 模式选择完成 | 5 |
| `story_list_loaded` | `list` | 剧情列表加载完成 | 5 |
| `story_selected` | `str` | 选择了某个剧情 | 6 |
| `story_chapter_started` | `dict` | 章节开始（含叙事文本） | 6 |
| `story_chapter_completed` | `dict` | 章节完成（含结果和分支） | 7 |
| `story_narrative_text` | `str` | 叙事过场文本 | 7 |
| `story_progress_updated` | `dict` | 章节进度更新 | 7 |
| `story_ending_reached` | `dict` | 到达结局 | 7 |

---

## 10. 实施分期

| 阶段 | 主题 | 核心改动 | 预估工期 |
|------|------|---------|----------|
| Phase 5 | 主菜单 + 会话管理 | 主菜单UI + GameSession协调器 + 模式选择 + 自定义模式接入 | **4天** |
| Phase 6 | 剧情引擎核心 | StoryEngine + 章节JSON Schema + StoryLoader + ChapterResult评估 + 分支系统 | **5天** |
| Phase 7 | 剧情模式UI | 叙事过场 + 章节进度条 + 分支提示 + 存档扩展 + WebBridge信号 | **4天** |
| Phase 8 | MVP剧情脚本 | 5章"寻找失踪父亲"脚本编写 + 剧情模式集成测试 | **5天** |
| Phase 9 | 约束式生成器 | generated章节支持 + case_constraints + 扩展至15章完整剧情 | **6天** |

> **总工期：约 24 天**（MVP 5章约 18 天，扩展15章另加 6 天）

### 依赖与并行

```
Phase 1 (Part A) ─┬─→ Phase 2+ (Part A，可并行)
                   │
                   └─→ Phase 5 (Part B)
                        └─→ Phase 6
                             └─→ Phase 7
                                  └─→ Phase 8
                                       └─→ Phase 9
```

---

## 11. 风险评估

| 风险 | 可能性 | 影响 | 等级 | 应对策略 |
|------|--------|------|------|----------|
| 审讯结果三级判定不够细，分支体验单一 | 中 | 高 | P1 | 可通过 `min_confession` / `min_evidence` 细化条件；MVP阶段验证后调整阈值 |
| 约束式案件生成质量不稳定 | 高 | 中 | P1 | Phase 5-8 全用 scripted，Phase 9 再引入 generated；生成结果缓存 |
| 15章剧情脚本内容量过大 | 高 | 中 | P1 | 先5章MVP验证系统，再逐步扩展 |
| WebMainWindow 职责膨胀 | 中 | 高 | P1 | GameSession 协调器抽离模式逻辑 |
| 存档恢复后StoryEngine状态不一致 | 低 | 高 | P1 | from_dict 时校验 story_progress 与 chapters 定义一致性 |
| 主菜单改造影响现有自定义模式流程 | 中 | 中 | P2 | GameSession 兼容旧流程，自定义模式行为不变 |
| 跨章节证据与当前案件 forbidden_to_reveal 冲突 | 中 | 中 | P2 | 跨章节证据不参与 forbidden_to_reveal 匹配 |

---

## 12. 测试计划

| Phase | 测试内容 |
|-------|---------|
| 5 | GameSession 模式切换、主菜单 UI 交互、自定义模式回归测试 |
| 6 | StoryEngine 章节流转、分支条件匹配、ChapterResult 评估、StoryLoader 校验 |
| 7 | 叙事过场 UI、章节进度更新、存档恢复剧情进度 |
| 8 | 5章完整剧情流程、分支覆盖、结局可达性、跨章节证据传递 |
| 9 | 约束式生成器质量、generated章节 CASE_SCHEMA 合规、15章完整通关 |

---

## 13. 弱模型执行任务包与验收

双模式系统可以和 Part A 后续阶段并行，但必须在 Phase 1 验收后启动。弱模型执行时优先实现纯 Python 的 GameSession/StoryEngine，再做 UI，最后写剧情内容和生成器。

### 任务包拆分

| 包 | 范围 | 允许修改 | 验收重点 |
|----|------|----------|----------|
| 5a GameSession骨架 | 模式切换、自定义模式兼容、engine属性转发 | `core/game_session.py`, `ui/web_main_window.py`, `tests/test_game_session.py` | 自定义模式行为不变 |
| 5b 主菜单UI | 模式选择、剧情入口占位、自定义入口 | `ui/web/`, `ui/web_bridge.py`, `tests/test_menu_ui.py` | 主菜单不破坏现有案件生成 |
| 6a Story schema | `schemas/story.py`、StoryLoader校验、fixture故事 | `schemas/story.py`, `core/story_loader.py`, `tests/test_story_loader.py` | 分支next、merge_to、case_data均校验 |
| 6b StoryEngine | 章节开始、完成、分支匹配、变量传递 | `core/story_engine.py`, `tests/test_story_engine.py` | 不使用 eval，声明式条件按顺序匹配 |
| 6c ChapterResult | 结果评估、`culprit_name`胜利判断、AP百分比 | `core/game_session.py`, `schemas/story.py`, `tests/test_chapter_result.py` | 无辜崩溃不能返回win |
| 7a 剧情UI | 叙事过场、章节进度、结局页 | `ui/web/js/story.js`, `ui/web/css/`, `ui/web_bridge.py`, `tests/test_story_ui.py` | 章节开始/完成事件字段一致 |
| 8a MVP脚本 | 5章 scripted 剧情、分支覆盖、结局可达 | `stories/missing_father.json`, `tests/test_story_mvp.py` | 每章case_data符合CASE_SCHEMA |
| 9a 约束生成器 | generated章节、case_constraints、生成结果缓存 | `core/case_generator.py`, `tests/test_story_generation.py` | 生成结果必须含 `culprit_name` 且Schema合规 |

### Definition of Done

| 条件 | 要求 |
|------|------|
| 自定义模式无回归 | 不选择剧情时，现有自定义案件流程完全可用 |
| 声明式分支 | 分支条件只用 JSON 字段，不使用 `eval()` 或 Python表达式 |
| 真凶判断 | ChapterResult 的 `win` 只允许 `culprit_name` 对应嫌疑人崩溃 |
| 存档恢复 | story_progress、current_chapter_id、completed_chapters、carried_evidence 可恢复 |
| 脚本合规 | scripted章节全部通过 CASE_SCHEMA 和 STORY_SCHEMA |
| 生成隔离 | Phase 5-8 不依赖 generated；Phase 9 才接入真实生成器 |

### 阶段验收场景

| 场景 | 验收方式 |
|------|----------|
| 自定义模式回归 | 从主菜单进入自定义模式，生成/加载/审讯流程和原先一致 |
| 剧情章节推进 | ch01 win/partial/fail 三条路径进入不同 next |
| 分支兜底 | 条件都不满足时命中最后一个只有 `next` 的兜底分支 |
| 跨章节证据 | carry_evidence 合并进下一章，但不参与 forbidden_to_reveal 胜利触发 |
| 存档恢复 | 中途退出后恢复到正确章节和变量 |
| 5章MVP通关 | 三种结果路径至少各覆盖一次，所有结局可达 |
