"""SQLite persistence for the standalone School Cycle Days product."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "calendar_entity": "", "us_state": "NH", "school_year_start": "", "school_year_end": "",
    "cycle_day_1": "Day 1", "cycle_day_2": "Day 2", "cycle_day_3": "Day 3",
    "cycle_day_4": "Day 4", "cycle_day_5": "Day 5", "starting_cycle_day": 1,
    "include_no_school_events": False, "include_weekend_events": False,
}

class Database:
    """SQLite repository. Schema changes are additive for easy migration."""
    def __init__(self, path: str) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self._initialize()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

    def _initialize(self) -> None:
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS non_school_days (day TEXT PRIMARY KEY, source TEXT NOT NULL DEFAULT 'manual');
            CREATE TABLE IF NOT EXISTS holiday_days (day TEXT PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS schedule_days (day TEXT PRIMARY KEY, kind TEXT NOT NULL, cycle_day INTEGER, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'generated');

            CREATE TABLE IF NOT EXISTS calendar_profiles (
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
              timezone TEXT NOT NULL DEFAULT 'America/New_York', school_year_start TEXT NOT NULL DEFAULT '',
              school_year_end TEXT NOT NULL DEFAULT '', starting_cycle_day INTEGER NOT NULL DEFAULT 1,
              us_state TEXT NOT NULL DEFAULT 'NH', public_share_token TEXT UNIQUE, ics_token TEXT UNIQUE,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS cycle_definitions (
              profile_id INTEGER NOT NULL, sequence_number INTEGER NOT NULL, label TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(profile_id, sequence_number), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS profile_non_school_days (
              profile_id INTEGER NOT NULL, day TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual', title TEXT NOT NULL DEFAULT 'No School', imported_from TEXT,
              PRIMARY KEY(profile_id, day), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS profile_holidays (
              profile_id INTEGER NOT NULL, day TEXT NOT NULL, name TEXT NOT NULL,
              PRIMARY KEY(profile_id, day), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS schedule_overrides (
              profile_id INTEGER NOT NULL, day TEXT NOT NULL, override_type TEXT NOT NULL, cycle_day INTEGER, title TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(profile_id, day), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS closure_rules (
              id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, name TEXT NOT NULL, weekday INTEGER,
              start_date TEXT, end_date TEXT, nth INTEGER, month INTEGER, enabled INTEGER NOT NULL DEFAULT 1,
              FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS profile_schedule (
              profile_id INTEGER NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, cycle_day INTEGER, title TEXT NOT NULL,
              detail TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'generated', overridden INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(profile_id, day), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS external_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, source_type TEXT NOT NULL, name TEXT NOT NULL,
              url TEXT, include_terms TEXT NOT NULL DEFAULT '["No School"]', exclude_terms TEXT NOT NULL DEFAULT '[]',
              last_checked TEXT, last_hash TEXT, enabled INTEGER NOT NULL DEFAULT 1,
              FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS published_events (
              profile_id INTEGER NOT NULL, provider TEXT NOT NULL, local_day TEXT NOT NULL, external_event_id TEXT NOT NULL, content_hash TEXT NOT NULL,
              PRIMARY KEY(profile_id, provider, local_day), FOREIGN KEY(profile_id) REFERENCES calendar_profiles(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER, created_at TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, created_at TEXT NOT NULL, label TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_targets (
              id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, config TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
            );
            """)
            if not c.execute("SELECT 1 FROM calendar_profiles LIMIT 1").fetchone():
                legacy = self.get_settings()
                c.execute("INSERT INTO calendar_profiles(name,slug,school_year_start,school_year_end,starting_cycle_day,us_state,public_share_token,ics_token) VALUES(?,?,?,?,?,?,?,?)",
                          ("School Calendar","school",legacy.get("school_year_start", ""),legacy.get("school_year_end", ""),int(legacy.get("starting_cycle_day",1)),legacy.get("us_state","NH"),secrets.token_urlsafe(18),secrets.token_urlsafe(18)))
                pid = c.execute("SELECT id FROM calendar_profiles WHERE slug='school'").fetchone()[0]
                for i in range(1,6): c.execute("INSERT INTO cycle_definitions(profile_id,sequence_number,label) VALUES(?,?,?)",(pid,i,legacy.get(f"cycle_day_{i}",f"Day {i}")))
                for r in c.execute("SELECT day,source FROM non_school_days").fetchall(): c.execute("INSERT OR IGNORE INTO profile_non_school_days(profile_id,day,source) VALUES(?,?,?)",(pid,r[0],r[1]))
                for r in c.execute("SELECT day,name FROM holiday_days").fetchall(): c.execute("INSERT OR IGNORE INTO profile_holidays(profile_id,day,name) VALUES(?,?,?)",(pid,r[0],r[1]))

    # Legacy compatibility API
    def get_settings(self) -> dict[str, Any]:
        values=dict(DEFAULT_SETTINGS)
        with self._connect() as c:
            for r in c.execute("SELECT key,value FROM settings"): values[r["key"]]=json.loads(r["value"])
        return values
    def update_settings(self, values: dict[str, Any]) -> None:
        with self._connect() as c: c.executemany("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",[(k,json.dumps(v)) for k,v in values.items()])
    def list_non_school_days(self):
        with self._connect() as c: return [dict(r) for r in c.execute("SELECT day,source FROM non_school_days ORDER BY day")]
    def add_non_school_day(self, day:str, source:str="manual"):
        with self._connect() as c: c.execute("INSERT INTO non_school_days(day,source) VALUES(?,?) ON CONFLICT(day) DO NOTHING",(day,source))
    def delete_non_school_day(self, day:str):
        with self._connect() as c: c.execute("DELETE FROM non_school_days WHERE day=?",(day,))
    def clear_non_school_days(self):
        with self._connect() as c: c.execute("DELETE FROM non_school_days")
    def replace_holidays(self, values):
        with self._connect() as c: c.execute("DELETE FROM holiday_days"); c.executemany("INSERT INTO holiday_days(day,name) VALUES(?,?)",values)
    def clear_holidays(self):
        with self._connect() as c: c.execute("DELETE FROM holiday_days")
    def list_holidays(self):
        with self._connect() as c: return [dict(r) for r in c.execute("SELECT day,name FROM holiday_days ORDER BY day")]
    def blocked_days(self): return {r["day"] for r in self.list_non_school_days()}|{r["day"] for r in self.list_holidays()}
    def holiday_map(self): return {r["day"]:r["name"] for r in self.list_holidays()}
    def replace_schedule(self, rows):
        with self._connect() as c:
            c.execute("DELETE FROM schedule_days"); c.executemany("INSERT INTO schedule_days(day,kind,cycle_day,title,detail,source) VALUES(:day,:kind,:cycle_day,:title,:detail,:source)",rows)
    def list_schedule(self,start=None,end=None):
        q="SELECT day,kind,cycle_day,title,detail,source FROM schedule_days"; vals=[]; clauses=[]
        if start: clauses.append("day>=?"); vals.append(start)
        if end: clauses.append("day<=?"); vals.append(end)
        if clauses:q+=" WHERE "+" AND ".join(clauses)
        with self._connect() as c:return [dict(r) for r in c.execute(q+" ORDER BY day",vals)]
    def schedule_day(self,day):
        with self._connect() as c:
            r=c.execute("SELECT day,kind,cycle_day,title,detail,source FROM schedule_days WHERE day=?",(day,)).fetchone(); return dict(r) if r else None

    # Product API
    def profiles(self):
        with self._connect() as c:return [dict(r) for r in c.execute("SELECT * FROM calendar_profiles ORDER BY name")]
    def profile(self, slug_or_id):
        with self._connect() as c:
            if str(slug_or_id).isdigit(): r=c.execute("SELECT * FROM calendar_profiles WHERE id=?",(int(slug_or_id),)).fetchone()
            else:r=c.execute("SELECT * FROM calendar_profiles WHERE slug=?",(str(slug_or_id),)).fetchone()
            return dict(r) if r else None
    def create_profile(self,name,slug,start="",end="",state="NH",cycle_labels=None):
        with self._connect() as c:
            cur=c.execute("INSERT INTO calendar_profiles(name,slug,school_year_start,school_year_end,us_state,public_share_token,ics_token) VALUES(?,?,?,?,?,?,?)",(name,slug,start,end,state,secrets.token_urlsafe(18),secrets.token_urlsafe(18))); pid=cur.lastrowid
            for i,label in enumerate(cycle_labels or [f"Day {i}" for i in range(1,6)],1):c.execute("INSERT INTO cycle_definitions(profile_id,sequence_number,label) VALUES(?,?,?)",(pid,i,label))
        self.audit(pid,"profile_created",{"name":name,"slug":slug}); return pid
    def cycles(self,pid):
        with self._connect() as c:return [dict(r) for r in c.execute("SELECT sequence_number,label,description FROM cycle_definitions WHERE profile_id=? ORDER BY sequence_number",(pid,))]
    def set_cycles(self,pid,labels):
        with self._connect() as c:
            c.execute("DELETE FROM cycle_definitions WHERE profile_id=?",(pid,)); c.executemany("INSERT INTO cycle_definitions(profile_id,sequence_number,label) VALUES(?,?,?)",[(pid,i,x) for i,x in enumerate(labels,1)])
        self.audit(pid,"cycles_updated",{"labels":labels})
    def profile_blocked(self,pid):
        with self._connect() as c:
            ns={r[0] for r in c.execute("SELECT day FROM profile_non_school_days WHERE profile_id=?",(pid,))}; hs={r[0] for r in c.execute("SELECT day FROM profile_holidays WHERE profile_id=?",(pid,))}
        return ns|hs
    def profile_holiday_map(self,pid):
        with self._connect() as c:return {r[0]:r[1] for r in c.execute("SELECT day,name FROM profile_holidays WHERE profile_id=?",(pid,))}
    def add_profile_non_school(self,pid,day,source="manual",title="No School",imported_from=None):
        self.snapshot(pid,"Before non-school change")
        with self._connect() as c:c.execute("INSERT INTO profile_non_school_days(profile_id,day,source,title,imported_from) VALUES(?,?,?,?,?) ON CONFLICT(profile_id,day) DO UPDATE SET source=excluded.source,title=excluded.title",(pid,day,source,title,imported_from))
        self.audit(pid,"non_school_added",{"day":day,"source":source,"title":title})
    def remove_profile_non_school(self,pid,day):
        self.snapshot(pid,"Before non-school removal")
        with self._connect() as c:c.execute("DELETE FROM profile_non_school_days WHERE profile_id=? AND day=?",(pid,day))
        self.audit(pid,"non_school_removed",{"day":day})
    def overrides(self,pid):
        with self._connect() as c:return {r["day"]:dict(r) for r in c.execute("SELECT * FROM schedule_overrides WHERE profile_id=?",(pid,))}
    def set_override(self,pid,day,otype,cycle_day=None,title="",note=""):
        self.snapshot(pid,"Before override")
        with self._connect() as c:c.execute("INSERT INTO schedule_overrides(profile_id,day,override_type,cycle_day,title,note) VALUES(?,?,?,?,?,?) ON CONFLICT(profile_id,day) DO UPDATE SET override_type=excluded.override_type,cycle_day=excluded.cycle_day,title=excluded.title,note=excluded.note",(pid,day,otype,cycle_day,title,note))
        self.audit(pid,"override_set",{"day":day,"type":otype,"cycle_day":cycle_day})
    def closure_rules(self,pid):
        with self._connect() as c:return [dict(r) for r in c.execute("SELECT * FROM closure_rules WHERE profile_id=? AND enabled=1",(pid,))]
    def replace_profile_schedule(self,pid,rows):
        with self._connect() as c:
            c.execute("DELETE FROM profile_schedule WHERE profile_id=?",(pid,)); c.executemany("INSERT INTO profile_schedule(profile_id,day,kind,cycle_day,title,detail,source,overridden) VALUES(:profile_id,:day,:kind,:cycle_day,:title,:detail,:source,:overridden)",rows)
    def profile_schedule(self,pid,start=None,end=None):
        q="SELECT day,kind,cycle_day,title,detail,source,overridden FROM profile_schedule WHERE profile_id=?"; vals=[pid]
        if start:q+=" AND day>=?"; vals.append(start)
        if end:q+=" AND day<=?"; vals.append(end)
        with self._connect() as c:return [dict(r) for r in c.execute(q+" ORDER BY day",vals)]
    def audit(self,pid,action,payload):
        with self._connect() as c:c.execute("INSERT INTO audit_log(profile_id,created_at,action,payload) VALUES(?,?,?,?)",(pid,datetime.now(timezone.utc).isoformat(),action,json.dumps(payload,default=str)))
    def audit_rows(self,pid,limit=50):
        with self._connect() as c:return [dict(r) for r in c.execute("SELECT * FROM audit_log WHERE profile_id=? ORDER BY id DESC LIMIT ?",(pid,limit))]
    def snapshot(self,pid,label):
        payload={"profile":self.profile(pid),"cycles":self.cycles(pid),"non_school":[],"overrides":self.overrides(pid),"schedule":self.profile_schedule(pid)}
        with self._connect() as c:
            payload["non_school"]=[dict(r) for r in c.execute("SELECT * FROM profile_non_school_days WHERE profile_id=?",(pid,))]
            c.execute("INSERT INTO snapshots(profile_id,created_at,label,payload) VALUES(?,?,?,?)",(pid,datetime.now(timezone.utc).isoformat(),label,json.dumps(payload,default=str)))
            c.execute("DELETE FROM snapshots WHERE profile_id=? AND id NOT IN (SELECT id FROM snapshots WHERE profile_id=? ORDER BY id DESC LIMIT 20)",(pid,pid))
    def undo(self,pid):
        with self._connect() as c:
            r=c.execute("SELECT * FROM snapshots WHERE profile_id=? ORDER BY id DESC LIMIT 1",(pid,)).fetchone()
            if not r:return False
            p=json.loads(r["payload"]); c.execute("DELETE FROM cycle_definitions WHERE profile_id=?",(pid,)); c.executemany("INSERT INTO cycle_definitions(profile_id,sequence_number,label,description) VALUES(?,?,?,?)",[(pid,x["sequence_number"],x["label"],x.get("description","")) for x in p["cycles"]]); c.execute("DELETE FROM profile_non_school_days WHERE profile_id=?",(pid,));
            for x in p["non_school"]: c.execute("INSERT INTO profile_non_school_days(profile_id,day,source,title,imported_from) VALUES(?,?,?,?,?)",(pid,x["day"],x["source"],x.get("title","No School"),x.get("imported_from")))
            c.execute("DELETE FROM schedule_overrides WHERE profile_id=?",(pid,));
            for x in p["overrides"].values(): c.execute("INSERT INTO schedule_overrides(profile_id,day,override_type,cycle_day,title,note) VALUES(?,?,?,?,?,?)",(pid,x["day"],x["override_type"],x.get("cycle_day"),x.get("title",""),x.get("note","")))
            c.execute("DELETE FROM snapshots WHERE id=?",(r["id"],))
        self.audit(pid,"undo",{"snapshot":r["id"]}); return True
    def token_profile(self,token,kind="public_share_token"):
        if kind not in {"public_share_token","ics_token"}:return None
        with self._connect() as c:
            r=c.execute(f"SELECT * FROM calendar_profiles WHERE {kind}=?",(token,)).fetchone(); return dict(r) if r else None
    @staticmethod
    def hash_password(password): return hashlib.sha256(("school-cycle-days:"+password).encode()).hexdigest()
