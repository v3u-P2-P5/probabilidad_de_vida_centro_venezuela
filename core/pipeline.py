"""Ensambla todas las capas y calcula el índice de prioridad por celda."""
from datetime import datetime, timezone
import pandas as pd

from core import scoring
from core.geo import make_grid
from core.population import generate_zone_population, population_present
from core.data_sources import get_sismo, synthetic_mmi
from core.reports import load_reports, boost_for_grid


def _parse_iso(s: str) -> datetime:
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def hours_since(sismo: dict, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return max((now - _parse_iso(sismo["origen_iso"])).total_seconds() / 3600.0, 0.0)


def quake_local_hour(sismo: dict) -> float:
    """Hora local (según el offset del ISO) en que ocurrió el sismo."""
    t = _parse_iso(sismo["origen_iso"])
    return t.hour + t.minute / 60.0


def build_zone(zone: dict, config: dict, now: datetime | None = None):
    """Devuelve (df_celdas_con_score, sismo, horas_transcurridas)."""
    sismo = get_sismo(config)
    grid = make_grid(zone["bbox"], config["rejilla"]["tamano_celda_m"])
    df = generate_zone_population(zone, grid)

    df["mmi"] = synthetic_mmi(df["lat"].values, df["lon"].values, sismo)
    df["pop_present"] = population_present(
        df["base_pop"].values, df["uso"].iloc[0], quake_local_hour(sismo)
    )
    df["pop_norm"] = scoring.normalize(df["pop_present"].values)

    reports = load_reports()
    if not reports.empty:
        reports = reports[reports["zona"] == zone["id"]]
    df["boost"] = boost_for_grid(df, reports)

    hs = hours_since(sismo, now)
    df["score"] = scoring.life_probability(
        df["mmi"].values, df["vuln"].values, df["void"].values,
        df["pop_norm"].values, hs, config["pesos"], df["boost"].values,
    )
    df["score_norm"] = scoring.normalize(df["score"].values)
    df["prioridad"] = scoring.priority_category(df["score_norm"].values)
    return df, sismo, hs
