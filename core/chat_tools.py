"""Skills (tool-calling) del asistente: traen DATOS REALES de la app en vivo.

Cada wrapper delega en una función YA EXISTENTE de core/ (no duplica lógica de
datos) y devuelve SIEMPRE un dict con: disponible (bool), los datos, fuente, url
y hora_consulta. Si el dato no está, disponible=False y números/listas vacíos —
NUNCA se inventa. dispatch() valida los argumentos del modelo antes de ejecutar y
captura cualquier error para que el bucle agéntico no se rompa.
"""
import math
from datetime import datetime, timezone

from core.chat_context import reunification_links
from core.config import get_zone, load_config
from core.data_sources import get_aftershock_resumen, get_aftershocks, get_sismo
from core.geo import CIUDADES_REF, haversine_m
from core.osm import KIND_ORDER, assign_areas, fetch_resources
from core.relief import get_gdacs, get_reliefweb_reports
from core.safety_tips import (SAFETY_TIPS, TELEFONOS_EMERGENCIA, TEMA_INDICE,
                              TEMA_INVERSO)
from core.ui import _cached_zone

ZONE_IDS = ["libertador", "sucre_petare", "baruta_hatillo", "la_guaira"]
_INE_URL = ("https://www.ine.gov.ve/index.php/estadisticas-sociales/"
            "demograficas-y-vitales/censo-de-poblacion-y-vivienda")
_OSM_FUENTE = "OpenStreetMap (© colaboradores OSM)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(v):
    """numpy/NaN → float|None nativo (para serializar a JSON sin sorpresas)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if math.isnan(f) else f


def _ctx(zona):
    cfg = load_config()
    z = get_zone(cfg, zona)                       # KeyError si zona no existe
    _, ctx = _cached_zone(zona, cfg.get("autorefresco_segundos", 0), with_osm=False)
    return cfg, z, ctx


# ── Skills: evento y réplicas (USGS en vivo) ──────────────────────────────────
def get_aftershocks_recientes(dias_atras=3, min_magnitud=2.5, radio_km=200, limite=20):
    return get_aftershocks(dias_atras=int(dias_atras), min_magnitud=float(min_magnitud),
                           radio_km=int(radio_km), limite=int(limite))


def get_aftershock_resumen_skill(dias_atras=7, min_magnitud=2.5, radio_km=200):
    return get_aftershock_resumen(dias_atras=int(dias_atras),
                                  min_magnitud=float(min_magnitud), radio_km=int(radio_km))


# ── Skills: por zona (ShakeMap + WorldPop + ground-failure) ───────────────────
def get_zone_summary(zona):
    cfg, z, ctx = _ctx(zona)
    pop_src = ctx.get("pop_src")
    pop_url = cfg["fuentes"]["worldpop"]["url"] if pop_src != "censo_ine" else _INE_URL
    return {
        "disponible": bool(ctx.get("shakemap_ok") or ctx.get("pop_available")),
        "zona_id": zona, "zona_nombre": z["nombre"],
        "mmi_max": _num(ctx.get("mmi_max")), "mmi_disponible": bool(ctx.get("shakemap_ok")),
        "poblacion_residente": (int(ctx["poblacion_total"])
                                if ctx.get("poblacion_total") is not None else None),
        "poblacion_fuente": pop_src, "poblacion_disponible": bool(ctx.get("pop_available")),
        "peligro_suelo_por_celda": bool(ctx.get("gf_cell")),
        "fuente": {"intensidad": "USGS ShakeMap (MMI máx combinada M7.5+M7.2)",
                   "poblacion": ("Censo INE Venezuela 2011" if pop_src == "censo_ine"
                                 else "WorldPop")},
        "url": {"intensidad": cfg["fuentes"]["usgs_shakemap"]["url"], "poblacion": pop_url},
        "hora_consulta": ctx.get("updated_at") or _now(),
        "nota": "MMI = envolvente máxima celda a celda de ambos ShakeMaps.",
    }


def get_zone_top_areas(zona, ordenar_por="mmi", limite=8):
    cfg, z, ctx = _ctx(zona)
    areas = ctx.get("areas") or []
    keymap = {"mmi": "mmi_max", "poblacion": "poblacion",
              "licuefaccion": "liquefaccion_max", "deslizamiento": "deslizamiento_max"}
    key = keymap.get(ordenar_por, "mmi_max")
    nota = ""
    if areas and key not in areas[0]:
        nota = f"'{ordenar_por}' no disponible en esta zona; ordenado por intensidad."
        key = "mmi_max"
    ordered = sorted(areas, key=lambda a: (a.get(key) if a.get(key) is not None else -1),
                     reverse=True)[:int(limite)]
    out = [{"sector": a.get("area"), "mmi_max": _num(a.get("mmi_max")),
            "mmi_medio": _num(a.get("mmi_mean")), "poblacion": int(a.get("poblacion") or 0),
            "licuefaccion_max": _num(a.get("liquefaccion_max")),
            "deslizamiento_max": _num(a.get("deslizamiento_max"))} for a in ordered]
    return {
        "disponible": bool(ctx.get("shakemap_ok") and out), "zona_id": zona,
        "zona_nombre": z["nombre"], "ordenado_por": ordenar_por, "areas": out, "nota": nota,
        "fuente": {"intensidad": "USGS ShakeMap",
                   "peligro_suelo": "USGS Ground Failure (Zhu 2017 / Jessee 2018)",
                   "sectores": "WorldPop + OSM (data/population_cells.csv)"},
        "url": {"intensidad": cfg["fuentes"]["usgs_shakemap"]["url"],
                "peligro_suelo": cfg["fuentes"]["usgs_ground_failure"]["url"]},
        "hora_consulta": ctx.get("updated_at") or _now(),
    }


# ── Skills: recursos de ayuda (OSM en vivo) ───────────────────────────────────
def _resources_df(cfg, z):
    df = fetch_resources(tuple(z["bbox"]), cfg["fuentes"]["osm"]["overpass"],
                         ttl=cfg.get("osm_ttl_segundos", 1800))
    return df


def list_help_resources(zona, tipo="todos", limite=15):
    cfg = load_config(); z = get_zone(cfg, zona)
    osm_url = cfg["fuentes"]["osm"]["url"]
    df = _resources_df(cfg, z)
    if df.attrs.get("error") or df.empty:
        return {"disponible": False, "zona_id": zona, "tipo": tipo, "total": 0,
                "recursos": [], "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}
    df = assign_areas(df, z["bbox"])
    if tipo != "todos":
        df = df[df["tipo"] == tipo]
    df = df.head(int(limite))
    recursos = [{"nombre": r["nombre"], "tipo": r["tipo"], "etiqueta": r["etiqueta"],
                 "etiqueta_en": r.get("etiqueta_en", ""), "lat": _num(r["lat"]),
                 "lon": _num(r["lon"]), "telefono": r.get("telefono", "") or "",
                 "direccion": r.get("direccion", "") or "", "web": r.get("web", "") or "",
                 "area": r.get("area", "") or ""} for _, r in df.iterrows()]
    return {"disponible": True, "zona_id": zona, "tipo": tipo, "total": len(recursos),
            "recursos": recursos, "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}


def find_nearest_resource(zona, lat, lon, tipo="todos", top_n=3):
    cfg = load_config(); z = get_zone(cfg, zona)
    osm_url = cfg["fuentes"]["osm"]["url"]
    lon_min, lat_min, lon_max, lat_max = z["bbox"]
    if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
        return {"disponible": False, "origen": {"lat": lat, "lon": lon},
                "nota": "coordenada fuera de la zona indicada", "resultados": [],
                "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}
    df = _resources_df(cfg, z)
    if df.attrs.get("error") or df.empty:
        return {"disponible": False, "origen": {"lat": lat, "lon": lon}, "resultados": [],
                "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}
    df = assign_areas(df, z["bbox"]).copy()
    df["distancia_m"] = [int(round(float(haversine_m(lat, lon, r.lat, r.lon))))
                         for r in df.itertuples()]
    if tipo != "todos":
        df = df[df["tipo"] == tipo]
    df = df.sort_values("distancia_m").head(int(top_n))
    resultados = [{"nombre": r["nombre"], "tipo": r["tipo"], "etiqueta": r["etiqueta"],
                   "etiqueta_en": r.get("etiqueta_en", ""), "lat": _num(r["lat"]),
                   "lon": _num(r["lon"]), "distancia_m": int(r["distancia_m"]),
                   "telefono": r.get("telefono", "") or "", "direccion": r.get("direccion", "") or "",
                   "web": r.get("web", "") or "", "area": r.get("area", "") or ""}
                  for _, r in df.iterrows()]
    return {"disponible": True, "origen": {"lat": lat, "lon": lon}, "tipo": tipo,
            "resultados": resultados, "fuente": _OSM_FUENTE + " + haversine local",
            "url": osm_url, "hora_consulta": _now()}


def count_resources_by_type(zona):
    cfg = load_config(); z = get_zone(cfg, zona)
    osm_url = cfg["fuentes"]["osm"]["url"]
    df = _resources_df(cfg, z)
    if df.attrs.get("error"):
        return {"disponible": False, "zona_id": zona, "conteo": {k: 0 for k in KIND_ORDER},
                "total": 0, "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}
    vc = df["tipo"].value_counts() if not df.empty else {}
    conteo = {k: int(vc.get(k, 0)) for k in KIND_ORDER}
    return {"disponible": True, "zona_id": zona, "conteo": conteo,
            "total": int(sum(conteo.values())),
            "nota": "Conteo de recursos MAPEADOS en OSM, no inventario oficial.",
            "fuente": _OSM_FUENTE, "url": osm_url, "hora_consulta": _now()}


# ── Skills: cifras oficiales y daños (config.yaml verbatim) ───────────────────
def get_official_casualty_figures(metrica="todas"):
    cfg = load_config()
    items = cfg.get("cifras_oficiales") or []
    if metrica != "todas":
        items = [c for c in items if c.get(metrica)]
    entradas = [{"fuente": c.get("fuente"), "fecha": c.get("fecha"), "url": c.get("url"),
                 "fallecidos": c.get("fallecidos"), "heridos": c.get("heridos"),
                 "desaparecidos": c.get("desaparecidos"), "notas": c.get("notas")} for c in items]
    return {"disponible": len(entradas) > 0, "entradas": entradas,
            "aviso": "Cifras preliminares; varían por fuente. PROHIBIDO sumar o reconciliar entre fuentes.",
            "fuente": "config.yaml: cifras_oficiales (citadas verbatim)",
            "url": "https://reliefweb.int/disaster/eq-2026-000093-ven", "hora_consulta": _now()}


def get_material_damage_reports():
    cfg = load_config()
    reportes = [{"texto": d.get("texto"), "fuente": d.get("fuente"), "fecha": d.get("fecha"),
                 "url": d.get("url")} for d in (cfg.get("danos_materiales") or [])]
    return {"disponible": len(reportes) > 0, "reportes": reportes,
            "aviso": "Reportes preliminares y atribuidos; muchas cifras son estimaciones satelitales.",
            "fuente": "config.yaml: danos_materiales (citados verbatim)",
            "url": cfg["fuentes"].get("copernicus_emsr884", {}).get("url", ""), "hora_consulta": _now()}


def get_missing_persons_count():
    cfg = load_config()
    cifras = [{"desaparecidos": c["desaparecidos"], "fuente": c.get("fuente"),
               "fecha": c.get("fecha"), "url": c.get("url")}
              for c in (cfg.get("cifras_oficiales") or []) if c.get("desaparecidos")]
    return {"disponible": len(cifras) > 0, "cifras": cifras,
            "lista_nombres_publica": bool(cfg.get("desaparecidos")),
            "aviso": ("Cifra agregada oficial citada verbatim. NO es una lista de personas y NO "
                      "permite confirmar el estado de nadie; para buscar a un familiar usa "
                      "get_reunification_channels."),
            "fuente": "config.yaml: cifras_oficiales (campo desaparecidos)",
            "url": "https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes", "hora_consulta": _now()}


# ── Skills: estado humanitario en vivo (GDACS / ReliefWeb) ────────────────────
def get_gdacs_alert():
    gd = get_gdacs(load_config())
    return {"disponible": bool(gd.get("alertlevel")), "alertlevel": gd.get("alertlevel"),
            "severity": gd.get("severity"), "summary": gd.get("summary"),
            "datemodified": gd.get("datemodified"),
            "fuente": "GDACS — Global Disaster Alert and Coordination System",
            "url": gd.get("url"), "hora_consulta": gd.get("fetched_at") or _now()}


def get_reliefweb_situation_reports(limit=6):
    rw = get_reliefweb_reports(load_config(), limit=int(limit))
    return {"disponible": bool(rw.get("reports")), "reports": rw.get("reports", []),
            "needs_appname": rw.get("needs_appname", False),
            "fuente": "ReliefWeb (OCHA) — Reportes de situación", "url": rw.get("url"),
            "hora_consulta": rw.get("fetched_at") or _now()}


def get_live_relief_status(fuente="ambas", max_reportes=6):
    out = {"hora_consulta": _now(), "fuente": "GDACS + ReliefWeb (OCHA)"}
    g = r = None
    if fuente in ("gdacs", "ambas"):
        g = get_gdacs_alert(); out["gdacs"] = g
    if fuente in ("reliefweb", "ambas"):
        r = get_reliefweb_situation_reports(limit=max_reportes); out["reliefweb"] = r
    out["disponible"] = bool((g and g.get("disponible")) or (r and r.get("disponible")))
    return out


# ── Skills: clima por zona (Open-Meteo en vivo) ───────────────────────────────
def get_zone_weather(zona, idioma="es"):
    from core.weather import get_weather
    cfg = load_config(); z = get_zone(cfg, zona)
    lon_min, lat_min, lon_max, lat_max = z["bbox"]
    lat, lon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
    w = get_weather(lat, lon, idioma if idioma in ("es", "en") else "es")
    if not w:
        return {"disponible": False, "zona_id": zona, "fuente": "Open-Meteo (CC BY 4.0)",
                "url": "https://open-meteo.com/", "hora_consulta": _now()}
    cur = w.get("current", {})
    return {"disponible": True, "zona_id": zona, "zona_nombre": z["nombre"],
            "actual": {"temperatura_C": _num(cur.get("temp")), "lluvia_mm": _num(cur.get("precip")),
                       "viento_kmh": _num(cur.get("wind")), "condicion": cur.get("condition")},
            "proximas_horas": w.get("hourly", [])[:6], "proximos_dias": w.get("daily", []),
            "fuente": "Open-Meteo (CC BY 4.0)", "url": "https://open-meteo.com/",
            "hora_consulta": cur.get("fetched_at") or _now()}


# ── Skills: buscar familiares (NUNCA afirma paradero) ─────────────────────────
_CAT = {"icrc_rfl": "buscar_registrar", "icrc_trace_face": "buscar_registrar",
        "cruz_roja_venezolana": "buscar_registrar", "desaparecidos_terremoto_ve": "buscar_registrar",
        "localiza_pacientes": "hospitalizados", "pacientes_terremoto_vzla": "hospitalizados"}


def get_reunification_channels(intent="todos", lang="es"):
    cfg = load_config()
    f = cfg.get("fuentes", {})
    from core.i18n import fuente_nombre
    want = {"buscar": "buscar_registrar", "registrar": "buscar_registrar",
            "hospitalizados": "hospitalizados"}.get(intent)
    canales = []
    for clave in ("icrc_rfl", "icrc_trace_face", "cruz_roja_venezolana",
                  "desaparecidos_terremoto_ve", "localiza_pacientes", "pacientes_terremoto_vzla"):
        if clave not in f:
            continue
        cat = _CAT.get(clave, "buscar_registrar")
        if want and cat != want:
            continue
        canales.append({"clave": clave, "nombre": fuente_nombre(f[clave], lang),
                        "url": f[clave]["url"], "categoria": cat})
    return {"disponible": len(canales) > 0, "canales": canales,
            "aviso": ("Canales para que TÚ gestiones la búsqueda/registro; la app NO conoce ni "
                      "puede confirmar el paradero o estado de ninguna persona."),
            "fuente": "Directorio de canales oficiales de reunificación (config.yaml)",
            "url": "https://familylinks.icrc.org/", "hora_consulta": _now()}


# ── Skills: consejos de seguridad (contenido curado verbatim) ─────────────────
def get_safety_tips(tema, idioma="es"):
    idi = idioma if idioma in ("es", "en") else "es"
    secciones = SAFETY_TIPS.get(idi, [])
    idx = TEMA_INDICE.get(tema)
    if idx is None or idx >= len(secciones):
        return {"disponible": False, "tema": tema, "idioma": idi, "tips": [], "titulo": "",
                "telefonos_emergencia": TELEFONOS_EMERGENCIA,
                "fuente": "App — Consejos de seguridad post-terremoto",
                "url": "pages/5_Consejos_post_terremoto.py", "hora_consulta": _now()}
    titulo, tips = secciones[idx]
    return {"disponible": True, "tema": tema, "idioma": idi, "titulo": titulo, "tips": list(tips),
            "telefonos_emergencia": TELEFONOS_EMERGENCIA,
            "fuente": "App — Consejos de seguridad post-terremoto (contenido curado)",
            "url": "pages/5_Consejos_post_terremoto.py", "hora_consulta": _now()}


def list_safety_topics(idioma="es"):
    idi = idioma if idioma in ("es", "en") else "es"
    secciones = SAFETY_TIPS.get(idi, [])
    temas = [{"tema": TEMA_INVERSO.get(i), "titulo": s[0], "resumen": (s[1][0] if s[1] else "")}
             for i, s in enumerate(secciones)]
    return {"disponible": len(temas) > 0, "idioma": idi, "temas": temas, "total": len(temas),
            "fuente": "App — Consejos de seguridad post-terremoto (contenido curado)",
            "url": "pages/5_Consejos_post_terremoto.py", "hora_consulta": _now()}


# ── Skills: geolocalización (cobertura / distancias) ──────────────────────────
def locate_point_in_zone(lat, lon):
    cfg = load_config()
    for z in cfg["zonas"]:
        lon_min, lat_min, lon_max, lat_max = z["bbox"]
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return {"disponible": True, "zona_id": z["id"], "zona_nombre": z["nombre"],
                    "dentro_cobertura": True, "lat": lat, "lon": lon, "bbox_usado": z["bbox"],
                    "fuente": "config.yaml: zonas (bboxes de cobertura)", "hora_consulta": _now()}
    return {"disponible": True, "zona_id": None, "zona_nombre": None, "dentro_cobertura": False,
            "lat": lat, "lon": lon, "bbox_usado": None,
            "nota": "Coordenada fuera de las 4 zonas cubiertas por la app.",
            "fuente": "config.yaml: zonas (bboxes de cobertura)", "hora_consulta": _now()}


def distance_to_references(lat, lon, incluir_epicentro=True):
    cfg = load_config()
    dist = [{"ciudad": n, "km": round(float(haversine_m(lat, lon, la, lo)) / 1000.0, 1)}
            for n, (la, lo) in CIUDADES_REF.items()]
    mas = min(dist, key=lambda d: d["km"]) if dist else None
    epi = None
    if incluir_epicentro:
        s = get_sismo(cfg); e = s.get("epicentro")
        if e:
            epi = {"km": round(float(haversine_m(lat, lon, e["lat"], e["lon"])) / 1000.0, 1),
                   "lat": e["lat"], "lon": e["lon"], "fuente": s.get("fuente"),
                   "url": s.get("url"), "origen_iso": s.get("origen_iso")}
    return {"disponible": True, "lat": lat, "lon": lon, "distancias_km": dist,
            "ciudad_mas_cercana": mas, "epicentro": epi,
            "fuente_ciudades": "core/geo.py: CIUDADES_REF (5 ciudades)",
            "fuente_distancia": "core/geo.py: haversine_m", "hora_consulta": _now()}


# ── Registro: callables + esquemas OpenAI + dispatch validado ─────────────────
TOOLS = {
    "get_aftershocks_recientes": get_aftershocks_recientes,
    "get_aftershock_resumen": get_aftershock_resumen_skill,
    "get_zone_summary": get_zone_summary,
    "get_zone_top_areas": get_zone_top_areas,
    "list_help_resources": list_help_resources,
    "find_nearest_resource": find_nearest_resource,
    "count_resources_by_type": count_resources_by_type,
    "get_official_casualty_figures": get_official_casualty_figures,
    "get_material_damage_reports": get_material_damage_reports,
    "get_missing_persons_count": get_missing_persons_count,
    "get_gdacs_alert": get_gdacs_alert,
    "get_reliefweb_situation_reports": get_reliefweb_situation_reports,
    "get_live_relief_status": get_live_relief_status,
    "get_zone_weather": get_zone_weather,
    "get_reunification_channels": get_reunification_channels,
    "get_safety_tips": get_safety_tips,
    "list_safety_topics": list_safety_topics,
    "locate_point_in_zone": locate_point_in_zone,
    "distance_to_references": distance_to_references,
}

_ZONA = {"type": "string", "enum": ZONE_IDS}
_TEMAS = list(TEMA_INDICE.keys())


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "additionalProperties": False,
                       "properties": props or {}, "required": required or []}}}


TOOLS_SCHEMA = [
    _fn("get_aftershocks_recientes",
        "Réplicas y sismos recientes reales cerca del epicentro (USGS en vivo). Marca es_evento_principal para no confundir los M7.5/M7.2 con réplicas.",
        {"dias_atras": {"type": "integer", "minimum": 1, "maximum": 30},
         "min_magnitud": {"type": "number", "minimum": 1.0, "maximum": 7.0},
         "radio_km": {"type": "integer", "enum": [100, 150, 200, 300]},
         "limite": {"type": "integer", "minimum": 1, "maximum": 50}}),
    _fn("get_aftershock_resumen",
        "Conteo real de sismos en una ventana + el de mayor magnitud (USGS). NO es predicción de réplicas futuras.",
        {"dias_atras": {"type": "integer", "minimum": 1, "maximum": 30},
         "min_magnitud": {"type": "number", "minimum": 1.0, "maximum": 7.0},
         "radio_km": {"type": "integer", "enum": [100, 150, 200, 300]}}),
    _fn("get_zone_summary",
        "Resumen de una zona: intensidad MMI máxima (USGS), población residente (WorldPop) y si hay peligro de suelo.",
        {"zona": _ZONA}, ["zona"]),
    _fn("get_zone_top_areas",
        "Barrios/sectores de una zona ordenados por mayor afectación medida (intensidad, población o peligro de suelo). Útil para priorizar dónde concentrar la ayuda.",
        {"zona": _ZONA, "ordenar_por": {"type": "string",
            "enum": ["mmi", "poblacion", "licuefaccion", "deslizamiento"]},
         "limite": {"type": "integer", "minimum": 1, "maximum": 12}}, ["zona"]),
    _fn("list_help_resources",
        "Lista hospitales, clínicas, bomberos, ambulancias y refugios mapeados en una zona (OSM), con teléfono y dirección si están.",
        {"zona": _ZONA, "tipo": {"type": "string",
            "enum": ["hospital", "clinic", "fire_station", "ambulance_station", "shelter", "todos"]},
         "limite": {"type": "integer", "minimum": 1, "maximum": 50}}, ["zona"]),
    _fn("find_nearest_resource",
        "Encuentra los recursos de ayuda más cercanos a una coordenada dentro de una zona (OSM + distancia haversine).",
        {"zona": _ZONA, "lat": {"type": "number", "minimum": -90, "maximum": 90},
         "lon": {"type": "number", "minimum": -180, "maximum": 180},
         "tipo": {"type": "string", "enum": ["hospital", "clinic", "fire_station",
            "ambulance_station", "shelter", "todos"]},
         "top_n": {"type": "integer", "minimum": 1, "maximum": 10}}, ["zona", "lat", "lon"]),
    _fn("count_resources_by_type",
        "Cuenta cuántos recursos de cada tipo hay mapeados en OSM en una zona.",
        {"zona": _ZONA}, ["zona"]),
    _fn("get_official_casualty_figures",
        "Cifras oficiales de víctimas (fallecidos/heridos/desaparecidos) citadas verbatim con su fuente y fecha. PROHIBIDO sumar entre fuentes.",
        {"metrica": {"type": "string", "enum": ["fallecidos", "heridos", "desaparecidos", "todas"]}}),
    _fn("get_material_damage_reports",
        "Reportes de daños materiales (edificios, infraestructura) citados verbatim con fuente y fecha."),
    _fn("get_missing_persons_count",
        "Cifra agregada oficial de desaparecidos, citada verbatim. NO es una lista de personas ni confirma estados."),
    _fn("get_gdacs_alert",
        "Nivel de alerta y severidad GDACS del evento (en vivo)."),
    _fn("get_reliefweb_situation_reports",
        "Últimos reportes de situación de ReliefWeb/OCHA (enlazables).",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 10}}),
    _fn("get_live_relief_status",
        "Estado humanitario en vivo: alerta GDACS + reportes OCHA/ReliefWeb.",
        {"fuente": {"type": "string", "enum": ["gdacs", "reliefweb", "ambas"]},
         "max_reportes": {"type": "integer", "minimum": 1, "maximum": 10}}),
    _fn("get_zone_weather",
        "Clima actual y pronóstico (lluvia/viento) de una zona — relevante para operaciones de rescate (Open-Meteo en vivo).",
        {"zona": _ZONA, "idioma": {"type": "string", "enum": ["es", "en"]}}, ["zona"]),
    _fn("get_reunification_channels",
        "Canales oficiales para BUSCAR o REGISTRAR a un familiar (CICR, Cruz Roja, etc.). NUNCA confirma el paradero de una persona.",
        {"intent": {"type": "string", "enum": ["buscar", "registrar", "hospitalizados", "todos"]},
         "lang": {"type": "string", "enum": ["es", "en"]}}),
    _fn("get_safety_tips",
        "Consejos de seguridad post-terremoto por tema (verbatim del contenido curado de la app).",
        {"tema": {"type": "string", "enum": _TEMAS},
         "idioma": {"type": "string", "enum": ["es", "en"]}}, ["tema"]),
    _fn("list_safety_topics",
        "Lista los temas de consejos de seguridad disponibles.",
        {"idioma": {"type": "string", "enum": ["es", "en"]}}),
    _fn("locate_point_in_zone",
        "Indica a cuál de las 4 zonas cubiertas pertenece una coordenada (o si está fuera de cobertura).",
        {"lat": {"type": "number", "minimum": -90, "maximum": 90},
         "lon": {"type": "number", "minimum": -180, "maximum": 180}}, ["lat", "lon"]),
    _fn("distance_to_references",
        "Distancia de una coordenada a ciudades grandes de referencia y al epicentro.",
        {"lat": {"type": "number", "minimum": -90, "maximum": 90},
         "lon": {"type": "number", "minimum": -180, "maximum": 180},
         "incluir_epicentro": {"type": "boolean"}}, ["lat", "lon"]),
]

_SCHEMA_BY_NAME = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS_SCHEMA}


def _validate(name, args):
    """Valida args contra el JSON-Schema de la skill. Devuelve (ok, motivo)."""
    schema = _SCHEMA_BY_NAME.get(name)
    if schema is None:
        return False, f"skill desconocida: {name}"
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            return False, f"falta el parámetro requerido: {req}"
    for k, v in args.items():
        spec = props.get(k)
        if spec is None:
            return False, f"parámetro no permitido: {k}"
        if "enum" in spec and v not in spec["enum"]:
            return False, f"{k} debe ser uno de {spec['enum']}"
        if spec.get("type") in ("number", "integer") and isinstance(v, (int, float)):
            if "minimum" in spec and v < spec["minimum"]:
                return False, f"{k} por debajo del mínimo"
            if "maximum" in spec and v > spec["maximum"]:
                return False, f"{k} por encima del máximo"
    return True, ""


def dispatch(name, args):
    """Ejecuta la skill validando los argumentos; nunca propaga excepciones."""
    args = args or {}
    ok, motivo = _validate(name, args)
    if not ok:
        return {"disponible": False, "error": motivo,
                "fuente": "validación interna", "url": "", "hora_consulta": _now()}
    try:
        return TOOLS[name](**args)
    except KeyError as e:
        return {"disponible": False, "error": f"dato no encontrado: {e}",
                "fuente": "skill", "url": "", "hora_consulta": _now()}
    except Exception as e:  # red, parsing, etc. → degradación, no crash
        return {"disponible": False, "error": f"{type(e).__name__}: {e}",
                "fuente": "skill", "url": "", "hora_consulta": _now()}
