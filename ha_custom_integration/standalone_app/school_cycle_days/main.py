"""FastAPI web application for School Cycle Days.

The standalone calendar is the primary product. Home Assistant and MQTT are
optional adapters and are never required for startup or ordinary schedule use.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import holidays as holiday_lib
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .database import Database
from .ha_client import HomeAssistantClient
from .ics_import import clean_no_school_calendar
from .mqtt_adapter import publish_discovery_and_state
from .schedule import ScheduleService, ScheduleSummary
from .service import SchoolCycleDaysService

runtime = get_settings()
database = Database(runtime.database_path)
schedule = ScheduleService(database)
ha = HomeAssistantClient(runtime.ha_base_url, runtime.ha_token, verify_ssl=runtime.verify_ssl)
ha_service = SchoolCycleDaysService(database, ha)

app = FastAPI(title="School Cycle Days", version="0.3.0")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
MAX_ICS_BYTES = 5 * 1024 * 1024


def redirect(message: str, *, month: str = "") -> RedirectResponse:
    suffix = f"&month={quote(month)}" if month else ""
    return RedirectResponse(url=f"/?message={quote(message)}{suffix}", status_code=303)


def publish_optional_state() -> None:
    """Best-effort optional outputs; failures never break the standalone app."""
    if not runtime.mqtt_enabled:
        return
    try:
        publish_discovery_and_state(runtime, schedule)
    except Exception:
        # Broker availability must never make the local calendar unavailable.
        pass


def rebuild_and_publish() -> ScheduleSummary:
    result = schedule.rebuild()
    publish_optional_state()
    return result


def rebuild_if_ready() -> bool:
    settings = database.get_settings()
    if not settings.get("school_year_start") or not settings.get("school_year_end"):
        return False
    try:
        rebuild_and_publish()
        return True
    except ValueError:
        return False


def parse_month(value: str | None) -> tuple[int, int]:
    if value:
        try:
            year_text, month_text = value.split("-", 1)
            year, month = int(year_text), int(month_text)
            if 1 <= month <= 12:
                return year, month
        except (TypeError, ValueError):
            pass
    today = date.today()
    return today.year, today.month


def adjacent_month(year: int, month: int, offset: int) -> str:
    absolute = year * 12 + (month - 1) + offset
    target_year, zero_month = divmod(absolute, 12)
    return f"{target_year:04d}-{zero_month + 1:02d}"


def load_local_holidays() -> int:
    settings = database.get_settings()
    start_raw = str(settings.get("school_year_start") or "")
    end_raw = str(settings.get("school_year_end") or "")
    if not start_raw or not end_raw:
        raise ValueError("Set the school-year start and end before loading holidays")
    start, end = date.fromisoformat(start_raw), date.fromisoformat(end_raw)
    state = str(settings.get("us_state") or "NH")
    values = holiday_lib.US(state=state, years=range(start.year, end.year + 1))
    selected = sorted(
        (holiday_date.isoformat(), str(name))
        for holiday_date, name in values.items()
        if start <= holiday_date <= end
    )
    database.replace_holidays(selected)
    return len(selected)


@app.get("/health")
@app.get("/api/v1/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "standalone": True,
        "home_assistant_configured": runtime.ha_enabled,
        "mqtt_configured": runtime.mqtt_enabled,
        "schedule_rows": len(database.list_schedule()),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, message: str = "", month: str = ""):
    settings = database.get_settings()
    if not database.list_schedule() and settings.get("school_year_start") and settings.get("school_year_end"):
        rebuild_if_ready()

    year, month_number = parse_month(month)
    grid = schedule.month_grid(year, month_number)
    today_row = schedule.today()
    next_school = schedule.next_school_day(date.today())

    ha_calendars: list[dict[str, str]] = []
    ha_error = ""
    if runtime.ha_enabled:
        try:
            ha_calendars = await ha.calendars()
        except Exception as exc:
            ha_error = str(exc)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "settings": settings,
            "calendar_grid": grid,
            "month_label": date(year, month_number, 1).strftime("%B %Y"),
            "month_value": f"{year:04d}-{month_number:02d}",
            "previous_month": adjacent_month(year, month_number, -1),
            "next_month": adjacent_month(year, month_number, 1),
            "today_row": today_row,
            "next_school": next_school,
            "non_school_days": database.list_non_school_days(),
            "holidays": database.list_holidays(),
            "message": message,
            "ha_enabled": runtime.ha_enabled,
            "ha_url": runtime.ha_base_url,
            "ha_calendars": ha_calendars,
            "ha_error": ha_error,
            "mqtt_enabled": runtime.mqtt_enabled,
        },
    )


@app.get("/api/v1/today")
async def api_today():
    return schedule.today()


@app.get("/api/v1/tomorrow")
async def api_tomorrow():
    return schedule.today(date.today() + timedelta(days=1))


@app.get("/api/v1/next-school-day")
async def api_next_school_day():
    return schedule.next_school_day(date.today()) or JSONResponse(
        {"detail": "No future school day in the configured schedule"}, status_code=404
    )


@app.get("/api/v1/schedule")
async def api_schedule(start: str = Query(""), end: str = Query("")):
    try:
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
    except ValueError:
        return JSONResponse({"detail": "Dates must use YYYY-MM-DD"}, status_code=400)
    return schedule.rows(start_date, end_date)


@app.get("/calendar.ics")
async def calendar_feed():
    return Response(
        content=schedule.to_ics(),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="school-cycle-days.ics"'},
    )


@app.post("/calendar/rebuild")
async def rebuild_calendar(month: str = Form("")):
    try:
        result = rebuild_and_publish()
    except ValueError as exc:
        return redirect(str(exc), month=month)
    return redirect(
        f"Calendar rebuilt: {result.school_days} school days, "
        f"{result.non_school_days} no-school weekdays, {result.weekend_days} weekend days.",
        month=month,
    )


@app.post("/migration/import-legacy-helpers")
async def import_legacy_helpers():
    if not runtime.ha_enabled:
        return redirect("Home Assistant is not configured; legacy Helper import is unavailable.")
    result = await ha_service.import_legacy_helpers()
    rebuild_if_ready()
    return redirect(
        "Imported legacy HA values: "
        f"{result['settings']} settings, {result['non_school_days']} non-school dates, "
        f"{result['holidays']} holiday dates."
    )


@app.post("/ics/process")
async def process_ics(calendar_file: UploadFile = File(...), mode: str = Form("import")):
    filename = Path(calendar_file.filename or "calendar.ics").name
    if not filename.lower().endswith(".ics"):
        return redirect("Please upload a .ics calendar file.")
    raw = await calendar_file.read(MAX_ICS_BYTES + 1)
    if len(raw) > MAX_ICS_BYTES:
        return redirect("ICS file is larger than the 5 MB upload limit.")

    result = clean_no_school_calendar(raw)
    if not result.events:
        return redirect("No events whose summary starts with 'No School' were found.")
    if mode == "download":
        clean_name = f"{Path(filename).stem}_no_school_clean.ics"
        return Response(
            content=result.clean_ics,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{clean_name}"'},
        )

    existing = {row["day"] for row in database.list_non_school_days()}
    imported = 0
    for imported_date in result.dates:
        iso = imported_date.isoformat()
        if iso not in existing:
            database.add_non_school_day(iso, source=f"ics:{filename}")
            existing.add(iso)
            imported += 1
    rebuild_if_ready()
    repair_note = " The final VEVENT was repaired." if result.repaired_final_event else ""
    return redirect(
        f"Found {len(result.events)} No School event(s) covering {len(result.dates)} date(s); "
        f"imported {imported} new non-school date(s).{repair_note}"
    )


@app.post("/settings")
async def save_settings(
    us_state: str = Form("NH"), school_year_start: str = Form(...), school_year_end: str = Form(...),
    cycle_day_1: str = Form(...), cycle_day_2: str = Form(...), cycle_day_3: str = Form(...),
    cycle_day_4: str = Form(...), cycle_day_5: str = Form(...), starting_cycle_day: int = Form(1),
    include_no_school_events: bool = Form(False), include_weekend_events: bool = Form(False),
):
    database.update_settings(
        {
            "us_state": us_state.upper(), "school_year_start": school_year_start,
            "school_year_end": school_year_end, "cycle_day_1": cycle_day_1,
            "cycle_day_2": cycle_day_2, "cycle_day_3": cycle_day_3,
            "cycle_day_4": cycle_day_4, "cycle_day_5": cycle_day_5,
            "starting_cycle_day": max(1, min(5, starting_cycle_day)),
            "include_no_school_events": include_no_school_events,
            "include_weekend_events": include_weekend_events,
        }
    )
    try:
        result = rebuild_and_publish()
        return redirect(f"Settings saved and calendar rebuilt with {result.school_days} school days.")
    except ValueError as exc:
        return redirect(f"Settings saved, but calendar was not rebuilt: {exc}")


@app.post("/non-school-days/add")
async def add_non_school_day(day: str = Form(...)):
    parsed = date.fromisoformat(day)
    database.add_non_school_day(parsed.isoformat(), source="manual")
    rebuild_if_ready()
    return redirect(f"Added {day} as a non-school day and recalculated the schedule.")


@app.post("/non-school-days/delete")
async def delete_non_school_day(day: str = Form(...)):
    database.delete_non_school_day(date.fromisoformat(day).isoformat())
    rebuild_if_ready()
    return redirect(f"Removed {day} from non-school days and recalculated the schedule.")


@app.post("/non-school-days/clear")
async def clear_non_school_days():
    database.clear_non_school_days()
    rebuild_if_ready()
    return redirect("Cleared manually/imported non-school days and recalculated the schedule.")


@app.post("/holidays/load")
async def load_holidays():
    try:
        count = load_local_holidays()
    except ValueError as exc:
        return redirect(str(exc))
    rebuild_if_ready()
    return redirect(f"Loaded {count} holidays and recalculated the schedule.")


@app.post("/holidays/clear")
async def clear_holidays():
    database.clear_holidays()
    rebuild_if_ready()
    return redirect("Cleared stored holidays and recalculated the schedule.")


@app.post("/integrations/mqtt/publish")
async def publish_mqtt_now():
    if not runtime.mqtt_enabled:
        return redirect("MQTT is not configured.")
    try:
        publish_discovery_and_state(runtime, schedule)
    except Exception as exc:
        return redirect(f"MQTT publish failed: {exc}")
    return redirect("Published Home Assistant MQTT Discovery and current schedule states.")


@app.post("/integrations/home-assistant/publish")
async def publish_to_home_assistant(calendar_entity: str = Form(...)):
    if not runtime.ha_enabled:
        return redirect("Home Assistant is not configured.")
    database.update_settings({"calendar_entity": calendar_entity})
    counts = await ha_service.generate()
    return redirect(
        f"Published {counts['school_days']} school-day events to {calendar_entity}. "
        "The standalone schedule remains authoritative."
    )
