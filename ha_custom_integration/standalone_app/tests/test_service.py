from __future__ import annotations

from datetime import date

import pytest

from school_cycle_days.database import Database
from school_cycle_days.service import GENERATED_MARKER, SchoolCycleDaysService


class FakeHA:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.event_rows: list[dict] = []

    async def config(self):
        return {"time_zone": "America/New_York"}

    async def create_event(self, entity_id: str, **data):
        self.created.append({"entity_id": entity_id, **data})

    async def events(self, entity_id: str, start: str, end: str):
        return list(self.event_rows)

    async def delete_event(self, entity_id: str, uid: str, *, recurrence_id=None):
        self.deleted.append(uid)


def configured_service(tmp_path):
    database = Database(str(tmp_path / "school.sqlite3"))
    database.update_settings(
        {
            "calendar_entity": "calendar.school_test",
            "us_state": "NH",
            "school_year_start": "2026-09-08",
            "school_year_end": "2026-09-11",
            "cycle_day_1": "Art",
            "cycle_day_2": "Music",
            "cycle_day_3": "Library",
            "cycle_day_4": "PE",
            "cycle_day_5": "STEM",
            "starting_cycle_day": 1,
            "include_no_school_events": False,
            "include_weekend_events": False,
        }
    )
    ha = FakeHA()
    return SchoolCycleDaysService(database, ha), database, ha


@pytest.mark.asyncio
async def test_generate_advances_cycle(tmp_path):
    service, _, ha = configured_service(tmp_path)

    result = await service.generate()

    assert result["school_days"] == 4
    assert [row["summary"] for row in ha.created] == [
        "Day 1 (Art)",
        "Day 2 (Music)",
        "Day 3 (Library)",
        "Day 4 (PE)",
    ]
    assert all(GENERATED_MARKER in row["description"] for row in ha.created)


@pytest.mark.asyncio
async def test_non_school_day_pauses_cycle(tmp_path):
    service, database, ha = configured_service(tmp_path)
    database.add_non_school_day("2026-09-09")

    await service.generate()

    assert [row["summary"] for row in ha.created] == [
        "Day 1 (Art)",
        "Day 2 (Music)",
        "Day 3 (Library)",
    ]
    assert [row["start_date"] for row in ha.created] == [
        "2026-09-08",
        "2026-09-10",
        "2026-09-11",
    ]


@pytest.mark.asyncio
async def test_delete_generated_events_preserves_unrelated(tmp_path):
    service, _, ha = configured_service(tmp_path)
    ha.event_rows = [
        {
            "uid": "owned-new",
            "summary": "Day 1 (Art)",
            "description": f"Art\n{GENERATED_MARKER}",
        },
        {
            "uid": "owned-legacy",
            "summary": "Day 2 (Music)",
            "description": "Music",
        },
        {
            "uid": "manual",
            "summary": "Dentist Appointment",
            "description": "Do not delete",
        },
    ]

    deleted = await service.delete_generated_events(
        date(2026, 9, 8), date(2026, 9, 11)
    )

    assert deleted == 2
    assert ha.deleted == ["owned-new", "owned-legacy"]


@pytest.mark.asyncio
async def test_regenerate_deletes_then_recreates(tmp_path):
    service, _, ha = configured_service(tmp_path)
    ha.event_rows = [
        {
            "uid": "old-cycle",
            "summary": "Day 1 (Art)",
            "description": "Art",
        }
    ]

    result = await service.regenerate()

    assert result["deleted"] == 1
    assert ha.deleted == ["old-cycle"]
    assert len(ha.created) == 4
