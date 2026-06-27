"""Reportes de campo: la única capa que se actualiza en tiempo real.

Llamadas, brigadas y redes confirmadas elevan la prioridad de las celdas
cercanas (boost). Se persisten en data/field_reports.csv (versionable).
"""
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from core.geo import haversine_m

ROOT = Path(__file__).resolve().parent.parent
REPORTS_PATH = ROOT / "data" / "field_reports.csv"
COLUMNS = [
    "timestamp", "zona", "lat", "lon", "personas_estimadas",
    "fuente", "confianza", "estado", "nota",
]


def load_reports(path: Path = REPORTS_PATH) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[COLUMNS]


def append_report(row: dict, path: Path = REPORTS_PATH) -> pd.DataFrame:
    row = {**row}
    row.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    df = load_reports(path)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def boost_for_grid(grid: pd.DataFrame, reports: pd.DataFrame,
                   radius_m: float = 300.0) -> np.ndarray:
    """Realce 0-1 por celda según reportes activos cercanos (decae con distancia)."""
    boost = np.zeros(len(grid))
    if reports is None or reports.empty:
        return boost
    active = reports[reports["estado"].fillna("") != "resuelto"]
    for _, r in active.iterrows():
        try:
            d = haversine_m(grid["lat"].values, grid["lon"].values,
                            float(r["lat"]), float(r["lon"]))
        except (TypeError, ValueError):
            continue
        conf = float(r.get("confianza", 0.5) or 0.5)
        contrib = np.where(d <= radius_m * 3, conf * np.exp(-d / radius_m), 0.0)
        boost = np.maximum(boost, contrib)  # el reporte más fuerte domina
    return np.clip(boost, 0.0, 1.0)
