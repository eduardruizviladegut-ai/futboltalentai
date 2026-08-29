from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# Render entrega a veces URLs con el esquema "postgres://" (heredado de
# Heroku); SQLAlchemy 2.x requiere "postgresql://".
db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
