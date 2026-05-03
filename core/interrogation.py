import logging
from typing import Dict, List, Optional

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

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Return a fixed response dict."""
        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": "我是无辜的"})
        return {
            "reply": "我是无辜的",
            "pressure_change": 0,
            "secret_triggered": None,
        }


class InterrogationEngine:
    """Manage the multi-suspect interrogation flow."""

    def __init__(self, case_data: dict) -> None:
        self.case: dict = case_data
        self.suspects: List[SuspectAgent] = [
            SuspectAgent(s, case_data["title"]) for s in case_data["suspects"]
        ]
        self.current_suspect_index: int = 0
        self.presented_evidence_ids: set = set()
        self.time_left: int = case_data["interrogation_time_limit_sec"]
        self.state: str = "selecting"

    def select_suspect(self, index: int) -> dict:
        """Switch to a suspect by index and return their info."""
        if index < 0 or index >= len(self.suspects):
            raise ValueError(f"Invalid suspect index: {index}")
        self.current_suspect_index = index
        suspect = self.suspects[index]
        if self.state == "selecting":
            self.state = "interrogating"
        return {"name": suspect.name, "pressure": suspect.pressure}

    def submit_action(
        self, action: str, content: str, evidence_id: Optional[str] = None
    ) -> List[UIEvent]:
        """Process a player action and return a list of UI events."""
        events: List[UIEvent] = []

        if self.state != "interrogating":
            return events

        player_msg: NewMessageEvent = {
            "type": "new_message",
            "role": "player",
            "content": content,
            "suspect_name": None,
        }
        events.append(player_msg)

        suspect = self.suspects[self.current_suspect_index]
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
            result = suspect.respond(content)
            if evidence.get("related_suspect") == suspect.name:
                suspect.pressure = max(0, min(100, suspect.pressure + 20))
                self.presented_evidence_ids.add(evidence_id)
        else:
            result = suspect.respond(content)
            if action == "pressure":
                suspect.pressure = max(0, min(100, suspect.pressure + 10))
            elif action == "empathy":
                suspect.pressure = max(0, min(100, suspect.pressure - 5))

        result["pressure_change"] = suspect.pressure - old_pressure

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

        if result.get("secret_triggered"):
            self.state = "breakdown"
            logger.info(
                f"状态变更: interrogating → breakdown, 原因: {suspect.name} 泄露秘密: {result['secret_triggered']}"
            )
            state_event: StateChangeEvent = {
                "type": "state_change",
                "new_state": "breakdown",
                "verdict_reason": f"{suspect.name} 泄露了秘密: {result['secret_triggered']}",
            }
            events.append(state_event)

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
        engine.presented_evidence_ids = set(state.get("presented_evidence_ids", []))
        engine.time_left = state.get("time_left", engine.time_left)
        engine.current_suspect_index = state.get("current_suspect_index", 0)
        engine.state = state.get("state", "selecting")
        return engine

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
