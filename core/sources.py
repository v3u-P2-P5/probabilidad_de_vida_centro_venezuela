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


_MESES_ABREV_ES = ["ene", "feb", "mar", "abr", "may", "jun",
                   "jul", "ago", "sep", "oct", "nov", "dic"]
_MESES_ABREV_EN = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
_MESES_LARGO_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_MESES_LARGO_EN = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]


def fmt_fecha_corta(fecha_iso: str, lang: str = "es") -> str:
    """'2026-07-01' -> '2026-jul-01' (mismo formato en es/en, mes abreviado en el idioma)."""
    try:
        y, m, d = str(fecha_iso).split("-")
        meses = _MESES_ABREV_EN if lang == "en" else _MESES_ABREV_ES
        return f"{y}-{meses[int(m) - 1]}-{d}"
    except (ValueError, IndexError):
        return fecha_iso


def fecha_larga_vet(lang: str = "es") -> str:
    """Fecha actual en VET en prosa: '2 de julio de 2026' (es) / 'July 2, 2026' (en).

    Se recalcula en cada llamada (sin caché): al no fijar un valor, la fecha
    avanza sola a medianoche VET en el próximo render de la página.
    """
    now = datetime.now(VET)
    if lang == "en":
        return f"{_MESES_LARGO_EN[now.month - 1]} {now.day}, {now.year}"
    return f"{now.day} de {_MESES_LARGO_ES[now.month - 1]} de {now.year}"


def layer(nombre: str, url: str, status: str = "ok",
          fetched: datetime | None = None, detalle: str = "",
          nombre_en: str = "") -> dict:
    """Crea un registro de procedencia para una capa de datos."""
    return {
        "nombre": nombre, "nombre_en": nombre_en,
        "url": url, "status": status,
        "fetched": fmt_vet_utc(fetched) if fetched else None,
        "detalle": detalle,
    }
