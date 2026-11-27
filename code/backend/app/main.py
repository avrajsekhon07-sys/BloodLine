import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, DATABASE_URL, engine
from .routers import (
    auth, inventory, demand, forecast, risk, donors, hospital, requests, screening, admin, donor, reports,
    donations, admin_users, notifications, units, regional, push, evaluation, demo,
)

if os.getenv("BLOODLINE_ENV") == "production":
    secret_key = os.getenv("BLOODLINE_SECRET_KEY", "dev-only-secret-change-me")
    if secret_key in {"dev-only-secret-change-me", "replace-with-output-of-python-secrets-token-url-safe-48"} or len(secret_key) < 32:
        raise RuntimeError("Set a unique BLOODLINE_SECRET_KEY of at least 32 characters before running in production.")
    if os.getenv("BLOODLINE_USE_MIGRATIONS") != "1":
        raise RuntimeError("Set BLOODLINE_USE_MIGRATIONS=1 in production; apply schema changes with Alembic.")
    if DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Production must use persistent PostgreSQL, not container-local SQLite.")

# With BLOODLINE_USE_MIGRATIONS=1 the schema is managed by Alembic (`alembic upgrade head`).
if os.getenv("BLOODLINE_USE_MIGRATIONS") != "1":
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BloodLine API",
    description=(
        "Predictive blood shortage & smart donor matching platform. "
        "Demand data served by this API is SYNTHETIC/SIMULATED and is "
        "clearly labelled as such — see DemandHistory.is_synthetic."
    ),
    version="1.0.0",
)

def configured_origins():
    raw = os.getenv("ALLOWED_ORIGINS")
    production = os.getenv("BLOODLINE_ENV") == "production"
    if production and not raw:
        raise RuntimeError("Set ALLOWED_ORIGINS to the exact HTTPS frontend origin(s) in production.")
    origins = [o.strip() for o in (raw or "*").split(",") if o.strip()]
    if production:
        if not origins:
            raise RuntimeError("Set at least one exact production frontend origin in ALLOWED_ORIGINS.")
        if "*" in origins:
            raise RuntimeError("Wildcard CORS origins are not allowed in production.")
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
                raise RuntimeError("Production ALLOWED_ORIGINS entries must be exact HTTPS origins without paths.")
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(demand.router)
app.include_router(forecast.router)
app.include_router(risk.router)
app.include_router(donors.router)
app.include_router(hospital.router)
app.include_router(requests.router)
app.include_router(screening.router)
app.include_router(admin.router)
app.include_router(donor.router)
app.include_router(reports.router)
app.include_router(donations.router)
app.include_router(admin_users.router)
app.include_router(notifications.router)
app.include_router(units.router)
app.include_router(regional.router)
app.include_router(push.router)
app.include_router(evaluation.router)
app.include_router(demo.router)


@app.get("/health")
def health():
    return {"status": "ok"}
