"""Authoritative standalone schedule engine with profile support."""
from __future__ import annotations
from calendar import Calendar as MonthCalendar
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from icalendar import Calendar, Event
from .database import Database

@dataclass(slots=True)
class ScheduleSummary:
    school_days:int; non_school_days:int; weekend_days:int; start:date; end:date

class ScheduleService:
    def __init__(self,database:Database): self.database=database
    def _profile(self,slug_or_id="school"):
        p=self.database.profile(slug_or_id)
        if not p: raise ValueError("Calendar profile not found")
        return p
    def _rule_dates(self,pid:int,start:date,end:date)->set[str]:
        out:set[str]=set()
        for rule in self.database.closure_rules(pid):
            rs=date.fromisoformat(rule["start_date"]) if rule.get("start_date") else start; re=date.fromisoformat(rule["end_date"]) if rule.get("end_date") else end; rs=max(rs,start); re=min(re,end); current=rs
            while current<=re:
                weekday=rule.get("weekday")
                if weekday is not None and current.weekday()!=int(weekday): current+=timedelta(days=1); continue
                if rule.get("month") and current.month!=int(rule["month"]): current+=timedelta(days=1); continue
                nth=rule.get("nth")
                if nth and (current.day-1)//7+1!=int(nth): current+=timedelta(days=1); continue
                out.add(current.isoformat()); current+=timedelta(days=1)
        return out
    def preview(self,profile="school",*,extra_blocked:set[str]|None=None)->tuple[list[dict[str,Any]],ScheduleSummary]:
        p=self._profile(profile); pid=p["id"]
        if not p["school_year_start"] or not p["school_year_end"]: raise ValueError("School year dates are required")
        start=date.fromisoformat(p["school_year_start"]); end=date.fromisoformat(p["school_year_end"])
        if end<start: raise ValueError("School year end must not be before school year start")
        cycles=self.database.cycles(pid)
        if not cycles: raise ValueError("At least one cycle definition is required")
        labels=[x["label"] for x in cycles]; cycle=((int(p.get("starting_cycle_day") or 1)-1)%len(labels))+1
        blocked=self.database.profile_blocked(pid)|self._rule_dates(pid,start,end)|(extra_blocked or set()); holidays=self.database.profile_holiday_map(pid); overrides=self.database.overrides(pid)
        rows=[]; counts={"school":0,"non_school":0,"weekend":0}; current=start
        while current<=end:
            iso=current.isoformat(); override=overrides.get(iso); overridden=0
            if override and override["override_type"]=="no_school": kind="no_school"; cday=None; title=override.get("title") or "No School"; detail=override.get("note") or "Override"; source="override"; overridden=1
            elif override and override["override_type"]=="school": cday=int(override.get("cycle_day") or cycle); cday=((cday-1)%len(labels))+1; kind="school"; title=override.get("title") or f"Day {cday}"; detail=override.get("note") or labels[cday-1]; source="override"; overridden=1; cycle=(cday%len(labels))+1
            elif current.weekday()>=5: kind="weekend"; cday=None; title="Weekend"; detail=""; source="generated"
            elif iso in blocked: kind="no_school"; cday=None; title="No School"; detail=holidays.get(iso,"No School"); source="holiday" if iso in holidays else "non_school_day"
            else: kind="school"; cday=cycle; title=f"Day {cycle}"; detail=labels[cycle-1]; source="generated"; cycle=(cycle%len(labels))+1
            counts["school" if kind=="school" else "weekend" if kind=="weekend" else "non_school"]+=1
            rows.append({"profile_id":pid,"day":iso,"kind":kind,"cycle_day":cday,"title":title,"detail":detail,"source":source,"overridden":overridden}); current+=timedelta(days=1)
        return rows,ScheduleSummary(counts["school"],counts["non_school"],counts["weekend"],start,end)
    def rebuild_profile(self,profile="school")->ScheduleSummary:
        p=self._profile(profile); rows,summary=self.preview(profile); self.database.replace_profile_schedule(p["id"],rows); payload=asdict(summary); payload["start"]=summary.start.isoformat(); payload["end"]=summary.end.isoformat(); self.database.audit(p["id"],"schedule_rebuilt",payload); return summary
    def add_snow_day_and_shift(self,profile,day:date,title="Snow Day")->ScheduleSummary:
        p=self._profile(profile); self.database.add_profile_non_school(p["id"],day.isoformat(),"snow_day",title); return self.rebuild_profile(profile)
    def validate(self,profile="school")->list[dict[str,str]]:
        p=self._profile(profile); warnings=[]
        try: rows,_=self.preview(profile)
        except ValueError as exc:return [{"level":"error","message":str(exc)}]
        if len(self.database.cycles(p["id"]))<2:warnings.append({"level":"warning","message":"Cycle has fewer than two entries."})
        overrides=self.database.overrides(p["id"])
        for day,o in overrides.items():
            if day<p["school_year_start"] or day>p["school_year_end"]:warnings.append({"level":"warning","message":f"Override {day} is outside the school year."})
            if o.get("cycle_day") and int(o["cycle_day"])>len(self.database.cycles(p["id"])):warnings.append({"level":"warning","message":f"Override {day} references a cycle day that no longer exists."})
        if not rows:warnings.append({"level":"error","message":"Schedule is empty."})
        return warnings
    def rebuild(self)->ScheduleSummary:
        legacy=self.database.get_settings(); p=self.database.profile("school")
        if p and legacy.get("school_year_start"):
            with self.database._connect() as c:c.execute("UPDATE calendar_profiles SET school_year_start=?,school_year_end=?,starting_cycle_day=?,us_state=? WHERE id=?",(legacy.get("school_year_start",""),legacy.get("school_year_end",""),legacy.get("starting_cycle_day",1),legacy.get("us_state","NH"),p["id"]))
            self.database.set_cycles(p["id"],[legacy.get(f"cycle_day_{i}",f"Day {i}") for i in range(1,6)])
            for r in self.database.list_non_school_days(): self.database.add_profile_non_school(p["id"],r["day"],r["source"])
            with self.database._connect() as c:
                for r in self.database.list_holidays(): c.execute("INSERT INTO profile_holidays(profile_id,day,name) VALUES(?,?,?) ON CONFLICT(profile_id,day) DO UPDATE SET name=excluded.name",(p["id"],r["day"],r["name"]))
        summary=self.rebuild_profile("school"); rows=self.database.profile_schedule(p["id"]); self.database.replace_schedule([{k:r[k] for k in ("day","kind","cycle_day","title","detail","source")} for r in rows]); return summary
    def rows(self,start:date|None=None,end:date|None=None,profile="school"):
        p=self._profile(profile); return self.database.profile_schedule(p["id"],start.isoformat() if start else None,end.isoformat() if end else None)
    def today(self,day:date|None=None,profile="school"):
        target=day or date.today(); rows=self.rows(target,target,profile); return rows[0] if rows else {"day":target.isoformat(),"kind":"outside_school_year","cycle_day":None,"title":"Outside configured school year","detail":"","source":"system","overridden":0}
    def next_school_day(self,after:date|None=None,profile="school"):
        for r in self.rows((after or date.today())+timedelta(days=1),None,profile):
            if r["kind"]=="school":return r
        return None
    def month_grid(self,year:int,month:int,profile="school"):
        cal=MonthCalendar(firstweekday=6); today=date.today(); weeks=[]
        for week in cal.monthdatescalendar(year,month):
            wr=[]
            for d in week: wr.append({"date":d,"iso":d.isoformat(),"in_month":d.month==month,"is_today":d==today,"schedule":self.today(d,profile) if self.rows(d,d,profile) else None})
            weeks.append(wr)
        return {"year":year,"month":month,"weeks":weeks}
    def to_ics(self,profile="school",include_no_school=True,include_weekends=False)->bytes:
        p=self._profile(profile); cal=Calendar(); cal.add("prodid","-//School Cycle Days//Standalone Calendar//EN"); cal.add("version","2.0"); cal.add("calscale","GREGORIAN"); cal.add("x-wr-calname",p["name"])
        for r in self.rows(profile=profile):
            if r["kind"]=="weekend" and not include_weekends:continue
            if r["kind"]=="no_school" and not include_no_school:continue
            e=Event(); d=date.fromisoformat(r["day"]); e.add("dtstart",d); e.add("dtend",d+timedelta(days=1)); e.add("summary",f"{r['title']} ({r['detail']})" if r["kind"]=="school" else r["title"]); e.add("description",r["detail"]); e.add("uid",f"scd-{p['slug']}-{r['day']}@local"); e.add("dtstamp",datetime.utcnow()); cal.add_component(e)
        return cal.to_ical()
