import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.exceptions import DatabaseError

logger = logging.getLogger("thebox")

DEFAULT_DB_PATH = "thebox.db"


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                title TEXT,
                json_data TEXT,
                created_at TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                case_id TEXT,
                current_state_json TEXT,
                saved_at TIMESTAMP
            )
        """
        )
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {db_path}")
    except sqlite3.Error as e:
        logger.error(f"数据库初始化失败: {e}")
        raise DatabaseError(f"数据库初始化失败: {e}") from e


def save_case(case_dict: Dict, db_path: str = DEFAULT_DB_PATH) -> None:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO cases (case_id, title, json_data, created_at) VALUES (?, ?, ?, ?)",
            (
                case_dict["case_id"],
                case_dict.get("title", ""),
                json.dumps(case_dict, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"案件已保存: {case_dict['case_id']}")
    except (sqlite3.Error, KeyError, json.JSONEncodeError) as e:
        logger.error(f"保存案件失败: {e}")
        raise DatabaseError(f"保存案件失败: {e}") from e


def load_case(case_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT json_data FROM cases WHERE case_id = ?", (case_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return json.loads(row[0])
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"加载案件失败: {e}")
        raise DatabaseError(f"加载案件失败: {e}") from e


def save_session(
    session_id: str, case_id: str, state_dict: Dict, db_path: str = DEFAULT_DB_PATH
) -> None:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sessions (session_id, case_id, current_state_json, saved_at) VALUES (?, ?, ?, ?)",
            (
                session_id,
                case_id,
                json.dumps(state_dict, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"存档已保存: {session_id}")
    except (sqlite3.Error, json.JSONEncodeError) as e:
        logger.error(f"保存存档失败: {e}")
        raise DatabaseError(f"保存存档失败: {e}") from e


def load_session(
    session_id: str, db_path: str = DEFAULT_DB_PATH
) -> Optional[Tuple[str, Dict]]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT case_id, current_state_json FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return row[0], json.loads(row[1])
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"加载存档失败: {e}")
        raise DatabaseError(f"加载存档失败: {e}") from e


def save_full_session(
    session_id: str, case_id: str, engine_state_dict: dict, db_path: str = DEFAULT_DB_PATH
) -> None:
    """Save a full interrogation session including engine state to the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sessions (session_id, case_id, current_state_json, saved_at) VALUES (?, ?, ?, ?)",
            (
                session_id,
                case_id,
                json.dumps(engine_state_dict, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"完整存档已保存: {session_id}")
    except (sqlite3.Error, json.JSONEncodeError) as e:
        logger.error(f"保存完整存档失败: {e}")
        raise DatabaseError(f"保存完整存档失败: {e}") from e


def load_full_session(
    session_id: str, db_path: str = DEFAULT_DB_PATH
) -> Optional[Tuple[str, dict]]:
    """Load a full session from the database and return (case_id, engine_state_dict) or None."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT case_id, current_state_json FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return row[0], json.loads(row[1])
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"加载完整存档失败: {e}")
        raise DatabaseError(f"加载完整存档失败: {e}") from e


def list_sessions(db_path: str = DEFAULT_DB_PATH) -> list:
    """Return a list of all saved sessions as dicts with session_id, case_id, and saved_at."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, case_id, saved_at FROM sessions ORDER BY saved_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"session_id": row[0], "case_id": row[1], "saved_at": row[2]}
            for row in rows
        ]
    except sqlite3.Error as e:
        logger.error(f"获取存档列表失败: {e}")
        raise DatabaseError(f"获取存档列表失败: {e}") from e
