"""Story mode data structures."""

from typing import Any, Dict, List, Literal, TypedDict


class ChapterResult(TypedDict):
    """章节完成后的审讯结果评估。"""

    result: Literal["win", "partial", "fail"]
    confession_level: int
    evidence_count: int
    ap_remaining_pct: float
    suspect_name: str
    culprit_name: str
    verdict_reason: str


class StoryProgress(TypedDict):
    """剧情进度状态。"""

    story_id: str
    current_chapter_id: str
    completed_chapters: List[str]
    story_variables: Dict[str, Any]
    carried_evidence: List[Dict[str, Any]]
