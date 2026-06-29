"""Construye el "context pack" factual del asistente: SOLO datos reales de la app.

Reúne, de las MISMAS fuentes que muestra la UI (sin duplicar literales ni
inventar nada):
  - Evento(s) USGS, alerta PAGER, horas transcurridas.
  - Por zona: intensidad MMI, población residente, barrios más intensos y
    recursos OSM (hospitales, bomberos, refugios) con teléfono/área.
  - Cifras oficiales y daños materiales (verbatim, con fuente + fecha + URL).
  - Canales oficiales de reunificación familiar (CICR, Cruz Roja, etc.).
Las capas no disponibles se marcan "NO DISPONIBLE" explícitamente, nunca se omiten.
"""
import streamlit as st

from core.config import load_config
from core.i18n import fuente_nombre
from core.relief import get_gdacs
from core.sources import fmt_vet_utc, parse_iso
from core.ui import _cached_zone

# Claves de fuentes para buscar/registrar familiares (orden de prioridad).
_REUNIFICACION = (
    "icrc_rfl", "icrc_trace_face", "cruz_roja_venezolana",
    "desaparecidos_terremoto_ve", "localiza_pacientes", "pacientes_terremoto_vzla",
)


def reunification_links(config: dict, lang: str = "es") -> list:
    """Lista [(nombre, url)] de canales oficiales de reunificación familiar."""
    f = config.get("fuentes", {})
    return [(fuente_nombre(f[k], lang), f[k]["url"]) for k in _REUNIFICACION if k in f]


def _event_block(ctx: dict) -> str:
    s = ctx.get("sismo", {}) or {}
    out = []
    hora = ""
    if s.get("origen_iso"):
        try:
            hora = fmt_vet_utc(parse_iso(s["origen_iso"]))
        except Exception:
            hora = s.get("origen_iso", "")
    out.append(f"- Evento principal: {s.get('id','?')} M{s.get('magnitud','?')}, "
               f"epicentro {s.get('lugar','?')}, profundidad {s.get('profundidad_km','?')} km, "
               f"hora {hora or '?'}.")
    for a in ctx.get("sismos_adicionales", []) or []:
        out.append(f"- Evento secundario: {a.get('id','?')} M{a.get('magnitud','?')}, "
                   f"epicentro {a.get('lugar','?')}.")
    if ctx.get("alert_pager"):
        out.append(f"- Alerta USGS PAGER: {str(ctx['alert_pager']).upper()}.")
    out.append(f"- Horas desde el sismo: {ctx.get('hours_since', 0):.0f} h. "
               f"Datos actualizados: {ctx.get('updated_at', '')}.")
    return "\n".join(out)


def _zone_block(zone: dict, ctx: dict) -> str:
    out = [f"### Zona: {zone['nombre']} (id: {zone['id']})"]
    mmi = ctx.get("mmi_max")
    pob = ctx.get("poblacion_total")
    out.append(f"- Intensidad máxima MMI (USGS ShakeMap): {mmi:.1f}"
               if mmi is not None else "- Intensidad MMI: NO DISPONIBLE")
    out.append(f"- Población residente (WorldPop): {int(pob):,}"
               if pob is not None else "- Población residente: NO DISPONIBLE")

    areas = (ctx.get("areas") or [])[:8]
    if areas:
        out.append("- Barrios/sectores más intensos:")
        for a in areas:
            extra = ""
            if a.get("liquefaccion_max"):
                extra += f", licuefacción {a['liquefaccion_max'] * 100:.0f}%"
            if a.get("deslizamiento_max"):
                extra += f", deslizamiento {a['deslizamiento_max'] * 100:.0f}%"
            out.append(f"    · {a.get('area','?')}: MMI {a.get('mmi_max', 0):.1f}, "
                       f"población {int(a.get('poblacion', 0)):,}{extra}")

    res = ctx.get("resources")
    if res is not None and not getattr(res, "empty", True):
        out.append(f"- Recursos de ayuda (OpenStreetMap): {len(res)} mapeados. Ejemplos:")
        for _, r in res.head(10).iterrows():
            tel = f", tel {r.get('telefono')}" if r.get("telefono") else ""
            area = f" [{r.get('area')}]" if r.get("area") else ""
            out.append(f"    · {r.get('etiqueta', '')}: {r.get('nombre', '')}{area}{tel}")
    else:
        out.append("- Recursos de ayuda (OSM): NO DISPONIBLE o sin resultados.")
    return "\n".join(out)


def _figures_block(config: dict) -> str:
    out = ["## Cifras oficiales (citar SIEMPRE fuente y fecha; PROHIBIDO estimar/sumar):"]
    for c in config.get("cifras_oficiales", []) or []:
        bits = []
        for k, lbl in (("fallecidos", "fallecidos"), ("heridos", "heridos"),
                       ("desaparecidos", "desaparecidos")):
            if c.get(k):
                bits.append(f"{lbl} {c[k]}")
        if c.get("notas"):
            bits.append(c["notas"])
        out.append(f"- {c.get('fuente','')} ({c.get('fecha','')}): "
                   f"{', '.join(bits) or '—'}. URL: {c.get('url','')}")
    for d in config.get("danos_materiales", []) or []:
        out.append(f"- Daños materiales: {d.get('texto','')} — {d.get('fuente','')} "
                   f"({d.get('fecha','')}). URL: {d.get('url','')}")
    return "\n".join(out)


def _links_block(config: dict, lang: str) -> str:
    out = ["## Canales oficiales para BUSCAR/REGISTRAR familiares "
           "(derivar aquí; NUNCA afirmar paradero ni estado de una persona):"]
    for nombre, url in reunification_links(config, lang):
        out.append(f"- {nombre}: {url}")
    return "\n".join(out)


@st.cache_data(ttl=300, show_spinner=False)
def build_chat_context(lang: str = "es") -> str:
    """Devuelve el bloque de CONTEXTO factual (texto) para el system prompt."""
    config = load_config()
    salt = config.get("autorefresco_segundos", 0)

    zone_blocks, event_done, event_txt = [], False, ""
    for z in config["zonas"]:
        try:
            _, ctx = _cached_zone(z["id"], salt)   # with_osm=True → reusa caché de la página de zona
        except Exception:
            zone_blocks.append(f"### Zona: {z['nombre']} (id: {z['id']})\n- Datos: NO DISPONIBLE.")
            continue
        if not event_done:
            event_txt = _event_block(ctx)
            event_done = True
        zone_blocks.append(_zone_block(z, ctx))

    gd = get_gdacs(config)
    gdacs_txt = ""
    if gd.get("alertlevel"):
        gdacs_txt = (f"\n## GDACS: alerta {gd['alertlevel']}"
                     + (f", severidad {gd['severity']}" if gd.get("severity") else "")
                     + f". URL: {gd.get('url','')}")

    parts = [
        "## Evento sísmico (USGS — oficial):",
        event_txt or "- NO DISPONIBLE.",
        gdacs_txt.strip(),
        "",
        "## Datos por zona (las ÚNICAS 4 zonas cubiertas por esta app):",
        "\n\n".join(zone_blocks),
        "",
        _figures_block(config),
        "",
        _links_block(config, lang),
    ]
    return "\n".join(p for p in parts if p)
