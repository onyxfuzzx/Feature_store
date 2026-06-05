from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, features, health, jobs, models, search, users, api_keys
from app.core.config import settings
from app.core.logging import configure_logging
from app.jobs.scheduler import start_scheduler, stop_scheduler

configure_logging()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(features.router)
app.include_router(models.router)
app.include_router(search.router)
app.include_router(jobs.router)
app.include_router(users.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def startup_event():
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()


@app.get("/")
def root():
    return {"name": settings.app_name, "status": "running"}
