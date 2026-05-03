# BUG-5: 嫌疑人崩溃后流程错误 + AI 复盘打分 — 优化方案（修订版 v2.0）

> 优先级: **P0** (游戏核心流程断裂)  
> 影响范围: 前端 JS + 后端 Python  
> 可并行: 是（与 BUG-2, BUG-4 无冲突）  
> 负责 Agent: Agent-C  
> 评审状态: **需修改后通过**

---

## 修订说明

| 修订项 | 原方案 | 修订后 | 原因 |
|--------|--------|--------|------|
| 信号设计 | `disable_all_actions` / `enable_all_actions` 两个信号 | `set_game_interactive(bool)` 单一信号 | 与 `set_input_enabled(bool)` 模式一致，避免不对称 |
| `load_case()` | 缺少操作启用逻辑 | 增加 `set_game_interactive.emit(True)` | 修复 `_restart()` 后操作无法恢复的 P0 问题 |
| 复盘加载 | 使用 `show_dialog` | 使用 `show_loading` | 避免用户关闭 dialog 后 Worker 仍在运行 |
| `_return_to_menu()` | 只禁用操作 | 禁用操作 + 重置嫌疑人面板 | 确保 UI 状态一致 |

---

## 1. 问题描述

嫌疑人崩溃（泄露秘密/认罪）后：
1. 时间已停止，但界面仍可审讯其他人、可输入、可出示证据
2. 嫌疑人不再回复，用户无法继续操作也无法结束游戏
3. 缺少游戏结束后的 AI 复盘和打分功能

## 2. 根因分析

### 2.1 BUG A：`_on_worker_finished()` 覆盖了结局时的输入禁用

**文件**: `ui/web_main_window.py:271-276`

```python
def _on_worker_finished(self, events):
    self.update_ui_from_engine(events)
    # ↑ update_ui_from_engine 处理 state_change 事件时，
    #   调用 _handle_ending() → set_input_enabled.emit(False)
    self.bridge.set_input_enabled.emit(True)  # ← 覆盖了上面的 False！
    self.bridge.show_typing_indicator.emit(False)
```

### 2.2 BUG B：结局处理只禁用了输入框，未禁用其他交互元素

**文件**: `ui/web_main_window.py:346-359`

```python
def _handle_ending(self, state_event):
    self._countdown_timer.stop()
    self.bridge.set_input_enabled.emit(False)  # ← 只禁用了聊天输入框+发送按钮
    # 未禁用：嫌疑人下拉框、施压按钮、共情按钮、证据卡片
```

### 2.3 BUG C：缺少复盘打分功能

当前结局对话框只有「重新开始」和「返回主菜单」两个选项，没有对审讯过程的总结评价。

---

## 3. 详细优化方案（修订版）

### 3.1 Step 1: 修复 `_on_worker_finished()` 的输入启用逻辑

**文件**: `ui/web_main_window.py:271-276`

**修改后**：
```python
def _on_worker_finished(self, events):
    self.update_ui_from_engine(events)
    # 修订：只有在引擎仍处于可交互状态时才启用输入
    if self.engine and self.engine.state not in ("breakdown", "verdict"):
        self.bridge.set_game_interactive.emit(True)
    self.bridge.show_typing_indicator.emit(False)
    self._current_worker = None
```

### 3.2 Step 2: 新增统一的游戏交互控制信号

**文件**: `ui/web_bridge.py`  
**新增信号**：

```python
# 替代原方案的 disable_all_actions / enable_all_actions
set_game_interactive = Signal(bool)  # 控制所有游戏操作
```

**文件**: `ui/web/js/bridge.js` — `_setupSignalListeners()` 中新增：

```javascript
this.pythonBridge.set_game_interactive.connect((enabled) => {
    this._trigger('gameInteractive', { enabled });
});
```

**文件**: `ui/web/js/app.js` — `bindBridgeEvents()` 中新增：

```javascript
bridge.on('gameInteractive', (data) => {
    const enabled = data.enabled;
    
    // 聊天输入框
    chatManager.setInputEnabled(enabled);
    
    // 嫌疑人下拉框
    const selector = document.getElementById('suspect-selector');
    if (selector) selector.disabled = !enabled;
    
    // 施压/共情按钮
    const btnPressure = document.getElementById('btn-pressure');
    const btnEmpathy = document.getElementById('btn-empathy');
    if (btnPressure) btnPressure.disabled = !enabled;
    if (btnEmpathy) btnEmpathy.disabled = !enabled;
    
    // 证据卡片
    document.querySelectorAll('.evidence-card').forEach(card => {
        card.style.pointerEvents = enabled ? '' : 'none';
        card.style.opacity = enabled ? '' : '0.5';
    });
});
```

### 3.3 Step 3: 修改 `_handle_ending()` 全面禁用操作

**文件**: `ui/web_main_window.py:346-359`

**修改后**：
```python
def _handle_ending(self, state_event):
    self._countdown_timer.stop()
    self.bridge.set_game_interactive.emit(False)  # 修订：禁用所有操作

    new_state = state_event["new_state"]
    if new_state == "breakdown":
        message = "破案成功！真凶已经崩溃认罪。"
    elif new_state == "verdict":
        message = "时间耗尽！律师介入，案件被迫终止。"
    else:
        message = f"游戏结束: {new_state}"

    self.bridge.show_ending_dialog.emit("审讯结束", message)
```

### 3.4 Step 4: 修改结局对话框，增加「复盘审讯」按钮

**文件**: `ui/web/js/modal.js:107-124` — `showEndingDialog()`

**修改后**：
```javascript
showEndingDialog(title, message) {
    this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
        {
            text: '复盘审讯',
            class: 'modal-btn-primary',
            callback: () => {
                if (window.bridge) window.bridge.requestReview();
            },
        },
        {
            text: '重新开始',
            class: 'modal-btn-secondary',
            callback: () => {
                if (window.bridge) window.bridge.requestRestart();
            },
        },
        {
            text: '返回主菜单',
            class: 'modal-btn-secondary',
            callback: () => {
                if (window.bridge) window.bridge.requestReturnToMenu();
            },
        },
    ]);
}
```

### 3.5 Step 5: 新增复盘生成器

**新文件**: `core/review_generator.py`

```python
"""审讯复盘报告生成器。"""

import json
import logging
import re
from typing import Dict, List, Optional

from core.llm_client import llm_client

logger = logging.getLogger("thebox")


def generate_review(engine_state: dict, case_data: dict) -> Optional[dict]:
    """调用 LLM 生成审讯复盘报告。

    Args:
        engine_state: InterrogationEngine.to_dict() 的输出
        case_data: 案件完整数据

    Returns:
        复盘报告字典，包含 score, strategy_analysis, key_moments, suggestions
        如果 LLM 调用失败返回 None
    """
    if not llm_client._initialized:  # 修订：使用正确的属性名
        logger.warning("LLMClient 未初始化，无法生成复盘报告")
        return _fallback_review(engine_state, case_data)

    case_title = case_data.get("title", "未知案件")
    state = engine_state.get("state", "")
    time_left = engine_state.get("time_left", 0)
    time_total = case_data.get("interrogation_time_limit_sec", 600)
    time_used = time_total - time_left
    evidence_presented = engine_state.get("presented_evidence_ids", [])

    # 修订：只传递摘要信息，不传递完整对话历史
    suspects_summary = []
    for s in engine_state.get("suspects_states", []):
        name = s.get("name", "未知")
        pressure = s.get("pressure", 0)
        memory_count = len(s.get("memory", []))
        suspects_summary.append(
            f"- {name}: 压力值 {pressure}/100, 对话轮数 {memory_count // 2}"
        )

    prompt = f"""你是一名审讯专家，请对以下审讯过程进行复盘和打分。

## 案件信息
案件名称: {case_title}
案件结果: {"破案成功（嫌疑人认罪）" if state == "breakdown" else "审讯失败（时间耗尽）"}

## 审讯统计
- 总审讯时间: {time_total}秒
- 已使用时间: {time_used}秒
- 剩余时间: {time_left}秒
- 出示证据数: {len(evidence_presented)}件

## 嫌疑人情况
{chr(10).join(suspects_summary)}

## 评价要求
请从以下维度评价审讯策略，并以 JSON 格式输出:
1. "score": 综合评分 (0-100)
2. "strategy_analysis": 审讯策略分析（2-3句话）
3. "key_moments": 关键转折点列表（数组，每项1句话）
4. "suggestions": 改进建议列表（数组，每项1句话）
5. "verdict": 一句话总结"""

    messages = [
        {"role": "system", "content": "你是一名资深审讯专家和培训教官，擅长分析审讯策略并给出专业评价。请以JSON格式输出评价结果。"},
        {"role": "user", "content": prompt},
    ]

    try:
        raw = llm_client.chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        text = raw.strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        result["score"] = int(result.get("score", 50))
        result.setdefault("strategy_analysis", "")
        result.setdefault("key_moments", [])
        result.setdefault("suggestions", [])
        result.setdefault("verdict", "")
        logger.info(f"复盘报告生成成功，评分: {result['score']}")
        return result
    except Exception as exc:
        logger.warning(f"复盘报告生成失败: {exc}")
        return _fallback_review(engine_state, case_data)


def _fallback_review(engine_state: dict, case_data: dict) -> dict:
    """当 LLM 不可用时的降级复盘。"""
    state = engine_state.get("state", "")
    score = 80 if state == "breakdown" else 30
    return {
        "score": score,
        "strategy_analysis": "（自动评价）" + ("成功突破嫌疑人心理防线。" if state == "breakdown" else "未能突破嫌疑人心理防线。"),
        "key_moments": ["审讯结束"],
        "suggestions": ["（需要 LLM 生成详细建议）"],
        "verdict": "破案成功" if state == "breakdown" else "审讯失败",
    }
```

### 3.6 Step 6: 新增 ReviewWorker 和信号处理

**文件**: `ui/web_main_window.py` — 新增 Worker 类

```python
class ReviewWorker(QThread):
    """后台线程 Worker，生成审讯复盘报告。"""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, engine):
        super().__init__()
        # 修订：保存引擎状态快照，避免线程安全问题
        self._engine_state = engine.to_dict()
        self._case_data = engine.case

    def run(self):
        try:
            from core.review_generator import generate_review
            result = generate_review(self._engine_state, self._case_data)
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("复盘报告生成失败")
        except Exception as exc:
            logger.error(f"复盘生成失败: {exc}")
            self.error.emit(str(exc))
```

**文件**: `ui/web_bridge.py` — 新增信号和 Slot

```python
# 复盘相关
review_requested = Signal()
show_review = Signal(dict)  # review_data

@Slot()
def requestReview(self):
    """请求复盘报告。"""
    self.review_requested.emit()
```

**文件**: `ui/web/js/bridge.js` — 新增信号监听和 JS→Python 方法

```javascript
// _setupSignalListeners() 中新增
this.pythonBridge.show_review.connect((data) => {
    this._trigger('showReview', { data });
});

// 新增 JS → Python 方法
requestReview() {
    if (this.pythonBridge) {
        this.pythonBridge.requestReview();
    }
}
```

**文件**: `ui/web_main_window.py` — 新增处理方法

```python
def _connect_bridge_signals(self):
    # ... 现有连接 ...
    self.bridge.review_requested.connect(self._on_review_requested)

def _on_review_requested(self):
    """生成审讯复盘报告。"""
    if self.engine is None:
        return
    if self._review_worker and self._review_worker.isRunning():
        return

    self._review_worker = ReviewWorker(self.engine)
    self._review_worker.finished.connect(self._on_review_ready)
    self._review_worker.error.connect(self._on_review_error)
    self._review_worker.start()

    # 修订：使用 show_loading 替代 show_dialog
    self.bridge.show_loading.emit("正在生成审讯复盘报告...", False)

def _on_review_ready(self, review_data):
    """复盘报告生成成功。"""
    self._review_worker = None
    self.bridge.hide_loading.emit()  # 修订：隐藏加载提示
    self.bridge.show_review.emit(review_data)

def _on_review_error(self, error_msg):
    """复盘报告生成失败。"""
    self._review_worker = None
    self.bridge.hide_loading.emit()  # 修订：隐藏加载提示
    self.bridge.show_dialog.emit("复盘失败", f"生成复盘报告失败: {error_msg}")
```

`__init__` 中需初始化 `self._review_worker: Optional[ReviewWorker] = None`

### 3.7 Step 7: 前端复盘报告展示

**文件**: `ui/web/js/app.js` — `bindBridgeEvents()` 中新增

```javascript
bridge.on('showReview', (data) => {
    if (!data || !data.data) return;
    modalManager.showReviewReport(data.data);
});
```

**文件**: `ui/web/js/modal.js` — 新增方法

```javascript
showReviewReport(reviewData) {
    const score = reviewData.score || 0;
    const scoreClass = score >= 70 ? 'success' : score >= 40 ? 'warning' : 'failure';
    const scoreIcon = score >= 70 ? '✓' : score >= 40 ? '!' : '✗';

    let momentsHtml = '';
    (reviewData.key_moments || []).forEach((m) => {
        momentsHtml += `<li>${this._escapeHtml(m)}</li>`;
    });

    let suggestionsHtml = '';
    (reviewData.suggestions || []).forEach((s) => {
        suggestionsHtml += `<li>${this._escapeHtml(s)}</li>`;
    });

    const bodyHtml = `
        <div class="result-modal">
            <div class="result-icon ${scoreClass}">${scoreIcon}</div>
            <div class="result-title ${scoreClass}">综合评分: ${score}/100</div>
            <div class="result-description">${this._escapeHtml(reviewData.verdict || '')}</div>
            <div style="text-align:left; margin: var(--space-4) 0;">
                <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">策略分析</h4>
                <p>${this._escapeHtml(reviewData.strategy_analysis || '')}</p>
            </div>
            <div style="text-align:left; margin: var(--space-4) 0;">
                <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">关键转折</h4>
                <ul style="padding-left: var(--space-6);">${momentsHtml || '<li>无</li>'}</ul>
            </div>
            <div style="text-align:left; margin: var(--space-4) 0;">
                <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">改进建议</h4>
                <ul style="padding-left: var(--space-6);">${suggestionsHtml || '<li>无</li>'}</ul>
            </div>
        </div>
    `;

    this._show('审讯复盘', bodyHtml, [
        {
            text: '重新开始',
            class: 'modal-btn-primary',
            callback: () => {
                if (window.bridge) window.bridge.requestRestart();
            },
        },
        {
            text: '返回主菜单',
            class: 'modal-btn-secondary',
            callback: () => {
                if (window.bridge) window.bridge.requestReturnToMenu();
            },
        },
    ]);
}
```

### 3.8 Step 8: `_restart()` 和 `_return_to_menu()` 恢复操作状态

**文件**: `ui/web_main_window.py`

```python
def _restart(self):
    if self.engine is None:
        return
    case_data = self.engine.case
    self.load_case(case_data)  # load_case 中会 emit set_game_interactive(True)

def _return_to_menu(self):
    self.engine = None
    self.bridge.clear_chat.emit()
    self.bridge.set_game_interactive.emit(False)  # 修订：禁用所有操作
    self._countdown_timer.stop()
    
    # 修订：重置嫌疑人面板
    self.bridge.init_game_state.emit({
        "suspects": [],
        "evidences": [],
        "timeLeft": 0,
        "current_suspect_index": 0,
        "state": "selecting",
        "case_id": "",
        "caseTitle": "",
    })
```

**`load_case()` 修订**（与 Agent-A 协调）：

```python
def load_case(self, case_data):
    """加载案件到引擎并更新 UI。"""
    # ... 现有逻辑 ...
    self.bridge.init_game_state.emit(state)
    self.bridge.set_game_interactive.emit(True)  # 修订：启用所有操作
    # ... 后续不变 ...
```

---

## 4. 验收测试

### 4.1 手动验收清单

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 崩溃后输入禁用 | 审讯到 breakdown | 输入框、下拉框、施压/共情、证据全部禁用 |
| 崩溃后复盘 | 点击"复盘审讯" | 显示加载提示，完成后显示复盘报告 |
| 崩溃后重新开始 | 点击"重新开始" | 所有操作恢复，可正常审讯 |
| 崩溃后返回菜单 | 点击"返回主菜单" | 所有操作禁用，嫌疑人面板重置 |
| 时间耗尽 | 等待时间耗尽 | 同崩溃后的行为 |
| 复盘失败 | LLM 不可用时点击复盘 | 显示降级复盘报告 |

### 4.2 自动化测试

```python
def test_worker_finished_does_not_enable_input_on_breakdown(qtbot):
    """验证 _on_worker_finished 不覆盖结局时的输入禁用"""
    ...

def test_fallback_review_without_llm():
    """验证 LLM 不可用时返回降级报告"""
    from core.review_generator import _fallback_review
    result = _fallback_review({"state": "breakdown"}, {"title": "测试"})
    assert result["score"] == 80
    assert "verdict" in result

def test_restart_restores_interactive(qtbot):
    """验证重新开始后操作恢复"""
    ...
```

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web_main_window.py` | 修改 | `_on_worker_finished()` 条件启用输入；`_handle_ending()` 禁用所有操作；新增 ReviewWorker + 信号处理；`_return_to_menu()` 禁用操作+重置UI；`load_case()` 增加 `set_game_interactive(True)` |
| `ui/web_bridge.py` | 修改 | 新增 `set_game_interactive(bool)`/`review_requested`/`show_review` 信号；新增 `requestReview()` Slot |
| `ui/web/js/bridge.js` | 修改 | 新增信号监听和 `requestReview()` 方法 |
| `ui/web/js/app.js` | 修改 | 新增 `gameInteractive`/`showReview` 事件处理 |
| `ui/web/js/modal.js` | 修改 | `showEndingDialog()` 增加复盘按钮；新增 `showReviewReport()` 方法 |
| `core/review_generator.py` | **新增** | 复盘报告生成器 |
| `core/interrogation.py` | 修改 | `to_dict()` 增加 case_id/case_title（与 BUG-4 共同修改） |
| `tests/test_fix_breakdown_flow.py` | **新增** | 验收测试 |

---

## 6. 分步实施顺序

1. **Step 1-3**: 修复崩溃后流程 BUG（P0，约 30min）
2. **Step 4-7**: 新增复盘打分功能（约 60min）
3. **Step 8**: 确保 restart/menu 状态恢复（约 15min）
4. 验收测试（约 30min）

建议先完成 Step 1-3 提交，再做 Step 4-8。
