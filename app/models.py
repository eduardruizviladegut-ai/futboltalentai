import uuid
from sqlalchemy import (
    Column, String, SmallInteger, Integer, Numeric, Boolean, Date,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base

PLAYER_POSITIONS = (
    "GK", "CB", "LB", "RB", "LWB", "RWB",
    "CDM", "CM", "CAM", "LM", "RM",
    "LW", "RW", "CF", "ST",
)
PositionEnum = Enum(*PLAYER_POSITIONS, name="player_position")


class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(SmallInteger, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    is_commercial_ok = Column(Boolean, nullable=False, default=False)
    notes = Column(String)


class Team(Base):
    __tablename__ = "teams"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(SmallInteger, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    short_name = Column(String(50))
    country = Column(String(80))
    logo_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("source_id", "external_id"),)


class Competition(Base):
    __tablename__ = "competitions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(SmallInteger, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    country = Column(String(80))
    tier = Column(SmallInteger)
    gender = Column(String(10), default="male")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    seasons = relationship("Season", back_populates="competition")

    __table_args__ = (UniqueConstraint("source_id", "external_id"),)


class Season(Base):
    __tablename__ = "seasons"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    competition_id = Column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(SmallInteger, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(50), nullable=False)
    name = Column(String(50), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    is_current = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    competition = relationship("Competition", back_populates="seasons")

    __table_args__ = (UniqueConstraint("competition_id", "external_id"),)


class Player(Base):
    __tablename__ = "players"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(SmallInteger, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(50), nullable=False)
    full_name = Column(String(150), nullable=False)
    display_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    nationality = Column(String(80))
    primary_position = Column(PositionEnum, nullable=False)
    secondary_positions = Column(ARRAY(String))
    height_cm = Column(SmallInteger)
    preferred_foot = Column(String(10))
    current_team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    photo_url = Column(String)
    photo_license_ok = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team")

    __table_args__ = (UniqueConstraint("source_id", "external_id"),)


class PlayerStatsSnapshot(Base):
    __tablename__ = "player_stats_snapshot"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season_id = Column(UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    source_id = Column(SmallInteger, ForeignKey("data_sources.id"), nullable=False)

    snapshot_date = Column(Date, nullable=False)
    accumulation_type = Column(String(20), nullable=False, default="total")

    raw_stats = Column(JSONB, nullable=False)

    matches_played = Column(SmallInteger)
    minutes_played = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "season_id", "source_id", "snapshot_date", "accumulation_type"),
    )


class AttributeCatalog(Base):
    __tablename__ = "attributes_catalog"
    id = Column(SmallInteger, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    display_name = Column(String(50), nullable=False)
    emoji = Column(String(10))


class PositionAttributeWeight(Base):
    __tablename__ = "position_attribute_weights"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position = Column(PositionEnum, nullable=False)
    attribute_id = Column(SmallInteger, ForeignKey("attributes_catalog.id"), nullable=False)
    stat_field = Column(String(60), nullable=False)
    weight = Column(Numeric(5, 3), nullable=False)
    formula_version = Column(SmallInteger, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("position", "attribute_id", "stat_field", "formula_version"),
    )


class PositionOverallWeight(Base):
    __tablename__ = "position_overall_weights"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position = Column(PositionEnum, nullable=False)
    attribute_id = Column(SmallInteger, ForeignKey("attributes_catalog.id"), nullable=False)
    weight = Column(Numeric(5, 3), nullable=False)
    formula_version = Column(SmallInteger, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("position", "attribute_id", "formula_version"),
    )


class PlayerMonthlyRating(Base):
    __tablename__ = "player_monthly_rating"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season_id = Column(UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    period_year = Column(SmallInteger, nullable=False)
    period_month = Column(SmallInteger, nullable=False)

    overall_rating = Column(Numeric(5, 2), nullable=False)
    formula_version = Column(SmallInteger, nullable=False, default=1)

    based_on_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("player_stats_snapshot.id"))

    matches_played_period = Column(SmallInteger)
    minutes_played_period = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attributes = relationship("PlayerMonthlyAttribute", back_populates="monthly_rating")

    __table_args__ = (
        UniqueConstraint("player_id", "season_id", "period_year", "period_month", "formula_version"),
        CheckConstraint("overall_rating BETWEEN 0 AND 100"),
        CheckConstraint("period_month BETWEEN 1 AND 12"),
    )


class PlayerMonthlyAttribute(Base):
    __tablename__ = "player_monthly_attribute"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monthly_rating_id = Column(UUID(as_uuid=True), ForeignKey("player_monthly_rating.id", ondelete="CASCADE"), nullable=False)
    attribute_id = Column(SmallInteger, ForeignKey("attributes_catalog.id"), nullable=False)
    value = Column(Numeric(5, 2), nullable=False)

    monthly_rating = relationship("PlayerMonthlyRating", back_populates="attributes")
    attribute = relationship("AttributeCatalog")

    __table_args__ = (
        UniqueConstraint("monthly_rating_id", "attribute_id"),
        CheckConstraint("value BETWEEN 0 AND 100"),
    )
