from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Player, PlayerMonthlyRating, PlayerMonthlyAttribute, AttributeCatalog, Team
from app.schemas import PlayerCardOut, AttributeOut, PlayerEvolutionOut, MonthlyPoint, PlayerSummaryOut

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerSummaryOut])
def list_players(
    q: str | None = Query(None, description="Buscar por nombre"),
    position: str | None = Query(None),
    team_id: UUID | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Listado de jugadores con su última media conocida (si existe)."""
    stmt = select(Player)
    if q:
        stmt = stmt.where(Player.display_name.ilike(f"%{q}%"))
    if position:
        stmt = stmt.where(Player.primary_position == position)
    if team_id:
        stmt = stmt.where(Player.current_team_id == team_id)
    stmt = stmt.limit(limit)

    players = db.execute(stmt).scalars().all()
    out = []
    for p in players:
        latest = db.execute(
            select(PlayerMonthlyRating)
            .where(PlayerMonthlyRating.player_id == p.id)
            .order_by(PlayerMonthlyRating.period_year.desc(), PlayerMonthlyRating.period_month.desc())
            .limit(1)
        ).scalar_one_or_none()
        team_name = p.team.name if p.team else None
        out.append(PlayerSummaryOut(
            id=p.id,
            display_name=p.display_name,
            team_name=team_name,
            primary_position=p.primary_position,
            overall_rating=float(latest.overall_rating) if latest else None,
            photo_url=p.photo_url if p.photo_license_ok else None,
        ))
    return out


@router.get("/{player_id}/card", response_model=PlayerCardOut)
def get_player_card(player_id: UUID, db: Session = Depends(get_db)):
    """
    Datos completos de la Player Card (sección 3 del documento):
    media general, atributos individuales y su tendencia.
    """
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    latest = db.execute(
        select(PlayerMonthlyRating)
        .where(PlayerMonthlyRating.player_id == player_id)
        .order_by(PlayerMonthlyRating.period_year.desc(), PlayerMonthlyRating.period_month.desc())
        .limit(1)
    ).scalar_one_or_none()

    attributes_out: list[AttributeOut] = []
    if latest:
        rows = db.execute(
            select(PlayerMonthlyAttribute, AttributeCatalog)
            .join(AttributeCatalog, AttributeCatalog.id == PlayerMonthlyAttribute.attribute_id)
            .where(PlayerMonthlyAttribute.monthly_rating_id == latest.id)
        ).all()
        attributes_out = [
            AttributeOut(
                code=attr.code,
                display_name=attr.display_name,
                emoji=attr.emoji,
                value=float(val.value),
            )
            for val, attr in rows
        ]

    return PlayerCardOut(
        id=player.id,
        display_name=player.display_name,
        team_name=player.team.name if player.team else None,
        primary_position=player.primary_position,
        date_of_birth=player.date_of_birth,
        photo_url=player.photo_url if player.photo_license_ok else None,
        overall_rating=float(latest.overall_rating) if latest else None,
        attributes=attributes_out,
        period_year=latest.period_year if latest else None,
        period_month=latest.period_month if latest else None,
    )


@router.get("/{player_id}/evolution", response_model=PlayerEvolutionOut)
def get_player_evolution(player_id: UUID, db: Session = Depends(get_db)):
    """Historial mensual de la media general (sección 5 y 7 del documento)."""
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    rows = db.execute(
        select(PlayerMonthlyRating)
        .where(PlayerMonthlyRating.player_id == player_id)
        .order_by(PlayerMonthlyRating.period_year, PlayerMonthlyRating.period_month)
    ).scalars().all()

    history = [
        MonthlyPoint(period_year=r.period_year, period_month=r.period_month, overall_rating=float(r.overall_rating))
        for r in rows
    ]

    return PlayerEvolutionOut(player_id=player.id, display_name=player.display_name, history=history)
