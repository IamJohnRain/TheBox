from typing import Literal, Optional, Union

from typing_extensions import TypedDict


class NewMessageEvent(TypedDict):
    type: Literal["new_message"]
    role: Literal["player", "suspect", "system"]
    content: str
    suspect_name: Optional[str]


class SuspectUpdateEvent(TypedDict):
    type: Literal["suspect_update"]
    suspect_index: int
    pressure: int
    secret_triggered: Optional[str]


class StateChangeEvent(TypedDict):
    type: Literal["state_change"]
    new_state: str
    verdict_reason: Optional[str]


class TimerTickEvent(TypedDict):
    type: Literal["timer_tick"]
    time_left: int


UIEvent = Union[NewMessageEvent, SuspectUpdateEvent, StateChangeEvent, TimerTickEvent]
