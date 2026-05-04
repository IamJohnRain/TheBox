# UI Modal & Evidence 修复方案

> 优先级: **P0** (用户体验严重受损)
> 影响范围: 前端 JS + CSS
> 可并行: **是** — CSS 修复与 JS 修复可独立进行
> 负责 Agent: UI Agent (前端)

---

## 1. 问题总览

| # | 问题描述 | 根因 | 影响文件 |
|---|---------|------|---------|
| Fix-A | 生成案件后的案件介绍弹窗，上下滑动时频闪 | Modal/Backdrop CSS 过度使用 GPU 合成层属性（`will-change`、`contain`、`backface-visibility`），在 Qt WebEngine 滚动时触发反复重绘 | `components.css` |
| Fix-B | 游戏超时后进入复盘，复盘等待界面频闪 | Loading Overlay 与 Modal Backdrop 共用 `z-index: 300`，且 transition 叠加时合成层竞争 | `components.css` |
| Fix-C | 审讯复盘子界面加载后出现透明蒙版，所有按钮无法点击 | `opacity: 0 + visibility: hidden` 隐藏的元素在 transition 被打断时仍接收 pointer 事件；Qt WebEngine 对 `visibility` 的事件屏蔽不可靠 | `components.css`, `modal.js` |
| Fix-D | 证据描述展示不全，且没有展开按钮 | 使用固定字符阈值 `DESC_COLLAPSE_THRESHOLD = 60` 判断，未考虑实际渲染行高；多行文本可能因换行被截断但无按钮 | `evidence.js` |

---

## 2. 根因分析

### 2.1 根因 A（频闪）：GPU 合成层属性过多

**文件**: `ui/web/css/components.css:599-648`

```css
.modal-backdrop {
    ...
    contain: strict;           /* ← 强制创建独立合成层 */
}

.modal-wrapper {
    ...
    will-change: opacity, transform;  /* ← 强制提升为合成层 */
    contain: layout style;            /* ← 同上 */
}

.modal {
    ...
    backface-visibility: hidden;  /* ← 触发合成层 */
    contain: paint;               /* ← 同上 */
}
```

当 Modal 内容触发 `overflow-y: auto` 滚动，或 Loading Overlay 的 spinner 动画运行时，多个合成层在 Qt WebEngine（Chromium 内核）中竞争 GPU 资源，导致滚动时画面反复重合成，表现为频闪。

### 2.2 根因 B（频闪）：Loading Overlay 与 Modal Backdrop 层级竞争

**文件**: `ui/web/css/components.css:518-616`

```css
.loading-overlay {
    z-index: var(--z-modal-backdrop);  /* ← 300，与 backdrop 相同 */
}
.modal-backdrop {
    z-index: var(--z-modal-backdrop);  /* ← 300 */
}
```

复盘流程：`showEndingDialog` (Modal) → 用户点击"复盘审讯" → `requestReview()` → `_on_review_requested()` emit `show_loading` → `hide_loading` → `show_review` (新 Modal)。

在此过程中，如果 `hide_loading` 和 `show_review` 调用间隔极短，两个 `z-index: 300` 的元素 transition 重叠，合成层切换导致闪烁。

### 2.3 根因 C（透明蒙版）：Transition 中断后事件未正确屏蔽

**文件**: `ui/web/css/components.css:518-616`, `ui/web/js/modal.js:863-870`

```css
.loading-overlay {
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
    /* 缺少 pointer-events: none，隐藏后仍可接收点击 */
}

.modal-backdrop {
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
    /* 同上 */
}
```

当快速切换（如 `hideLoading` 后立即 `showReview`），CSS transition 可能被 JS 的 class 切换打断。此时元素可能卡在 `opacity: 0` 但 `visibility` 尚未生效的中间态。在 Qt WebEngine 中，`visibility: hidden` 有时不能立即禁用鼠标事件，导致一个完全透明但覆盖全屏的元素拦截所有点击。

### 2.4 根因 D（证据展开）：基于字符数而非实际渲染高度

**文件**: `ui/web/js/evidence.js:100-117`

```javascript
const DESC_COLLAPSE_THRESHOLD = 60;
// ...
${desc.length > DESC_COLLAPSE_THRESHOLD ? '<button class="evidence-expand-btn">展开</button>' : ''}
```

问题：
1. 证据面板宽度固定 `300px`，同样的 60 个字符在中文（窄字符）和英文长单词下的实际占用行数差异极大。
2. CSS 中 `.evidence-description` 的 `max-height: 4.5em` 约等于 3 行（`line-height: 1.5`），但一个 50 字符的英文 URL 可能只占 1 行，而一个 30 字符的中文描述配标点可能占 3 行。
3. 当 `desc.length <= 60` 但实际渲染高度超过 `4.5em` 时，描述被 CSS 截断，但由于阈值判断不通过，**不渲染展开按钮**，用户无法查看完整内容。

---

## 3. 详细修复方案

### 3.1 Fix-A & Fix-B：移除过度合成层属性

**文件**: `ui/web/css/components.css`

#### 3.1.1 修改 `.modal-backdrop`

```diff
 .modal-backdrop {
     position: fixed;
     top: 0;
     left: 0;
     right: 0;
     bottom: 0;
     background: rgba(10, 14, 23, 0.92);
     z-index: var(--z-modal-backdrop);
     opacity: 0;
     visibility: hidden;
     transition: opacity 0.3s, visibility 0.3s;
-    contain: strict;
+    pointer-events: none;  /* Fix-C 同步修复 */
 }
```

#### 3.1.2 修改 `.modal-wrapper`

```diff
 .modal-wrapper {
     position: fixed;
     top: 50%;
     left: 50%;
     transform: translate(-50%, -50%) scale(0.9);
     z-index: var(--z-modal);
     opacity: 0;
     visibility: hidden;
     transition: opacity 0.3s ease, visibility 0.3s ease, transform 0.3s ease;
-    will-change: opacity, transform;
-    contain: layout style;
 }
```

#### 3.1.3 修改 `.modal`

```diff
 .modal {
     background: var(--color-bg-secondary);
     border: 1px solid rgba(0, 245, 255, 0.2);
     border-radius: var(--layout-border-radius-xl);
     padding: var(--space-8);
     min-width: 400px;
     max-width: 90vw;
     max-height: 90vh;
     overflow-y: auto;
-    backface-visibility: hidden;
-    contain: paint;
 }
```

#### 3.1.4 修改 `.loading-overlay`

```diff
 .loading-overlay {
     position: fixed;
     top: 0;
     left: 0;
     right: 0;
     bottom: 0;
     background: rgba(10, 14, 23, 0.94);
     display: flex;
     flex-direction: column;
     align-items: center;
     justify-content: center;
     gap: var(--space-6);
     z-index: var(--z-modal-backdrop);
     opacity: 0;
     visibility: hidden;
     transition: opacity 0.3s, visibility 0.3s;
+    pointer-events: none;  /* Fix-C 同步修复 */
 }
```

**原理说明**：
- `will-change`、`contain`、`backface-visibility` 都是**强制创建独立 GPU 合成层**的属性。
- 在标准浏览器中，这些属性能提升动画性能；但在 Qt WebEngine 中，叠加的 `position: fixed` 元素 + 合成层 + `overflow-y: auto` 滚动会导致合成器频繁重新计算层级，表现为闪烁。
- 移除这些属性后，Modal 和 Loading 仍然正常工作（`transition: opacity/transform` 由浏览器原生支持，不需要手动提升合成层），且滚动时不再触发频闪。

### 3.2 Fix-C：增加 `pointer-events` 显式控制

**文件**: `ui/web/css/components.css`

#### 3.2.1 为 overlay/backdrop 的显隐状态增加 pointer-events

```diff
 .loading-overlay.active {
     opacity: 1;
     visibility: visible;
+    pointer-events: auto;
 }

 .modal-backdrop.active {
     opacity: 1;
     visibility: visible;
+    pointer-events: auto;
 }
```

**文件**: `ui/web/js/modal.js`

#### 3.2.2 `hide()` 方法增加防御性设置

```diff
 hide() {
-    if (this.backdrop) this.backdrop.classList.remove('active');
+    if (this.backdrop) {
+        this.backdrop.classList.remove('active');
+        this.backdrop.style.pointerEvents = 'none';  /* 防御性：确保不可点击 */
+    }
     if (this.wrapper) this.wrapper.classList.remove('active');
     if (this.modal) this.modal.classList.remove('active');
     this._confirmCallback = null;
     document.body.classList.remove('modal-open');
     if (window.timerManager) window.timerManager.flush();
 }
```

**原理说明**：
- `pointer-events: none` 是 CSS 中**最可靠**的禁用点击事件方式，比 `visibility: hidden` 更即时、不受 transition 时序影响。
- 在 `hide()` 中显式设置 `pointerEvents = 'none'` 作为防御性编程，防止 class 切换和 transition 之间的竞争条件。
- 此修复同时解决了 Loading Overlay 在隐藏后拦截点击的问题。

### 3.3 Fix-D：基于实际渲染高度的展开按钮判断

**文件**: `ui/web/js/evidence.js`

#### 3.3.1 重写 `_addEvidenceCard()` 中的展开按钮逻辑

```diff
 _addEvidenceCard(evidence) {
     if (!this.listEl) return;

     const emptyMsg = this.listEl.querySelector('.evidence-empty');
     if (emptyMsg) {
         emptyMsg.remove();
     }

     const card = document.createElement('div');
     card.className = 'evidence-card card-hoverable' + (evidence.isNew ? ' new' : '');
     card.setAttribute('role', 'listitem');
     card.setAttribute('data-evidence-id', evidence.id);
     card.setAttribute('tabindex', '0');

-    const desc = evidence.description || '';
-    const DESC_COLLAPSE_THRESHOLD = 60;

     card.innerHTML = `
         <div class="evidence-header">
             <div class="evidence-icon">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                     <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                     <polyline points="14 2 14 8 20 8"/>
                     <line x1="16" y1="13" x2="8" y2="13"/>
                     <line x1="16" y1="17" x2="8" y2="17"/>
                     <polyline points="10 9 9 9 8 9"/>
                 </svg>
             </div>
             <h4 class="evidence-title">${this._escapeHtml(evidence.name || '未知证据')}</h4>
         </div>
         <p class="evidence-description">${this._escapeHtml(evidence.description || '')}</p>
-        ${desc.length > DESC_COLLAPSE_THRESHOLD ? '<button class="evidence-expand-btn">展开</button>' : ''}
+        <button class="evidence-expand-btn" style="display:none;">展开</button>
     `;

     const descEl = card.querySelector('.evidence-description');
     const expandBtn = card.querySelector('.evidence-expand-btn');

+    // 基于实际渲染高度判断是否需要展开按钮
+    requestAnimationFrame(() => {
+        if (descEl && descEl.scrollHeight > descEl.clientHeight + 2) {
+            expandBtn.style.display = 'inline-block';
+        }
+    });

     if (expandBtn) {
         expandBtn.addEventListener('click', (e) => {
             e.stopPropagation();
-            const descEl = card.querySelector('.evidence-description');
             if (descEl.classList.contains('expanded')) {
                 descEl.classList.remove('expanded');
                 expandBtn.textContent = '展开';
             } else {
                 descEl.classList.add('expanded');
                 expandBtn.textContent = '收起';
             }
         });
     }

     // ... 后续事件绑定不变
 }
```

**原理说明**：
- `scrollHeight` 是元素的**实际内容高度**（包括被 overflow 隐藏的部分）。
- `clientHeight` 是元素的**可见高度**（受 `max-height` 限制后的高度）。
- 当 `scrollHeight > clientHeight` 时，说明内容确实被截断了，此时显示展开按钮。
- 使用 `requestAnimationFrame` 确保在 DOM 渲染完成后再检测高度，避免获取到未布局完成的高度值。
- `+ 2` 的容差值用于抵消浏览器舍入误差和 border/padding 的微小差异。

---

## 4. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web/css/components.css` | 修改 | 删除 `.modal-wrapper` 的 `will-change`/`contain`；删除 `.modal-backdrop` 的 `contain: strict`；删除 `.modal` 的 `backface-visibility`/`contain`；为 `.loading-overlay`/`.modal-backdrop` 增加 `pointer-events` 控制 |
| `ui/web/js/modal.js` | 修改 | `hide()` 方法增加 `this.backdrop.style.pointerEvents = 'none'` 防御性设置 |
| `ui/web/js/evidence.js` | 修改 | `_addEvidenceCard()` 移除固定字符阈值 `DESC_COLLAPSE_THRESHOLD`，改为基于 `scrollHeight > clientHeight` 的动态检测；统一渲染展开按钮但默认隐藏 |

---

## 5. 验收测试

### 5.1 手动验收清单

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 案件介绍弹窗滚动 | 生成案件 → 点击"开始审讯"前查看案件资料 → 上下滑动弹窗 | 滚动平滑，无频闪 |
| 复盘等待界面 | 游戏超时 → 点击"复盘审讯" → 等待复盘生成 | Loading 界面显示正常，无频闪 |
| 复盘弹窗交互 | 复盘报告生成后 → 点击"重新开始"/"返回主菜单" | 按钮可正常点击，无透明蒙版阻断 |
| 证据展开按钮 | 查看证据面板 → 检查描述较长的证据卡片 | 若描述被截断，应显示"展开"按钮；点击后完整显示并变为"收起" |
| 证据无需展开 | 查看描述很短的证据卡片 | 不应显示"展开"按钮 |
| 快速切换 Modal | 打开设置 → 关闭 → 立即打开存档 | 界面响应正常，无残留蒙版 |

### 5.2 自动化测试

**文件**: `tests/test_ui_modal_evidence.py`（新增）

```python
"""Fix-A/B/C/D: UI Modal 频闪、透明蒙版、证据展开按钮修复验证。

由于频闪和蒙版是纯前端渲染问题，主要通过静态分析验证代码修改。
"""

import pytest


class TestModalCSSNoCompositorProps:
    """验证 Modal 相关 CSS 不含有会触发过度合成层的属性。"""

    @pytest.fixture
    def components_css(self):
        with open("ui/web/css/components.css", "r", encoding="utf-8") as f:
            return f.read()

    def test_modal_backdrop_no_contain_strict(self, components_css):
        """.modal-backdrop 不应包含 contain: strict。"""
        # 找到 .modal-backdrop 的声明块
        start = components_css.index(".modal-backdrop {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "contain: strict" not in block, (
            ".modal-backdrop 不应使用 contain: strict，会导致 Qt WebEngine 频闪"
        )

    def test_modal_wrapper_no_will_change(self, components_css):
        """.modal-wrapper 不应包含 will-change。"""
        start = components_css.index(".modal-wrapper {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "will-change" not in block, (
            ".modal-wrapper 不应使用 will-change，会导致 Qt WebEngine 频闪"
        )

    def test_modal_wrapper_no_contain(self, components_css):
        """.modal-wrapper 不应包含 contain。"""
        start = components_css.index(".modal-wrapper {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "contain" not in block, (
            ".modal-wrapper 不应使用 contain，会导致 Qt WebEngine 频闪"
        )

    def test_modal_no_backface_visibility(self, components_css):
        """.modal 不应包含 backface-visibility。"""
        start = components_css.index(".modal {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "backface-visibility" not in block, (
            ".modal 不应使用 backface-visibility，会导致 Qt WebEngine 频闪"
        )

    def test_modal_no_contain_paint(self, components_css):
        """.modal 不应包含 contain: paint。"""
        start = components_css.index(".modal {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "contain: paint" not in block, (
            ".modal 不应使用 contain: paint，会导致 Qt WebEngine 频闪"
        )


class TestOverlayPointerEvents:
    """验证 Loading Overlay 和 Modal Backdrop 有正确的 pointer-events 控制。"""

    @pytest.fixture
    def components_css(self):
        with open("ui/web/css/components.css", "r", encoding="utf-8") as f:
            return f.read()

    def test_loading_overlay_has_pointer_events_none(self, components_css):
        """.loading-overlay 应包含 pointer-events: none。"""
        start = components_css.index(".loading-overlay {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "pointer-events: none" in block, (
            ".loading-overlay 应设置 pointer-events: none 防止隐藏后拦截点击"
        )

    def test_loading_overlay_active_has_pointer_events_auto(self, components_css):
        """.loading-overlay.active 应包含 pointer-events: auto。"""
        start = components_css.index(".loading-overlay.active {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "pointer-events: auto" in block, (
            ".loading-overlay.active 应设置 pointer-events: auto"
        )

    def test_modal_backdrop_has_pointer_events_none(self, components_css):
        """.modal-backdrop 应包含 pointer-events: none。"""
        start = components_css.index(".modal-backdrop {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "pointer-events: none" in block, (
            ".modal-backdrop 应设置 pointer-events: none 防止隐藏后拦截点击"
        )

    def test_modal_backdrop_active_has_pointer_events_auto(self, components_css):
        """.modal-backdrop.active 应包含 pointer-events: auto。"""
        start = components_css.index(".modal-backdrop.active {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "pointer-events: auto" in block, (
            ".modal-backdrop.active 应设置 pointer-events: auto"
        )


class TestModalHidePointerEventsDefense:
    """验证 modal.js 的 hide() 方法有防御性 pointerEvents 设置。"""

    @pytest.fixture
    def modal_js(self):
        with open("ui/web/js/modal.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_hide_sets_pointer_events_none(self, modal_js):
        """hide() 方法应设置 this.backdrop.style.pointerEvents = 'none'。"""
        assert "pointerEvents = 'none'" in modal_js or 'pointerEvents = "none"' in modal_js, (
            "modal.js hide() 应设置 backdrop.style.pointerEvents = 'none' 作为防御"
        )


class TestEvidenceExpandByRenderedHeight:
    """验证 evidence.js 使用实际渲染高度判断展开按钮。"""

    @pytest.fixture
    def evidence_js(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_no_fixed_char_threshold(self, evidence_js):
        """不应使用固定字符阈值 DESC_COLLAPSE_THRESHOLD。"""
        assert "DESC_COLLAPSE_THRESHOLD" not in evidence_js, (
            "evidence.js 不应使用 DESC_COLLAPSE_THRESHOLD，应基于实际渲染高度判断"
        )

    def test_uses_scroll_height_check(self, evidence_js):
        """应使用 scrollHeight > clientHeight 判断内容是否溢出。"""
        assert "scrollHeight" in evidence_js, (
            "evidence.js 应使用 scrollHeight 检测内容是否被截断"
        )
        assert "clientHeight" in evidence_js, (
            "evidence.js 应使用 clientHeight 检测内容是否被截断"
        )

    def test_expand_btn_initially_hidden(self, evidence_js):
        """展开按钮应默认隐藏（style=\"display:none\"）。"""
        assert 'style="display:none"' in evidence_js or "style='display:none'" in evidence_js, (
            "evidence.js 应默认隐藏展开按钮，仅在内容溢出时显示"
        )

    def test_uses_request_animation_frame(self, evidence_js):
        """应在 requestAnimationFrame 回调中检测高度。"""
        assert "requestAnimationFrame" in evidence_js, (
            "evidence.js 应使用 requestAnimationFrame 确保 DOM 布局完成后再检测高度"
        )
```

---

## 6. 分步实施顺序

1. **Step 1**: 修改 `components.css`（Fix-A/B/C 的 CSS 部分，约 15min）
2. **Step 2**: 修改 `modal.js`（Fix-C 的 JS 防御性设置，约 5min）
3. **Step 3**: 修改 `evidence.js`（Fix-D，约 15min）
4. **Step 4**: 运行新增测试 `tests/test_ui_modal_evidence.py`，确认全部通过
5. **Step 5**: 运行已有测试 `pytest tests/ -m "not slow and not real_api" -v`，确认无回归
6. **Step 6**: 手动验收（见 §5.1 清单）

---

## 7. 风险与注意事项

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|---------|
| 移除 `will-change` 后 Modal 动画略有卡顿 | P2 | 低端设备上 0.3s 的 opacity/transform 动画可能不够流畅 | 本项目中 Modal 内容以文本为主，动画简单，实际影响极小；如确有卡顿可仅对 `.modal-wrapper.active` 添加 `will-change: transform` |
| `scrollHeight` 检测在极短描述时误判 | P2 | 若描述恰好等于 `max-height`，容差值 `+2` 可能不足以覆盖所有浏览器舍入 | 将容差值增大到 `+4`；或改用 `getBoundingClientRect` 计算精确高度 |
| `requestAnimationFrame` 在 Qt WebEngine 中不触发 | P1 | 极少数 Qt 版本中 rAF 行为异常 | 增加 `setTimeout(..., 0)` 作为 fallback |
| 与已有 `01-page-flicker-v2.md` 方案的冲突 | P1 | 已有方案建议在 overlay 上增加 `will-change: transform`，与本方案矛盾 | **本方案优先**。已有方案的 `will-change` 会加剧频闪，不应实施；如需要合成层提升，应仅在 `.active` 状态下动态添加 |

---

## 8. 附录：相关文档

- `docs/optimization-plan/01-page-flicker-v2.md` — 页面闪动优化方案（需注意与本方案在 `will-change` 使用上的冲突）
- `docs/fix-bug-fix-plan.md` — 历史 Bug 修复方案（存档/读档、独立对话上下文等）
- `docs/review-bug-fix-plan.md` — 架构评审报告
