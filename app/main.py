import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import players
from app.init_db import run_db_init

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


@app.on_event("startup")
def on_startup():
    """
    Carga el esquema de base de datos automáticamente si aún no existe.
    Permite desplegar sin ejecutar psql manualmente.
    """
    try:
        run_db_init()
    except Exception:
        logging.exception("No se pudo inicializar la base de datos automáticamente")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"project": "Football Talent AI", "status": "v1 MVP en construcción"}
