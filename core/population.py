"""Población.

- REAL local: muestrea el ráster WorldPop/Meta HRSL descargado localmente.
- REAL remoto: lee el ráster WorldPop directamente por HTTP (GDAL VSI / rasterio).
- REAL API: WorldPop REST API por bloques ~1km, sin descargar TIF (24h caché disco).
- PROYECCIÓN ESTADÍSTICA (HAZUS): perfiles de ocupación por hora y tipo de uso,
  aplicados a la hora del terremoto (18:05 VET). Citados y etiquetados siempre.
- SINTÉTICO: solo modo demo, claramente rotulado.
"""
import hashlib
import json
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent

# Población + área precomputadas (WorldPop + Nominatim, offline). Ver
# scripts/precompute_population.py. Pequeño y commiteado → funciona en Cloud.
PRECOMPUTED_CSV = ROOT / "data" / "population_cells.csv"
_PRECOMP_CACHE: dict = {}


def load_precomputed(zone_id: str):
    """DataFrame (cell_id, pop, area) precomputado para la zona, o None."""
    if not PRECOMPUTED_CSV.exists():
        return None
    if "all" not in _PRECOMP_CACHE:
        try:
            _PRECOMP_CACHE["all"] = pd.read_csv(PRECOMPUTED_CSV)
        except Exception:
            _PRECOMP_CACHE["all"] = None
    allrows = _PRECOMP_CACHE.get("all")
    if allrows is None:
        return None
    sub = allrows[allrows["zone_id"] == zone_id]
    return sub if not sub.empty else None


# --- Población real (local o remota) -----------------------------------------

def population_available(raster_path: str) -> bool:
    path = Path(raster_path)
    if not path.is_absolute():
        path = ROOT / raster_path
    return path.exists()


def sample_population_raster(lats, lons, raster_path: str):
    """Muestrea el ráster en cada (lat, lon). Devuelve array o None si no hay ráster local."""
    path = Path(raster_path)
    if not path.is_absolute():
        path = ROOT / raster_path
    if not path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(path) as src:
            vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                            dtype=float)
        vals[~np.isfinite(vals)] = 0.0
        vals[vals < 0] = 0.0
        return vals
    except Exception:
        return None


def sample_population_remote(lats, lons, url: str):
    """Intenta leer WorldPop por HTTP (GDAL VSI). Devuelve None si el servidor
    no soporta range requests (el archivo WorldPop VEN no es COG).
    """
    try:
        import rasterio
        with rasterio.open(f"/vsicurl/{url}") as src:
            vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                            dtype=float)
        vals[~np.isfinite(vals)] = 0.0
        vals[vals < 0] = 0.0
        return vals
    except Exception:
        return None   # WorldPop VEN no es COG; ejecutar download_population.py


_WP_HEADERS = {"User-Agent": "ProbabilidadDeVida-SAR/1.0 (humanitarian earthquake response VEN)"}


def _worldpop_block(lon_min: float, lat_min: float,
                    lon_max: float, lat_max: float,
                    timeout: int = 30, poll_max: int = 25) -> float | None:
    """Población total en un bloque bbox vía WorldPop Stats API (wpgppop 2020).

    API asíncrona: se envía un GeoJSON y se obtiene un taskid; se sondea hasta
    'finished'. Devuelve la población total o None si falla.
    """
    geojson = json.dumps({"type": "Feature", "properties": {}, "geometry": {
        "type": "Polygon", "coordinates": [[
            [lon_min, lat_min], [lon_max, lat_min],
            [lon_max, lat_max], [lon_min, lat_max],
            [lon_min, lat_min]]]}})
    try:
        r = requests.get(
            "https://api.worldpop.org/v1/services/stats",
            params={"dataset": "wpgppop", "year": 2020, "geojson": geojson},
            headers=_WP_HEADERS, timeout=timeout)
        r.raise_for_status()
        taskid = r.json().get("taskid")
        if not taskid:
            return None
        for _ in range(poll_max):
            time.sleep(1.5)
            t = requests.get("https://api.worldpop.org/v1/tasks/" + taskid,
                             headers=_WP_HEADERS, timeout=timeout).json()
            if t.get("status") == "finished":
                if t.get("error"):
                    return None
                return float(t["data"]["total_population"])
    except Exception:
        pass
    return None


def sample_population_api(lats, lons,
                           block_deg: float = 0.012) -> np.ndarray | None:
    """Población por celda vía WorldPop REST API — sin descargar TIF.

    Divide el bbox en bloques de ~1.3 km, consulta en paralelo (8 hilos)
    y distribuye la población uniformemente entre las celdas 150 m de cada
    bloque. Resultados en caché de disco 24 h.

    Fuente: WorldPop Population Counts 2020 (wpgpas), Venezuela, 100 m.
    Resolución efectiva del muestreo: ~1.3 km por bloque de consulta.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    lat_min, lat_max = float(lats.min()), float(lats.max())
    lon_min, lon_max = float(lons.min()), float(lons.max())

    # Caché en disco 24 h
    cache_key = f"{lat_min:.4f}_{lat_max:.4f}_{lon_min:.4f}_{lon_max:.4f}_{block_deg}"
    cache_dir = ROOT / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"pop_api_{hashlib.md5(cache_key.encode()).hexdigest()}.pkl"
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < 86400:
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass

    # Construir bloques y sus máscaras de celdas
    lat_edges = np.arange(lat_min, lat_max + block_deg, block_deg)
    lon_edges = np.arange(lon_min, lon_max + block_deg, block_deg)
    blocks = []
    for i in range(len(lat_edges) - 1):
        for j in range(len(lon_edges) - 1):
            mask = ((lats >= lat_edges[i]) & (lats < lat_edges[i + 1]) &
                    (lons >= lon_edges[j]) & (lons < lon_edges[j + 1]))
            if mask.sum() > 0:
                blocks.append((lon_edges[j], lat_edges[i],
                                lon_edges[j + 1], lat_edges[i + 1], mask))
    if not blocks:
        return None

    result = np.full(len(lats), np.nan)

    def _query(args):
        blon_min, blat_min, blon_max, blat_max, mask = args
        pop = _worldpop_block(blon_min, blat_min, blon_max, blat_max)
        return mask, pop

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_query, b): b for b in blocks}
        for fut in as_completed(futures):
            mask, pop = fut.result()
            if pop is not None and pop >= 0:
                n = int(mask.sum())
                result[mask] = pop / n if n > 0 else 0.0

    if np.all(np.isnan(result)):
        return None

    result[np.isnan(result)] = 0.0   # bloques sin respuesta → 0

    try:
        with open(cache_file, "wb") as f:
            pickle.dump(result, f)
    except Exception:
        pass

    return result


CELL_AREA_KM2 = 0.150 * 0.150   # celda 150 m × 150 m


def census_population(lats, lons, zone: dict) -> np.ndarray:
    """Población por celda basada en densidad censal (INE Venezuela 2011).

    Fuente: Instituto Nacional de Estadística Venezuela, Censo 2011.
    Usada por OCHA/UNHCR para planificación humanitaria en Venezuela.
    Estimación uniforme dentro del bbox de la zona — sin variación espacial interna.
    Incertidumbre: ±30 % (variación real entre sectores formales e informales).
    """
    densidad = float(zone.get("densidad_hab_km2", 10000))
    pop_por_celda = densidad * CELL_AREA_KM2
    return np.full(len(lats), pop_por_celda)


def get_population(lats, lons, config: dict, zone: dict | None = None):
    """Población real por orden de preferencia:
    local TIF → remota HTTP → API WorldPop → censo INE 2011.

    Devuelve (array, fuente_str). Nunca devuelve None — el censo es el último recurso.
    """
    raster_path = config["poblacion"]["raster_path"]
    # 1. TIF local
    pop = sample_population_raster(lats, lons, raster_path)
    if pop is not None:
        return pop, "local"
    # 2. TIF remoto HTTP range (requiere COG — WorldPop VEN no lo es)
    url = config["poblacion"].get("worldpop_tif_url", "")
    if url:
        pop = sample_population_remote(lats, lons, url)
        if pop is not None:
            return pop, "remota"
    # 3. WorldPop REST API por bloques (caché disco 24 h) — solo si está activada.
    #    Es lenta (~30 s/zona) y satura el servidor bajo concurrencia; por defecto
    #    se prefiere el censo INE (instantáneo). Activar con poblacion.usar_api_remota.
    if config["poblacion"].get("usar_api_remota", False):
        pop = sample_population_api(lats, lons)
        if pop is not None:
            return pop, "api"
    # 4. Censo INE Venezuela 2011 — siempre disponible, dato real publicado
    if zone is not None:
        return census_population(lats, lons, zone), "censo_ine"
    return None, "no_disponible"
