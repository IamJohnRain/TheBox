# UI Modal & Evidence 修复方案（修订版 v2）

> 优先级: **P0** (用户体验严重受损)
> 影响范围: 前端 JS + CSS + Python Bridge
> 可并行: **是** — CSS 修复、JS 修复、Python 时序修复可独立进行
> 负责 Agent: UI Agent (前端) + 后端 Agent (Python bridge 时序)
> 评审状态: **需修改后通过** — 基于 `docs/REPORT-ui-modal-evidence-bug-fix-plan.md`

---

## 修订说明

| 修订项 | 原方案 | 修订后 | 原因 |
|--------|--------|--------|------|
| Fix-A/B 根因 | 仅归因于 GPU 合成层属性过多 | **增加 JS 时序竞争根因** | 合成层只是表象，hide→show 同帧执行才是 transition 重叠的直接触发原因 |
| JS 时序修复 | 无 | **Python 端增加 `QTimer.singleShot` 延迟** | 确保 loading fade-out 完成后再触发 modal fade-in |
| `loading.js` | 未修改 | **增加防御性 `pointer-events` 设置** | Fix-C 同样适用于 loading overlay |
| `backdrop-filter` | 未分析 | **Modal 打开时暂停 navbar blur** | `.navbar.blurred` 的全视口合成层会加剧竞争 |
| z-index | 共用 300 | **loading overlay 改为 250** | 避免同层 transition 竞争 |
| 与旧方案冲突 | 仅声明"本方案优先" | **明确废弃 `01-page-flicker-v2.md` Step 5** | 防止实施混乱 |

---

## 1. 问题总览

| # | 问题描述 | 根因 | 影响文件 |
|---|---------|------|---------|
| Fix-A | 生成案件后的案件介绍弹窗，上下滑动时频闪 | **复合根因**：① CSS 过度使用 GPU 合成层属性；② `body.modal-open` 时 `.navbar.blurred` 的 `backdrop-filter` 创建额外合成层；③ Qt WebEngine 对多层 `position: fixed` 的渲染管线限制 | `components.css`, `style.css` |
| Fix-B | 游戏超时后进入复盘，复盘等待界面频闪 | **复合根因**：① Loading Overlay 与 Modal Backdrop 共用 `z-index: 300`；② Python 端 `hide_loading` → `show_review` **同帧执行**，transition 重叠；③ 合成层属性叠加 | `components.css`, `web_main_window.py` |
| Fix-C | 审讯复盘子界面加载后出现透明蒙版，所有按钮无法点击 | `opacity: 0 + visibility: hidden` 隐藏的元素在 transition 被打断时仍接收 pointer 事件；Qt WebEngine 对 `visibility` 的事件屏蔽不可靠；**loading overlay 同样存在此问题** | `components.css`, `modal.js`, `loading.js` |
| Fix-D | 证据描述展示不全，且没有展开按钮 | 使用固定字符阈值 `DESC_COLLAPSE_THRESHOLD = 60` 判断，未考虑实际渲染行高；多行文本可能因换行被截断但无按钮 | `evidence.js` |

---

## 2. 根因分析

### 2.1 根因 A（频闪）：GPU 合成层属性过多 + backdrop-filter 竞争

**文件**: `ui/web/css/components.css:599-648`, `ui/web/css/style.css:233`

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

同时，`style.css` 中：

```css
.navbar.blurred {
    backdrop-filter: blur(12px);  /* ← 创建全视口合成层 */
}
```

当 Modal 打开时，`body.modal-open` 激活，`.navbar.blurred` 仍在后台维持 `backdrop-filter` 合成层。多个合成层在 Qt WebEngine（Chromium 内核）中竞争 GPU 资源，Modal 内容触发 `overflow-y: auto` 滚动时，合成器频繁重新计算层级，表现为频闪。

### 2.2 根因 B（频闪）：JS 时序竞争 + z-index 重叠 ⭐ 核心遗漏

**文件**: `ui/web/css/components.css:518-616`, `ui/web_main_window.py`

```css
.loading-overlay {
    z-index: var(--z-modal-backdrop);  /* ← 300，与 backdrop 相同 */
}
.modal-backdrop {
    z-index: var(--z-modal-backdrop);  /* ← 300 */
}
```

复盘流程：

```
showEndingDialog (Modal) → 用户点击"复盘审讯" → requestReview()
  → _on_review_requested() emit show_loading
  → [异步等待复盘生成...]
  → _on_review_ready() emit hide_loading + show_review (同帧!)
```

在 `_on_review_ready()` 中，`hide_loading.emit()` 和 `show_review.emit()` **在同一个 Python 函数调用中连续执行**。对应的 JS 端：

1. `loadingManager.hide()` → `.loading-overlay` 开始 `opacity: 1 → 0` transition（0.3s）
2. `modalManager.showReviewReport()` → `.modal-backdrop` 开始 `opacity: 0 → 1` transition（0.3s）

两个 `position: fixed` + 全屏 + `z-index: 300` 的元素在同一 0.3s 窗口内同时渐变，浏览器合成器需要在每一帧重新计算两个半透明层的叠加结果。**这是 Fix-B 频闪的最直接触发原因**。

> **为什么之前修多轮有缓解但没彻底解决？**
> 前几次修复可能移除了部分合成层属性（如 `backdrop-filter`），减少了合成器压力，所以"有缓解"。但只要 `hide()` 和 `show()` 仍在同帧执行，transition 重叠就无法避免，所以"还是没彻底解决"。

### 2.3 根因 C（透明蒙版）：Transition 中断后事件未正确屏蔽

**文件**: `ui/web/css/components.css:518-616`, `ui/web/js/modal.js:863-870`, `ui/web/js/loading.js:103-109`

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

**注意**：此问题同时影响 `.loading-overlay` 和 `.modal-backdrop`，但原方案遗漏了 `loading.js` 的修改。

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

### 3.1 Fix-A & Fix-B（Part 1）：移除过度合成层属性

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
-    z-index: var(--z-modal-backdrop);
+    z-index: var(--z-loading-overlay);  /* Fix-B: 差异化层级，避免同层竞争 */
     opacity: 0;
     visibility: hidden;
     transition: opacity 0.3s, visibility 0.3s;
+    pointer-events: none;  /* Fix-C 同步修复 */
 }
```

**同时修改 `style.css`**：

```diff
 :root {
     ...
     --z-modal-backdrop: 300;
+    --z-loading-overlay: 250;  /* Fix-B: 低于 modal-backdrop */
     --z-modal: 400;
     ...
 }
```

**原理说明**：
- `will-change`、`contain`、`backface-visibility` 都是**强制创建独立 GPU 合成层**的属性。在标准浏览器中这些属性能提升动画性能，但在 Qt WebEngine 中，叠加的 `position: fixed` 元素 + 合成层 + `overflow-y: auto` 滚动会导致合成器频繁重新计算层级，表现为闪烁。
- 移除这些属性后，Modal 和 Loading 仍然正常工作（`transition: opacity/transform` 由浏览器原生支持，不需要手动提升合成层），且滚动时不再触发频闪。
- **z-index 差异化**：将 `.loading-overlay` 从 300 降为 250，确保即使 transition 重叠，也不会因为同 z-index 导致合成器反复切换渲染顺序。

### 3.2 Fix-A（Part 2）：Modal 打开时暂停 navbar backdrop-filter

**文件**: `ui/web/css/components.css`

```css
/* 新增：Modal 打开时暂停 navbar 的 backdrop-filter，避免额外合成层竞争 */
body.modal-open .navbar.blurred {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
}
```

**原理说明**：
- `.navbar.blurred` 的 `backdrop-filter: blur(12px)` 会创建覆盖整个视口的合成层。
- 当 Modal 打开时，`.navbar` 在视觉层级上被 Modal backdrop 覆盖，其 blur 效果不可见，但合成层仍在占用 GPU 资源。
- 通过 `body.modal-open` 选择器在 Modal 打开时暂停 `backdrop-filter`，可减少一个全视口合成层，降低频闪概率。

### 3.3 Fix-B（Part 2）：Python 端 JS 时序修复 ⭐ 核心修改

**文件**: `ui/web_main_window.py`

在 `_on_review_ready()`（或等价的复盘数据就绪处理函数）中：

```diff
 def _on_review_ready(self, review_data):
     self._review_worker = None
     self.bridge.hide_loading.emit()
-    # ... 原有的 case_truth 追加等逻辑 ...
-    self.bridge.show_review.emit(review_data)
+    # 延迟显示复盘报告，等 loading overlay 的 fade-out transition（0.3s）完全完成
+    # 避免 loading fade-out 和 modal fade-in 在同一窗口内重叠导致频闪
+    QTimer.singleShot(350, lambda: self._emit_show_review(review_data))
+
+ def _emit_show_review(self, review_data):
+     # ... 原有的 case_truth 追加等逻辑 ...
+     self.bridge.show_review.emit(review_data)
```

**同理处理 `_on_review_error()`**（如有）：

```diff
 def _on_review_error(self, error_message):
     self._review_worker = None
     self.bridge.hide_loading.emit()
-    self.bridge.show_dialog.emit("复盘失败", error_message)
+    QTimer.singleShot(350, lambda: self.bridge.show_dialog.emit("复盘失败", error_message))
```

**原理说明**：
- 这是**根治 Fix-B 频闪的核心修改**。`hide_loading` 和 `show_review` 之间插入 350ms 延迟，确保 `.loading-overlay` 的 `opacity: 1 → 0` transition 完全结束后，再开始 `.modal-backdrop` 的 `opacity: 0 → 1` transition。
- 两个全屏覆盖层不再同时处于渐变状态，合成器不需要在同一帧内反复计算两个半透明层的叠加结果。
- **350ms 的选择依据**：CSS transition 时长为 0.3s，增加 50ms 缓冲确保 transitionend 事件已完成。

### 3.4 Fix-C：增加 `pointer-events` 显式控制

**文件**: `ui/web/css/components.css`

#### 3.4.1 为 overlay/backdrop 的显隐状态增加 pointer-events

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

#### 3.4.2 `hide()` 方法增加防御性设置

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

#### 3.4.3 `_show()` 方法清除内联样式

```diff
 _show(title, bodyHtml, buttons) {
     if (!this.modal || !this.backdrop) {
         console.error('[ModalManager] Modal elements not found');
         return;
     }

+    if (this.backdrop) {
+        this.backdrop.style.pointerEvents = '';  /* 清除 hide() 的内联样式 */
+    }
+
     if (this.titleEl) {
         this.titleEl.textContent = title;
     }
     // ... 后续不变
 }
```

**文件**: `ui/web/js/loading.js`

#### 3.4.4 `LoadingManager` 增加防御性设置

```diff
 show(message, cancellable) {
     if (!this.overlay) {
         console.error('[LoadingManager] Overlay element not found');
         return;
     }

     // 设置文本
     if (this.textEl) {
         this.textEl.textContent = message || '正在处理...';
     }

     // 设置状态
     if (this.statusEl) {
         this.statusEl.textContent = '已等待 0s';
     }

     // 控制取消按钮显示
     this._cancellable = Boolean(cancellable);
     if (this.cancelBtn) {
         this.cancelBtn.style.display = this._cancellable ? 'inline-block' : 'none';
     }

     // 显示遮罩
+    if (this.overlay) {
+        this.overlay.style.pointerEvents = '';  /* 清除 hide() 的内联样式 */
         this.overlay.classList.add('active');
+    }

     // 启动进度更新
     this._startProgressUpdate();
 }

 hide() {
-    if (this.overlay) {
-        this.overlay.classList.remove('active');
-    }
+    if (this.overlay) {
+        this.overlay.classList.remove('active');
+        this.overlay.style.pointerEvents = 'none';  /* 防御性：确保不可点击 */
+    }

     // 停止进度更新
     this._stopProgressUpdate();
 }
```

**原理说明**：
- `pointer-events: none` 是 CSS 中**最可靠**的禁用点击事件方式，比 `visibility: hidden` 更即时、不受 transition 时序影响。
- 在 `hide()` 中显式设置 `pointerEvents = 'none'` 作为防御性编程，防止 class 切换和 transition 之间的竞争条件。
- 在 `show()` 中清除内联样式，确保 `.active` 状态的 `pointer-events: auto` 能正常生效（虽然 CSS 优先级已足够覆盖，显式清除语义更清晰）。
- 此修复同时解决了 Loading Overlay 和 Modal Backdrop 在隐藏后拦截点击的问题。

### 3.5 Fix-D：基于实际渲染高度的展开按钮判断

**文件**: `ui/web/js/evidence.js`

#### 3.5.1 重写 `_addEvidenceCard()` 中的展开按钮逻辑

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
+        if (descEl && descEl.scrollHeight > descEl.clientHeight + 4) {
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
- `+ 4` 的容差值用于抵消浏览器舍入误差和 border/padding 的微小差异（比原方案的 `+ 2` 更宽松，覆盖更多边界情况）。

---

## 4. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web/css/components.css` | 修改 | ① 删除 `.modal-wrapper` 的 `will-change`/`contain`；② 删除 `.modal-backdrop` 的 `contain: strict`；③ 删除 `.modal` 的 `backface-visibility`/`contain`；④ 为 `.loading-overlay`/`.modal-backdrop` 增加 `pointer-events` 控制；⑤ `.loading-overlay` z-index 改为 `--z-loading-overlay`；⑥ 新增 `body.modal-open .navbar.blurred` 规则 |
| `ui/web/css/style.css` | 修改 | 新增 `--z-loading-overlay: 250` CSS 变量 |
| `ui/web_main_window.py` | 修改 | `_on_review_ready()` 中 `hide_loading` → `show_review` 之间增加 `QTimer.singleShot(350, ...)` 延迟；同理处理 `_on_review_error()` |
| `ui/web/js/modal.js` | 修改 | `hide()` 增加 `this.backdrop.style.pointerEvents = 'none'`；`_show()` 增加 `this.backdrop.style.pointerEvents = ''` |
| `ui/web/js/loading.js` | 修改 | `show()` 增加 `this.overlay.style.pointerEvents = ''`；`hide()` 增加 `this.overlay.style.pointerEvents = 'none'` |
| `ui/web/js/evidence.js` | 修改 | `_addEvidenceCard()` 移除固定字符阈值 `DESC_COLLAPSE_THRESHOLD`，改为基于 `scrollHeight > clientHeight + 4` 的动态检测；统一渲染展开按钮但默认隐藏 |

---

## 5. 验收测试

### 5.1 手动验收清单

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 案件介绍弹窗滚动 | 生成案件 → 点击"开始审讯"前查看案件资料 → 上下滑动弹窗 | 滚动平滑，无频闪 |
| 复盘等待界面 | 游戏超时 → 点击"复盘审讯" → 等待复盘生成 | Loading 界面显示正常，无频闪；Loading 消失后 Modal 平滑出现 |
| 复盘弹窗交互 | 复盘报告生成后 → 点击"重新开始"/"返回主菜单" | 按钮可正常点击，无透明蒙版阻断 |
| 证据展开按钮 | 查看证据面板 → 检查描述较长的证据卡片 | 若描述被截断，应显示"展开"按钮；点击后完整显示并变为"收起" |
| 证据无需展开 | 查看描述很短的证据卡片 | 不应显示"展开"按钮 |
| 快速切换 Modal | 打开设置 → 关闭 → 立即打开存档 | 界面响应正常，无残留蒙版 |
| 生成案件后弹窗 | 生成案件 → 查看案件介绍弹窗 → 滚动内容 | 无频闪，navbar 的毛玻璃效果在 Modal 打开时暂停 |

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

    def test_body_modal_open_pauses_navbar_blur(self, components_css):
        """body.modal-open .navbar.blurred 应禁用 backdrop-filter。"""
        assert "body.modal-open .navbar.blurred" in components_css, (
            "应存在 body.modal-open .navbar.blurred 规则以暂停 backdrop-filter"
        )
        start = components_css.index("body.modal-open .navbar.blurred")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "backdrop-filter: none" in block, (
            "body.modal-open 时应暂停 navbar 的 backdrop-filter"
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

    def test_loading_overlay_uses_different_z_index(self, components_css):
        """.loading-overlay 应使用 --z-loading-overlay 而非 --z-modal-backdrop。"""
        start = components_css.index(".loading-overlay {")
        end = components_css.index("}", start)
        block = components_css[start:end]
        assert "--z-loading-overlay" in block, (
            ".loading-overlay 应使用独立的 z-index 变量避免同层竞争"
        )
        assert "--z-modal-backdrop" not in block, (
            ".loading-overlay 不应与 modal-backdrop 共用 z-index"
        )


class TestZIndexVariableDefined:
    """验证 style.css 中定义了 --z-loading-overlay。"""

    @pytest.fixture
    def style_css(self):
        with open("ui/web/css/style.css", "r", encoding="utf-8") as f:
            return f.read()

    def test_z_loading_overlay_defined(self, style_css):
        """应定义 --z-loading-overlay: 250。"""
        assert "--z-loading-overlay: 250" in style_css, (
            "style.css 应定义 --z-loading-overlay: 250"
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

    def test_show_clears_pointer_events_inline(self, modal_js):
        """_show() 方法应清除 backdrop 的内联 pointerEvents 样式。"""
        assert "pointerEvents = ''" in modal_js or 'pointerEvents = ""' in modal_js, (
            "modal.js _show() 应清除 backdrop 的内联 pointerEvents 样式"
        )


class TestLoadingManagerPointerEventsDefense:
    """验证 loading.js 的 show/hide 方法有防御性 pointerEvents 设置。"""

    @pytest.fixture
    def loading_js(self):
        with open("ui/web/js/loading.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_hide_sets_pointer_events_none(self, loading_js):
        """hide() 方法应设置 this.overlay.style.pointerEvents = 'none'。"""
        assert "pointerEvents = 'none'" in loading_js or 'pointerEvents = "none"' in loading_js, (
            "loading.js hide() 应设置 overlay.style.pointerEvents = 'none' 作为防御"
        )

    def test_show_clears_pointer_events_inline(self, loading_js):
        """show() 方法应清除 overlay 的内联 pointerEvents 样式。"""
        assert "pointerEvents = ''" in loading_js or 'pointerEvents = ""' in loading_js, (
            "loading.js show() 应清除 overlay 的内联 pointerEvents 样式"
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

**推荐分 Phase 实施，每 Phase 完成后验证：**

### Phase 1：CSS 基础修复（Fix-A Part 1 + Fix-C CSS 部分）
1. 修改 `components.css`：移除合成层属性，增加 pointer-events 控制
2. 修改 `style.css`：新增 `--z-loading-overlay: 250`
3. 修改 `components.css`：`.loading-overlay` 使用新的 z-index 变量
4. **验证**：运行新增测试 `TestModalCSSNoCompositorProps` 和 `TestOverlayPointerEvents`

### Phase 2：Python 时序修复（Fix-B Part 2）⭐ 核心
5. 修改 `web_main_window.py`：`_on_review_ready()` 中增加 `QTimer.singleShot(350, ...)`
6. 同理处理 `_on_review_error()`（如有）
7. **验证**：手动测试复盘流程，确认 Loading → Modal 切换无频闪

### Phase 3：JS 防御性修复（Fix-C JS 部分）
8. 修改 `modal.js`：`hide()` 和 `_show()` 增加 pointer-events 控制
9. 修改 `loading.js`：`show()` 和 `hide()` 增加 pointer-events 控制
10. **验证**：运行新增测试 `TestModalHidePointerEventsDefense` 和 `TestLoadingManagerPointerEventsDefense`

### Phase 4：backdrop-filter 竞争修复（Fix-A Part 2）
11. 修改 `components.css`：新增 `body.modal-open .navbar.blurred` 规则
12. **验证**：手动测试 Modal 打开时 navbar 的毛玻璃效果是否暂停

### Phase 5：证据展开修复（Fix-D）
13. 修改 `evidence.js`：使用 `scrollHeight > clientHeight + 4` 动态检测
14. **验证**：运行新增测试 `TestEvidenceExpandByRenderedHeight`

### Phase 6：回归测试
15. 运行已有测试：`pytest tests/ -m "not slow and not real_api" -v`，确认无回归
16. 运行全部新增测试：`pytest tests/test_ui_modal_evidence.py -v`
17. 手动验收（见 §5.1 清单）

---

## 7. 风险与注意事项

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|---------|
| 移除 `will-change` 后 Modal 动画略有卡顿 | P2 | 低端设备上 0.3s 的 opacity/transform 动画可能不够流畅 | 本项目中 Modal 内容以文本为主，动画简单，实际影响极小；如确有卡顿可仅对 `.modal-wrapper.active` 动态添加 `will-change: transform`，动画结束后移除 |
| Python 端 `QTimer.singleShot` 引入 350ms 延迟影响用户体验 | P2 | 复盘流程多等待 350ms 可能被用户感知 | 350ms 与 transition 时长一致，用户感知不明显；如需要可缩短到 320ms，但不建议低于 300ms |
| `scrollHeight` 检测在极短描述时误判 | P2 | 若描述恰好等于 `max-height`，容差值 `+4` 可能不足以覆盖所有浏览器舍入 | 容差已从 `+2` 增大到 `+4`；如仍有误判可改用 `getBoundingClientRect` 计算精确高度 |
| 与已有 `01-page-flicker-v2.md` 方案的冲突 | **P0** | 已有方案 Step 5 建议在 overlay 上增加 `will-change: transform`，与本方案矛盾 | **本方案优先**。已有方案的 Step 5 已废弃，不应实施；需同步更新 `01-page-flicker-v2.md` 文档标注废弃状态 |
| z-index 差异化后 Loading Overlay 被 Modal 覆盖时无法交互 | P2 | `--z-loading-overlay: 250` 低于 `--z-modal-backdrop: 300` | 这是正确行为——当 Modal 打开时 Loading 不应被点击；Loading 的关闭由 Python/JS 逻辑控制，不依赖用户点击 |

### 关于 `01-page-flicker-v2.md` 的协调声明

`docs/optimization-plan/01-page-flicker-v2.md` Step 5 建议在 `.loading-overlay` 和 `.modal-backdrop` 上增加 `will-change: transform`，**与本方案直接矛盾**。协调决议如下：

1. **本方案优先**：`will-change` 在 Qt WebEngine 中会强制创建合成层，与频闪的根因一致，不应使用。
2. **旧方案 Step 5 废弃**：`01-page-flicker-v2.md` 的 Step 5 不再实施，需在文档中标注 "已废弃，参见 ui-modal-evidence-bug-fix-plan-v2.md"。
3. **旧方案 Step 4 复用**：`01-page-flicker-v2.md` Step 4（案件生成完成后延迟加载）的 `QTimer.singleShot` 模式可在本方案的 Python 时序修复中直接复用。

---

## 8. 附录

### 8.1 频闪根因完整清单

| 根因 | 原方案是否处理 | 修订版是否处理 | 处理方式 |
|------|---------------|---------------|---------|
| CSS 过度合成层属性 | ✅ | ✅ | 移除 `will-change`/`contain`/`backface-visibility` |
| `.loading-overlay` 与 `.modal-backdrop` 同 z-index | ⚠️ | ✅ | z-index 差异化（300 → 250） |
| JS 时序竞争（hide→show 同帧） | ❌ | ✅ | Python 端 `QTimer.singleShot(350, ...)` |
| `backdrop-filter: blur()` 参与合成层竞争 | ❌ | ✅ | `body.modal-open` 时暂停 navbar blur |
| `body.modal-open` + `overflow: hidden` 全局重排 | ❌ | ⚠️ | 保持现有实现，影响较小，不单独处理 |
| Qt WebEngine 渲染管线自身限制 | ❌ | ❌ | 无法处理，通过上述措施规避 |

### 8.2 相关文档

- `docs/ui-modal-evidence-bug-fix-plan.md` — 原修复方案（已修订为本文档）
- `docs/optimization-plan/01-page-flicker-v2.md` — 页面闪动优化方案（Step 5 已废弃，Step 4 模式复用）
- `docs/REPORT-ui-modal-evidence-bug-fix-plan.md` — 架构评审报告（本方案的评审依据）
- `docs/fix-bug-fix-plan.md` — 历史 Bug 修复方案（存档/读档、独立对话上下文等）

### 8.3 为什么这个修订版能彻底解决频闪？

原方案只处理了 **CSS 合成层属性** 这一个根因，属于"减少合成器压力"。这在合成器负载较轻时有明显效果（所以"有缓解"），但在快速切换场景下，transition 重叠仍然会触发频闪（所以"没彻底解决"）。

修订版增加了三个关键修复：
1. **JS 时序修复**：从根本上消除了 transition 重叠的可能性
2. **z-index 差异化**：即使 transition 重叠，也不会因为同层竞争导致合成器反复切换
3. **backdrop-filter 暂停**：减少了一个全视口合成层，进一步降低合成器压力

三者叠加，覆盖了频闪的所有可控根因，能够**彻底解决**该问题。

(End of file)
