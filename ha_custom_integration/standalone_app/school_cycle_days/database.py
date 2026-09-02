"""SQLite persistence for the standalone application."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "calendar_entity": "",
    "us_state": "NH",
    "school_year_start": "",
    "school_year_end": "",
    "cycle_day_1": "Day 1",
    "cycle_day_2": "Day 2",
    "cycle_day_3": "Day 3",
    "cycle_day_4": "Day 4",
    "cycle_day_5": "Day 5",
    "starting_cycle_day": 1,
    "include_no_school_events": False,
    "include_weekend_events": False,
}


class Database:
    """Small SQLite repository for app-owned state."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS non_school_days (
                    day TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT 'manual'
                );

                CREATE TABLE IF NOT EXISTS holiday_days (
                    day TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schedule_days (
                    day TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    cycle_day INTEGER,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'generated'
                );
                """
            )

    def get_settings(self) -> dict[str, Any]:
        values = dict(DEFAULT_SETTINGS)
        with self._connect() as connection:
            for row in connection.execute("SELECT key, value FROM settings"):
                values[row["key"]] = json.loads(row["value"])
        return values

    def update_settings(self, values: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                [(key, json.dumps(value)) for key, value in values.items()],
            )

    def list_non_school_days(self) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT day, source FROM non_school_days ORDER BY day"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_non_school_day(self, day: str, source: str = "manual") -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO non_school_days(day, source) VALUES(?, ?)
                ON CONFLICT(day) DO NOTHING
                """,
                (day, source),
            )

    def delete_non_school_day(self, day: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM non_school_days WHERE day = ?", (day,))

    def clear_non_school_days(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM non_school_days")

    def replace_holidays(self, holidays: list[tuple[str, str]]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM holiday_days")
            connection.executemany(
                "INSERT INTO holiday_days(day, name) VALUES(?, ?)", holidays
            )

    def clear_holidays(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM holiday_days")

    def list_holidays(self) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT day, name FROM holiday_days ORDER BY day"
            ).fetchall()
        return [dict(row) for row in rows]

    def blocked_days(self) -> set[str]:
        with self._connect() as connection:
            manual = {
                row["day"]
                for row in connection.execute("SELECT day FROM non_school_days")
            }
            holidays = {
                row["day"] for row in connection.execute("SELECT day FROM holiday_days")
            }
        return manual | holidays

    def holiday_map(self) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT day, name FROM holiday_days").fetchall()
        return {row["day"]: row["name"] for row in rows}

    def replace_schedule(self, rows: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM schedule_days")
            connection.executemany(
                """
                INSERT INTO schedule_days(day, kind, cycle_day, title, detail, source)
                VALUES(:day, :kind, :cycle_day, :title, :detail, :source)
                """,
                rows,
            )

    def list_schedule(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT day, kind, cycle_day, title, detail, source FROM schedule_days"
        values: list[str] = []
        clauses: list[str] = []
        if start:
            clauses.append("day >= ?")
            values.append(start)
        if end:
            clauses.append("day <= ?")
            values.append(end)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY day"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def schedule_day(self, day: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT day, kind, cycle_day, title, detail, source FROM schedule_days WHERE day = ?",
                (day,),
            ).fetchone()
        return dict(row) if row else None
