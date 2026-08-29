from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import players

app = FastAPI(
    title="Football Talent AI — API",
    description="API de la plataforma de scouting inteligente Football Talent AI (v1 MVP).",
    version="0.1.0",
)

# En v1 abrimos CORS a cualquier origen; ajustar al dominio real del
# frontend antes de producción.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"project": "Football Talent AI", "status": "v1 MVP en construcción"}
