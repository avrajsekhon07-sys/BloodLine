from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, inventory, demand, forecast, risk, donors, hospital, requests, screening, admin, donor, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BloodLine API",
    description=(
        "Predictive blood shortage & smart donor matching platform. "
        "Demand data served by this API is SYNTHETIC/SIMULATED and is "
        "clearly labelled as such — see DemandHistory.is_synthetic."
    ),
    version="0.2.0-w6",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local prototype; restrict for staging
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


@app.get("/health")
def health():
    return {"status": "ok"}
