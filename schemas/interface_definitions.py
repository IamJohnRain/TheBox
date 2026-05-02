from typing import Dict, List, Optional, Protocol, TypedDict


class SuspectAgentProtocol(Protocol):
    name: str
    pressure: int
    memory: List[Dict[str, str]]

    def respond(self, player_input: str, context: Optional[Dict] = None) -> Dict:
        """
        返回格式必须为：
        {
            "reply": str,
            "pressure_change": int,
            "secret_triggered": Optional[str]
        }
        """
        ...


class SuspectData(TypedDict):
    name: str
    role: str
    personality: str
    knowledge: str
    forbidden_to_reveal: List[str]


class EvidenceData(TypedDict):
    id: str
    name: str
    description: str
    related_suspect: Optional[str]


class CaseDict(TypedDict):
    case_id: str
    title: str
    victim: str
    cause_of_death: str
    crime_scene: str
    truth: str
    suspects: List[SuspectData]
    evidences: List[EvidenceData]
    interrogation_time_limit_sec: int


class EngineStateDict(TypedDict):
    current_suspect_index: int
    presented_evidence_ids: List[str]
    time_left: int
    state: str
    suspects_states: List[Dict]
