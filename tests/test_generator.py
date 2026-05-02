import os

import pytest

from core.case_generator import CASE_SCHEMA, generate_case
from scripts.validate_case import validate_case

BACKGROUND_STORIES = [
    "一栋豪华别墅中，富商在书房内被发现死亡，现场有一杯被打翻的红酒和一封未写完的遗嘱。",
    "深夜的美术馆，著名画家的工作室里，画家被发现死在画架前，画布上溅满了血迹。",
    "偏远山区的温泉旅馆，老板在温泉池中被发现溺亡，但身上有奇怪的伤痕。",
    "大学实验室里，一位教授在下班后被发现倒在实验台旁，旁边有打翻的化学试剂。",
    "老城区的茶馆，茶馆老板在阁楼密室中被发现窒息身亡，门窗紧锁。",
    "游轮上的宴会结束后，一名商人被发现死在船舱中，房间内有大量现金散落。",
    "古寺藏经阁中，一位老僧被发现圆寂，但法医鉴定为中毒而非自然死亡。",
    "乡村诊所的药柜被撬开，医生在诊所后院被发现死亡，手中握着一张处方笺。",
    "剧院后台，女演员在演出间隙被发现死在化妆间，镜子上有用口红写的字。",
    "地下赌场被发现倒闭，赌场老板死在保险柜旁，保险柜门大开，里面空无一物。",
]


def _has_api_key():
    if os.environ.get("OPENAI_API_KEY"):
        return True
    try:
        from core.config import get_api_key

        return bool(get_api_key())
    except Exception:
        return False


@pytest.mark.slow
@pytest.mark.real_api
@pytest.mark.skipif(not _has_api_key(), reason="未设置 API Key，跳过真实 API 调用")
class TestCaseGeneratorAPI:
    def test_generate_and_validate_all_backgrounds(self):
        success_count = 0
        total = len(BACKGROUND_STORIES)
        failures = []

        for i, background in enumerate(BACKGROUND_STORIES):
            try:
                case = generate_case(background)
                jsonschema_result = self._validate_schema(case)
                logic_result = self._validate_logic(case)

                if jsonschema_result and logic_result:
                    success_count += 1
                else:
                    failures.append(
                        f"背景 {i + 1}: "
                        f"schema={'通过' if jsonschema_result else '失败'}, "
                        f"logic={'通过' if logic_result else '失败'}"
                    )
            except Exception as e:
                failures.append(f"背景 {i + 1}: 生成异常 - {str(e)}")

        success_rate = success_count / total
        print(f"\n成功率: {success_count}/{total} ({success_rate * 100:.1f}%)")
        for f in failures:
            print(f"  失败: {f}")

        assert success_rate >= 0.9, f"成功率 {success_rate * 100:.1f}% 低于 90%。失败详情: {failures}"

    def _validate_schema(self, case):
        import jsonschema

        try:
            jsonschema.validate(instance=case, schema=CASE_SCHEMA)
            return True
        except jsonschema.ValidationError:
            return False

    def _validate_logic(self, case):
        all_pass, _ = validate_case(case)
        return all_pass

    def test_generate_single_case_basic(self):
        case = generate_case(BACKGROUND_STORIES[0])
        assert isinstance(case, dict)
        assert "case_id" in case
        assert "title" in case
        assert "suspects" in case
        assert len(case["suspects"]) >= 2
        assert "truth" in case
        assert "evidences" in case


class TestCaseGeneratorUnit:
    def test_build_system_prompt(self):
        from core.case_generator import _build_system_prompt

        prompt = _build_system_prompt("测试背景")
        assert "测试背景" in prompt
        assert "JSON" in prompt
        assert "truth" in prompt
        assert "suspects" in prompt
        assert "forbidden_to_reveal" in prompt
        assert "动机" in prompt
        assert "手段" in prompt
        assert "时机" in prompt

    def test_validate_case_with_fixture(self):
        import json
        from pathlib import Path

        fixture_path = Path(__file__).parent / "fixtures" / "mock_cases" / "simple.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            case = json.load(f)
        all_pass, results = validate_case(case)
        assert all_pass, f"Fixture should pass validation: {results}"

    def test_extract_elements(self):
        from scripts.validate_case import _extract_elements

        elements = _extract_elements("邻居李四因偷花被老张发现，争执中用锄头打死老张。")
        assert "motive" in elements
        assert "means" in elements
        assert "opportunity" in elements
