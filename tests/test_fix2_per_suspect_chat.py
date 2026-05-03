"""Fix-2: 验证每个嫌疑人有独立的对话上下文。

P0 场景（静态分析 chat.js）：
1. 首次加载时 _currentSuspect 为 null
2. 切换到无对话的嫌疑人时显示占位消息
3. 系统消息跨嫌疑人显示

P1 场景（静态分析 chat.js）：
4. 连续快速切换嫌疑人消息不混淆
5. ChatManager.clear() 重置所有状态
6. addMessage 中 system 角色消息存储到 _default
7. switchSuspect 中移除 typing indicator
"""

import pytest


class TestCurrentSuspectInitiallyNull:
    """P0-1: 首次加载时 _currentSuspect 为 null。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_current_suspect_initialized_to_null(self, chat_js_content):
        """ChatManager 构造函数中 _currentSuspect 应初始化为 null。"""
        # 查找 constructor 中 _currentSuspect 的初始化
        constructor_start = chat_js_content.index("constructor()")
        constructor_section = chat_js_content[constructor_start:constructor_start + 500]
        assert "this._currentSuspect = null" in constructor_section, (
            "ChatManager 构造函数中 _currentSuspect 应初始化为 null，"
            "表示尚未选择任何嫌疑人"
        )


class TestSwitchToSuspectWithNoMessages:
    """P0-2: 切换到无对话的嫌疑人时显示占位消息。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_switch_suspect_shows_placeholder_when_no_messages(self, chat_js_content):
        """switchSuspect 在无消息时应显示占位消息。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 800]
        # 应有检查消息为空并显示占位符的逻辑
        assert "msgs.length === 0" in switch_section or "msgs.length==0" in switch_section or \
               "defaultMsgs.length === 0" in switch_section, (
            "switchSuspect 应检查消息数量，为空时显示占位消息"
        )

    def test_placeholder_contains_suspect_name(self, chat_js_content):
        """占位消息应包含嫌疑人名称。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 1200]
        # 实际文本是 "的对话将在这里显示"
        assert "对话将在这里显示" in switch_section, (
            "占位消息应提示用户此嫌疑人的对话将在此显示"
        )


class TestSystemMessagesCrossSuspect:
    """P0-3: 系统消息跨嫌疑人显示。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_add_message_system_role_stored_in_default(self, chat_js_content):
        """addMessage 中 system 角色消息应存储到 _default 分组。"""
        addmsg_start = chat_js_content.index("addMessage(")
        addmsg_section = chat_js_content[addmsg_start:addmsg_start + 800]
        # system 消息的 owner 应为 '_default'
        assert "_default" in addmsg_section, (
            "addMessage 应使用 '_default' 作为系统消息的存储分组"
        )

    def test_switch_suspect_renders_default_system_messages(self, chat_js_content):
        """switchSuspect 应重新渲染 _default 中的 system 消息。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 800]
        # 应遍历 _default 消息
        assert "_default" in switch_section, (
            "switchSuspect 应读取 _default 分组中的系统消息并渲染"
        )

    def test_system_messages_rendered_for_all_suspects(self, chat_js_content):
        """系统消息在切换嫌疑人时应始终显示。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 800]
        # 应先渲染 default 的 system 消息，再渲染嫌疑人消息
        assert "role === 'system'" in switch_section or "msg.role === 'system'" in switch_section, (
            "switchSuspect 应筛选 _default 中的 system 消息进行渲染"
        )


class TestRapidSuspectSwitchNoMixup:
    """P1-4: 连续快速切换嫌疑人消息不混淆。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_switch_suspect_clears_container_before_render(self, chat_js_content):
        """switchSuspect 应在重新渲染前清空容器。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 800]
        # 应有 container.innerHTML = '' 或类似清空操作
        assert "innerHTML = ''" in switch_section or "innerHTML=''" in switch_section, (
            "switchSuspect 应在渲染前清空容器 innerHTML，"
            "防止快速切换时消息混淆"
        )

    def test_messages_stored_per_suspect_not_globally(self, chat_js_content):
        """消息应按嫌疑人分组存储，而非全局列表。"""
        # 验证 addMessage 使用 _messagesBySuspect[owner] 追加
        addmsg_start = chat_js_content.index("addMessage(")
        addmsg_section = chat_js_content[addmsg_start:addmsg_start + 800]
        assert "_messagesBySuspect" in addmsg_section, (
            "addMessage 应使用 _messagesBySuspect[owner] 按嫌疑人分组存储消息"
        )

    def test_switch_suspect_sets_current_suspect_first(self, chat_js_content):
        """switchSuspect 应先设置 _currentSuspect 再渲染。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 300]
        # this._currentSuspect = suspectName 应在容器操作之前
        assert "this._currentSuspect = suspectName" in switch_section or \
               "this._currentSuspect=suspectName" in switch_section, (
            "switchSuspect 应先设置 _currentSuspect 再执行渲染操作"
        )


class TestChatManagerClearResetsAll:
    """P1-5: ChatManager.clear() 重置所有状态。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_clear_resets_messages_by_suspect(self, chat_js_content):
        """clear() 应重置 _messagesBySuspect 为空对象。"""
        clear_start = chat_js_content.index("clear()")
        clear_section = chat_js_content[clear_start:clear_start + 400]
        assert "_messagesBySuspect = {}" in clear_section or \
               "_messagesBySuspect={}" in clear_section, (
            "clear() 应重置 _messagesBySuspect = {}"
        )

    def test_clear_resets_current_suspect(self, chat_js_content):
        """clear() 应重置 _currentSuspect 为 null。"""
        clear_start = chat_js_content.index("clear()")
        clear_section = chat_js_content[clear_start:clear_start + 400]
        assert "_currentSuspect = null" in clear_section or \
               "_currentSuspect=null" in clear_section, (
            "clear() 应重置 _currentSuspect = null"
        )

    def test_clear_resets_typing_indicator(self, chat_js_content):
        """clear() 应重置 _typingEl 为 null。"""
        clear_start = chat_js_content.index("clear()")
        clear_section = chat_js_content[clear_start:clear_start + 400]
        assert "_typingEl = null" in clear_section or \
               "_typingEl=null" in clear_section, (
            "clear() 应重置 _typingEl = null"
        )

    def test_clear_clears_container_innerHTML(self, chat_js_content):
        """clear() 应清空容器内容。"""
        clear_start = chat_js_content.index("clear()")
        clear_section = chat_js_content[clear_start:clear_start + 400]
        assert "innerHTML" in clear_section, (
            "clear() 应清空容器 innerHTML"
        )


class TestAddMessageSystemStoredInDefault:
    """P1-6: addMessage 中 system 角色消息存储到 _default。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_system_role_owner_is_default(self, chat_js_content):
        """当 role 为 system 时，owner 应为 '_default'。"""
        addmsg_start = chat_js_content.index("addMessage(")
        addmsg_section = chat_js_content[addmsg_start:addmsg_start + 800]
        # owner 计算逻辑：player → _currentSuspect, else → suspectName || _default
        # 但 system 消息的 suspectName 通常是空，所以 owner 应为 '_default'
        # 验证逻辑中包含 '_default' 作为降级值
        assert "'_default'" in addmsg_section or '"_default"' in addmsg_section, (
            "addMessage 应使用 '_default' 作为系统消息的 owner 降级值"
        )

    def test_system_role_rendered_for_current_view(self, chat_js_content):
        """system 消息应在当前视图中渲染（无论哪个嫌疑人被选中）。"""
        addmsg_start = chat_js_content.index("addMessage(")
        addmsg_section = chat_js_content[addmsg_start:addmsg_start + 800]
        # 应有条件判断：owner === _currentSuspect || owner === '_default' || role === 'system'
        assert "role === 'system'" in addmsg_section or "role==='system'" in addmsg_section, (
            "addMessage 应在 role === 'system' 时始终渲染消息"
        )


class TestSwitchSuspectRemovesTypingIndicator:
    """P1-7: switchSuspect 中移除 typing indicator。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_switch_suspect_calls_remove_typing_indicator(self, chat_js_content):
        """switchSuspect 应调用 _removeTypingIndicator()。"""
        switch_start = chat_js_content.index("switchSuspect(")
        switch_section = chat_js_content[switch_start:switch_start + 800]
        assert "_removeTypingIndicator" in switch_section, (
            "switchSuspect 应调用 _removeTypingIndicator()，"
            "防止切换嫌疑人时残留 typing indicator"
        )

    def test_remove_typing_indicator_nullifies_element(self, chat_js_content):
        """_removeTypingIndicator 应移除 DOM 元素并置空 _typingEl。"""
        # Use rfind to find the method definition, not the call sites
        remove_idx = chat_js_content.rfind("_removeTypingIndicator()")
        if remove_idx == -1:
            remove_idx = chat_js_content.rfind("_removeTypingIndicator")
        assert remove_idx != -1, "应找到 _removeTypingIndicator 定义"
        remove_section = chat_js_content[remove_idx:remove_idx + 300]
        assert "_typingEl = null" in remove_section or \
               "_typingEl=null" in remove_section, (
            f"_removeTypingIndicator 应设置 _typingEl = null, "
            f"section: {remove_section[:200]}"
        )
        assert "removeChild" in remove_section or "remove()" in remove_section, (
            "_removeTypingIndicator 应从 DOM 中移除 typing indicator 元素"
        )


# ============================================================
# 原有测试保留
# ============================================================


class TestChatJSPerSuspectContext:
    """验证 chat.js 实现了按嫌疑人分组的消息存储。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_chat_manager_has_messages_by_suspect(self, chat_js_content):
        assert "_messagesBySuspect" in chat_js_content

    def test_chat_manager_has_current_suspect(self, chat_js_content):
        assert "_currentSuspect" in chat_js_content

    def test_chat_manager_has_switch_suspect_method(self, chat_js_content):
        assert "switchSuspect" in chat_js_content

    def test_switch_suspect_clears_container(self, chat_js_content):
        assert "switchSuspect" in chat_js_content
        switch_start = chat_js_content.index("switchSuspect")
        switch_section = chat_js_content[switch_start:switch_start + 500]
        assert "innerHTML" in switch_section or "textContent" in switch_section or "removeChild" in switch_section


class TestAppJSSuspectSwitch:
    """验证 app.js 在嫌疑人切换时调用 switchSuspect。"""

    @pytest.fixture
    def app_js_content(self):
        with open("ui/web/js/app.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_suspect_selector_calls_switch_suspect(self, app_js_content):
        assert "switchSuspect" in app_js_content

    def test_init_game_state_sets_suspect_context(self, app_js_content):
        assert "switchSuspect" in app_js_content
