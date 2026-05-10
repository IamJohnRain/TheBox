"""Story engine for chapter flow and branching."""

import logging
from typing import Any, Dict, List, Optional

from schemas.story import ChapterResult

logger = logging.getLogger("thebox")


class StoryEngine:
    """剧情引擎：管理章节流转、分支判定、叙事状态。"""

    def __init__(self, story_data: dict):
        self.story: dict = story_data
        self.current_chapter_id: str = story_data["chapters"][0]["chapter_id"]
        self.completed_chapters: List[str] = []
        self.story_variables: Dict[str, Any] = {}
        self.carried_evidence: List[dict] = []
        self.interrogation_engine = None

        # 构建章节索引
        self._chapters_by_id: Dict[str, dict] = {
            ch["chapter_id"]: ch for ch in story_data["chapters"]
        }
        self._endings_by_id: Dict[str, dict] = {
            e["id"]: e for e in story_data.get("endings", [])
        }

    def _get_current_chapter(self) -> dict:
        """获取当前章节数据。"""
        chapter = self._chapters_by_id.get(self.current_chapter_id)
        if not chapter:
            raise ValueError(f"章节不存在: {self.current_chapter_id}")
        return chapter

    def start_chapter(self) -> dict:
        """开始当前章节，返回符合 CASE_SCHEMA 的 case_data。"""
        chapter = self._get_current_chapter()

        if chapter["type"] == "scripted":
            case_data = dict(chapter["case_data"])
        elif chapter["type"] == "generated":
            from core.case_generator import generate_case_with_constraints

            constraints = chapter.get("case_constraints", {})
            case_data = generate_case_with_constraints(
                constraints=constraints,
                story_variables=self.story_variables,
            )
        else:
            raise ValueError(f"未知章节类型: {chapter['type']}")

        # 合并跨章节携带证据
        if self.carried_evidence:
            case_data["evidences"] = list(case_data.get("evidences", []))
            existing_ids = {e["id"] for e in case_data["evidences"]}
            for ev in self.carried_evidence:
                if ev["id"] not in existing_ids:
                    case_data["evidences"].append(ev)

        logger.info(f"开始章节: {chapter['title']} ({self.current_chapter_id})")
        return case_data

    def complete_chapter(self, result: ChapterResult) -> Optional[str]:
        """完成当前章节，评估分支，返回下一章 chapter_id 或结局 id。"""
        chapter = self._get_current_chapter()
        self.completed_chapters.append(self.current_chapter_id)

        # 更新叙事状态
        self._apply_story_variables(chapter)

        # 评估分支
        next_id = self._evaluate_branch(chapter["branch"], result)

        # 检查是否到达结局
        if next_id in self._endings_by_id:
            self.current_chapter_id = next_id
            logger.info(f"到达结局: {next_id}")
            return next_id

        # 检查 merge_to
        next_chapter = self._chapters_by_id.get(next_id)
        if next_chapter and next_chapter.get("merge_to"):
            next_id = next_chapter["merge_to"]

        self.current_chapter_id = next_id
        logger.info(f"推进到章节: {next_id}")
        return next_id

    def _evaluate_branch(self, branch: dict, result: ChapterResult) -> str:
        """评估分支条件，返回下一章/结局 ID。"""
        for condition in branch["conditions"]:
            if self._match_condition(condition, result):
                return condition["next"]
        # 兜底
        return branch["conditions"][-1]["next"]

    def _match_condition(self, condition: dict, result: ChapterResult) -> bool:
        """匹配单个声明式条件。"""
        if "result" in condition:
            if condition["result"] != result["result"]:
                return False

        if "min_confession" in condition:
            if result["confession_level"] < condition["min_confession"]:
                return False

        if "min_evidence" in condition:
            if result["evidence_count"] < condition["min_evidence"]:
                return False

        return True

    def _apply_story_variables(self, chapter: dict) -> None:
        """应用章节的叙事状态变量。"""
        variables = chapter.get("story_variables", {})

        # 设置变量
        for key, value in variables.get("set", {}).items():
            self.story_variables[key] = value

        # 收集携带证据
        for ev_id in variables.get("carry_evidence", []):
            if self.interrogation_engine:
                ev = self.interrogation_engine.get_evidence(ev_id)
                if ev and ev not in self.carried_evidence:
                    self.carried_evidence.append(ev)

    def get_narrative(self, result: ChapterResult) -> str:
        """根据审讯结果返回对应的叙事文本。"""
        chapter = self._get_current_chapter()
        narrative = chapter.get("narrative", {})

        result_key = f"closing_{result['result']}"
        return narrative.get(result_key, narrative.get("closing_fail", ""))

    def get_ending(self, ending_id: str) -> Optional[dict]:
        """获取结局数据。"""
        return self._endings_by_id.get(ending_id)

    def is_ending(self, chapter_id: str) -> bool:
        """检查是否是结局。"""
        return chapter_id in self._endings_by_id

    def get_progress(self) -> dict:
        """获取剧情进度。"""
        return {
            "story_id": self.story["story_id"],
            "title": self.story["title"],
            "current_chapter_id": self.current_chapter_id,
            "current_chapter_title": self._get_current_chapter()["title"],
            "completed_count": len(self.completed_chapters),
            "total_chapters": len(self.story["chapters"]),
            "story_variables": self.story_variables,
        }
