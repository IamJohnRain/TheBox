"""Fix-3: 验证证据字段降级处理和 XSS 防护。

P0 场景（静态分析 evidence.js）：
1. 证据 name 为空字符串时降级显示
2. 证据 name 为 null/undefined 时降级显示

P1 场景（静态分析 evidence.js）：
3. 证据 description 为空/null 时不崩溃
4. 证据 id 缺失时点击不崩溃
5. 证据名称包含 HTML 特殊字符时 XSS 防护
6. 证据 description 包含 HTML 特殊字符时 XSS 防护
7. loadEvidences 传入 null/undefined 时降级
"""

import json
import pytest


class TestEvidenceNameEmptyFallback:
    """P0-1: 证据 name 为空字符串时降级显示。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_name_empty_string_fallback(self, evidence_js_content):
        """evidence.name 为空字符串时，应降级显示 '未知证据'。

        静态分析：代码中应使用 evidence.name || '未知证据' 模式。
        """
        # 查找 _addEvidenceCard 中对 name 的使用
        assert "未知证据" in evidence_js_content, (
            "evidence.js 应在 name 为空时降级显示 '未知证据'"
        )
        # 验证使用 || 降级模式
        assert "evidence.name || '未知证据'" in evidence_js_content or \
               "evidence.name||'未知证据'" in evidence_js_content or \
               "evidence.name || \"未知证据\"" in evidence_js_content, (
            "evidence.js 应使用 evidence.name || '未知证据' 降级模式处理空 name"
        )


class TestEvidenceNameNullFallback:
    """P0-2: 证据 name 为 null/undefined 时降级显示。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_name_null_undefined_fallback(self, evidence_js_content):
        """evidence.name 为 null/undefined 时，应降级显示 '未知证据'。

        静态分析：|| 运算符对 null/undefined/空字符串均生效。
        """
        # || 运算符在 JS 中对 null, undefined, '' 均为 falsy，会降级
        assert "evidence.name ||" in evidence_js_content or \
               "evidence.name||" in evidence_js_content, (
            "evidence.js 应使用 || 运算符对 null/undefined 降级"
        )


class TestEvidenceDescriptionEmptyNoCrash:
    """P1-3: 证据 description 为空/null 时不崩溃。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_description_empty_or_null_handled(self, evidence_js_content):
        """description 为空/null 时，_addEvidenceCard 应使用降级值。

        静态分析：代码中应使用 evidence.description || '' 模式。
        """
        assert "evidence.description ||" in evidence_js_content or \
               "evidence.description||" in evidence_js_content, (
            "evidence.js 应使用 evidence.description || '' 降级模式处理空 description"
        )


class TestEvidenceIdMissingNoCrash:
    """P1-4: 证据 id 缺失时点击不崩溃。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_id_used_in_data_attribute(self, evidence_js_content):
        """evidence.id 在 data-evidence-id 属性中使用，缺失时仍可渲染。"""
        # 验证 data-evidence-id 使用 evidence.id
        assert "data-evidence-id" in evidence_js_content, (
            "evidence.js 应使用 data-evidence-id 属性存储 evidence.id"
        )

    def test_click_handler_uses_evidence_id(self, evidence_js_content):
        """点击事件使用 evidence.id 调用 bridge.presentEvidence。"""
        assert "evidence.id" in evidence_js_content, (
            "evidence.js 点击事件应使用 evidence.id"
        )
        assert "presentEvidence" in evidence_js_content, (
            "evidence.js 点击确认后应调用 bridge.presentEvidence"
        )


class TestEvidenceNameXSSProtection:
    """P1-5: 证据名称包含 HTML 特殊字符时 XSS 防护。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_name_escaped_through_escapeHtml(self, evidence_js_content):
        """evidence.name 应通过 _escapeHtml() 转义，而非直接 innerHTML。"""
        # 查找 name 使用 _escapeHtml 的模式
        assert "_escapeHtml(evidence.name" in evidence_js_content or \
               "_escapeHtml(evidence.name ||" in evidence_js_content, (
            "evidence.name 应通过 _escapeHtml() 转义防止 XSS"
        )

    def test_escapeHtml_function_exists(self, evidence_js_content):
        """_escapeHtml 方法应存在且使用 textContent/innerHTML 安全模式。"""
        assert "_escapeHtml" in evidence_js_content, (
            "evidence.js 应定义 _escapeHtml 方法"
        )
        # 查找 _escapeHtml 方法定义（以 _escapeHtml(text) 开头）
        # 用 rfind 找最后出现的定义（非调用）
        def_idx = evidence_js_content.rfind("_escapeHtml(text)")
        if def_idx == -1:
            def_idx = evidence_js_content.rfind("_escapeHtml(")
        assert def_idx != -1, "应找到 _escapeHtml 方法定义"
        escape_section = evidence_js_content[def_idx:def_idx + 300]
        assert "textContent" in escape_section, (
            "_escapeHtml 应使用 textContent 赋值再取 innerHTML 的安全模式"
        )


class TestEvidenceDescriptionXSSProtection:
    """P1-6: 证据 description 包含 HTML 特殊字符时 XSS 防护。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_description_escaped_through_escapeHtml(self, evidence_js_content):
        """evidence.description 应通过 _escapeHtml() 转义。"""
        assert "_escapeHtml(evidence.description" in evidence_js_content or \
               "_escapeHtml(evidence.description ||" in evidence_js_content, (
            "evidence.description 应通过 _escapeHtml() 转义防止 XSS"
        )


class TestLoadEvidencesNullFallback:
    """P1-7: loadEvidences 传入 null/undefined 时降级。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_loadEvidences_null_or_undefined_fallback(self, evidence_js_content):
        """loadEvidences(evidences) 在 evidences 为 null/undefined 时应降级为空数组。"""
        # 查找 loadEvidences 方法中对 null/undefined 的处理
        load_start = evidence_js_content.index("loadEvidences")
        load_section = evidence_js_content[load_start:load_start + 400]
        assert "evidences ||" in load_section or "evidences||" in load_section, (
            "loadEvidences 应使用 evidences || [] 降级处理 null/undefined 输入"
        )


# ============================================================
# 原有测试保留：数据字段一致性和 JS 字段映射
# ============================================================


class TestEvidenceDataFieldConsistency:
    """验证证据数据结构与前端 JS 读取的字段名一致。"""

    def test_evidence_has_name_field(self, mock_case_simple):
        for evidence in mock_case_simple["evidences"]:
            assert "name" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'name' 字段"
            )

    def test_evidence_has_id_field(self, mock_case_simple):
        for evidence in mock_case_simple["evidences"]:
            assert "id" in evidence, (
                f"证据缺少 'id' 字段"
            )

    def test_evidence_has_description_field(self, mock_case_simple):
        for evidence in mock_case_simple["evidences"]:
            assert "description" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'description' 字段"
            )

    def test_evidence_has_related_suspect_field(self, mock_case_simple):
        for evidence in mock_case_simple["evidences"]:
            assert "related_suspect" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'related_suspect' 字段"
            )


class TestEvidenceJSFieldMapping:
    """验证 evidence.js 读取的字段名与后端数据一致。"""

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_js_uses_evidence_name_not_title(self, evidence_js_content):
        assert "evidence.title" not in evidence_js_content, (
            "evidence.js 不应使用 evidence.title，应使用 evidence.name"
        )

    def test_js_uses_evidence_id(self, evidence_js_content):
        assert "evidence.id" in evidence_js_content, (
            "evidence.js 应使用 evidence.id"
        )

    def test_js_uses_evidence_name(self, evidence_js_content):
        assert "evidence.name" in evidence_js_content, (
            "evidence.js 应使用 evidence.name"
        )

    def test_js_does_not_use_evidence_tag(self, evidence_js_content):
        assert "evidence.tag" not in evidence_js_content, (
            "evidence.js 不应使用 evidence.tag，后端 EvidenceData 无此字段"
        )
