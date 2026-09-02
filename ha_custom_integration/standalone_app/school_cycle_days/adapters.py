"""Pluggable calendar source, publisher, and notification adapters."""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any
import httpx
from icalendar import Calendar

@dataclass(slots=True)
class ExternalEvent:
    uid:str; summary:str; start:date; end:date; description:str=""; raw:dict[str,Any]|None=None

@dataclass(slots=True)
class SyncResult:
    created:int=0; updated:int=0; deleted:int=0; unchanged:int=0

class CalendarSource(ABC):
    @abstractmethod
    async def fetch_events(self)->list[ExternalEvent]: ...

class ICSUrlSource(CalendarSource):
    def __init__(self,url:str,include_terms:list[str]|None=None,exclude_terms:list[str]|None=None):
        self.url=url; self.include=[x.lower() for x in (include_terms or ["no school","school closed","vacation","teacher workday"])]; self.exclude=[x.lower() for x in (exclude_terms or [])]
    async def fetch_events(self):
        async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
            r=await client.get(self.url); r.raise_for_status(); raw=r.content
        cal=Calendar.from_ical(raw); out=[]
        for comp in cal.walk("VEVENT"):
            summary=str(comp.get("summary","")).strip(); hay=summary.lower()+" "+str(comp.get("description","")).lower()
            if self.include and not any(t in hay for t in self.include): continue
            if any(t in hay for t in self.exclude): continue
            start=comp.decoded("dtstart"); end=comp.decoded("dtend") if comp.get("dtend") is not None else start
            if hasattr(start,"date"): start=start.date()
            if hasattr(end,"date"): end=end.date()
            out.append(ExternalEvent(str(comp.get("uid",hashlib.sha1((summary+str(start)).encode()).hexdigest())),summary,start,end,str(comp.get("description",""))))
        return out

class CalendarPublisher(ABC):
    @abstractmethod
    async def sync(self,schedule:list[dict[str,Any]])->SyncResult: ...

class RemoteJsonCalendarPublisher(CalendarPublisher):
    """Generic idempotent webhook publisher; useful for custom integrations."""
    def __init__(self,url:str,token:str=""): self.url=url; self.token=token
    async def sync(self,schedule):
        headers={"Authorization":f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post(self.url,json={"schedule":schedule},headers=headers); r.raise_for_status()
        payload=r.json() if r.content else {}; return SyncResult(**{k:int(payload.get(k,0)) for k in ("created","updated","deleted","unchanged")})

class GoogleCalendarPublisher(CalendarPublisher):
    """Google Calendar adapter boundary. OAuth token acquisition is handled by the web layer."""
    def __init__(self,calendar_id:str,access_token:str): self.calendar_id=calendar_id; self.token=access_token
    async def sync(self,schedule):
        # Uses deterministic extendedProperties so repeated syncs can be reconciled.
        headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json"}; result=SyncResult()
        async with httpx.AsyncClient(timeout=30) as client:
            for row in schedule:
                key=f"scd-{row['day']}"; q=await client.get(f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events",headers=headers,params={"privateExtendedProperty":f"scd_key={key}"}); q.raise_for_status(); items=q.json().get("items",[])
                body={"summary":f"{row['title']} ({row['detail']})" if row['kind']=="school" else row['title'],"description":row.get("detail", ""),"start":{"date":row['day']},"end":{"date":date.fromisoformat(row['day']).fromordinal(date.fromisoformat(row['day']).toordinal()+1).isoformat()},"extendedProperties":{"private":{"scd_key":key}}}
                digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
                if items:
                    event=items[0]
                    if event.get("description","").endswith(f"\nscd_hash:{digest}"): result.unchanged+=1; continue
                    body["description"]=(body["description"]+f"\nscd_hash:{digest}").strip(); u=await client.put(f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events/{event['id']}",headers=headers,json=body); u.raise_for_status(); result.updated+=1
                else:
                    body["description"]=(body["description"]+f"\nscd_hash:{digest}").strip(); c=await client.post(f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events",headers=headers,json=body); c.raise_for_status(); result.created+=1
        return result

class OutlookCalendarPublisher(CalendarPublisher):
    """Microsoft Graph publisher using an externally acquired OAuth access token."""
    def __init__(self,calendar_id:str,access_token:str): self.calendar_id=calendar_id; self.token=access_token
    async def sync(self,schedule):
        headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json"}; result=SyncResult()
        async with httpx.AsyncClient(timeout=30) as client:
            for row in schedule:
                # Graph extensions are distribution-specific; create endpoint is functional,
                # while durable update/delete reconciliation uses published_events in Database.
                d=date.fromisoformat(row["day"]); nxt=date.fromordinal(d.toordinal()+1)
                body={"subject":f"{row['title']} ({row['detail']})" if row['kind']=="school" else row['title'],"isAllDay":True,"body":{"contentType":"text","content":row.get("detail","")},"start":{"dateTime":d.isoformat()+"T00:00:00","timeZone":"UTC"},"end":{"dateTime":nxt.isoformat()+"T00:00:00","timeZone":"UTC"}}
                r=await client.post(f"https://graph.microsoft.com/v1.0/me/calendars/{self.calendar_id}/events",headers=headers,json=body); r.raise_for_status(); result.created+=1
        return result

class NotificationPublisher(ABC):
    @abstractmethod
    async def send(self,title:str,message:str,payload:dict[str,Any]|None=None)->None: ...

class WebhookNotificationPublisher(NotificationPublisher):
    def __init__(self,url:str): self.url=url
    async def send(self,title,message,payload=None):
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.post(self.url,json={"title":title,"message":message,"data":payload or {}}); r.raise_for_status()

class NtfyPublisher(NotificationPublisher):
    def __init__(self,url:str,topic:str,token:str=""): self.url=url.rstrip("/"); self.topic=topic; self.token=token
    async def send(self,title,message,payload=None):
        headers={"Title":title};
        if self.token: headers["Authorization"]=f"Bearer {self.token}"
        async with httpx.AsyncClient(timeout=15) as c:
            r=await c.post(f"{self.url}/{self.topic}",content=message.encode(),headers=headers); r.raise_for_status()
