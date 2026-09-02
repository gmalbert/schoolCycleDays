"""Plan create/update/delete operations for external calendar publishers."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from .database import Database

@dataclass(slots=True)
class SyncPlan:
    create:list[dict[str,Any]]; update:list[dict[str,Any]]; delete:list[dict[str,Any]]; unchanged:list[dict[str,Any]]

class PublicationSyncPlanner:
    def __init__(self,db:Database):self.db=db
    @staticmethod
    def content_hash(row:dict[str,Any])->str:
        stable={k:row.get(k) for k in ("day","kind","cycle_day","title","detail")}; return hashlib.sha256(json.dumps(stable,sort_keys=True).encode()).hexdigest()
    def existing(self,pid:int,provider:str)->dict[str,dict[str,str]]:
        with self.db._connect() as c:return {r["local_day"]:dict(r) for r in c.execute("SELECT * FROM published_events WHERE profile_id=? AND provider=?",(pid,provider))}
    def plan(self,pid:int,provider:str,schedule:list[dict[str,Any]])->SyncPlan:
        existing=self.existing(pid,provider); current={r["day"]:r for r in schedule}; create=[];update=[];delete=[];unchanged=[]
        for day,row in current.items():
            digest=self.content_hash(row); old=existing.get(day)
            if not old:create.append({**row,"content_hash":digest})
            elif old["content_hash"]!=digest:update.append({**row,"content_hash":digest,"external_event_id":old["external_event_id"]})
            else:unchanged.append({**row,"content_hash":digest,"external_event_id":old["external_event_id"]})
        for day,old in existing.items():
            if day not in current:delete.append(old)
        return SyncPlan(create,update,delete,unchanged)
    def record(self,pid:int,provider:str,day:str,external_id:str,digest:str):
        with self.db._connect() as c:c.execute("INSERT INTO published_events(profile_id,provider,local_day,external_event_id,content_hash) VALUES(?,?,?,?,?) ON CONFLICT(profile_id,provider,local_day) DO UPDATE SET external_event_id=excluded.external_event_id,content_hash=excluded.content_hash",(pid,provider,day,external_id,digest))
    def remove(self,pid:int,provider:str,day:str):
        with self.db._connect() as c:c.execute("DELETE FROM published_events WHERE profile_id=? AND provider=? AND local_day=?",(pid,provider,day))
