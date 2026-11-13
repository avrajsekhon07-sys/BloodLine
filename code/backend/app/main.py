import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import (
    auth, inventory, demand, forecast, risk, donors, hospital, requests, screening, admin, donor, reports,
    donations, admin_users, notifications, units, regional, push, evaluation, demo,
)

if os.getenv("BLOODLINE_ENV") == "production" and os.getenv("BLOODLINE_SECRET_KEY", "dev-only-secret-change-me") == "dev-only-secret-change-me":
    raise RuntimeError("Set BLOODLINE_SECRET_KEY before running in production.")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")],  # restrict in staging/production
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
