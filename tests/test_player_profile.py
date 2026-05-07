"""Tests for player profile system - Phase 3b."""

import sqlite3

import pytest

from core.db import init_db


@pytest.fixture
def player_db(tmp_path):
    """Create a temp database with player_profile table for testing."""
    db_path = str(tmp_path / "player_test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def player_conn(player_db):
    """Return a sqlite3 connection with row_factory for player tests."""
    conn = sqlite3.connect(player_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestPlayerProfile:
    """Test PlayerProfile class."""

    def test_initial_level_is_1(self):
        """Initial level should be 1."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        assert profile.level == 1

    def test_initial_experience_is_0(self):
        """Initial experience should be 0."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        assert profile.experience == 0

    def test_add_experience(self):
        """Adding experience should update total."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.add_experience(30)
        assert profile.experience == 30

    def test_level_up(self):
        """Experience threshold should trigger level up."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        # Level 1 -> 2 requires 50 exp
        leveled = profile.add_experience(50)
        assert leveled is True
        assert profile.level == 2

    def test_no_level_up_below_threshold(self):
        """Experience below threshold should not trigger level up."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        leveled = profile.add_experience(30)
        assert leveled is False
        assert profile.level == 1

    def test_multiple_level_ups(self):
        """Multiple thresholds should trigger multiple level ups."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        # Level 1 -> 3 requires 110 exp (thresholds: 50 for lvl2, 110 for lvl3)
        profile.add_experience(110)
        assert profile.level == 3

    def test_save_and_load(self, player_conn):
        """Profile should persist across save/load cycles."""
        from core.player import PlayerProfile

        profile = PlayerProfile(player_conn)
        profile.level = 5
        profile.experience = 200
        profile.total_sessions = 10
        profile.successful_sessions = 7
        profile.best_grade = "A"
        profile.save()

        # Load fresh profile from same DB
        profile2 = PlayerProfile(player_conn)
        assert profile2.level == 5
        assert profile2.experience == 200
        assert profile2.total_sessions == 10
        assert profile2.successful_sessions == 7
        assert profile2.best_grade == "A"

    def test_save_without_db(self):
        """save() should be a no-op when no DB connection is provided."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 3
        profile.save()  # Should not raise


class TestLevelUnlocks:
    """Test level unlock system."""

    def test_level_2_unlocks_basic_profile(self):
        """Level 2 should unlock basic psych profile."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 2
        tools = profile.get_available_tools()

        assert "psych_profile_basic" in tools

    def test_level_10_unlocks_advanced(self):
        """Level 10 should unlock advanced tools."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 10
        tools = profile.get_available_tools()

        assert "psych_profile_advanced" in tools
        assert "silent_pressure" in tools

    def test_level_1_no_extra_tools(self):
        """Level 1 should have no extra tools."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 1
        tools = profile.get_available_tools()

        assert tools == []

    def test_evidence_uses_increase(self):
        """Higher level should get more evidence uses."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 1
        assert profile.get_evidence_uses() == 4

        profile.level = 5
        assert profile.get_evidence_uses() == 5

        profile.level = 10
        assert profile.get_evidence_uses() == 6

    def test_evidence_uses_fallback_for_unknown_level(self):
        """Unknown levels should fall back to DEFAULT_EVIDENCE_USES."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 3  # No explicit entry for level 3
        assert profile.get_evidence_uses() == 4  # DEFAULT_EVIDENCE_USES

    def test_ap_bonus(self):
        """Higher level should get AP bonus."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 1
        assert profile.get_total_action_points(22) == 22

        profile.level = 11
        assert profile.get_total_action_points(22) == 24  # +2 bonus from level 11

    def test_ap_bonus_stacks(self):
        """AP bonuses from multiple levels should stack."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 16
        # Level 11 gives +2, Level 16 gives +2 = total +4
        assert profile.get_total_action_points(22) == 26

    def test_level_15_unlocks_master(self):
        """Level 15 should unlock master psych profile."""
        from core.player import PlayerProfile

        profile = PlayerProfile()
        profile.level = 15
        tools = profile.get_available_tools()

        assert "psych_profile_master" in tools


class TestDatabaseMigration:
    """Test database migration for Phase 3b."""

    def test_init_db_creates_player_profile_table(self, player_db):
        """init_db should create player_profile table."""
        conn = sqlite3.connect(player_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_profile'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_init_db_creates_db_version_table(self, player_db):
        """init_db should create db_version table."""
        conn = sqlite3.connect(player_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='db_version'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_db_version_is_current(self, player_db):
        """db_version should reflect current DB_VERSION."""
        from core.db import DB_VERSION

        conn = sqlite3.connect(player_db)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM db_version LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == DB_VERSION

    def test_migration_from_v0(self, tmp_path):
        """Fresh DB should go through all migrations to current version."""
        from core.db import DB_VERSION, init_db

        db_path = str(tmp_path / "fresh.db")
        init_db(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM db_version LIMIT 1")
        row = cursor.fetchone()
        # Verify all tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cursor.fetchall()}
        conn.close()

        assert row[0] == DB_VERSION
        assert "cases" in tables
        assert "sessions" in tables
        assert "player_profile" in tables

    def test_idempotent_migration(self, tmp_path):
        """Running init_db multiple times should be safe."""
        from core.db import DB_VERSION, init_db

        db_path = str(tmp_path / "idempotent.db")
        init_db(db_path)
        init_db(db_path)  # Run again

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM db_version LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == DB_VERSION

    def test_player_profile_columns(self, player_db):
        """player_profile table should have expected columns."""
        conn = sqlite3.connect(player_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(player_profile)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {"id", "level", "experience", "total_sessions", "successful_sessions", "best_grade", "created_at", "updated_at"}
        assert expected.issubset(columns)


class TestGameConfigProgression:
    """Test game_config progression accessors."""

    def test_experience_curve_loaded(self):
        """EXPERIENCE_CURVE should be loaded from config."""
        from core.game_config import EXPERIENCE_CURVE

        assert isinstance(EXPERIENCE_CURVE, list)
        assert len(EXPERIENCE_CURVE) > 1
        assert EXPERIENCE_CURVE[0] == 0
        assert EXPERIENCE_CURVE[1] == 50

    def test_level_unlocks_loaded(self):
        """LEVEL_UNLOCKS should be loaded from config with int keys."""
        from core.game_config import LEVEL_UNLOCKS

        assert isinstance(LEVEL_UNLOCKS, dict)
        assert 1 in LEVEL_UNLOCKS
        assert 2 in LEVEL_UNLOCKS
        assert LEVEL_UNLOCKS[2]["tools"] == ["psych_profile_basic"]

    def test_get_experience_curve(self):
        """get_experience_curve accessor should return list."""
        from core.game_config import get_experience_curve

        curve = get_experience_curve()
        assert curve[0] == 0
        assert curve[1] == 50
        assert curve[2] == 110

    def test_get_level_unlocks(self):
        """get_level_unlocks accessor should return dict with int keys."""
        from core.game_config import get_level_unlocks

        unlocks = get_level_unlocks()
        assert isinstance(unlocks, dict)
        assert 10 in unlocks
        assert "psych_profile_advanced" in unlocks[10]["tools"]
