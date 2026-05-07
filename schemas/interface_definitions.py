from typing import Dict, List, Optional, Protocol, TypedDict


class SuspectAgentProtocol(Protocol):
    name: str
    pressure: int
    memory: List[Dict[str, str]]
    confession_level: int
    confession_progress: float
    turn_count: int
    fear: int
    defiance: int
    empathy_susceptibility: int
    deception_skill: int
    loyalty: int
    credibility: int

    def respond(self, player_input: str, context: Optional[Dict] = None) -> Dict:
        """
        返回格式必须为：
        {
            "reply": str,
            "secret_triggered": Optional[str]
        }
        """
        ...

    def respond_evidence(self, evidence_description: str, evidence_type: str = "unknown") -> Dict:
        """
        对出示证据做出反应（不传入证据名）。

        返回格式必须为：
        {
            "reply": str,
            "secret_triggered": Optional[str]
        }
        """
        ...

    def update_confession_progress(self) -> float:
        """根据当前压力更新供词反馈进度。"""
        ...

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        """检查是否满足供词升级条件。"""
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
