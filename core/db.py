import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.exceptions import DatabaseError

logger = logging.getLogger("thebox")

DEFAULT_DB_PATH = "thebox.db"

MAX_SLOTS = 5

DB_VERSION = 2


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize database with migration support.

    Creates the db_version table and runs incremental migrations
    from the current schema version to DB_VERSION.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 版本号表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS db_version (
                version INTEGER PRIMARY KEY
            )
        """
        )

        # 获取当前版本
        cursor.execute("SELECT version FROM db_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0

        # 增量迁移
        if current_version < 1:
            _migrate_v0_to_v1(cursor)
        if current_version < 2:
            _migrate_v1_to_v2(cursor)

        # 更新版本号
        cursor.execute("DELETE FROM db_version")
        cursor.execute("INSERT INTO db_version (version) VALUES (?)", (DB_VERSION,))

        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成 (v{current_version} -> v{DB_VERSION}): {db_path}")
    except sqlite3.Error as e:
        logger.error(f"数据库初始化失败: {e}")
        raise DatabaseError(f"数据库初始化失败: {e}") from e


def _migrate_v0_to_v1(cursor):
    """初始表结构 - cases 和 sessions。"""
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
            saved_at TIMESTAMP,
            slot_number INTEGER
        )
    """
    )
    # 兼容旧库：如果 sessions 表缺少 slot_number 列则添加
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN slot_number INTEGER")
    except sqlite3.OperationalError:
        pass


def _migrate_v1_to_v2(cursor):
    """Phase 3b 新增 player_profile 表。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS player_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            successful_sessions INTEGER DEFAULT 0,
            best_grade TEXT DEFAULT 'D',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )


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


def save_session_to_slot(
    slot_number: int, case_id: str, engine_state_dict: dict, db_path: str = DEFAULT_DB_PATH
) -> None:
    """Save session to a specific slot (1-MAX_SLOTS). Uses INSERT OR REPLACE on slot_number."""
    if not (1 <= slot_number <= MAX_SLOTS):
        raise DatabaseError(f"无效槽位: {slot_number}，有效范围 1-{MAX_SLOTS}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "SELECT session_id FROM sessions WHERE slot_number = ?",
            (slot_number,),
        )
        existing = cursor.fetchone()
        if existing:
            session_id = existing[0]
            cursor.execute(
                "UPDATE sessions SET case_id = ?, current_state_json = ?, saved_at = ? WHERE session_id = ?",
                (
                    case_id,
                    json.dumps(engine_state_dict, ensure_ascii=False),
                    now,
                    session_id,
                ),
            )
        else:
            import uuid
            session_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO sessions "
                "(session_id, case_id, current_state_json, saved_at, slot_number) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    case_id,
                    json.dumps(engine_state_dict, ensure_ascii=False),
                    now,
                    slot_number,
                ),
            )
        conn.commit()
        conn.close()
        logger.info(f"存档已保存到槽位 {slot_number}: session_id={session_id}")
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"保存存档到槽位失败: {e}")
        raise DatabaseError(f"保存存档到槽位失败: {e}") from e


def delete_session_by_slot(
    slot_number: int, db_path: str = DEFAULT_DB_PATH
) -> None:
    """Delete a session by slot number."""
    if not (1 <= slot_number <= MAX_SLOTS):
        raise DatabaseError(f"无效槽位: {slot_number}，有效范围 1-{MAX_SLOTS}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM sessions WHERE slot_number = ?",
            (slot_number,),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        if deleted:
            logger.info(f"槽位 {slot_number} 存档已删除")
        else:
            logger.info(f"槽位 {slot_number} 无存档，跳过删除")
    except sqlite3.Error as e:
        logger.error(f"删除存档失败: {e}")
        raise DatabaseError(f"删除存档失败: {e}") from e


def list_all_slots(db_path: str = DEFAULT_DB_PATH) -> list:
    """Return a list of MAX_SLOTS slot dicts, each with slot_number, session_id, case_id, saved_at, and empty flag."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, case_id, saved_at, slot_number "
            "FROM sessions WHERE slot_number IS NOT NULL "
            "ORDER BY slot_number"
        )
        rows = cursor.fetchall()
        conn.close()
        occupied = {}
        for row in rows:
            sn = row[3]
            if 1 <= sn <= MAX_SLOTS:
                occupied[sn] = {
                    "slot_number": sn,
                    "session_id": row[0],
                    "case_id": row[1],
                    "saved_at": row[2],
                    "empty": False,
                }
        result = []
        for i in range(1, MAX_SLOTS + 1):
            if i in occupied:
                result.append(occupied[i])
            else:
                result.append({
                    "slot_number": i,
                    "session_id": None,
                    "case_id": None,
                    "saved_at": None,
                    "empty": True,
                })
        return result
    except sqlite3.Error as e:
        logger.error(f"获取存档槽位列表失败: {e}")
        raise DatabaseError(f"获取存档槽位列表失败: {e}") from e


def find_first_empty_slot(db_path: str = DEFAULT_DB_PATH) -> Optional[int]:
    """Return the first empty slot number (1-based), or None if all occupied."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT slot_number FROM sessions WHERE slot_number IS NOT NULL"
        )
        occupied = {row[0] for row in cursor.fetchall()}
        conn.close()
        for i in range(1, MAX_SLOTS + 1):
            if i not in occupied:
                return i
        return None
    except sqlite3.Error as e:
        logger.error(f"查找空槽位失败: {e}")
        raise DatabaseError(f"查找空槽位失败: {e}") from e


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
