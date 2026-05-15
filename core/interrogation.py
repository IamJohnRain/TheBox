import logging
from typing import Dict, List, Optional

from core.game_config import (
    ACTION_AP_COST,
    CHAT_TURNS_PER_SUSPECT,
    DEFAULT_EVIDENCE_USES,
    DEFAULT_INTERROGATION_TIME_LIMIT,
    DEFAULT_TOTAL_ACTION_POINTS,
    EMPATHY_USES_PER_SUSPECT,
    EVIDENCE_CHAIN_BONUS,
    PRESSURE_USES_PER_SUSPECT,
    REBUTTAL_DECAY_CONFIG,
)
from core.suspect_agent import SuspectAgent
from schemas.events import (
    NewMessageEvent,
    StateChangeEvent,
    SuspectUpdateEvent,
    TimerTickEvent,
    UIEvent,
)

logger = logging.getLogger("thebox")


class DummySuspectAgent:
    """A deterministic stand-in for SuspectAgent that returns fixed responses without LLM."""

    def __init__(self, suspect_data: dict, case_title: str = "") -> None:
        self.name: str = suspect_data["name"]
        self.pressure: int = 50
        self.memory: List[Dict[str, str]] = []
        self.confession_level: int = 0
        self.confession_progress: float = 0.0
        self.turn_count: int = 0
        self.fear: int = 50
        self.defiance: int = 50
        self.empathy_susceptibility: int = 50
        self.deception_skill: int = 50
        self.loyalty: int = 50
        self.credibility: int = 50

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Return a fixed response dict."""
        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": "我是无辜的"})
        return {
            "reply": "我是无辜的",
            "secret_triggered": None,
        }

    def respond_evidence(
        self, evidence_description: str, evidence_type: str = "unknown"
    ) -> dict:
        """Return a fixed response dict for evidence presentation."""
        self.memory.append({"role": "user", "content": f"[出示证据] {evidence_description}"})
        self.memory.append({"role": "assistant", "content": "我是无辜的"})
        return {
            "reply": "我是无辜的",
            "secret_triggered": None,
            "rebuttal": False,
            "rebuttal_believable": False,
        }

    def update_confession_progress(self) -> float:
        """No-op for dummy agent."""
        return self.confession_progress

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        """No-op for dummy agent."""
        return None


class InterrogationEngine:
    """Manage the multi-suspect interrogation flow."""

    def __init__(self, case_data: dict) -> None:
        self.case: dict = case_data
        self.suspects: List[SuspectAgent] = [
            SuspectAgent(s, case_data["title"]) for s in case_data["suspects"]
        ]
        self.current_suspect_index: int = 0
        self.presented_evidence_ids: set = set()
        self.time_left: int = case_data.get(
            "interrogation_time_limit_sec", DEFAULT_INTERROGATION_TIME_LIMIT
        )
        self.state: str = "selecting"

        # AP系统
        self.action_points_remaining: int = case_data.get(
            "total_action_points", DEFAULT_TOTAL_ACTION_POINTS
        )
        self.total_action_points: int = self.action_points_remaining

        # 证据使用次数
        self.evidence_uses_remaining: int = case_data.get(
            "evidence_uses", DEFAULT_EVIDENCE_USES
        )

        # 每个嫌疑人的交互使用次数
        num_suspects = len(self.suspects)
        self.chat_turns_remaining: List[int] = [CHAT_TURNS_PER_SUSPECT] * num_suspects
        self.pressure_uses_remaining: List[int] = [PRESSURE_USES_PER_SUSPECT] * num_suspects
        self.empathy_uses_remaining: List[int] = [EMPATHY_USES_PER_SUSPECT] * num_suspects

        # 错误操作记录
        self.mistake_log: List[dict] = []

        # 工具系统
        self.available_tools: Dict[str, int] = {}  # tool_name -> remaining_uses
        self.used_tools: List[str] = []

    def select_suspect(self, index: int) -> dict:
        """Switch to a suspect by index and return their info."""
        if index < 0 or index >= len(self.suspects):
            raise ValueError(f"Invalid suspect index: {index}")
        self.current_suspect_index = index
        suspect = self.suspects[index]
        if self.state == "selecting":
            self.state = "interrogating"
        return {"name": suspect.name, "pressure": suspect.pressure}

    def init_tools(self, player_level: int = 1):
        """根据玩家等级初始化可用工具。

        Args:
            player_level: 玩家当前等级，决定可用工具和次数。
        """
        from core.tools import TOOL_REGISTRY, get_tool

        config = self._get_level_unlocks()
        self.available_tools = {}
        for level_str, unlock in config.items():
            level = int(level_str)
            if level <= player_level:
                for tool_name in unlock.get("tools", []):
                    if tool_name in TOOL_REGISTRY:
                        tool = get_tool(tool_name)
                        max_uses = tool.max_uses
                        if player_level >= 20:
                            max_uses += 1
                        self.available_tools[tool_name] = max_uses

    def _get_level_unlocks(self) -> dict:
        """获取等级解锁配置，优先从 game_config 读取。"""
        from core.game_config import get_gameplay_config

        config = get_gameplay_config()
        progression = config.get("progression", {})
        return progression.get("level_unlocks", {})

    def _use_tool(self, tool_name: str, content: str) -> List[UIEvent]:
        """执行工具使用逻辑。

        Args:
            tool_name: 工具标识名。
            content: 附加内容（部分工具可能使用）。

        Returns:
            UIEvent 列表。
        """
        from core.tools import get_tool

        events: List[UIEvent] = []

        if tool_name not in self.available_tools:
            events.append(self._system_message("该工具不可用"))
            return events
        if self.available_tools[tool_name] <= 0:
            events.append(self._system_message("工具次数已耗尽"))
            return events

        tool = get_tool(tool_name)

        # 检查 AP
        if tool.cost_ap > 0:
            if self.action_points_remaining < tool.cost_ap:
                events.append(
                    self._system_message(
                        f"行动点数不足，{tool.display_name}需要{tool.cost_ap}AP"
                    )
                )
                return events
            self.action_points_remaining -= tool.cost_ap

        # 扣减次数
        self.available_tools[tool_name] -= 1
        self.used_tools.append(tool_name)

        # 执行工具
        suspect = self.suspects[self.current_suspect_index]
        try:
            tool_events = tool.execute(self, suspect, content)
            events.extend(tool_events)
        except Exception as exc:
            logger.error(f"工具 {tool_name} 执行失败: {exc}")
            events.append(self._system_message(f"工具执行失败: {exc}"))

        return events

    def _system_message(self, content: str) -> NewMessageEvent:
        """Create a system message event."""
        return {
            "type": "new_message",
            "role": "system",
            "content": content,
            "suspect_name": None,
        }

    def _check_victory(self, suspect, result: dict) -> Optional[StateChangeEvent]:
        """统一检查所有胜利条件。

        胜利条件优先级：
        1. 供词层级达到 4：完全崩溃（主要胜利条件）
        2. secret_triggered 且供词层级 >= 3：完美胜利（关键词触发）
        3. 时间耗尽：失败

        Returns:
            StateChangeEvent 或 None
        """
        # 条件1：供词层级 4 → 完全崩溃（主要胜利条件）
        if suspect.confession_level >= 4 and self.state != "breakdown":
            self.state = "breakdown"
            return StateChangeEvent(
                type="state_change",
                new_state="breakdown",
                verdict_reason=f"{suspect.name} 完全崩溃认罪",
            )

        # 条件2：secret_triggered + 高供词层级 → 完美胜利（彩蛋，不纳入平衡基准）
        if result.get("secret_triggered") and suspect.confession_level >= 3:
            self.state = "breakdown"
            return StateChangeEvent(
                type="state_change",
                new_state="breakdown",
                verdict_reason=f"{suspect.name} 泄露了秘密: {result['secret_triggered']}",
            )

        return None

    def _apply_dimension_per_turn_effects(self, suspect) -> List[UIEvent]:
        """每轮维度联动效果。"""
        from core.game_config import DIMENSION_BOUNDS

        changes = {}

        if suspect.pressure > 60:
            changes["defiance"] = changes.get("defiance", 0) - 1
        if suspect.pressure < 30:
            changes["defiance"] = changes.get("defiance", 0) + 1
        if suspect.pressure > 70:
            changes["deception_skill"] = changes.get("deception_skill", 0) - 2
        if suspect.fear > 70:
            changes["defiance"] = changes.get("defiance", 0) - 2
            changes["deception_skill"] = changes.get("deception_skill", 0) - 3
            changes["loyalty"] = changes.get("loyalty", 0) - 2
        if suspect.fear > 60:
            changes["empathy_susceptibility"] = changes.get("empathy_susceptibility", 0) + 1
        if suspect.fear < 15:
            changes["defiance"] = changes.get("defiance", 0) + 2
        if suspect.defiance > 70:
            changes["empathy_susceptibility"] = changes.get("empathy_susceptibility", 0) - 1

        # 应用变化（受边界约束）
        for dim, delta in changes.items():
            if delta == 0:
                continue
            old_val = getattr(suspect, dim)
            bounds = DIMENSION_BOUNDS.get(dim, {"min": 0, "max": 100})
            new_val = max(bounds["min"], min(bounds["max"], old_val + delta))
            setattr(suspect, dim, new_val)

        return []  # 维度变化事件可选发送

    def submit_action(
        self, action: str, content: str, evidence_id: Optional[str] = None
    ) -> List[UIEvent]:
        """Process a player action and return a list of UI events."""
        events: List[UIEvent] = []

        if self.state != "interrogating":
            return events

        # ── 工具分支（不走常规AP/轮次扣减逻辑） ──
        if action.startswith("tool_"):
            tool_name = action[5:]
            result = self._use_tool(tool_name, content)
            events.extend(result)
            return events

        suspect = self.suspects[self.current_suspect_index]

        # ── 检查聊天轮次 ──
        if self.chat_turns_remaining[self.current_suspect_index] <= 0:
            events.append(self._system_message(
                f"{suspect.name} 拒绝再和你说话了。"
            ))
            return events

        # ── 检查行动点数 ──
        ap_cost = ACTION_AP_COST.get(action, 1)
        if self.action_points_remaining < ap_cost:
            events.append(self._system_message(
                f"行动点数不足（需要{ap_cost}AP，剩余{self.action_points_remaining}AP）。"
            ))
            return events

        # ── 检查施压/共情次数 ──
        if action == "pressure":
            if self.pressure_uses_remaining[self.current_suspect_index] <= 0:
                events.append(self._system_message(
                    f"你已经对 {suspect.name} 施压过了。"
                ))
                return events
            self.pressure_uses_remaining[self.current_suspect_index] -= 1
        elif action == "empathy":
            if self.empathy_uses_remaining[self.current_suspect_index] <= 0:
                events.append(self._system_message(
                    f"你已经对 {suspect.name} 共情过了。"
                ))
                return events
            self.empathy_uses_remaining[self.current_suspect_index] -= 1

        # ── 检查证据次数 ──
        if action == "present_evidence":
            if self.evidence_uses_remaining <= 0:
                events.append(self._system_message("证据出示次数已耗尽。"))
                return events
            self.evidence_uses_remaining -= 1

        # ── 扣减行动点数 ──
        self.action_points_remaining -= ap_cost

        # ── 扣减聊天轮次 ──
        self.chat_turns_remaining[self.current_suspect_index] -= 1

        player_msg: NewMessageEvent = {
            "type": "new_message",
            "role": "player",
            "content": content,
            "suspect_name": None,
        }
        events.append(player_msg)

        old_pressure = suspect.pressure

        if action == "present_evidence":
            evidence = self._find_evidence(evidence_id)
            if evidence is None:
                system_msg: NewMessageEvent = {
                    "type": "new_message",
                    "role": "system",
                    "content": f"证据 {evidence_id} 不存在。",
                    "suspect_name": None,
                }
                events.append(system_msg)
                return events

            # 调用 respond_evidence（不传证据名，只传描述）
            evidence_desc = evidence.get("description", "")
            evidence_type = evidence.get("type", "unknown")
            result = suspect.respond_evidence(evidence_desc, evidence_type)

            # 压力增量由引擎程序化计算（取代硬编码 +20 和 LLM 返回的 pressure_change）
            from core.game_config import (
                EVIDENCE_PRESSURE_BASE,
                EVIDENCE_STRENGTH_MULTIPLIER,
                FEAR_NEUTRAL,
                PRESSURE_SOFT_FACTOR_MIN,
                PRESSURE_SOFT_FACTOR_MAX,
            )

            pressure_delta = 0
            if evidence.get("related_suspect") == suspect.name:
                # 正确证据：计算压力增量
                base = EVIDENCE_PRESSURE_BASE.get(evidence_type, 10)
                strength = evidence.get("strength", 5)

                # 检查证据链
                chain_bonus = 0
                for prev_id in self.presented_evidence_ids:
                    prev_evidence = self._find_evidence(prev_id)
                    if prev_evidence and evidence_id in prev_evidence.get("chain_with", []):
                        chain_bonus = EVIDENCE_CHAIN_BONUS
                        break

                # 压力增量 = 证据基础值 + 证据链奖励
                pressure_delta = int(base * (1 + strength * EVIDENCE_STRENGTH_MULTIPLIER)) + chain_bonus

                # 恐惧值和抗压性综合影响施压效果（带软上限，防止极端差距）
                fear = suspect.fear
                defiance = suspect.defiance
                fear_factor = fear / FEAR_NEUTRAL
                defiance_factor = 1.0 / (1.0 + defiance * 0.01)
                raw_factor = fear_factor * defiance_factor
                soft_factor = max(PRESSURE_SOFT_FACTOR_MIN, min(PRESSURE_SOFT_FACTOR_MAX, raw_factor))
                pressure_delta = int(pressure_delta * soft_factor)

                # ── 反驳机制处理 ──
                rebuttal = result.get("rebuttal", False)
                rebuttal_believable = result.get("rebuttal_believable", False)

                # 程序化兜底：高压时反驳可信度强制衰减
                if rebuttal and rebuttal_believable:
                    effective_hard_threshold = REBUTTAL_DECAY_CONFIG["pressure_threshold_hard"] + \
                        int((suspect.deception_skill - 50) * REBUTTAL_DECAY_CONFIG["deception_threshold_scale"])

                    if suspect.pressure > effective_hard_threshold:
                        rebuttal_believable = False

                if rebuttal:
                    if rebuttal_believable:
                        # 反驳成功：压力不增加
                        suspect.credibility = min(
                            100, suspect.credibility + REBUTTAL_DECAY_CONFIG["credibility_bonus_success"]
                        )
                        pressure_delta = 0
                    else:
                        # 反驳失败：压力正常增加
                        suspect.credibility = max(
                            0, suspect.credibility - REBUTTAL_DECAY_CONFIG["credibility_penalty_fail"]
                        )

                # 出示正确证据 → 恐惧上升
                from core.game_config import DIMENSION_BOUNDS
                suspect.fear = min(DIMENSION_BOUNDS["fear"]["max"], suspect.fear + 8)

                self.presented_evidence_ids.add(evidence_id)
            else:
                # 出示错误证据 → 恐惧下降 + 记录错误
                from core.game_config import DIMENSION_BOUNDS
                suspect.fear = max(DIMENSION_BOUNDS["fear"]["min"], suspect.fear - 10)

                self.mistake_log.append({
                    "type": "wrong_evidence",
                    "evidence_id": evidence_id,
                    "suspect_name": suspect.name,
                    "turn": suspect.turn_count,
                })

            suspect.pressure = max(0, min(100, suspect.pressure + pressure_delta))
            actual_pressure_change = suspect.pressure - old_pressure
        else:
            result = suspect.respond(content)
            if action == "pressure":
                suspect.pressure = max(0, min(100, suspect.pressure + 10))
            elif action == "empathy":
                suspect.pressure = max(0, min(100, suspect.pressure - 5))
            actual_pressure_change = suspect.pressure - old_pressure

        result["pressure_change"] = actual_pressure_change

        # ── 错误惩罚检查 ──
        mistake = self._check_mistake(action, suspect, result, evidence_id=evidence_id)
        if mistake:
            self.mistake_log.append(mistake)

        suspect_msg: NewMessageEvent = {
            "type": "new_message",
            "role": "suspect",
            "content": result["reply"],
            "suspect_name": suspect.name,
        }
        events.append(suspect_msg)

        update: SuspectUpdateEvent = {
            "type": "suspect_update",
            "suspect_index": self.current_suspect_index,
            "pressure": suspect.pressure,
            "secret_triggered": result.get("secret_triggered"),
        }
        events.append(update)

        # ── 供词进度更新 ──
        suspect.turn_count += 1
        has_evidence = any(
            self._find_evidence(eid).get("related_suspect") == suspect.name
            for eid in self.presented_evidence_ids
            if self._find_evidence(eid) is not None
        )
        suspect.update_confession_progress()
        suspect.check_confession_upgrade(has_evidence)

        # ── 每轮维度联动 ──
        self._apply_dimension_per_turn_effects(suspect)

        # ── 每轮压力/恐惧动态 ──
        self._apply_per_turn_dynamics(suspect)

        # ── 反扑检查 ──
        proactive_result = self._check_proactive(suspect)
        if proactive_result:
            proactive_msg: NewMessageEvent = {
                "type": "new_message",
                "role": "suspect",
                "content": proactive_result["content"],
                "suspect_name": suspect.name,
            }
            events.append(proactive_msg)
            # Apply proactive effects
            effects = proactive_result.get("effects", {})
            if "pressure" in effects:
                suspect.pressure = max(0, min(100, suspect.pressure + effects["pressure"]))
            if "defiance" in effects:
                suspect.defiance = max(5, min(100, suspect.defiance + effects["defiance"]))
            if "fear" in effects:
                suspect.fear = max(0, min(100, suspect.fear + effects["fear"]))

        # ── 统一胜利判定 ──
        victory_event = self._check_victory(suspect, result)
        if victory_event:
            events.append(victory_event)

        return events

    def tick(self, seconds_elapsed: int = 1) -> List[UIEvent]:
        """Decrease time_left and return timer events."""
        events: List[UIEvent] = []
        self.time_left = max(0, self.time_left - seconds_elapsed)

        timer_event: TimerTickEvent = {
            "type": "timer_tick",
            "time_left": self.time_left,
        }
        events.append(timer_event)

        if self.time_left <= 0 and self.state not in ("verdict", "breakdown"):
            self.state = "verdict"
            logger.info("状态变更: interrogating → verdict, 原因: 审讯时间耗尽")
            state_event: StateChangeEvent = {
                "type": "state_change",
                "new_state": "verdict",
                "verdict_reason": "审讯时间耗尽",
            }
            events.append(state_event)

        return events

    def to_dict(self) -> dict:
        """Serialize the engine state to a dictionary for persistence."""
        suspects_states = []
        for suspect in self.suspects:
            suspects_states.append(
                {
                    "name": suspect.name,
                    "pressure": suspect.pressure,
                    "memory": suspect.memory,
                    "confession_level": suspect.confession_level,
                    "confession_progress": suspect.confession_progress,
                    "turn_count": suspect.turn_count,
                    "fear": suspect.fear,
                    "defiance": suspect.defiance,
                    "empathy_susceptibility": suspect.empathy_susceptibility,
                    "deception_skill": suspect.deception_skill,
                    "loyalty": suspect.loyalty,
                    "credibility": suspect.credibility,
                }
            )
        return {
            "case_id": self.case.get("case_id", ""),
            "case_title": self.case.get("title", ""),
            "suspects_states": suspects_states,
            "presented_evidence_ids": list(self.presented_evidence_ids),
            "time_left": self.time_left,
            "current_suspect_index": self.current_suspect_index,
            "state": self.state,
            "action_points_remaining": self.action_points_remaining,
            "evidence_uses_remaining": self.evidence_uses_remaining,
            "chat_turns_remaining": self.chat_turns_remaining,
            "pressure_uses_remaining": self.pressure_uses_remaining,
            "empathy_uses_remaining": self.empathy_uses_remaining,
            "mistake_log": self.mistake_log,
            "available_tools": self.available_tools,
            "used_tools": self.used_tools,
        }

    @staticmethod
    def from_dict(state: dict, case_data: dict) -> "InterrogationEngine":
        """Rebuild an InterrogationEngine from a serialized state dict and case data."""
        # 在创建引擎前，确保 case_data 包含 case_id / title
        if "case_id" not in case_data and state.get("case_id"):
            case_data["case_id"] = state["case_id"]
        if "title" not in case_data and state.get("case_title"):
            case_data["title"] = state["case_title"]

        engine = InterrogationEngine(case_data)
        suspects_states = state.get("suspects_states", [])
        for i, suspect_state in enumerate(suspects_states):
            if i < len(engine.suspects):
                engine.suspects[i].pressure = suspect_state.get("pressure", 50)
                engine.suspects[i].memory = suspect_state.get("memory", [])
                engine.suspects[i].confession_level = suspect_state.get("confession_level", 0)
                engine.suspects[i].confession_progress = suspect_state.get("confession_progress", 0.0)
                engine.suspects[i].turn_count = suspect_state.get("turn_count", 0)
                engine.suspects[i].fear = suspect_state.get("fear", 50)
                engine.suspects[i].defiance = suspect_state.get("defiance", 50)
                engine.suspects[i].empathy_susceptibility = suspect_state.get("empathy_susceptibility", 50)
                engine.suspects[i].deception_skill = suspect_state.get("deception_skill", 50)
                engine.suspects[i].loyalty = suspect_state.get("loyalty", 50)
                engine.suspects[i].credibility = suspect_state.get("credibility", 50)
        engine.presented_evidence_ids = set(state.get("presented_evidence_ids", []))
        engine.time_left = state.get("time_left", engine.time_left)
        engine.current_suspect_index = state.get("current_suspect_index", 0)
        engine.state = state.get("state", "selecting")
        engine.action_points_remaining = state.get("action_points_remaining", DEFAULT_TOTAL_ACTION_POINTS)
        engine.evidence_uses_remaining = state.get("evidence_uses_remaining", DEFAULT_EVIDENCE_USES)
        engine.chat_turns_remaining = state.get(
            "chat_turns_remaining", [CHAT_TURNS_PER_SUSPECT] * len(engine.suspects)
        )
        engine.pressure_uses_remaining = state.get(
            "pressure_uses_remaining", [PRESSURE_USES_PER_SUSPECT] * len(engine.suspects)
        )
        engine.empathy_uses_remaining = state.get(
            "empathy_uses_remaining", [EMPATHY_USES_PER_SUSPECT] * len(engine.suspects)
        )
        engine.mistake_log = state.get("mistake_log", [])
        engine.available_tools = state.get("available_tools", {})
        engine.used_tools = state.get("used_tools", [])
        return engine

    def _apply_per_turn_dynamics(self, suspect) -> List[UIEvent]:
        """每次操作后结算压力/恐惧的自然动态变化。"""
        from core.game_config import PRESSURE_PER_TURN_DYNAMICS, FEAR_PER_TURN_DECAY, DIMENSION_BOUNDS
        events = []
        dynamics = PRESSURE_PER_TURN_DYNAMICS

        # 压力每轮动态
        if suspect.pressure < dynamics["decay_zone"][1]:
            suspect.pressure = max(dynamics["pressure_floor"], suspect.pressure + dynamics["decay_rate"])
        elif suspect.pressure >= dynamics["growth_zone"][0]:
            suspect.pressure = min(100, suspect.pressure + dynamics["growth_rate"])

        # 恐惧每轮自然冷却
        suspect.fear = max(DIMENSION_BOUNDS["fear"]["min"], suspect.fear + FEAR_PER_TURN_DECAY)

        return events

    def _check_mistake(self, action: str, suspect, result: dict, evidence_id: Optional[str] = None) -> Optional[dict]:
        """检查操作是否为错误操作，返回错误记录或 None。

        注意：present_evidence 的 wrong_evidence 记录已在证据分支中完成，
        此方法只负责 AP 惩罚和额外的恐惧/恐惧变化。
        """
        from core.game_config import AP_PENALTY
        is_culprit = suspect.name == self.case.get("culprit_name")

        if action == "present_evidence":
            evidence = self._find_evidence(evidence_id)
            if evidence and evidence.get("related_suspect") != suspect.name:
                self.action_points_remaining = max(0, self.action_points_remaining - AP_PENALTY["wrong_evidence"])
                # mistake_log 已在证据分支中记录，此处不再重复
                return None

        elif action == "pressure":
            if not is_culprit:
                suspect.fear = max(0, suspect.fear - 5)
                self.action_points_remaining = max(0, self.action_points_remaining - AP_PENALTY["wrong_pressure"])
                return {"type": "wrong_pressure", "suspect_name": suspect.name}

        elif action == "empathy":
            if is_culprit:
                suspect.fear = min(100, suspect.fear + 5)
                self.action_points_remaining = max(0, self.action_points_remaining - AP_PENALTY["wrong_empathy"])
                return {"type": "wrong_empathy", "suspect_name": suspect.name}

        # 无辜崩溃检查
        if suspect.confession_level >= 4 and not is_culprit:
            self.action_points_remaining = max(0, self.action_points_remaining - AP_PENALTY["innocent_breakdown"])
            return {"type": "innocent_breakdown", "suspect_name": suspect.name}

        return None

    def _check_proactive(self, suspect) -> Optional[dict]:
        """检查反扑条件。"""
        from core.game_config import FEAR_PROVOCATION_THRESHOLD

        # 冷却检查
        last_proactive_turn = getattr(suspect, '_last_proactive_turn', -999)
        if suspect.turn_count - last_proactive_turn < 3:
            return None

        triggered = None

        # 优先级1：挑衅态度（fear < 15）
        if suspect.fear < FEAR_PROVOCATION_THRESHOLD:
            triggered = {
                "type": "proactive",
                "proactive_type": "provocation",
                "content": f"{suspect.name} 冷笑一声：'你就这点本事？'",
                "effects": {"pressure": -2, "defiance": +2},
            }
        # 优先级2：恢复镇定（连续3轮无有效施压）
        elif getattr(self, '_consecutive_idle_turns', 0) >= 3:
            triggered = {
                "type": "proactive",
                "proactive_type": "recover",
                "content": f"{suspect.name} 深呼吸，似乎恢复了镇定。",
                "effects": {"defiance": +3, "fear": -5},
            }

        if triggered:
            suspect._last_proactive_turn = suspect.turn_count

        return triggered

    def get_evidence(self, evidence_id: str) -> Optional[dict]:
        """获取证据信息（公共 API）。

        Args:
            evidence_id: 证据 ID。

        Returns:
            证据字典，若未找到返回 None。
        """
        for e in self.case.get("evidences", []):
            if e.get("id") == evidence_id:
                return e
        return None

    def _find_evidence(self, evidence_id: Optional[str]) -> Optional[dict]:
        """Find an evidence by ID in the case data."""
        if evidence_id is None:
            return None
        for e in self.case.get("evidences", []):
            if e["id"] == evidence_id:
                return e
        return None
