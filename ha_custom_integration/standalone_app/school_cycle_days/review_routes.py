"""Two-step ICS import review workflow."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from .database import Database
from .ics_import import clean_no_school_calendar
from .schedule import ScheduleService

MAX_BYTES=5*1024*1024

def build_review_router(db:Database,schedule:ScheduleService,templates:Jinja2Templates)->APIRouter:
    router=APIRouter()
    @router.post("/profile/{profile}/ics/review")
    async def review(request:Request,profile:str,calendar_file:UploadFile=File(...)):
        p=db.profile(profile)
        if not p:raise HTTPException(404,"Profile not found")
        filename=Path(calendar_file.filename or "calendar.ics").name; raw=await calendar_file.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise HTTPException(413,"ICS file exceeds 5 MB")
        result=clean_no_school_calendar(raw)
        candidates=[]
        for event in result.events:
            for day in event.dates:candidates.append({"day":day.isoformat(),"summary":event.summary})
        # Deduplicate while preserving first title.
        unique={x["day"]:x for x in candidates}; candidates=[unique[k] for k in sorted(unique)]
        request.session["ics_review"]={"profile_id":p["id"],"filename":filename,"candidates":candidates}
        return templates.TemplateResponse(request,"ics_review.html",{"profile":p,"filename":filename,"candidates":candidates,"repaired":result.repaired_final_event})
    @router.post("/profile/{profile}/ics/confirm")
    async def confirm(request:Request,profile:str,selected:list[str]=Form(default=[])):
        p=db.profile(profile); pending=request.session.get("ics_review")
        if not p or not pending or pending.get("profile_id")!=p["id"]:raise HTTPException(400,"No matching ICS review is pending")
        allowed={x["day"]:x for x in pending["candidates"]}; imported=0
        for day in selected:
            if day not in allowed:continue
            db.add_profile_non_school(p["id"],day,f"ics:{pending['filename']}",allowed[day]["summary"],pending["filename"]); imported+=1
        request.session.pop("ics_review",None); schedule.rebuild_profile(p["id"])
        return RedirectResponse(f"/profile/{p['id']}?message=Imported+{imported}+reviewed+date(s).",303)
    return router
