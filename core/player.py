"""Player profile and level system - Phase 3b."""

import logging

logger = logging.getLogger("thebox")


class PlayerProfile:
    """玩家档案，管理等级和经验。"""

    def __init__(self, db_connection=None):
        self.level: int = 1
        self.experience: int = 0
        self.total_sessions: int = 0
        self.successful_sessions: int = 0
        self.best_grade: str = "D"
        self._conn = db_connection
        if db_connection:
            self._load()

    def _load(self):
        """从数据库加载玩家档案。"""
        try:
            row = self._conn.execute("SELECT * FROM player_profile WHERE id = 1").fetchone()
            if row:
                self.level = row["level"]
                self.experience = row["experience"]
                self.total_sessions = row["total_sessions"]
                self.successful_sessions = row["successful_sessions"]
                self.best_grade = row["best_grade"]
        except Exception as e:
            logger.warning(f"Failed to load player profile: {e}")

    def save(self):
        """保存玩家档案到数据库。"""
        if not self._conn:
            return
        self._conn.execute(
            """
            INSERT OR REPLACE INTO player_profile
            (id, level, experience, total_sessions, successful_sessions, best_grade, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (self.level, self.experience, self.total_sessions, self.successful_sessions, self.best_grade),
        )
        self._conn.commit()

    def add_experience(self, amount: int) -> bool:
        """添加经验并检查升级。返回是否升级。

        Args:
            amount: 获得的经验值

        Returns:
            是否触发了升级
        """
        from core.game_config import EXPERIENCE_CURVE

        self.experience += amount
        leveled_up = False
        while self.level < len(EXPERIENCE_CURVE) - 1:
            next_threshold = EXPERIENCE_CURVE[self.level]
            if self.experience >= next_threshold:
                self.level += 1
                leveled_up = True
                logger.info(f"玩家升级到 {self.level} 级！")
            else:
                break
        self.save()
        return leveled_up

    def get_evidence_uses(self) -> int:
        """获取当前等级的证据使用次数。"""
        from core.game_config import LEVEL_UNLOCKS, DEFAULT_EVIDENCE_USES

        return LEVEL_UNLOCKS.get(self.level, {}).get("evidence_uses", DEFAULT_EVIDENCE_USES)

    def get_total_action_points(self, base_ap: int) -> int:
        """根据等级奖励计算本局总 AP。

        Args:
            base_ap: 基础行动点数

        Returns:
            含等级奖励的总行动点数
        """
        from core.game_config import LEVEL_UNLOCKS

        bonus = 0
        for level, unlock in LEVEL_UNLOCKS.items():
            if level <= self.level:
                bonus += unlock.get("ap_bonus", 0)
        return base_ap + bonus

    def get_available_tools(self) -> list:
        """获取当前等级可用的工具列表。"""
        from core.game_config import LEVEL_UNLOCKS

        tools = []
        for level, unlock in LEVEL_UNLOCKS.items():
            if level <= self.level:
                tools.extend(unlock.get("tools", []))
        return tools
