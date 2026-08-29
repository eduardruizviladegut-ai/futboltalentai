from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class AttributeOut(BaseModel):
    code: str
    display_name: str
    emoji: Optional[str] = None
    value: float


class PlayerCardOut(BaseModel):
    """Todo lo necesario para pintar una Player Card (sección 3 del doc)."""
    id: UUID
    display_name: str
    team_name: Optional[str] = None
    primary_position: str
    date_of_birth: Optional[date] = None
    photo_url: Optional[str] = None
    overall_rating: Optional[float] = None
    attributes: list[AttributeOut] = []
    period_year: Optional[int] = None
    period_month: Optional[int] = None


class MonthlyPoint(BaseModel):
    period_year: int
    period_month: int
    overall_rating: float


class PlayerEvolutionOut(BaseModel):
    player_id: UUID
    display_name: str
    history: list[MonthlyPoint]


class PlayerSummaryOut(BaseModel):
    id: UUID
    display_name: str
    team_name: Optional[str] = None
    primary_position: str
    overall_rating: Optional[float] = None
    photo_url: Optional[str] = None
