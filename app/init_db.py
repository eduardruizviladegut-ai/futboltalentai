"""
Inicialización automática de la base de datos.

Pensado para poder desplegar sin usar psql en local: al arrancar el
backend (evento 'startup' de FastAPI), se comprueba si el esquema ya
existe (tabla 'players'). Si no existe, se ejecutan schema.sql y
seed_formulas.sql directamente contra DATABASE_URL.

Es idempotente: en arranques posteriores, al detectar que la tabla
'players' ya existe, no vuelve a ejecutar nada.
"""

import logging
from pathlib import Path
import psycopg2

from app.config import settings

log = logging.getLogger("init_db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
SEED_PATH = PROJECT_ROOT / "db" / "seed_formulas.sql"


def _get_raw_connection():
    db_url = settings.database_url
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url)


def run_db_init() -> None:
    conn = _get_raw_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("SELECT to_regclass('players')")
        already_exists = cur.fetchone()[0] is not None

        if already_exists:
            log.info("El esquema ya existe (tabla 'players' encontrada). No se hace nada.")
            return

        log.info("Tabla 'players' no encontrada. Cargando schema.sql ...")
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        log.info("schema.sql cargado correctamente.")

        log.info("Cargando seed_formulas.sql ...")
        cur.execute(SEED_PATH.read_text(encoding="utf-8"))
        log.info("seed_formulas.sql cargado correctamente. Base de datos lista.")

    finally:
        cur.close()
        conn.close()
