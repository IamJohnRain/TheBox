# BUG-4: 存档读档失败 — 优化方案

> 优先级: **P0** (核心功能不可用)  
> 影响范围: 后端 Python  
> 可并行: 是（与 BUG-2, BUG-5, BUG-6 无文件冲突）  
> 负责 Agent: Agent-A

---

## 1. 问题描述

用户存档后再读档，存档列表显示"未知案件"，点击后读档失败，提示"关联案件未找到"。

## 2. 根因分析

### 2.1 核心BUG：存档时未保存案件数据到 `cases` 表

完整调用链路追踪：

**Step 1: 案件生成时** — `web_main_window.py:481-485`

```python
def _on_case_generated(self, case_dict):
    self.bridge.case_generation_complete.emit(case_dict)
    self.load_case(case_dict)  # ← 只加载到引擎，未调用 db.save_case()
```

`load_case()` 只做了 `self.engine = InterrogationEngine(case_data)` + 向前端发信号，**从未将 case_dict 写入 `cases` 表**。

**Step 2: 存档时** — `web_main_window.py:507-525`

```python
def _on_save_game(self):
    case_id = self.engine.case.get("case_id", "unknown")  # ← case_id 可能是 "unknown"
    db.save_full_session(session_id, case_id, engine_state_dict)
    # ← 只存了 session 到 sessions 表，未存 case 到 cases 表！
```

**Step 3: 读档列表显示时** — `web_main_window.py:533-535`

```python
case_data = db.load_case(case_id)  # ← 从 cases 表查找，返回 None！
case_title = case_data.get("title", "未知案件") if case_data else "未知案件"
# ← case_data 为 None → 显示 "未知案件"
```

**Step 4: 加载存档时** — `web_main_window.py:565-567`

```python
case_data = db.load_case(case_id)  # ← 同样返回 None
if case_data is None:
    self.bridge.show_dialog.emit("读档失败", f"关联案件未找到: {case_id}")
    return  # ← 直接返回，加载失败
```

### 2.2 次要问题：case_id 可能为 "unknown"

LLM 生成的 `case_dict` 不一定包含 `case_id` 字段。`case_generator.py` 生成案件时，如果 LLM 输出的 JSON 中没有 `case_id`，则 `self.engine.case.get("case_id", "unknown")` 会得到 `"unknown"`。存入 session 的 `case_id = "unknown"` 后，后续多个案件的 session 都关联到同一个 "unknown" case_id，导致混乱。

### 2.3 次要问题：`to_dict()` 未备份案件元信息

`core/interrogation.py:151-168` 的 `to_dict()` 只序列化了引擎状态，未包含 `case_title` 和 `case_id`。如果 `cases` 表数据丢失，session 将无法恢复。

### 2.4 次要问题：存档列表读取时 N+1 查询

`_on_load_game()` 对每个 session 都调用 `db.load_case(case_id)`，如果存档很多，会逐个打开数据库连接查询，效率低。

---

## 3. 详细优化方案

### 3.1 Step 1: `load_case()` 中确保案件数据入库

**文件**: `ui/web_main_window.py:185-207`  
**修改**: 在 `load_case()` 方法中，加载到引擎后立即保存到数据库

```python
def load_case(self, case_data):
    """加载案件到引擎并更新 UI。"""
    # 确保 case_data 有 case_id
    if "case_id" not in case_data or not case_data["case_id"]:
        case_data["case_id"] = str(uuid.uuid4())

    self.engine = InterrogationEngine(case_data)

    # 确保案件数据入库
    try:
        db.save_case(case_data)
    except Exception as exc:
        logger.warning(f"案件数据入库失败（不影响游戏）: {exc}")

    state = {
        "suspects": [
            {"name": s.name, "pressure": s.pressure}
            for s in self.engine.suspects
        ],
        "evidences": case_data.get("evidences", []),
        "timeLeft": self.engine.time_left,
        "current_suspect_index": 0,
        "state": self.engine.state,
        "case_id": case_data.get("case_id", ""),
        "caseTitle": case_data.get("title", ""),
    }

    self.bridge.init_game_state.emit(state)
    self.bridge.set_input_enabled.emit(True)

    if self.engine.suspects:
        self._on_suspect_changed(0)
```

**原因**: 案件数据是存档恢复的必要前提，必须在加载时确保入库。

### 3.2 Step 2: `to_dict()` 增加案件元信息冗余备份

**文件**: `core/interrogation.py:151-168`  
**修改**: 序列化时增加 `case_title` 和 `case_id`

```python
def to_dict(self) -> dict:
    suspects_states = []
    for suspect in self.suspects:
        suspects_states.append(
            {
                "name": suspect.name,
                "pressure": suspect.pressure,
                "memory": suspect.memory,
            }
        )
    return {
        "case_id": self.case.get("case_id", ""),
        "case_title": self.case.get("title", ""),
        "suspects_states": suspects_states,
        "presented_evidence_ids": list(self.presented_evidence_ids),
        "time_left": self.time_left,
        "current_suspect_index": self.current_suspect_index,
        "state": self.state,
    }
```

**原因**: 防御性编程，即使 `cases` 表数据丢失，也能从 session 中恢复案件标题。

### 3.3 Step 3: `from_dict()` 兼容旧格式

**文件**: `core/interrogation.py:170-183`  
**修改**: 无需修改，`from_dict()` 不使用 `case_id`/`case_title`，它们仅用于展示。

### 3.4 Step 4: `_on_save_game()` 存档前确保案件数据最新

**文件**: `ui/web_main_window.py:507-525`  
**修改**: 在 `save_full_session` 前先保存案件数据

```python
def _on_save_game(self):
    if self.engine is None:
        return
    try:
        session_id = str(uuid.uuid4())
        case_id = self.engine.case.get("case_id", "unknown")
        case_title = self.engine.case.get("title", "未知案件")

        # 确保案件数据在数据库中是最新的
        db.save_case(self.engine.case)

        engine_state_dict = self.engine.to_dict()
        db.save_full_session(session_id, case_id, engine_state_dict)

        from datetime import datetime as dt
        now_str = dt.now().strftime("%Y-%m-%d %H:%M")
        self.bridge.show_dialog.emit(
            "存档成功", f"「{case_title}」已保存\n{now_str}"
        )
    except Exception as exc:
        logger.error(f"存档失败: {exc}")
        self.bridge.show_dialog.emit("存档失败", f"保存失败: {exc}")
```

### 3.5 Step 5: `_on_load_game()` 降级处理

**文件**: `ui/web_main_window.py:527-554`  
**修改**: `db.load_case()` 返回 None 时，从 session 列表中提取降级标题

```python
def _on_load_game(self):
    try:
        sessions = db.list_sessions()
        formatted_sessions = []
        for s in sessions:
            case_id = s.get("case_id", "")
            case_data = db.load_case(case_id)
            if case_data:
                case_title = case_data.get("title", "未知案件")
            else:
                # 降级：尝试从 session 的 engine_state 中提取 case_title
                result = db.load_full_session(s["session_id"])
                if result:
                    _, engine_state = result
                    case_title = engine_state.get("case_title", "未知案件")
                else:
                    case_title = "未知案件"

            saved_at = s.get("saved_at", "")
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(saved_at)
                date_str = parsed.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date_str = saved_at

            formatted_sessions.append({
                "session_id": s["session_id"],
                "name": f"{case_title} - {date_str}",
                "date": date_str,
                "summary": "",
            })
        self.bridge.show_save_list.emit(formatted_sessions)
    except Exception as exc:
        logger.error(f"获取存档列表失败: {exc}")
        self.bridge.show_dialog.emit("读档失败", f"无法读取存档列表: {exc}")
```

### 3.6 Step 6: `_on_save_selected()` 降级处理

**文件**: `ui/web_main_window.py:556-603`  
**修改**: `db.load_case()` 返回 None 时，尝试从 engine_state 恢复

```python
def _on_save_selected(self, session_id):
    try:
        result = db.load_full_session(session_id)
        if result is None:
            self.bridge.show_dialog.emit("读档失败", "存档数据不存在")
            return

        case_id, engine_state_dict = result
        case_data = db.load_case(case_id)

        if case_data is None:
            # 降级：尝试从 engine_state_dict 中恢复案件信息
            # 注意：to_dict() 不存储完整 case_data，只能提示用户
            case_title = engine_state_dict.get("case_title", "未知案件")
            self.bridge.show_dialog.emit(
                "读档警告",
                f"关联案件「{case_title}」的数据缺失，无法完整恢复。\n"
                f"案件ID: {case_id}"
            )
            return

        # ... 后续正常流程不变
```

---

## 4. 验收测试

**测试文件**: `tests/test_fix_save_load.py`

### 4.1 单元测试

```python
# 测试1: load_case 后案件数据入库
def test_load_case_saves_to_db(tmp_path):
    case_data = {"case_id": "test-001", "title": "测试案件", "suspects": [...], ...}
    init_db(str(tmp_path / "test.db"))
    load_case(case_data)  # 应自动 save_case
    loaded = db.load_case("test-001")
    assert loaded is not None
    assert loaded["title"] == "测试案件"

# 测试2: to_dict 包含 case_id 和 case_title
def test_to_dict_includes_case_metadata():
    engine = InterrogationEngine(mock_case_data)
    state = engine.to_dict()
    assert "case_id" in state
    assert "case_title" in state

# 测试3: case_id 为空时自动生成
def test_load_case_generates_case_id():
    case_data = {"title": "无ID案件", "suspects": [...]}
    # case_id 不存在
    load_case(case_data)
    assert "case_id" in case_data
    assert case_data["case_id"] != "unknown"

# 测试4: 存档后读档列表显示正确标题
def test_save_and_load_session_title(tmp_path):
    # 存档
    save_full_session("sess-1", "case-1", engine_state)
    # 读档列表
    sessions = list_sessions()
    # case_title 应正确显示，不是 "未知案件"
    assert sessions[0]["name"] 不包含 "未知案件"
```

### 4.2 集成测试（标记 `@pytest.mark.slow`）

```python
# 测试5: 完整存档-读档流程
def test_full_save_load_cycle(tmp_path):
    # 1. 生成/加载案件
    # 2. 进行一些审讯操作
    # 3. 存档
    # 4. 读档
    # 5. 验证引擎状态完全恢复
```

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web_main_window.py` | 修改 | `load_case()` 增加自动 save_case；`_on_save_game()` 增加 save_case；`_on_load_game()` 降级处理；`_on_save_selected()` 降级处理 |
| `core/interrogation.py` | 修改 | `to_dict()` 增加 `case_id`/`case_title` 字段 |
| `tests/test_fix_save_load.py` | 新增 | 验收测试用例 |
