from __future__ import annotations
from datetime import date
from school_cycle_days.database import Database
from school_cycle_days.product_routes import password_hash, verify_password
from school_cycle_days.schedule import ScheduleService
from school_cycle_days.sync_engine import PublicationSyncPlanner


def make_profile(tmp_path,labels=None):
    db=Database(str(tmp_path/"product.sqlite3")); pid=db.create_profile("Test School","test-school","2026-09-01","2026-09-14",cycle_labels=labels or ["A","B","C"]); service=ScheduleService(db); service.rebuild_profile(pid); return db,pid,service

def test_arbitrary_cycle_length(tmp_path):
    db,pid,service=make_profile(tmp_path,["Red","Blue","Green"])
    school=[r for r in service.rows(profile=pid) if r["kind"]=="school"]
    assert [r["detail"] for r in school[:5]]==["Red","Blue","Green","Red","Blue"]

def test_snow_day_shifts_cycle(tmp_path):
    db,pid,service=make_profile(tmp_path,["A","B","C"])
    before={r["day"]:r for r in service.rows(profile=pid)}
    assert before["2026-09-02"]["detail"]=="B"
    service.add_snow_day_and_shift(pid,date(2026,9,2))
    after={r["day"]:r for r in service.rows(profile=pid)}
    assert after["2026-09-02"]["kind"]=="no_school"
    assert after["2026-09-03"]["detail"]=="B"

def test_date_override_can_force_cycle(tmp_path):
    db,pid,service=make_profile(tmp_path)
    db.set_override(pid,"2026-09-03","school",3,"Special C","Assembly")
    service.rebuild_profile(pid); row=service.rows(date(2026,9,3),date(2026,9,3),pid)[0]
    assert row["cycle_day"]==3 and row["overridden"]==1 and row["title"]=="Special C"

def test_recurring_closure_rule(tmp_path):
    db,pid,service=make_profile(tmp_path)
    with db._connect() as c:c.execute("INSERT INTO closure_rules(profile_id,name,weekday,start_date,end_date) VALUES(?,?,?,?,?)",(pid,"Friday off",4,"2026-09-01","2026-09-14"))
    service.rebuild_profile(pid); rows={r["day"]:r for r in service.rows(profile=pid)}
    assert rows["2026-09-04"]["kind"]=="no_school" and rows["2026-09-11"]["kind"]=="no_school"

def test_multiple_profiles_are_independent(tmp_path):
    db,pid,service=make_profile(tmp_path)
    other=db.create_profile("Other School","other","2026-09-01","2026-09-08",cycle_labels=["1","2"]); service.rebuild_profile(other)
    db.add_profile_non_school(pid,"2026-09-02","manual","Closed"); service.rebuild_profile(pid)
    assert service.rows(date(2026,9,2),date(2026,9,2),pid)[0]["kind"]=="no_school"
    assert service.rows(date(2026,9,2),date(2026,9,2),other)[0]["kind"]=="school"

def test_sync_planner_detects_create_update_delete(tmp_path):
    db,pid,service=make_profile(tmp_path); planner=PublicationSyncPlanner(db); rows=service.rows(profile=pid); initial=planner.plan(pid,"test",rows)
    assert len(initial.create)==len(rows)
    first=rows[0]; planner.record(pid,"test",first["day"],"external-1",planner.content_hash(first))
    unchanged=planner.plan(pid,"test",rows); assert any(r["day"]==first["day"] for r in unchanged.unchanged)
    changed=[dict(r) for r in rows]; changed[0]["detail"]="Changed"; plan=planner.plan(pid,"test",changed); assert plan.update[0]["day"]==first["day"]
    without_first=rows[1:]; deleted=planner.plan(pid,"test",without_first); assert deleted.delete[0]["local_day"]==first["day"]

def test_tokens_are_unique_and_resolvable(tmp_path):
    db,pid,service=make_profile(tmp_path); p=db.profile(pid); other=db.create_profile("Other","other"); q=db.profile(other)
    assert p["public_share_token"]!=q["public_share_token"]
    assert db.token_profile(p["public_share_token"])["id"]==pid
    assert db.token_profile(p["ics_token"],"ics_token")["id"]==pid

def test_undo_restores_non_school_state(tmp_path):
    db,pid,service=make_profile(tmp_path); db.add_profile_non_school(pid,"2026-09-02","manual","Closed"); assert "2026-09-02" in db.profile_blocked(pid)
    db.remove_profile_non_school(pid,"2026-09-02"); assert "2026-09-02" not in db.profile_blocked(pid)
    assert db.undo(pid); assert "2026-09-02" in db.profile_blocked(pid)

def test_password_hashing(tmp_path):
    stored=password_hash("correct horse battery staple")
    assert verify_password("correct horse battery staple",stored)
    assert not verify_password("wrong",stored)

def test_validation_warns_about_invalid_override(tmp_path):
    db,pid,service=make_profile(tmp_path,["A","B"]); db.set_override(pid,"2026-09-03","school",9)
    warnings=service.validate(pid); assert any("cycle day" in w["message"] for w in warnings)
