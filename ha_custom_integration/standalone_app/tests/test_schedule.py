from datetime import date

from school_cycle_days.database import Database
from school_cycle_days.schedule import ScheduleService


def configured_schedule(tmp_path):
    database = Database(str(tmp_path / "schedule.sqlite3"))
    database.update_settings(
        {
            "school_year_start": "2026-09-08",
            "school_year_end": "2026-09-14",
            "cycle_day_1": "Art",
            "cycle_day_2": "Music",
            "cycle_day_3": "Library",
            "cycle_day_4": "PE",
            "cycle_day_5": "STEM",
            "starting_cycle_day": 1,
            "include_no_school_events": True,
            "include_weekend_events": False,
        }
    )
    return ScheduleService(database), database


def test_standalone_schedule_advances_only_on_school_days(tmp_path):
    schedule, database = configured_schedule(tmp_path)
    database.add_non_school_day("2026-09-10", source="manual")

    result = schedule.rebuild()
    rows = database.list_schedule()

    assert result.school_days == 4
    school = [row for row in rows if row["kind"] == "school"]
    assert [(row["day"], row["cycle_day"], row["detail"]) for row in school] == [
        ("2026-09-08", 1, "Art"),
        ("2026-09-09", 2, "Music"),
        ("2026-09-11", 3, "Library"),
        ("2026-09-14", 4, "PE"),
    ]


def test_standalone_schedule_records_weekends_and_closures(tmp_path):
    schedule, database = configured_schedule(tmp_path)
    database.add_non_school_day("2026-09-10", source="ics:district.ics")
    schedule.rebuild()

    closed = database.schedule_day("2026-09-10")
    saturday = database.schedule_day("2026-09-12")

    assert closed["kind"] == "no_school"
    assert closed["title"] == "No School"
    assert saturday["kind"] == "weekend"


def test_today_and_next_school_day_are_local_database_queries(tmp_path):
    schedule, database = configured_schedule(tmp_path)
    database.add_non_school_day("2026-09-10")
    schedule.rebuild()

    assert schedule.today(date(2026, 9, 10))["kind"] == "no_school"
    assert schedule.next_school_day(date(2026, 9, 10))["day"] == "2026-09-11"


def test_ics_export_does_not_require_home_assistant(tmp_path):
    schedule, _ = configured_schedule(tmp_path)
    schedule.rebuild()

    rendered = schedule.to_ics().decode("utf-8")

    assert "BEGIN:VCALENDAR" in rendered
    assert "Day 1 (Art)" in rendered
    assert "No School" not in rendered  # none configured in this fixture
    assert "school-cycle-days-2026-09-08@local" in rendered
