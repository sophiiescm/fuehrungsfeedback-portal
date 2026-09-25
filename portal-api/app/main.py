import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PYTEST_CURRENT_TEST wird von pytest automatisch gesetzt: Tests bringen ihre
    # eigene isolierte DB mit (siehe tests/conftest.py) und sollen nie die echte,
    # in .env konfigurierte Datenbank anfassen.
    if settings.app_env == "dev" and "PYTEST_CURRENT_TEST" not in os.environ:
        from app.bootstrap_dev_data import ensure_dev_fixture_users

        ensure_dev_fixture_users()
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
