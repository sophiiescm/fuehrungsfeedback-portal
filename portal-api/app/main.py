import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health, organisation, surveys
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

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(organisation.router)
app.include_router(surveys.router)
