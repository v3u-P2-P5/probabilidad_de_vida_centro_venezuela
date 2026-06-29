"""Traducción es/en. Español por defecto."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "locales"
IDIOMAS = {"es": "Español", "en": "English"}
_cache: dict[str, dict] = {}


def load_locale(lang: str) -> dict:
    if lang not in _cache:
        p = LOCALES / f"{lang}.json"
        if not p.exists():
            lang, p = "es", LOCALES / "es.json"
        with open(p, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def t(key: str, lang: str = "es", **kwargs) -> str:
    """Traduce una clave; admite formato con kwargs. Devuelve la clave si falta."""
    s = load_locale(lang).get(key, key)
    return s.format(**kwargs) if kwargs else s


def fuente_nombre(f: dict, lang: str) -> str:
    """Display name for a data source in the given language."""
    if lang == "en":
        return f.get("nombre_en") or f.get("nombre", "")
    return f.get("nombre", "")


def fmt_int(n, lang: str = "es") -> str:
    """Entero con separador de millar según idioma: 1.719 (es) / 1,719 (en).

    Evita mostrar 'Población 1,719' (formato inglés) junto a 'Fallecidos 1.719'
    (formato español) en la misma pantalla.
    """
    try:
        s = f"{int(round(float(n))):,}"
    except (TypeError, ValueError):
        return "—"
    return s.replace(",", ".") if lang == "es" else s
