"""Final distributable app composition."""
from __future__ import annotations
import asyncio
import secrets
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from .main import app, database, runtime, schedule, templates
from .notifications import notification_loop
from .product_routes import build_product_router, subscription_refresh_loop
from .review_routes import build_review_router

app.title="School Cycle Days"; app.version="0.4.0"
app.add_middleware(SessionMiddleware,secret_key=runtime.session_secret or secrets.token_urlsafe(32),same_site="lax",https_only=False)
app.include_router(build_product_router(database,schedule,templates)); app.include_router(build_review_router(database,schedule,templates))

PUBLIC_PREFIXES=("/login","/setup-admin","/share/","/calendar/","/api/v1/health","/manifest.webmanifest","/service-worker.js")
@app.middleware("http")
async def optional_auth_guard(request:Request,call_next):
    if runtime.require_login and not request.url.path.startswith(PUBLIC_PREFIXES) and not request.session.get("user_id"):return RedirectResponse("/login",303)
    return await call_next(request)

_refresh_task:asyncio.Task|None=None; _notification_task:asyncio.Task|None=None
@app.on_event("startup")
async def product_startup():
    global _refresh_task,_notification_task
    _refresh_task=asyncio.create_task(subscription_refresh_loop(database,schedule,runtime.source_refresh_seconds)); _notification_task=asyncio.create_task(notification_loop(database,schedule))
@app.on_event("shutdown")
async def product_shutdown():
    for task in (_refresh_task,_notification_task):
        if task:task.cancel()
