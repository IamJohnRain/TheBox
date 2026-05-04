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
        assert 'display:none' in evidence_js and 'evidence-expand-btn' in evidence_js, (
            "evidence.js 应默认隐藏展开按钮，仅在内容溢出时显示"
        )

    def test_uses_request_animation_frame(self, evidence_js):
        """应在 requestAnimationFrame 回调中检测高度。"""
        assert "requestAnimationFrame" in evidence_js, (
            "evidence.js 应使用 requestAnimationFrame 确保 DOM 布局完成后再检测高度"
        )


class TestNoTransitionAllOnModalElements:
    """验证 Modal 内部元素不使用 transition: all，避免 Qt WebEngine 频闪。"""

    @pytest.fixture
    def components_css(self):
        with open("ui/web/css/components.css", "r", encoding="utf-8") as f:
            return f.read()

    def _get_block(self, css, selector):
        start = css.index(selector + " {")
        end = css.index("}", start)
        return css[start:end]

    def test_save_slot_no_transition_all(self, components_css):
        """.save-slot 不应使用 transition: all。"""
        block = self._get_block(components_css, ".save-slot")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".save-slot 不应使用 transition: all，会导致 Qt WebEngine 频闪"
        )

    def test_evidence_card_no_transition_all(self, components_css):
        """.evidence-card 不应使用 transition: all。"""
        block = self._get_block(components_css, ".evidence-card")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".evidence-card 不应使用 transition: all"
        )

    def test_btn_action_no_transition_all(self, components_css):
        """.btn-action 不应使用 transition: all。"""
        block = self._get_block(components_css, ".btn-action")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".btn-action 不应使用 transition: all"
        )

    def test_modal_close_no_transition_all(self, components_css):
        """.modal-close 不应使用 transition: all。"""
        block = self._get_block(components_css, ".modal-close")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".modal-close 不应使用 transition: all"
        )

    def test_modal_btn_no_transition_all(self, components_css):
        """.modal-btn 不应使用 transition: all。"""
        block = self._get_block(components_css, ".modal-btn")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".modal-btn 不应使用 transition: all"
        )

    def test_save_slot_action_btn_no_transition_all(self, components_css):
        """.save-slot-action-btn 不应使用 transition: all。"""
        block = self._get_block(components_css, ".save-slot-action-btn")
        assert "transition: all" not in block and "transition-all" not in block, (
            ".save-slot-action-btn 不应使用 transition: all"
        )
