"""FastAPI web application for School Cycle Days."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .database import Database
from .ha_client import HomeAssistantClient
from .service import SchoolCycleDaysService

runtime = get_settings()
database = Database(runtime.database_path)
ha = HomeAssistantClient(
    runtime.ha_base_url, runtime.ha_token, verify_ssl=runtime.verify_ssl
)
service = SchoolCycleDaysService(database, ha)

app = FastAPI(title="School Cycle Days", version="0.2.0")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/?message={quote(message)}", status_code=303)


@app.get("/health")
async def health() -> dict[str, str]:
    await ha.test_connection()
    return {"status": "ok", "home_assistant": "connected"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, message: str = ""):
    settings = service.settings()
    calendars: list[dict[str, str]] = []
    connection_error = ""
    try:
        calendars = await ha.calendars()
    except Exception as exc:  # surface connection trouble in the UI
        connection_error = str(exc)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "settings": settings,
            "calendars": calendars,
            "non_school_days": database.list_non_school_days(),
            "holidays": database.list_holidays(),
            "message": message,
            "connection_error": connection_error,
            "ha_url": runtime.ha_base_url,
        },
    )


@app.post("/settings")
async def save_settings(
    calendar_entity: str = Form(...),
    us_state: str = Form("NH"),
    school_year_start: str = Form(...),
    school_year_end: str = Form(...),
    cycle_day_1: str = Form(...),
    cycle_day_2: str = Form(...),
    cycle_day_3: str = Form(...),
    cycle_day_4: str = Form(...),
    cycle_day_5: str = Form(...),
    starting_cycle_day: int = Form(1),
    include_no_school_events: bool = Form(False),
    include_weekend_events: bool = Form(False),
):
    service.update_settings(
        {
            "calendar_entity": calendar_entity,
            "us_state": us_state.upper(),
            "school_year_start": school_year_start,
            "school_year_end": school_year_end,
            "cycle_day_1": cycle_day_1,
            "cycle_day_2": cycle_day_2,
            "cycle_day_3": cycle_day_3,
            "cycle_day_4": cycle_day_4,
            "cycle_day_5": cycle_day_5,
            "starting_cycle_day": max(1, min(5, starting_cycle_day)),
            "include_no_school_events": include_no_school_events,
            "include_weekend_events": include_weekend_events,
        }
    )
    return redirect("Settings saved.")


@app.post("/non-school-days/add")
async def add_non_school_day(day: str = Form(...)):
    service.add_non_school_day(day)
    return redirect(f"Added {day} as a non-school day.")


@app.post("/non-school-days/delete")
async def delete_non_school_day(day: str = Form(...)):
    service.delete_non_school_day(day)
    return redirect(f"Removed {day} from non-school days.")


@app.post("/non-school-days/clear")
async def clear_non_school_days():
    service.clear_non_school_days()
    return redirect("Cleared all manually entered non-school days.")


@app.post("/holidays/load")
async def load_holidays():
    count = service.load_holidays()
    return redirect(f"Loaded {count} holidays for the configured school year.")


@app.post("/holidays/clear")
async def clear_holidays():
    service.clear_holidays()
    return redirect("Cleared stored holidays.")


@app.post("/calendar/generate")
async def generate_calendar():
    counts = await service.generate()
    return redirect(
        "Generated "
        f"{counts['school_days']} school days; "
        f"{counts['non_school_days']} blocked weekdays; "
        f"{counts['weekend_days']} weekend days processed."
    )


@app.post("/calendar/regenerate")
async def regenerate_calendar(start_date: str = Form(""), end_date: str = Form("")):
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    result = await service.regenerate(start=start, end=end)
    return redirect(
        f"Deleted {result['deleted']} generated events and created "
        f"{result['school_days']} school-day events."
    )


@app.post("/calendar/delete-day")
async def delete_day(day: str = Form(...)):
    count = await service.delete_generated_events_on_day(date.fromisoformat(day))
    return redirect(f"Deleted {count} School Cycle Days event(s) on {day}.")
