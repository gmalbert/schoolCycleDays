"""Security-management routes for share and subscription tokens."""
from __future__ import annotations
import secrets
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from .database import Database

def build_security_router(db:Database)->APIRouter:
    router=APIRouter()
    @router.post("/profile/{profile}/tokens/rotate-share")
    async def rotate_share(profile:str):
        p=db.profile(profile)
        if not p:raise HTTPException(404,"Profile not found")
        token=secrets.token_urlsafe(18)
        with db._connect() as c:c.execute("UPDATE calendar_profiles SET public_share_token=? WHERE id=?",(token,p["id"]))
        db.audit(p["id"],"share_token_rotated",{}); return RedirectResponse(f"/profile/{p['id']}?message=Read-only+share+link+rotated",303)
    @router.post("/profile/{profile}/tokens/rotate-ics")
    async def rotate_ics(profile:str):
        p=db.profile(profile)
        if not p:raise HTTPException(404,"Profile not found")
        token=secrets.token_urlsafe(18)
        with db._connect() as c:c.execute("UPDATE calendar_profiles SET ics_token=? WHERE id=?",(token,p["id"]))
        db.audit(p["id"],"ics_token_rotated",{}); return RedirectResponse(f"/profile/{p['id']}?message=ICS+subscription+token+rotated",303)
    return router
