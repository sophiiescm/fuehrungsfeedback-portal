import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import access, actions, report_layout, dev, auth, feedbacks, health, notifications, organisation, reports, rounds, surveys
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PYTEST_CURRENT_TEST wird von pytest automatisch gesetzt: Tests bringen ihre
    # eigene isolierte DB mit (siehe tests/conftest.py) und sollen nie die echte,
    # in .env konfigurierte Datenbank anfassen, und keinen Scheduler starten.
    is_test = "PYTEST_CURRENT_TEST" in os.environ
    if settings.app_env == "dev" and not is_test:
        from app.bootstrap_dev_data import ensure_dev_fixture_users

        ensure_dev_fixture_users()

    if not is_test:
        from app.db import SessionLocal
        from app.services.permissions import ensure_default_roles

        with SessionLocal() as _db:
            ensure_default_roles(_db)

    if not is_test:
        from app.bootstrap_mail_templates import ensure_default_mail_templates

        ensure_default_mail_templates()

    if not is_test:
        from app.services.scheduler import start_scheduler, stop_scheduler

        start_scheduler()
        yield
        stop_scheduler()
    else:
        yield


app = FastAPI(title="Fuehrungsfeedback Portal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.app_env != "dev":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(organisation.router)
app.include_router(surveys.router)
app.include_router(rounds.router)
app.include_router(reports.router)
app.include_router(reports.admin_router)
app.include_router(access.router)
app.include_router(report_layout.router)
app.include_router(dev.router)
app.include_router(actions.router)
app.include_router(feedbacks.router)
app.include_router(notifications.router)
app.include_router(notifications.mail_template_router)
