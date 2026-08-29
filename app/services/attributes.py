"""
Cálculo de atributos 0-100 (Ritmo, Tiro, Pase, Regate, Defensa, Físico)
a partir de las stats crudas ingeridas de Sofascore.

Enfoque v1 (simple y transparente, mejorable en el futuro):
  1. Para cada atributo y posición, se toman los stat_field configurados
     en position_attribute_weights (ej. 'tiro' para un ST pesa
     principalmente 'expectedGoals' y 'totalShots').
  2. Cada stat se normaliza 0-100 vía min-max contra el resto de
     jugadores de la MISMA posición en la misma temporada (así un
     central no compite con un delantero en "tiro").
  3. Se combina con los pesos configurados -> valor del atributo.
  4. La media general combina los atributos con position_overall_weights.

No se inventan datos: si un stat_field no existe en raw_stats para un
jugador, simplemente no participa en ese cálculo (se excluye, no se
asume 0), y se registra qué campos faltaron para poder revisarlo.
"""

from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import (
    PlayerStatsSnapshot, PositionAttributeWeight, PositionOverallWeight,
    AttributeCatalog, Player,
)


@dataclass
class AttributeResult:
    code: str
    display_name: str
    emoji: str | None
    value: float


def _minmax_normalize(value: float, min_v: float, max_v: float) -> float:
    if max_v == min_v:
        return 50.0  # sin variación en el grupo: valor neutro
    scaled = (value - min_v) / (max_v - min_v) * 100
    return max(0.0, min(100.0, scaled))


def compute_player_attributes(
    db: Session,
    player: Player,
    season_id,
    snapshot: PlayerStatsSnapshot,
    formula_version: int = 1,
) -> tuple[list[AttributeResult], float | None, list[str]]:
    """
    Devuelve (lista de atributos calculados, media general, avisos).
    Los avisos listan stat_field que faltaban para algún cálculo.
    """
    position = player.primary_position
    warnings: list[str] = []

    # Pesos configurados para esta posición
    weights = db.execute(
        select(PositionAttributeWeight, AttributeCatalog)
        .join(AttributeCatalog, AttributeCatalog.id == PositionAttributeWeight.attribute_id)
        .where(
            PositionAttributeWeight.position == position,
            PositionAttributeWeight.formula_version == formula_version,
            PositionAttributeWeight.is_active.is_(True),
        )
    ).all()

    if not weights:
        warnings.append(f"Sin fórmula configurada para la posición {position}")
        return [], None, warnings

    # Stats crudas de todos los jugadores de la misma posición/temporada,
    # para poder normalizar min-max de forma justa.
    peer_snapshots = db.execute(
        select(PlayerStatsSnapshot, Player)
        .join(Player, Player.id == PlayerStatsSnapshot.player_id)
        .where(
            PlayerStatsSnapshot.season_id == season_id,
            Player.primary_position == position,
            PlayerStatsSnapshot.accumulation_type == snapshot.accumulation_type,
        )
    ).all()

    # Agrupar pesos por atributo
    by_attribute: dict[int, list] = {}
    for w, attr in weights:
        by_attribute.setdefault(attr.id, []).append((w, attr))

    results: list[AttributeResult] = []
    attribute_values: dict[str, float] = {}
    overall_components: dict[int, float] = {}

    for attr_id, weight_rows in by_attribute.items():
        attr = weight_rows[0][1]
        weighted_sum = 0.0
        weight_total = 0.0

        for w, _ in weight_rows:
            field = w.stat_field
            player_val = snapshot.raw_stats.get(field)
            if player_val is None:
                warnings.append(f"Campo '{field}' ausente para {player.display_name}")
                continue

            peer_values = [
                s.raw_stats.get(field)
                for s, _ in peer_snapshots
                if s.raw_stats.get(field) is not None
            ]
            if not peer_values:
                continue

            normalized = _minmax_normalize(float(player_val), min(peer_values), max(peer_values))
            weighted_sum += normalized * float(w.weight)
            weight_total += float(w.weight)

        if weight_total == 0:
            continue

        attribute_value = round(weighted_sum / weight_total, 2)
        attribute_values[attr.code] = attribute_value
        overall_components[attr_id] = attribute_value

        results.append(AttributeResult(
            code=attr.code,
            display_name=attr.display_name,
            emoji=attr.emoji,
            value=attribute_value,
        ))

    # Media general ponderada por posición
    overall_weights = db.execute(
        select(PositionOverallWeight).where(
            PositionOverallWeight.position == position,
            PositionOverallWeight.formula_version == formula_version,
            PositionOverallWeight.is_active.is_(True),
        )
    ).scalars().all()

    overall_rating = None
    if overall_weights:
        weighted_sum, weight_total = 0.0, 0.0
        for ow in overall_weights:
            if ow.attribute_id in overall_components:
                weighted_sum += overall_components[ow.attribute_id] * float(ow.weight)
                weight_total += float(ow.weight)
        if weight_total > 0:
            overall_rating = round(weighted_sum / weight_total, 2)

    return results, overall_rating, warnings
