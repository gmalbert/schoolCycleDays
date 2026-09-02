"""Diff-based Google Calendar and Outlook publishing endpoints."""
from __future__ import annotations
from datetime import date, timedelta
from urllib.parse import quote
import httpx
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse
from .database import Database
from .schedule import ScheduleService
from .sync_engine import PublicationSyncPlanner


def event_payload(row):
    d=date.fromisoformat(row["day"]); nxt=d+timedelta(days=1); summary=f"{row['title']} ({row['detail']})" if row["kind"]=="school" else row["title"]
    return summary,d,nxt

def build_publisher_router(db:Database,schedule:ScheduleService)->APIRouter:
    router=APIRouter(); planner=PublicationSyncPlanner(db)

    @router.post("/profile/{profile}/publish/plan")
    async def plan(profile:str,provider:str=Form(...)):
        p=db.profile(profile)
        if not p:raise HTTPException(404,"Profile not found")
        result=planner.plan(p["id"],provider,schedule.rows(profile=p["id"]))
        return {"provider":provider,"create":result.create,"update":result.update,"delete":result.delete,"unchanged":result.unchanged,"counts":{"create":len(result.create),"update":len(result.update),"delete":len(result.delete),"unchanged":len(result.unchanged)}}

    @router.post("/profile/{profile}/publish/google")
    async def google(profile:str,calendar_id:str=Form(...),access_token:str=Form(...)):
        p=db.profile(profile); provider=f"google:{calendar_id}"; plan=planner.plan(p["id"],provider,schedule.rows(profile=p["id"])); headers={"Authorization":f"Bearer {access_token}","Content-Type":"application/json"}; base=f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id,safe='')}/events"
        async with httpx.AsyncClient(timeout=30) as client:
            for row in plan.create:
                summary,d,nxt=event_payload(row); body={"summary":summary,"description":row.get("detail",""),"start":{"date":d.isoformat()},"end":{"date":nxt.isoformat()},"extendedProperties":{"private":{"school_cycle_days":"true","local_day":row["day"]}}}; r=await client.post(base,headers=headers,json=body); r.raise_for_status(); planner.record(p["id"],provider,row["day"],r.json()["id"],row["content_hash"])
            for row in plan.update:
                summary,d,nxt=event_payload(row); body={"summary":summary,"description":row.get("detail",""),"start":{"date":d.isoformat()},"end":{"date":nxt.isoformat()},"extendedProperties":{"private":{"school_cycle_days":"true","local_day":row["day"]}}}; r=await client.patch(f"{base}/{quote(row['external_event_id'],safe='')}",headers=headers,json=body); r.raise_for_status(); planner.record(p["id"],provider,row["day"],row["external_event_id"],row["content_hash"])
            for row in plan.delete:
                r=await client.delete(f"{base}/{quote(row['external_event_id'],safe='')}",headers=headers)
                if r.status_code not in (204,404):r.raise_for_status()
                planner.remove(p["id"],provider,row["local_day"])
        db.audit(p["id"],"google_sync",{"created":len(plan.create),"updated":len(plan.update),"deleted":len(plan.delete)}); return RedirectResponse(f"/profile/{p['id']}?message=Google+sync+complete",303)

    @router.post("/profile/{profile}/publish/outlook")
    async def outlook(profile:str,calendar_id:str=Form(...),access_token:str=Form(...)):
        p=db.profile(profile); provider=f"outlook:{calendar_id}"; plan=planner.plan(p["id"],provider,schedule.rows(profile=p["id"])); headers={"Authorization":f"Bearer {access_token}","Content-Type":"application/json"}; base=f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id,safe='')}/events"
        async with httpx.AsyncClient(timeout=30) as client:
            for row in plan.create:
                summary,d,nxt=event_payload(row); body={"subject":summary,"isAllDay":True,"body":{"contentType":"text","content":row.get("detail","")},"start":{"dateTime":d.isoformat()+"T00:00:00","timeZone":"UTC"},"end":{"dateTime":nxt.isoformat()+"T00:00:00","timeZone":"UTC"},"categories":["School Cycle Days"]}; r=await client.post(base,headers=headers,json=body); r.raise_for_status(); planner.record(p["id"],provider,row["day"],r.json()["id"],row["content_hash"])
            for row in plan.update:
                summary,d,nxt=event_payload(row); body={"subject":summary,"isAllDay":True,"body":{"contentType":"text","content":row.get("detail","")},"start":{"dateTime":d.isoformat()+"T00:00:00","timeZone":"UTC"},"end":{"dateTime":nxt.isoformat()+"T00:00:00","timeZone":"UTC"}}; r=await client.patch(f"https://graph.microsoft.com/v1.0/me/events/{quote(row['external_event_id'],safe='')}",headers=headers,json=body); r.raise_for_status(); planner.record(p["id"],provider,row["day"],row["external_event_id"],row["content_hash"])
            for row in plan.delete:
                r=await client.delete(f"https://graph.microsoft.com/v1.0/me/events/{quote(row['external_event_id'],safe='')}",headers=headers)
                if r.status_code not in (204,404):r.raise_for_status()
                planner.remove(p["id"],provider,row["local_day"])
        db.audit(p["id"],"outlook_sync",{"created":len(plan.create),"updated":len(plan.update),"deleted":len(plan.delete)}); return RedirectResponse(f"/profile/{p['id']}?message=Outlook+sync+complete",303)
    return router
