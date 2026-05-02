# 《The Box: Local Verdict》AI Agent 自主开发与验收文档

## 文档目的
本文档用于指导多个 AI Agent（开发Agent、测试Agent、评审Agent）按阶段自主完成项目 **The Box: Local Verdict** 的全部开发、测试与交付。  
每个阶段包含：
- **任务目标**
- **输入/输出规范**
- **开发Agent Prompt**（需实现的内容）
- **测试Agent Prompt**（需编写的验收脚本及执行命令）
- **评审Agent Prompt**（验证交付物是否达标）

项目完全基于 **Python 3.10+**，使用 PySide6、SQLite、OpenAI API，代码风格遵循 PEP8。

---

## 全局约定（所有Agent必须遵守）

### 项目结构（最终形态，各阶段逐步生成）
```
the_box_local/
├── .github/
│   └── workflows/
│       └── ci.yml
├── main.py
├── core/
│   ├── __init__.py
│   ├── exceptions.py              # 自定义异常层次
│   ├── config.py
│   ├── logger.py                  # 统一日志配置
│   ├── llm_client.py              # LLM 调用封装（单例）
│   ├── db.py
│   ├── case_generator.py
│   ├── suspect_agent.py
│   └── interrogation.py
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── chat_widget.py
│   ├── evidence_panel.py
│   ├── suspect_display.py
│   └── admin_dialog.py
├── schemas/
│   ├── __init__.py
│   ├── interface_definitions.py   # 跨模块接口类型定义
│   ├── events.py                  # 引擎与UI事件格式
│   └── validation_schema.json     # 案件JSON Schema
├── assets/                        # 占位图片
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── mock_cases/
│   │   │   ├── simple.json
│   │   │   └── full.json
│   │   ├── mock_suspect_responses.json
│   │   └── conftest.py            # 全局fixtures
│   ├── test_db.py
│   ├── test_config.py
│   ├── test_generator.py
│   ├── test_suspect.py
│   ├── test_engine.py
│   ├── test_gui.py
│   ├── test_gui_full.py
│   └── test_e2e.py
├── scripts/
│   ├── validate_case.py
│   └── quality_metrics.py
├── docs/
│   ├── ERROR_HANDLING.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── USER_STORIES.md
│   └── TEMPLATE_MODULE.md
├── .flake8
├── .isort.cfg
├── .pre-commit-config.yaml
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 依赖统一（requirements.txt）
```
pyside6>=6.5.0
openai>=1.0.0
pytest>=7.0
pytest-qt>=4.2
pytest-cov>=4.0
pytest-timeout>=2.1
jsonschema>=4.17
keyring>=24.0.0
cryptography>=41.0.0
pre-commit>=3.5.0
radon>=6.0
flake8>=6.0
black>=23.0
isort>=5.12
```

### 环境变量 / 配置
API key 存储在用户本地，通过 `keyring` 读取。模型名默认 `gpt-4o-mini`，可配置。

### 通用函数签名（必须遵循）
所有模块的函数签名在文档中严格定义，实现时不得随意修改。

### 日志与错误处理
每个模块使用 `logging.getLogger("thebox")`，输出到 `logs/thebox.log`。日志配置由 `core/logger.py` 统一管理。

### 验收通用标准
- 所有 `pytest` 测试通过（无错误、无跳过）
- 代码覆盖率（核心模块）≥ 80%
- 无内存泄漏（通过 `tracemalloc` 简测）
- 符合 PEP8（可用 `flake8` 检查）

---

## 里程碑0：基础设施与环境搭建

### 任务目标
创建项目目录结构、虚拟环境、依赖文件、数据库初始化模块、配置管理模块、日志模块、异常定义、LLM客户端封装、接口契约。

### 输入
无（从头开始）

### 输出
- 整个项目骨架（目录结构，含 schemas/、docs/、tests/fixtures/ 等）
- `requirements.txt`
- `core/exceptions.py` 自定义异常层次
- `core/logger.py` 统一日志配置
- `core/db.py` 实现数据库表创建、保存/加载案件、存档/读档基本函数
- `core/config.py` 实现API key读取/存储（使用keyring）
- `core/llm_client.py` LLM调用封装（单例，懒初始化）
- `schemas/interface_definitions.py` 跨模块接口类型定义
- `schemas/events.py` 引擎与UI事件格式
- `schemas/validation_schema.json` 案件JSON Schema
- `main.py` 空窗口启动（显示"Hello The Box"）

### 开发Agent Prompt

```markdown
你是一个Python后端开发Agent。任务：搭建项目基础设施。

请执行以下操作：
1. 在空白目录创建上述项目结构，所有 `__init__.py` 可为空。
2. 编写 `requirements.txt` 内容如上。
3. 实现 `core/db.py`：
   - 定义 `init_db(db_path="thebox.db")` -> None，创建两张表：
     - cases: (case_id TEXT PRIMARY KEY, title TEXT, json_data TEXT, created_at TIMESTAMP)
     - sessions: (session_id TEXT PRIMARY KEY, case_id TEXT, current_state_json TEXT, saved_at TIMESTAMP)
   - 实现 `save_case(case_dict) -> None`
   - 实现 `load_case(case_id) -> dict | None`
   - 实现 `save_session(session_id, case_id, state_dict) -> None`
   - 实现 `load_session(session_id) -> (case_id, state_dict) | None`
   - 使用 sqlite3 标准库，所有操作包装在 try/except，记录日志。
4. 实现 `core/config.py`：
   - `get_api_key(service="openai") -> str`：使用 keyring.get_password
   - `set_api_key(key: str, service="openai") -> None`：使用 keyring.set_password
   - `get_model() -> str`：从环境变量或配置文件读取，默认 "gpt-4o-mini"
   - `set_model(model: str) -> None`：写入用户目录下的 `.thebox_config.json`
5. 实现 `main.py`：
   - 导入 `PySide6.QtWidgets` 创建 QApplication 和 QMainWindow，窗口标题 "The Box: Local Verdict"
   - 添加菜单栏“设置” -> “API Key”，弹出对话框调用 `set_api_key`
   - 状态栏显示当前模型名称
   - 窗口中央显示标签“开发中 – 里程碑0”
   - 在程序启动时调用 `init_db()` 确保数据库存在。

6. 实现 `core/exceptions.py`：
   - 定义 `TheBoxError(Exception)` 基类及子类：`NetworkError`, `LLMResponseError`, `DatabaseError`, `ValidationError`, `ConfigError`。
7. 实现 `core/logger.py`：
   - 全局 logger 名为 `"thebox"`，配置 RotatingFileHandler（10MB滚动，5备份）和 StreamHandler。
   - 提供 `setup_logger()` 函数和模块级 `logger` 实例。
8. 实现 `core/llm_client.py`：
   - `LLMClient` 单例类，**懒初始化**：`__new__` 不自动调用 `_init_client`，而是提供 `initialize()` 方法，首次使用时或 API Key 设置后调用。
   - `chat_completion(messages, temperature, max_tokens, response_format)` 方法：重试2次，指数退避。
   - `_init_client()` 从 `config.get_api_key()` 获取 key，如无 key 则设置 `self._initialized = False`（不抛异常，以便离线模式可用）。
   - 全局实例 `llm_client = LLMClient()` 在模块导入时不执行网络操作。
9. 实现 `schemas/interface_definitions.py` 和 `schemas/events.py`：
   - 类型定义如 `project-init.md` 中所述（`SuspectAgentProtocol`, `CaseDict`, `EngineStateDict`, 各种 Event 类型）。
10. 实现 `schemas/validation_schema.json`：保存案件 JSON Schema（内容见下方 M1 中的 JSON Schema 定义，M0 阶段提前创建此文件）。
**注意**：不要遗漏任何导入和错误处理。所有函数必须有 docstring。
```

### 测试Agent Prompt

```markdown
你是一个测试开发Agent。任务：为里程碑0编写自动化验收测试。

请编写以下测试文件：
1. `tests/test_db.py`：
   - 测试 `init_db` 创建表（可以检查表是否存在）
   - 测试 `save_case` 和 `load_case` 的存储与读取正确性（使用临时数据库）
   - 测试 `save_session`/`load_session`
2. `tests/test_config.py`：
   - 使用 `unittest.mock` 模拟 keyring，测试 get/set api key
   - 测试模型读写（临时配置文件）
3. `tests/test_exceptions.py`：
   - 测试所有自定义异常的继承关系正确
4. `tests/test_logger.py`：
   - 测试 `setup_logger` 返回名为 "thebox" 的 logger
   - 测试 handler 不重复添加
5. `tests/test_llm_client.py`：
   - 测试 `LLMClient` 单例行为
   - 测试 `initialize()` 在无 API Key 时 `_initialized` 为 False，不抛异常
   - Mock 测试 `chat_completion` 重试逻辑
6. `tests/test_main.py` (pytest-qt)：
   - 启动 `main.py` 中的主窗口，检查标题、菜单栏是否存在
   - 模拟点击“设置”->“API Key”，输入测试key，验证 keyring 被调用

执行要求：
- 所有测试必须独立，不依赖外部网络（除了模拟）。
- 使用 `pytest --cov=core --cov=ui --cov-report=term` 运行。

验收命令：`pytest tests/ -v --tb=short`
```

### 评审Agent Prompt

```markdown
你是一个评审Agent。请验证里程碑0的交付成果满足以下指标：
- 目录结构完整，所有文件存在（含 schemas/、core/exceptions.py、core/logger.py、core/llm_client.py）。
- `python main.py` 能正常启动图形窗口，无报错。
- 运行 `pytest tests/` 全部通过（需要安装在干净虚拟环境）。
- 代码中无硬编码 API Key，无明文存储。
- 数据库文件 `thebox.db` 在运行后自动生成，表结构正确。
- `LLMClient` 在未设置 API Key 时不抛异常，`_initialized` 为 False。
- `schemas/` 下所有类型定义可正常导入，无语法错误。

若满足，输出 “M0验收通过”；否则列出不满足项和修复建议。
```

---

## 里程碑1：案件生成器与逻辑验证器

### 任务目标
实现 `case_generator.py` 调用 LLM 生成符合 JSON Schema 的案件；实现 `validate_case.py` 自动检查逻辑闭环（动机、手段、时机覆盖唯一性）。

### 输入
管理员输入的背景故事（字符串）。

### 输出
- `core/case_generator.py`：包含 `generate_case(background: str, model_override: str = None) -> dict`
- `scripts/validate_case.py`：命令行工具，接收 JSON 文件路径，输出验证报告
- `tests/test_generator.py`：测试生成器成功率、Schema 验证、逻辑验证

### JSON Schema（固定）
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "case_id": {"type": "string"},
    "title": {"type": "string"},
    "victim": {"type": "string"},
    "cause_of_death": {"type": "string"},
    "crime_scene": {"type": "string"},
    "truth": {"type": "string"},
    "suspects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "role": {"type": "string"},
          "personality": {"type": "string"},
          "knowledge": {"type": "string"},
          "forbidden_to_reveal": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["name", "knowledge", "forbidden_to_reveal"]
      }
    },
    "evidences": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string"},
          "related_suspect": {"type": "string"}
        },
        "required": ["id", "name", "description"]
      }
    },
    "interrogation_time_limit_sec": {"type": "integer"}
  },
  "required": ["case_id", "title", "victim", "cause_of_death", "crime_scene", "truth", "suspects", "evidences", "interrogation_time_limit_sec"]
}
```

### 开发Agent Prompt

```markdown
你是一个后端开发Agent。实现案件生成器与逻辑验证器。

**1. 实现 `core/case_generator.py`**：
- 函数 `_build_system_prompt(background)`：返回字符串，指导 LLM 输出严格 JSON，包含上述 Schema 的所有字段，并附加约束：
  - 所有嫌疑人的 `knowledge` 并集必须能推出 `truth`
  - 只有一个真凶（可在 `knowledge` 中暗示，但不要直接写"我是凶手"）
  - `forbidden_to_reveal` 包含真凶绝不能直接承认的关键词。
- 使用 `core.llm_client.LLMClient` 单例调用 `chat_completion`，设置 `response_format={"type": "json_object"}`，模型默认为配置中的模型。
- 解析响应为 dict，使用 `jsonschema.validate` 校验，校验失败则重试一次（更换 seed）。
- 返回案件 dict。

**2. 实现 `scripts/validate_case.py`**：
- 命令行参数 `--case-file`，加载 JSON。
- 实现三个检查：
  a) Schema 校验。
  b) **动机-手段-时机覆盖检查**：从 `truth` 中提取三要素（例如通过关键词正则或简单规则：truth 必须包含“因…动机”、“用…手段”、“在…时间”这样的模式，或者更鲁棒：将 `knowledge` 与 `truth` 做文本包含检查，确保每个要素至少被一个嫌疑人知道）。
  c) **真凶唯一性检查**：根据 `knowledge` 构建简单推理：如果某嫌疑人知道的要素集合包含所有三个要素，且其他嫌疑人都不完全包含，则唯一；否则报告冲突。
- 输出通过/失败及详细原因。

**3. 编写测试 `tests/test_generator.py`**：
- 使用预定义的 10 个背景故事（硬编码），循环调用 `generate_case`，对每个结果：
  - 通过 jsonschema 校验
  - 通过 `validate_case` 脚本（导入模块调用）
- 统计成功率，要求 ≥ 90%（允许因 API 输出格式问题失败 1 次，重试后仍失败可算一次失败）。
- 使用 `pytest.mark.slow` 标记。

**注意**：真实调用 API，需要设置环境变量 OPENAI_API_KEY（测试时会从 keyring 读取）。你可以在测试中跳过如果没有 key，但必须在 CI 中运行。
```

### 测试Agent Prompt

```markdown
你是一个测试Agent。为案件生成器编写更全面的验收测试。

1. 编写 `tests/test_validate_case.py`：
   - 提供一个正确的样本案件（手工构造），验证 `validate_case` 返回 True。
   - 提供一个缺失动机的案件（故意修改），验证返回 False 并指出缺失项。
2. 编写 `tests/test_generator_schema_failure.py`：
   - 使用 `unittest.mock` 模拟 LLM 返回非 JSON，验证生成器会重试并最终抛出异常。
3. 编写性能测试：生成一个案件的平均耗时不超过 15 秒（在正常网络下）。

验收命令：
```bash
pytest tests/test_generator.py tests/test_validate_case.py -v --durations=5
```
```

### 评审Agent Prompt

```markdown
评审标准：
- 运行 `python scripts/validate_case.py --case-file sample_cases/valid_case.json` 输出 “验证通过”。
- 运行 `pytest tests/test_generator.py -k test_success_rate` 成功率 ≥ 90%。
- 检查 `case_generator.py` 中 API 调用使用了 `LLMClient` 单例，没有硬编码 API Key。
- 生成的案件 JSON 中所有 `forbidden_to_reveal` 列表非空。
- 逻辑验证器能准确识别出故意破坏的案件。

如果全部满足，输出 “M1验收通过”。
```

---

## 里程碑2：嫌疑人Agent核心（防自爆、压力系统）

### 任务目标
实现 `SuspectAgent` 类，每个实例管理单个嫌疑人的对话历史、压力值，调用 LLM 回复玩家，并确保不泄露 `forbidden_to_reveal` 内容。

### 输入
案件 JSON 中单个 suspect 对象 + 案件标题。

### 输出
- `core/suspect_agent.py`
- `tests/test_suspect.py`（包含防自爆、人设一致性、压力变化、内存泄漏测试）

### 接口定义
```python
class SuspectAgent:
    def __init__(self, suspect_data: dict, case_title: str):
        self.name = suspect_data["name"]
        self.pressure = 50  # 0-100
        self.memory = []    # list of {"role": "user"/"assistant", "content": str}
        self._build_system_prompt(suspect_data, case_title)

    def respond(self, player_input: str, context: dict = None) -> dict:
        """
        返回格式：
        {
            "reply": str,
            "pressure_change": int,   # 正值增加压力，负值减少
            "secret_triggered": str | None   # 如果触发了某个 forbidden 条目，返回该条目
        }
        """
        pass
```

### 开发Agent Prompt

```markdown
你是一个 Agent 开发专家。实现 `SuspectAgent` 类，遵循以下详细要求。

**系统提示构建**：
- 包含角色背景、性格、知识（`knowledge`）、禁忌列表（`forbidden_to_reveal`）。
- 明确指令：决不能在回复中包含 `forbidden_to_reveal` 中的任何词语或同义表达。
- 加入压力值描述：压力值越高，嫌疑人越容易慌乱，可能语无伦次或不小心说漏嘴（但仍不能直接说出 forbidden 内容）。
- 回复要符合人设，长度控制在 1-3 句。

**LLM 调用**：
- 使用 `core.llm_client.LLMClient` 单例调用 `chat_completion`，消息列表 = 系统提示 + memory（最近10轮） + 当前用户输入。
- 传入 `response_format={"type": "json_object"}`，要求输出 JSON 包含 `reply`, `pressure_change`, `secret_triggered`。
- 处理异常（`NetworkError`, `LLMResponseError`）：返回默认回复"（嫌疑人沉默不语）"，pressure_change=0。

**后处理**：
- 检查 `reply` 中是否包含任何 `forbidden_to_reveal` 子串（忽略大小写），若包含则替换为：“（嫌疑人略显紧张，但并没有直接回答你的问题。）”，并将 `secret_triggered` 设置为匹配到的条目，压力值额外 +20。
- 更新 `self.pressure = max(0, min(100, self.pressure + pressure_change))`。
- 将用户输入和回复追加到 `self.memory`，保持最近 10 轮。

**内存管理**：
- 提供 `truncate_memory(max_turns=10)` 方法。
```

### 测试Agent Prompt

```markdown
你是一个测试Agent。编写 `tests/test_suspect.py`，至少包含以下测试用例：

1. **test_forbidden_not_leaked**：
   - 创建一个具有显式 `forbidden_to_reveal = ["我是凶手", "我杀了他"]` 的嫌疑人。
   - 多次发送引导性提问（如“凶手就是你吧？”），收集回复。
   - 断言没有任何回复包含 forbidden 短语。

2. **test_pressure_change_on_evidence**：
   - Mock LLM 返回固定的 `pressure_change=+30`。
   - 调用 `respond` 后检查 `agent.pressure` 从 50 变为 80。

3. **test_consistency_with_personality**（需要辅助 LLM 裁判）：
   - 准备 5 轮对话历史，调用一个低成本模型（如 gpt-3.5-turbo）评估回复是否符合角色性格，要求平均分 ≥ 4/5。
   - 打分提示词：“给定角色描述：{personality}，以下对话是否符合该角色的语气和知识？请输出1-5分。”

4. **test_memory_limit**：
   - 连续发送 20 条消息，检查内存列表长度 ≤ 11（系统提示+10轮）。

5. **test_no_memory_leak**：
   - 循环调用 `respond` 1000 次，使用 `tracemalloc` 检查内存增长 < 10%。

注意：对于需要真实 LLM 调用的测试，使用 `pytest.mark.real_api` 标记，默认跳过；但在验收时会运行。
```

### 评审Agent Prompt

```markdown
评审指标：
- 运行 `pytest tests/test_suspect.py -m "not real_api"` 全部通过。
- 手动触发真实 API 测试（若网络允许）显示防自爆通过率 100%。
- 检查代码：`respond` 方法中通过 `LLMClient` 单例调用 LLM，没有直接使用 `openai` 或硬编码 API Key。
- 压力值变化逻辑正确：范围限制在 0-100。

通过后输出 “M2验收通过”。
```

---

## 里程碑3：审讯引擎 + GUI基础框架

### 任务目标
实现审讯引擎 `InterrogationEngine` 管理多嫌疑人审讯流程；实现主窗口的基本布局（聊天区域、嫌疑人选择、倒计时、输入框），且能使用 Mock 嫌疑人完成一轮简单对话。

### 输入
案件 dict，玩家动作。

### 输出
- `core/interrogation.py`
- `ui/main_window.py`（初步）
- `tests/test_engine.py`
- `tests/test_gui_smoke.py`

### 接口定义（引擎）
```python
from schemas.events import UIEvent

class InterrogationEngine:
    def __init__(self, case_data: dict):
        self.case = case_data
        self.suspects = [SuspectAgent(s, case_data["title"]) for s in case_data["suspects"]]
        self.current_suspect_index = 0
        self.presented_evidence_ids = set()
        self.time_left = case_data["interrogation_time_limit_sec"]
        self.state = "selecting"  # selecting, interrogating, breakdown, verdict

    def select_suspect(self, index: int) -> dict:
        # 返回当前嫌疑人信息（名字、压力值）
        pass

    def submit_action(self, action: str, content: str, evidence_id: str = None) -> list[UIEvent]:
        """
        action: "chat", "pressure", "empathy", "present_evidence"
        返回 UIEvent 列表，包含 NewMessageEvent、SuspectUpdateEvent、
        StateChangeEvent、TimerTickEvent 等事件（见 schemas/events.py）。
        UI 层遍历事件列表，逐一处理更新界面。
        """
        pass
```

### 开发Agent Prompt

```markdown
你是一个后端+前端开发Agent。实现审讯引擎和主窗口骨架。

**1. 引擎实现**：
- `submit_action` 调用当前嫌疑人的 `respond` 方法，根据 `action` 类型调整 `pressure_change`：
  - "chat": 无额外修正。
  - "pressure": pressure_change += 10（施压）。
  - "empathy": pressure_change -= 5（共情）。
  - "present_evidence": 检查证据 ID 是否在案件的 `evidences` 中，如果与该嫌疑人相关（`related_suspect` 匹配或描述包含其名），则 pressure_change += 20，并记录到 `presented_evidence_ids`。
- 如果 `secret_triggered` 不为空，将 `state` 置为 "breakdown"，并触发结局判断。
- 倒计时：提供 `tick(seconds_elapsed)` 方法，减 `time_left`，如果 ≤0 则状态变为 "verdict" 且结局为超时。

**2. 主窗口实现**（`ui/main_window.py`）：
- 继承 `QMainWindow`，使用 QWidget 作为 central widget，布局为 QVBoxLayout。
- 顶部：QLabel 显示嫌疑人名字 + QProgressBar 压力条。
- 中间：QTextEdit 只读聊天记录。
- 底部：QLineEdit + QPushButton “发送”。
- 左侧或下拉框：QComboBox 用于选择嫌疑人（只有 state 为 selecting 时启用）。
- 菜单栏：案件 -> 生成新案件（调用 admin_dialog 占位）、加载预置案件。
- 绑定信号槽：发送按钮将输入传给引擎的 `submit_action("chat", ...)`，更新聊天记录和压力条。

**3. 与引擎集成**：
- 创建 `MainWindow.engine` 属性。
- 定义 `update_ui_from_engine(events: list[UIEvent])` 遍历事件列表，根据事件类型刷新聊天区域、压力条、倒计时等。

**注意**：目前阶段使用 `DummySuspectAgent`（固定回复）代替真实 SuspectAgent，以便快速测试 UI。
```

### 测试Agent Prompt

```markdown
编写测试：

**`tests/test_engine.py`**：
- 使用固定测试案件，创建一个 `DummySuspectAgent`（返回预设回复）。
- 测试 `select_suspect` 切换后 `current_suspect_index` 正确。
- 测试 `submit_action` 出示不存在的证据，压力不变。
- 测试倒计时归零触发超时状态。
- 测试触发秘密破绽后状态变为 "breakdown"。

**`tests/test_gui_smoke.py`**（pytest-qt）：
- 启动主窗口，加载测试案件。
- 模拟点击嫌疑人下拉框，选择第二个嫌疑人。
- 在输入框输入“你好”，点击发送，验证聊天记录出现嫌疑人回复（预设回复）。
- 模拟点击“生成案件”菜单（弹出对话框），取消对话框，无崩溃。

验收命令：
```bash
pytest tests/test_engine.py tests/test_gui_smoke.py -v
```
```

### 评审Agent Prompt

```markdown
验证：
- 运行 `python main.py` 后，可以手动加载案件（从预置 JSON），选择嫌疑人，发送消息，聊天显示正常。
- 切换到另一个嫌疑人，压力条更新。
- 运行测试套件全部通过，无 Qt 相关警告。

满足后输出 “M3验收通过”。
```

---

## 里程碑4：完整UI与证据系统集成

### 任务目标
实现证据面板、施压/共情按钮、立绘压力表情变化、管理员生成对话框和完整审讯流程（含结局）。

### 输出
- `ui/evidence_panel.py`, `ui/suspect_display.py`, `ui/admin_dialog.py`
- 完善 `main_window.py`
- `tests/test_gui_full.py`

### 开发Agent Prompt

```markdown
你是一个全栈Agent。实现以下UI组件并集成：

**1. 证据面板**（`evidence_panel.py`）：
- 类 `EvidencePanel(QDockWidget)`，右侧停靠。
- 列表显示所有证据（从 `engine.case["evidences"]` 加载），每个项包含名称、简要描述，点击时发出 `evidence_selected(evidence_id)` 信号。
- 主窗口接收信号，启用“出示证据”按钮（或直接调用引擎）。

**2. 嫌疑人立绘显示**（`suspect_display.py`）：
- 类 `SuspectDisplay(QWidget)`：包含 QLabel 显示图片（根据压力值切换：<30 正常，30-70 紧张，>70 崩溃）。
- 提供 `update_pressure(pressure)` 方法切换图片。
- 使用 assets 中的占位图（可提供三个默认 SVG 或 PNG）。

**3. 管理员对话框**（`admin_dialog.py`）：
- 类 `AdminDialog(QDialog)`：包含 QTextEdit 输入背景故事，QLineEdit 输入模型名（可选），QPushButton “生成”。
- 调用 `case_generator.generate_case`，成功后关闭对话框并发出 `case_generated(case_dict)` 信号，主窗口加载该案件并初始化引擎。

**4. 主窗口完善**：
- 添加 QToolBar 包含“施压”、“共情”按钮，调用 `engine.submit_action` 对应操作。
- 集成证据面板：点击证据后显示确认框，确认后调用 `submit_action("present_evidence", evidence_id=id)`。
- 实现结局处理：当引擎状态变为 "verdict" 时，弹出 QMessageBox 显示结局（破案成功/超时/律师介入），并提供“重新开始”或“返回主菜单”选项。

**5. 倒计时实现**：使用 QTimer 每秒触发 `engine.tick(1)` 并更新界面显示。

**注意**：所有引擎调用需放在 QThread 中避免界面卡顿（因为 LLM 请求耗时）。实现一个 `Worker` 类。
```

### 测试Agent Prompt

```markdown
编写 `tests/test_gui_full.py`：
- 使用 `pytest-qt` 模拟完整游戏流程：
  - 点击“案件”->“生成新案件”，在对话框中输入“工厂谋杀案”，点击生成。
  - 等待生成完成（模拟信号）。
  - 选择嫌疑人，依次点击“施压”、“出示证据”（模拟点击某个证据项）。
  - 验证聊天记录包含嫌疑人回复，压力条变化，立绘改变。
  - 验证倒计时走到最后弹出超时结局。
  - 验证结局对话框含有“律师介入”字样。
- 使用 mock 替换真实 LLM 调用，使测试快速且稳定。

验收命令：`pytest tests/test_gui_full.py -v --qt-logging=WARNING`
```

### 评审Agent Prompt

```markdown
手动验证：
- 管理员可以生成案件，生成后立即可审。
- 出示证据时，效果明显（压力增加）。
- 立绘随压力平滑切换。
- 倒计时动效正常，超时弹出正确结局。
- 存档功能（尚未实现，但界面不应崩溃）。

若功能完整且测试通过，输出 “M4验收通过”。
```

---

## 里程碑5：集成、存档/读档与端到端测试

### 任务目标
实现完整的存档/读档功能；串联所有模块，用真实 LLM 端到端测试；打包可执行文件。

### 输出
- 存档/读档功能
- `tests/test_e2e.py`
- PyInstaller 打包脚本 `build.spec`
- README 用户文档

### 开发Agent Prompt

```markdown
实现存档/读档功能：

**1. 在 `core/db.py` 中补充**：
- `save_full_session(session_id, case_id, engine_state_dict)`，其中 engine_state_dict 包含：
  - suspects_states: 每个嫌疑人的 memory, pressure, name 等
  - presented_evidence_ids, time_left, current_suspect_index, state
- `load_full_session(session_id)` 返回 engine_state_dict。

**2. 在 `InterrogationEngine` 中增加**：
- `to_dict()` 序列化自身。
- `from_dict(state, case_data)` 静态方法重建引擎。

**3. 在 UI 中添加**：
- 菜单栏“游戏” -> “存档” (调用 engine 保存到数据库，生成 session_id)
- “读档” -> 弹窗显示已有存档列表，选择后加载。

**4. 打包**：
- 创建 `build.spec` 使用 PyInstaller，包含所有 assets 和数据库初始化脚本。
- 运行 `pyinstaller build.spec` 生成 `dist/TheBox.exe`。

**5. 端到端测试脚本** `tests/test_e2e.py`：
- 使用预定义的 3 个背景故事，调用真实案件生成。
- 模拟最优策略（遍历所有证据，对每个嫌疑人施压直到压力>80），确保最终能指认真凶。
- 中途随机执行一次存档，退出程序，重新加载并恢复，确认状态一致。
- 验证最终结局为“成功破案”。

注意：真实 API 测试可能耗时，使用 `pytest.mark.slow` 标记。
```

### 测试Agent Prompt

```markdown
编写 e2e 测试，要求：
- 使用 `pytest` 的 fixture 准备一个干净的数据库。
- 对每个案件，运行审讯并断言结局为成功。
- 使用 `pytest-timeout` 设置每个案件最长 5 分钟。
- 测试存档恢复：在审讯中调用 `save_session`，然后新建引擎加载，比较所有属性是否一致。

验收命令：
```bash
pytest tests/test_e2e.py -v -m slow
```
```

### 评审Agent Prompt

```markdown
最终验收：
1. 运行 `pytest tests/ -m "not slow"` 快速测试全部通过。
2. 运行 `pytest tests/test_e2e.py -m slow` 三个案件全部成功破案（可接受一次重试）。
3. 手动测试：生成一个案件，审讯一半存档，退出程序，重启读档，完全恢复。
4. 在无 Python 环境的新机器上运行 `dist/TheBox.exe`，能正常启动、生成案件、审讯。
5. README 包含 API Key 配置说明、支持模型列表、常见问题。

全部满足后输出 “项目验收完成，可交付”。
```

---

## 附：跨阶段通用验收脚本

项目根目录提供 `run_all_checks.sh` (Linux/macOS) 或 `run_all_checks.bat` (Windows)：
```bash
# 设置 PYTHONPATH
export PYTHONPATH=$(pwd)
# 运行所有非慢速测试
pytest tests/ -m "not slow" --cov=core --cov=ui --cov-report=html
# 运行 flake8
flake8 core ui --max-line-length=120
# 检查数据库初始化
python -c "from core.db import init_db; init_db(); print('DB OK')"
```

AI Agent 在每个阶段交付时必须提供该脚本通过的结果。

---

## 总结

本文档提供了从 M0 到 M5 的详细任务分解、针对开发Agent和测试Agent的精确 Prompt，以及评审标准。每个阶段的交付物均可独立验证，最终整合为完整的桌面游戏。AI Agent 团队可根据此文档并行工作，确保高质量、可验收的产出。