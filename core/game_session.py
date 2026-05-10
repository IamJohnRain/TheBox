"""Game session coordinator for dual-mode system."""

import logging
from typing import Literal, Optional

from core.exceptions import TheBoxError
from schemas.story import ChapterResult, StoryProgress

logger = logging.getLogger("thebox")


class SessionModeError(TheBoxError):
    """会话模式相关错误。"""

    pass


class GameSession:
    """游戏会话协调器，管理双模式切换。

    协调剧情模式（story）和自定义模式（custom），
    统一管理 InterrogationEngine 的生命周期，
    并提供章节评估和剧情推进接口。
    """

    def __init__(self):
        self.mode: Optional[Literal["story", "custom"]] = None
        self.story_engine = None  # Phase 6 实现
        self.engine = None  # InterrogationEngine
        self.player = None  # PlayerProfile
        self._story_id: Optional[str] = None
        self._chapter_result: Optional[ChapterResult] = None

    def start_story(self, story_id: str, player=None) -> None:
        """启动剧情模式。

        Args:
            story_id: 剧情 ID，如 "missing_father"。
            player: 玩家档案（可选）。
        """
        from core.story_engine import StoryEngine
        from core.story_loader import load_story

        self.mode = "story"
        self._story_id = story_id
        self.player = player

        # 加载剧情脚本
        story_data = load_story(story_id)
        self.story_engine = StoryEngine(story_data)

        logger.info(f"启动剧情模式: {story_data['title']}")

    def start_custom(self, case_data: dict, player=None) -> None:
        """启动自定义模式（现有流程）。

        Args:
            case_data: 案件数据字典。
            player: 玩家档案（可选）。
        """
        from core.interrogation import InterrogationEngine

        self.mode = "custom"
        self.player = player
        self.engine = InterrogationEngine(case_data)

        # 初始化工具（根据玩家等级）
        if player:
            self.engine.init_tools(player.level)

        logger.info(f"启动自定义模式: {case_data.get('title', '未知案件')}")

    def start_chapter(self) -> dict:
        """开始当前章节，返回 case_data。仅剧情模式。

        Returns:
            当前章节的 case_data 字典。

        Raises:
            SessionModeError: 当前不在剧情模式。
        """
        if self.mode != "story" or not self.story_engine:
            raise SessionModeError("当前不在剧情模式")
        return self.story_engine.start_chapter()

    def evaluate_chapter(self) -> ChapterResult:
        """评估当前章节审讯结果。

        根据供词层级、证据出示数量、行动点数剩余比例，
        判定 win / partial / fail 三级结果。

        Returns:
            ChapterResult 字典。

        Raises:
            SessionModeError: 没有活跃的审讯引擎。
        """
        if not self.engine:
            raise SessionModeError("没有活跃的审讯引擎")

        suspect = self.engine.suspects[self.engine.current_suspect_index]
        total_ap = self.engine.total_action_points
        culprit_name = self.engine.case.get("culprit_name", "")
        is_culprit = suspect.name == culprit_name

        # 三级判定
        if is_culprit and (self.engine.state == "breakdown" or suspect.confession_level >= 4):
            result = "win"
        elif suspect.confession_level >= 2 or (
            self.engine.state == "verdict" and len(self.engine.presented_evidence_ids) > 0
        ):
            result = "partial"
        else:
            result = "fail"

        self._chapter_result = ChapterResult(
            result=result,
            confession_level=suspect.confession_level,
            evidence_count=len(self.engine.presented_evidence_ids),
            ap_remaining_pct=round(self.engine.action_points_remaining / max(total_ap, 1), 2),
            suspect_name=suspect.name,
            culprit_name=culprit_name,
            verdict_reason=f"供词层级{suspect.confession_level}，状态{self.engine.state}",
        )
        return self._chapter_result

    def complete_chapter(self, result: ChapterResult) -> Optional[str]:
        """完成章节，推进剧情。返回下一章 narrative 或 None（结局）。

        Args:
            result: 章节评估结果。

        Returns:
            下一章叙事文本，或 None 表示已到结局。
        """
        if self.mode != "story" or not self.story_engine:
            return None
        return self.story_engine.complete_chapter(result)

    def get_narrative(self, result: ChapterResult) -> str:
        """获取章节叙事文本。

        Args:
            result: 章节评估结果。

        Returns:
            叙事文本字符串，非剧情模式返回空字符串。
        """
        if self.mode != "story" or not self.story_engine:
            return ""
        return self.story_engine.get_narrative(result)

    def on_interrogation_ending(self, state_event: dict) -> None:
        """审讯结束时统一调度。

        根据当前模式执行不同的后续逻辑：
        - 剧情模式：推进章节
        - 自定义模式：直接结束

        Args:
            state_event: 状态变更事件字典。
        """
        result = self.evaluate_chapter()

        if self.mode == "story":
            # 剧情模式：推进章节
            narrative = self.complete_chapter(result)
            logger.info(f"章节完成: {result['result']}, 下一章: {narrative}")
        else:
            # 自定义模式：直接结束
            logger.info(f"审讯结束: {result['result']}")

    def get_progress(self) -> Optional[StoryProgress]:
        """获取剧情进度（仅剧情模式）。

        Returns:
            StoryProgress 字典，或 None（非剧情模式）。
        """
        if self.mode != "story" or not self.story_engine:
            return None
        return StoryProgress(
            story_id=self._story_id,
            current_chapter_id=self.story_engine.current_chapter_id,
            completed_chapters=self.story_engine.completed_chapters,
            story_variables=self.story_engine.story_variables,
            carried_evidence=self.story_engine.carried_evidence,
        )

    def to_dict(self) -> dict:
        """序列化会话状态。

        Returns:
            包含 mode、story_id 和引擎状态的字典。
        """
        return {
            "mode": self.mode,
            "story_id": self._story_id,
            "engine_state": self.engine.to_dict() if self.engine else None,
        }

    @classmethod
    def from_dict(cls, state: dict, player=None) -> "GameSession":
        """从字典恢复会话。

        Args:
            state: 序列化的会话状态字典。
            player: 玩家档案（可选）。

        Returns:
            恢复的 GameSession 实例。
        """
        from core.interrogation import InterrogationEngine

        session = cls()
        session.mode = state.get("mode")
        session._story_id = state.get("story_id")
        session.player = player

        engine_state = state.get("engine_state")
        if engine_state:
            # from_dict 需要 case_data，但 engine_state 中包含 case_id / case_title
            # 构造最小 case_data，具体数据应从 DB 加载
            case_data = {}
            if engine_state.get("case_id"):
                case_data["case_id"] = engine_state["case_id"]
            if engine_state.get("case_title"):
                case_data["title"] = engine_state["case_title"]
            # 尝试从 DB 加载完整 case_data
            try:
                from core import db

                full_case = db.load_case(case_data.get("case_id", ""))
                if full_case:
                    case_data = full_case
            except Exception as exc:
                logger.warning(f"从 DB 加载案件数据失败，使用最小数据: {exc}")

            session.engine = InterrogationEngine.from_dict(engine_state, case_data)

        return session
