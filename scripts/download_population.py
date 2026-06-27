#!/usr/bin/env python3
"""Descarga el ráster de población REAL de Venezuela (WorldPop 100 m, CC-BY 4.0).

Uso:
    python scripts/download_population.py

Fuente oficial (citar):
  WorldPop Hub — https://hub.worldpop.org/geodata/listing?id=6448
  WorldPop — https://www.worldpop.org/
  Página del país (HDX):
    https://data.humdata.org/dataset/worldpop-population-density-for-venezuela-bolivarian-republic-of

Nota: El archivo pesa ~477 MB. La lectura remota no es posible porque el servidor
WorldPop no soporta HTTP range requests (no es COG). Se descarga una sola vez.

Alternativa de mayor resolución (30 m): Meta/CIESIN HRSL en HDX
https://data.humdata.org/dataset/kontur-population-venezuela-bolivarian-republic-of
"""
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    url = cfg["poblacion"]["worldpop_tif_url"]
    dest = ROOT / cfg["poblacion"]["raster_path"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    print(f"Descargando: {url}\n -> {dest}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done/1e6:.1f}/{total/1e6:.1f} MB", end="")
    print(f"\nListo. {dest} ({dest.stat().st_size/1e6:.1f} MB)")
    print("Reinicie la app: la capa de población quedará disponible automáticamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
