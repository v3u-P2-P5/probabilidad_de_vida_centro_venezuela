"""Procedencia de datos: tiempo y trazabilidad de cada capa.

Toda métrica que se muestra debe poder citar su fuente, enlace oficial y hora
de obtención (VET principal, UTC entre paréntesis), en formato ISO militar.
"""
from datetime import datetime, timezone, timedelta

VET = timezone(timedelta(hours=-4))


def parse_iso(s) -> datetime:
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def fmt_vet_utc(dt: datetime | None = None) -> str:
    """'YYYY-MM-DDTHH:MM (VET) / YYYY-MM-DDTHH:MMZ (UTC)'."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (f"{dt.astimezone(VET):%Y-%m-%dT%H:%M} (VET) / "
            f"{dt.astimezone(timezone.utc):%Y-%m-%dT%H:%M}Z (UTC)")


def layer(nombre: str, url: str, status: str = "ok",
          fetched: datetime | None = None, detalle: str = "") -> dict:
    """Crea un registro de procedencia para una capa de datos."""
    return {
        "nombre": nombre, "url": url, "status": status,
        "fetched": fmt_vet_utc(fetched) if fetched else None,
        "detalle": detalle,
    }
