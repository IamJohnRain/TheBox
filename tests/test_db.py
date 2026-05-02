import sqlite3

import pytest

from core.db import init_db, load_case, load_session, save_case, save_session


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def test_init_db_creates_tables(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "cases" in tables
    assert "sessions" in tables


def test_save_and_load_case(temp_db):
    case = {
        "case_id": "test_001",
        "title": "测试案件",
        "victim": "张三",
    }
    save_case(case, temp_db)
    loaded = load_case("test_001", temp_db)
    assert loaded is not None
    assert loaded["case_id"] == "test_001"
    assert loaded["title"] == "测试案件"


def test_load_nonexistent_case(temp_db):
    result = load_case("nonexistent", temp_db)
    assert result is None


def test_save_and_load_session(temp_db):
    state = {"current_suspect_index": 1, "time_left": 300}
    save_session("sess_001", "test_001", state, temp_db)
    result = load_session("sess_001", temp_db)
    assert result is not None
    case_id, loaded_state = result
    assert case_id == "test_001"
    assert loaded_state["current_suspect_index"] == 1


def test_load_nonexistent_session(temp_db):
    result = load_session("nonexistent", temp_db)
    assert result is None
