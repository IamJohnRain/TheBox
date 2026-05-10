"""Story script loader and validator."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from core.exceptions import TheBoxError

logger = logging.getLogger("thebox")

STORIES_DIR = Path(__file__).parent.parent / "stories"


class StoryLoadError(TheBoxError):
    """故事加载错误。"""

    pass


# 章节基本 Schema 校验
REQUIRED_CHAPTER_FIELDS = ["chapter_id", "seq", "title", "type", "narrative", "branch"]
REQUIRED_STORY_FIELDS = ["story_id", "title", "chapters", "endings"]


def load_story(story_id: str) -> dict:
    """加载剧情脚本。

    Args:
        story_id: 剧情ID，对应 stories/{story_id}.json

    Returns:
        校验后的剧情数据

    Raises:
        StoryLoadError: 加载或校验失败
    """
    story_path = STORIES_DIR / f"{story_id}.json"

    if not story_path.exists():
        raise StoryLoadError(f"剧情脚本不存在: {story_path}")

    try:
        with open(story_path, "r", encoding="utf-8") as f:
            story_data = json.load(f)
    except json.JSONDecodeError as e:
        raise StoryLoadError(f"JSON 解析失败: {e}")

    # 校验
    validate_story(story_data)

    logger.info(f"加载剧情: {story_data['title']}, {len(story_data['chapters'])} 章节")
    return story_data


def validate_story(story_data: dict) -> None:
    """校验剧情脚本结构。

    Raises:
        StoryLoadError: 校验失败
    """
    # 检查顶层字段
    for field in REQUIRED_STORY_FIELDS:
        if field not in story_data:
            raise StoryLoadError(f"缺少必需字段: {field}")

    chapters = story_data["chapters"]
    endings = story_data["endings"]
    chapter_ids = {ch["chapter_id"] for ch in chapters}
    ending_ids = {e["id"] for e in endings}

    # 校验每个章节
    for chapter in chapters:
        _validate_chapter(chapter, chapter_ids, ending_ids)

    # 校验结局
    for ending in endings:
        if "id" not in ending or "title" not in ending:
            raise StoryLoadError(f"结局缺少必需字段: {ending}")


def _validate_chapter(chapter: dict, chapter_ids: set, ending_ids: set) -> None:
    """校验单个章节。"""
    # 检查必需字段
    for field in REQUIRED_CHAPTER_FIELDS:
        if field not in chapter:
            raise StoryLoadError(f"章节 {chapter.get('chapter_id', '?')} 缺少字段: {field}")

    # 校验类型
    if chapter["type"] not in ("scripted", "generated"):
        raise StoryLoadError(f"未知章节类型: {chapter['type']}")

    # scripted 类型必须有 case_data
    if chapter["type"] == "scripted" and "case_data" not in chapter:
        raise StoryLoadError(f"scripted 章节 {chapter['chapter_id']} 缺少 case_data")

    # 校验分支条件
    branch = chapter["branch"]
    if "conditions" not in branch:
        raise StoryLoadError(f"章节 {chapter['chapter_id']} 分支缺少 conditions")

    for condition in branch["conditions"]:
        if "next" not in condition:
            raise StoryLoadError("分支条件缺少 next 字段")
        # next 必须指向有效章节或结局
        next_id = condition["next"]
        if next_id not in chapter_ids and next_id not in ending_ids:
            logger.warning(f"分支目标 {next_id} 未在章节或结局中找到")

    # 校验 merge_to
    if "merge_to" in chapter and chapter["merge_to"]:
        if chapter["merge_to"] not in chapter_ids:
            raise StoryLoadError(f"merge_to 目标不存在: {chapter['merge_to']}")


def list_available_stories() -> List[Dict[str, Any]]:
    """列出所有可用的剧情。"""
    stories = []

    if not STORIES_DIR.exists():
        return stories

    for story_file in STORIES_DIR.glob("*.json"):
        try:
            with open(story_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            stories.append(
                {
                    "story_id": data.get("story_id", story_file.stem),
                    "title": data.get("title", "未知"),
                    "desc": data.get("desc", ""),
                    "chapter_count": len(data.get("chapters", [])),
                }
            )
        except Exception as e:
            logger.warning(f"无法读取 {story_file}: {e}")

    return stories
