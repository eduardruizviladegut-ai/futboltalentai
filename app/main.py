import logging

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.routers import players
from app.init_db import run_db_init
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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


@app.post("/admin/ingest/premier-league")
def trigger_premier_league_ingestion(background_tasks: BackgroundTasks, secret: str):
    """
    Dispara la ingesta de la Premier League desde Sofascore en segundo
    plano. Pensado como botón temporal para arrancar la v1 sin usar
    terminal local — protegido con un secreto simple (variable de
    entorno ADMIN_SECRET en Render).

    Uso: POST a
    /admin/ingest/premier-league?secret=TU_SECRETO
    El progreso se ve en la pestaña Logs de Render.
    """
    if secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Secreto inválido")

    def _run_safe():
        try:
            from ingestion.ingest_premier_league import run
            run()
        except Exception:
            logging.exception("La ingesta de Premier League falló")

    background_tasks.add_task(_run_safe)
    return {
        "status": "ingesta iniciada en segundo plano",
        "nota": "revisa la pestaña Logs de Render para ver el progreso (puede tardar varios minutos)",
    }


@app.get("/")
def root():
    return {"project": "Football Talent AI", "status": "v1 MVP en construcción"}
