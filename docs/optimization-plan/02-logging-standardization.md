# BUG-2: 系统日志规范化 — 优化方案

> 优先级: **P1** (运维/调试能力缺失)  
> 影响范围: 后端 Python 全局  
> 可并行: 是（与 BUG-4, BUG-5, BUG-6 无冲突；仅与 BUG-3 有依赖）  
> 负责 Agent: Agent-B

---

## 1. 问题描述

1. Console handler 日志格式缺少时间戳和日志级别标识
2. 用户点击操作（施压/共情/切换嫌疑人/出示证据等）无日志记录
3. 模型生成的内容（嫌疑人回复）无日志记录
4. 模型 API 请求/响应无 DEBUG 级别日志
5. 存档/读档等关键操作日志不完整

## 2. 根因分析

### 2.1 Console handler 格式缺失

**文件**: `core/logger.py:25-27`

```python
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
```

缺少 `%(asctime)s` 时间戳，导致控制台日志无法定位事件发生时间。

### 2.2 关键操作无日志

`web_main_window.py` 中的信号处理方法（`_on_chat_message_sent`, `_on_pressure`, `_on_empathy`, `_on_evidence_selected`, `_on_suspect_changed`）**没有添加任何 `logger.debug()` 或 `logger.info()` 调用**。

### 2.3 LLM 请求/响应无日志

`core/llm_client.py:chat_completion()` 中：
- 请求前无 DEBUG 日志（记录模型名称、消息数量）
- 响应后无 DEBUG 日志（记录耗时、token 使用量）
- 异常日志使用 `logger.warning`/`logger.error`，但没有结构化的请求/响应日志

### 2.4 嫌疑人回复无日志

`core/suspect_agent.py:respond()` 返回后没有记录回复内容，仅在 `_postprocess()` 中记录了禁止内容触发。

---

## 3. 详细优化方案

### 3.1 Step 1: 统一 Console Handler 格式

**文件**: `core/logger.py:25-27`

**修改前**：
```python
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
```

**修改后**：
```python
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
)
```

**输出效果**：
```
14:30:25 [INFO] 案件已保存: case-001
14:30:26 [DEBUG] 用户发送消息: 你昨天去了哪里？
14:30:28 [DEBUG] API响应: model=minimax/text-01, latency=1823ms
```

### 3.2 Step 2: 增加用户操作日志

**文件**: `ui/web_main_window.py`

在以下方法入口处增加 `logger.debug()` 调用：

| 方法 | 新增日志 | 级别 |
|------|---------|------|
| `_on_chat_message_sent(text)` | `logger.debug(f"用户发送消息: {text[:50]}")` | DEBUG |
| `_on_suspect_changed(index)` | `logger.debug(f"切换嫌疑人: index={index}")` | DEBUG |
| `_on_pressure()` | `logger.debug(f"用户施压，当前嫌疑人: {self.engine.suspects[self.engine.current_suspect_index].name if self.engine else 'N/A'}")` | DEBUG |
| `_on_empathy()` | `logger.debug(f"用户共情，当前嫌疑人: {self.engine.suspects[self.engine.current_suspect_index].name if self.engine else 'N/A'}")` | DEBUG |
| `_on_evidence_selected(evidence_id)` | `logger.debug(f"用户出示证据: {evidence_id}")` | DEBUG |
| `_on_save_game()` (成功) | `logger.info(f"存档成功: session_id={session_id}, case={case_title}")` | INFO |
| `_on_load_game()` | `logger.info("请求读档列表")` | INFO |
| `_on_save_selected(session_id)` | `logger.info(f"加载存档: session_id={session_id}")` | INFO |
| `_on_generate_case()` | `logger.info("请求生成新案件")` | INFO |
| `_on_case_generated(case_dict)` | `logger.info(f"案件生成成功: {case_dict.get('title', '未知')}")` | INFO |

### 3.3 Step 3: 增加 LLM API 日志

**文件**: `core/llm_client.py:chat_completion()`

在方法中增加请求/响应日志：

```python
def chat_completion(self, messages, temperature=0.7, max_tokens=500, response_format=None):
    if not self._initialized:
        raise ConfigError("LLMClient 未初始化")

    logger.debug(f"API请求: model={self.model}, messages_count={len(messages)}")

    start_time = time.time()
    for attempt in range(self.max_retries + 1):
        try:
            kwargs = { ... }
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content

            elapsed_ms = int((time.time() - start_time) * 1000)
            usage = response.usage
            tokens_info = f"prompt={usage.prompt_tokens}, completion={usage.completion_tokens}" if usage else "N/A"
            logger.debug(f"API响应: model={self.model}, latency={elapsed_ms}ms, tokens={tokens_info}")

            if not content:
                raise LLMResponseError("LLM 返回 content 为 None")
            return content
        except ...:
            ...
```

### 3.4 Step 4: 增加嫌疑人回复日志

**文件**: `core/suspect_agent.py:respond()`

在方法返回前增加日志：

```python
def respond(self, player_input, context=None):
    # ... 现有逻辑 ...

    self._postprocess(result)
    self.pressure = max(0, min(100, self.pressure + result["pressure_change"]))
    self._append_memory(player_input, result["reply"])
    self.truncate_memory()

    # 新增：记录回复
    logger.debug(f"嫌疑人[{self.name}]回复: {result['reply'][:100]}, pressure_change={result['pressure_change']}")

    return result
```

### 3.5 Step 5: 增加引擎状态变更日志

**文件**: `core/interrogation.py`

在 `submit_action()` 中状态变更时增加 INFO 日志：

```python
if result.get("secret_triggered"):
    self.state = "breakdown"
    logger.info(f"状态变更: interrogating → breakdown, 原因: {suspect.name} 泄露秘密: {result['secret_triggered']}")
    ...
```

在 `tick()` 中状态变更时：

```python
if self.time_left <= 0 and self.state not in ("verdict", "breakdown"):
    self.state = "verdict"
    logger.info("状态变更: interrogating → verdict, 原因: 审讯时间耗尽")
    ...
```

---

## 4. 验收测试

**测试文件**: `tests/test_fix_logging.py`

### 4.1 单元测试

```python
import logging
from io import StringIO

# 测试1: Console handler 格式包含时间戳
def test_console_handler_format():
    logger = logging.getLogger("thebox")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.info("测试消息")
    output = stream.getvalue()
    assert "[" in output  # 包含 [INFO]
    assert "测试消息" in output

# 测试2: 用户操作产生 DEBUG 日志
def test_user_actions_logged(caplog):
    with caplog.at_level(logging.DEBUG, logger="thebox"):
        # 模拟用户发送消息
        window._on_chat_message_sent("你在哪里？")
        assert any("用户发送消息" in r.message for r in caplog.records)

# 测试3: LLM API 请求/响应产生 DEBUG 日志
def test_llm_api_logged(caplog, mock_llm):
    with caplog.at_level(logging.DEBUG, logger="thebox"):
        llm_client.chat_completion(messages=[...])
        assert any("API请求" in r.message for r in caplog.records)
        assert any("API响应" in r.message for r in caplog.records)

# 测试4: 嫌疑人回复产生 DEBUG 日志
def test_suspect_reply_logged(caplog, mock_llm):
    with caplog.at_level(logging.DEBUG, logger="thebox"):
        agent = SuspectAgent(mock_suspect_data, "测试案件")
        agent.respond("你在哪里？")
        assert any("嫌疑人[" in r.message for r in caplog.records)

# 测试5: 引擎状态变更产生 INFO 日志
def test_state_change_logged(caplog):
    with caplog.at_level(logging.INFO, logger="thebox"):
        engine.state = "breakdown"
        # ... 触发状态变更
        assert any("状态变更" in r.message for r in caplog.records)
```

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `core/logger.py` | 修改 | Console handler 增加时间戳格式 |
| `ui/web_main_window.py` | 修改 | 各信号处理方法增加 `logger.debug/info` 调用 |
| `core/llm_client.py` | 修改 | `chat_completion()` 增加请求/响应 DEBUG 日志 |
| `core/suspect_agent.py` | 修改 | `respond()` 增加回复 DEBUG 日志 |
| `core/interrogation.py` | 修改 | 状态变更增加 INFO 日志 |
| `tests/test_fix_logging.py` | **新增** | 验收测试 |

---

## 6. 日志级别规范汇总

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| **DEBUG** | 用户操作、API请求/响应、嫌疑人回复 | `用户发送消息: 你在哪里？` |
| **INFO** | 关键业务事件（存档/读档/生成/状态变更） | `存档成功: session_id=xxx, case=测试案件` |
| **WARNING** | 可恢复的异常、降级处理 | `LLMClient 未初始化，返回默认回复` |
| **ERROR** | 操作失败、不可恢复异常 | `存档失败: database is locked` |
