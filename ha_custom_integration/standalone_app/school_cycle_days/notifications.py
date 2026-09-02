"""Scheduled notification delivery for tomorrow/no-school/cycle reminders."""
from __future__ import annotations
import asyncio
import json
from datetime import date, datetime, timezone
from .adapters import NtfyPublisher, WebhookNotificationPublisher
from .database import Database
from .schedule import ScheduleService

async def deliver_daily_notifications(db:Database,schedule:ScheduleService)->int:
    sent=0
    with db._connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS notification_deliveries(profile_id INTEGER NOT NULL,target_id INTEGER NOT NULL,delivery_key TEXT NOT NULL,sent_at TEXT NOT NULL,PRIMARY KEY(profile_id,target_id,delivery_key))")
    for p in db.profiles():
        tomorrow=schedule.today(date.fromordinal(date.today().toordinal()+1),p["id"])
        next_day=schedule.next_school_day(date.today(),p["id"])
        with db._connect() as c: targets=[dict(r) for r in c.execute("SELECT * FROM notification_targets WHERE profile_id=? AND enabled=1",(p["id"],))]
        for t in targets:
            key=f"{date.today().isoformat()}:tomorrow" 
            with db._connect() as c:
                if c.execute("SELECT 1 FROM notification_deliveries WHERE profile_id=? AND target_id=? AND delivery_key=?",(p["id"],t["id"],key)).fetchone():continue
            cfg=json.loads(t["config"]); pub=NtfyPublisher(cfg["url"],cfg.get("topic",p["slug"]),cfg.get("token","")) if t["kind"]=="ntfy" else WebhookNotificationPublisher(cfg["url"])
            title=f"{p['name']}: tomorrow"
            message=("No school tomorrow"+(f" — {tomorrow['detail']}" if tomorrow.get('detail') else "")) if tomorrow["kind"]=="no_school" else (f"Tomorrow is {tomorrow['title']} — {tomorrow['detail']}" if tomorrow["kind"]=="school" else f"Tomorrow: {tomorrow['title']}")
            await pub.send(title,message,{"tomorrow":tomorrow,"next_school_day":next_day})
            with db._connect() as c:c.execute("INSERT INTO notification_deliveries(profile_id,target_id,delivery_key,sent_at) VALUES(?,?,?,?)",(p["id"],t["id"],key,datetime.now(timezone.utc).isoformat()))
            db.audit(p["id"],"notification_sent",{"target":t["id"],"key":key}); sent+=1
    return sent

async def notification_loop(db:Database,schedule:ScheduleService,interval_seconds:int=3600):
    while True:
        try: await deliver_daily_notifications(db,schedule)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
