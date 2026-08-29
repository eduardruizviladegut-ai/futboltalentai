"""
Ingesta piloto: Premier League (temporada actual) desde Sofascore.

Uso:
    python -m ingestion.ingest_premier_league

Qué hace:
    1. Llama al endpoint de estadísticas de liga de Sofascore.
    2. Crea/actualiza Competition, Season, Team, Player.
    3. Inserta un nuevo PlayerStatsSnapshot con snapshot_date = hoy.
       (Pensado para correr una vez al mes — sección 5 del doc: la
       actualización no depende de un único partido.)

IDs de Sofascore usados (confirmados a fecha de escritura):
    Premier League -> unique_tournament_id = 17
    Temporada 25/26 -> season_id = 76986
    (Si cambia la temporada, hay que actualizar SEASON_ID_SOFASCORE
     o resolverlo dinámicamente con get_tournament_seasons()).
"""

import sys
import logging
from datetime import date, datetime

sys.path.append(".")  # permite ejecutar como script suelto también

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import DataSource as DS, Competition, Season, Team, Player, PlayerStatsSnapshot
from ingestion.sofascore_client import SofascoreClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_premier_league")

SOURCE_CODE = "sofascore"
TOURNAMENT_ID_SOFASCORE = 17
SEASON_ID_SOFASCORE = 76986
SEASON_NAME = "2025/2026"
COMPETITION_NAME = "Premier League"
COMPETITION_COUNTRY = "England"

# Campos que pedimos a Sofascore — deben existir en attributes_catalog/
# position_attribute_weights para que luego el cálculo de atributos
# los pueda usar (ver app/services/attributes.py).
STAT_FIELDS = [
    "goals", "assists", "expectedGoals", "totalShots", "shotsOnTarget",
    "keyPasses", "accuratePasses", "accuratePassesPercentage",
    "accurateFinalThirdPasses", "bigChancesCreated",
    "successfulDribbles", "successfulDribblesPercentage",
    "groundDuelsWon", "groundDuelsWonPercentage",
    "aerialDuelsWon", "aerialDuelsWonPercentage",
    "totalDuelsWon", "totalDuelsWonPercentage",
    "tackles", "interceptions", "clearances", "dribbledPast",
    "minutesPlayed", "appearances", "rating",
    "saves", "cleanSheets", "goalsConcededInsideTheBox",
]

POSITION_MAP = {
    "G": "GK", "D": "CB", "M": "CM", "F": "ST",
}


def get_or_create_source(db: Session) -> DS:
    source = db.query(DS).filter(DS.code == SOURCE_CODE).one_or_none()
    if not source:
        source = DS(code=SOURCE_CODE, name="Sofascore (API interna, scraping)", is_commercial_ok=False)
        db.add(source)
        db.flush()
    return source


def get_or_create_competition(db: Session, source: DS) -> Competition:
    comp = db.query(Competition).filter(
        Competition.source_id == source.id,
        Competition.external_id == str(TOURNAMENT_ID_SOFASCORE),
    ).one_or_none()
    if not comp:
        comp = Competition(
            source_id=source.id,
            external_id=str(TOURNAMENT_ID_SOFASCORE),
            name=COMPETITION_NAME,
            country=COMPETITION_COUNTRY,
            tier=1,
        )
        db.add(comp)
        db.flush()
    return comp


def get_or_create_season(db: Session, source: DS, competition: Competition) -> Season:
    season = db.query(Season).filter(
        Season.competition_id == competition.id,
        Season.external_id == str(SEASON_ID_SOFASCORE),
    ).one_or_none()
    if not season:
        season = Season(
            competition_id=competition.id,
            source_id=source.id,
            external_id=str(SEASON_ID_SOFASCORE),
            name=SEASON_NAME,
            is_current=True,
        )
        db.add(season)
        db.flush()
    return season


def get_or_create_team(db: Session, source: DS, team_data: dict) -> Team:
    external_id = str(team_data["id"])
    team = db.query(Team).filter(Team.source_id == source.id, Team.external_id == external_id).one_or_none()
    if not team:
        team = Team(
            source_id=source.id,
            external_id=external_id,
            name=team_data.get("name", "Desconocido"),
            short_name=team_data.get("shortName"),
        )
        db.add(team)
        db.flush()
    return team


def get_or_create_player(db: Session, source: DS, player_data: dict, team: Team) -> Player:
    external_id = str(player_data["id"])
    player = db.query(Player).filter(Player.source_id == source.id, Player.external_id == external_id).one_or_none()

    position_raw = player_data.get("position", "M")
    position = POSITION_MAP.get(position_raw, "CM")

    if not player:
        player = Player(
            source_id=source.id,
            external_id=external_id,
            full_name=player_data.get("name", "Desconocido"),
            display_name=player_data.get("shortName") or player_data.get("name", "Desconocido"),
            primary_position=position,
            current_team_id=team.id,
            photo_license_ok=False,  # sin licencia confirmada -> no se muestra foto
        )
        db.add(player)
        db.flush()
    else:
        player.current_team_id = team.id
        player.updated_at = datetime.utcnow()

    return player


def run():
    client = SofascoreClient()
    client.warm_up()
    db = SessionLocal()

    try:
        source = get_or_create_source(db)
        competition = get_or_create_competition(db, source)
        season = get_or_create_season(db, source, competition)
        db.commit()

        today = date.today()
        offset = 0
        total_ingested = 0

        while True:
            log.info(f"Pidiendo stats de Premier League, offset={offset}")
            data = client.get_league_player_statistics(
                tournament_id=TOURNAMENT_ID_SOFASCORE,
                season_id=SEASON_ID_SOFASCORE,
                fields=STAT_FIELDS,
                offset=offset,
            )

            results = data.get("results", [])
            if not results:
                break

            for row in results:
                player_data = row.get("player", {})
                team_data = row.get("team", {})
                if not player_data or not team_data:
                    continue

                team = get_or_create_team(db, source, team_data)
                player = get_or_create_player(db, source, player_data, team)

                raw_stats = {k: v for k, v in row.items() if k in STAT_FIELDS}

                existing = db.query(PlayerStatsSnapshot).filter(
                    PlayerStatsSnapshot.player_id == player.id,
                    PlayerStatsSnapshot.season_id == season.id,
                    PlayerStatsSnapshot.source_id == source.id,
                    PlayerStatsSnapshot.snapshot_date == today,
                    PlayerStatsSnapshot.accumulation_type == "total",
                ).one_or_none()

                if existing:
                    existing.raw_stats = raw_stats
                    existing.matches_played = raw_stats.get("appearances")
                    existing.minutes_played = raw_stats.get("minutesPlayed")
                else:
                    snapshot = PlayerStatsSnapshot(
                        player_id=player.id,
                        season_id=season.id,
                        team_id=team.id,
                        source_id=source.id,
                        snapshot_date=today,
                        accumulation_type="total",
                        raw_stats=raw_stats,
                        matches_played=raw_stats.get("appearances"),
                        minutes_played=raw_stats.get("minutesPlayed"),
                    )
                    db.add(snapshot)

                total_ingested += 1

            db.commit()

            page = data.get("page")
            pages = data.get("pages")
            if page is not None and pages is not None and page >= pages:
                break
            offset += 100

        log.info(f"Ingesta completada. Jugadores procesados: {total_ingested}")

    except Exception:
        db.rollback()
        log.exception("Fallo en la ingesta")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
