"""Profile-scoped management routes."""
from __future__ import annotations
import json
from datetime import date
import holidays
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from .database import Database
from .schedule import ScheduleService

def build_management_router(db:Database,schedule:ScheduleService)->APIRouter:
    router=APIRouter()
    def profile(value):
        p=db.profile(value)
        if not p:raise HTTPException(404,"Profile not found")
        return p
    def back(pid,msg):return RedirectResponse(f"/profile/{pid}?message={msg.replace(' ','+')}",303)

    @router.post("/profile/{value}/settings")
    async def settings(value:str,name:str=Form(...),school_year_start:str=Form(...),school_year_end:str=Form(...),us_state:str=Form("NH"),starting_cycle_day:int=Form(1),timezone:str=Form("America/New_York")):
        p=profile(value); db.snapshot(p["id"],"Before profile settings")
        with db._connect() as c:c.execute("UPDATE calendar_profiles SET name=?,school_year_start=?,school_year_end=?,us_state=?,starting_cycle_day=?,timezone=? WHERE id=?",(name,school_year_start,school_year_end,us_state.upper(),max(1,starting_cycle_day),timezone,p["id"]))
        db.audit(p["id"],"profile_settings_updated",{"start":school_year_start,"end":school_year_end,"state":us_state}); schedule.rebuild_profile(p["id"]); return back(p["id"],"Profile settings saved")

    @router.post("/profile/{value}/non-school")
    async def add_non_school(value:str,day:str=Form(...),title:str=Form("No School")):
        p=profile(value); db.add_profile_non_school(p["id"],date.fromisoformat(day).isoformat(),"manual",title); schedule.rebuild_profile(p["id"]); return back(p["id"],"No-school date added")
    @router.post("/profile/{value}/non-school/remove")
    async def remove_non_school(value:str,day:str=Form(...)):
        p=profile(value); db.remove_profile_non_school(p["id"],day); schedule.rebuild_profile(p["id"]); return back(p["id"],"No-school date removed")

    @router.post("/profile/{value}/holidays/load")
    async def load_holidays(value:str):
        p=profile(value); start=date.fromisoformat(p["school_year_start"]); end=date.fromisoformat(p["school_year_end"]); values=holidays.US(state=p["us_state"],years=range(start.year,end.year+1)); rows=sorted((d.isoformat(),str(n)) for d,n in values.items() if start<=d<=end)
        with db._connect() as c:c.execute("DELETE FROM profile_holidays WHERE profile_id=?",(p["id"],)); c.executemany("INSERT INTO profile_holidays(profile_id,day,name) VALUES(?,?,?)",[(p["id"],d,n) for d,n in rows])
        db.audit(p["id"],"holidays_loaded",{"count":len(rows)}); schedule.rebuild_profile(p["id"]); return back(p["id"],f"Loaded {len(rows)} holidays")
    @router.post("/profile/{value}/holidays/clear")
    async def clear_holidays(value:str):
        p=profile(value)
        with db._connect() as c:c.execute("DELETE FROM profile_holidays WHERE profile_id=?",(p["id"],))
        schedule.rebuild_profile(p["id"]); return back(p["id"],"Holidays cleared")

    @router.post("/profile/{value}/override/remove")
    async def remove_override(value:str,day:str=Form(...)):
        p=profile(value); db.snapshot(p["id"],"Before override removal")
        with db._connect() as c:c.execute("DELETE FROM schedule_overrides WHERE profile_id=? AND day=?",(p["id"],day))
        db.audit(p["id"],"override_removed",{"day":day}); schedule.rebuild_profile(p["id"]); return back(p["id"],"Override removed")
    @router.post("/closure-rules/{rule_id}/delete")
    async def delete_rule(rule_id:int):
        with db._connect() as c:
            r=c.execute("SELECT profile_id FROM closure_rules WHERE id=?",(rule_id,)).fetchone()
            if not r:raise HTTPException(404,"Rule not found")
            pid=r[0]; c.execute("DELETE FROM closure_rules WHERE id=?",(rule_id,))
        db.audit(pid,"closure_rule_removed",{"id":rule_id}); schedule.rebuild_profile(pid); return back(pid,"Closure rule removed")
    @router.post("/sources/{source_id}/delete")
    async def delete_source(source_id:int):
        with db._connect() as c:
            r=c.execute("SELECT profile_id FROM external_sources WHERE id=?",(source_id,)).fetchone()
            if not r:raise HTTPException(404,"Source not found")
            pid=r[0]; c.execute("DELETE FROM external_sources WHERE id=?",(source_id,))
        db.audit(pid,"source_removed",{"id":source_id}); return back(pid,"Source removed")
    @router.post("/sources/{source_id}/toggle")
    async def toggle_source(source_id:int):
        with db._connect() as c:
            r=c.execute("SELECT profile_id,enabled FROM external_sources WHERE id=?",(source_id,)).fetchone()
            if not r:raise HTTPException(404,"Source not found")
            pid=r[0]; c.execute("UPDATE external_sources SET enabled=? WHERE id=?",(0 if r[1] else 1,source_id))
        return back(pid,"Source toggled")

    @router.get("/api/v1/profiles/{value}/export")
    async def export_profile(value:str):
        p=profile(value)
        with db._connect() as c:
            non_school=[dict(r) for r in c.execute("SELECT day,source,title,imported_from FROM profile_non_school_days WHERE profile_id=? ORDER BY day",(p["id"],))]; holidays_rows=[dict(r) for r in c.execute("SELECT day,name FROM profile_holidays WHERE profile_id=? ORDER BY day",(p["id"],))]; rules=[dict(r) for r in c.execute("SELECT * FROM closure_rules WHERE profile_id=?",(p["id"],))]
        return JSONResponse({"schema_version":1,"profile":p,"cycles":db.cycles(p["id"]),"non_school_days":non_school,"holidays":holidays_rows,"overrides":list(db.overrides(p["id"]).values()),"closure_rules":rules,"schedule":db.profile_schedule(p["id"])})
    return router
