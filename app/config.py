from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación, leída de variables de entorno.
    En Render, DATABASE_URL se inyecta automáticamente al vincular
    el servicio web con la base de datos PostgreSQL.
    """

    database_url: str = "postgresql://postgres:postgres@localhost:5432/football_talent_ai"
    environment: str = "development"
    formula_version: int = 1  # versión activa de las fórmulas de atributos
    admin_secret: str = "cambia-esto-en-render-2026"  # protege el endpoint de ingesta manual

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
