"""Final distributable app composition.

Imports the compatibility application and layers the product router, sessions,
optional login enforcement, and background source refresh on top.
"""
from __future__ import annotations

import asyncio
import secrets
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .main import app, database, runtime, schedule, templates
from .product_routes import build_product_router, subscription_refresh_loop

app.title="School Cycle Days"
app.version="0.4.0"
app.add_middleware(SessionMiddleware,secret_key=runtime.session_secret or secrets.token_urlsafe(32),same_site="lax",https_only=False)
app.include_router(build_product_router(database,schedule,templates))

PUBLIC_PREFIXES=("/login","/setup-admin","/share/","/calendar/","/api/v1/health","/manifest.webmanifest","/service-worker.js")
@app.middleware("http")
async def optional_auth_guard(request:Request,call_next):
    if runtime.require_login and not request.url.path.startswith(PUBLIC_PREFIXES) and not request.session.get("user_id"):
        return RedirectResponse("/login",303)
    return await call_next(request)

_refresh_task:asyncio.Task|None=None
@app.on_event("startup")
async def start_source_refresh():
    global _refresh_task
    _refresh_task=asyncio.create_task(subscription_refresh_loop(database,schedule,runtime.source_refresh_seconds))

@app.on_event("shutdown")
async def stop_source_refresh():
    if _refresh_task:
        _refresh_task.cancel()
