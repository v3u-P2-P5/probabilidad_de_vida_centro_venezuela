# 🛰️ Mapa de Probabilidad de Vida — Caracas y La Guaira

Dashboard para **priorizar búsqueda y rescate (SAR)** tras un terremoto, estimando
por celda la *probabilidad relativa de encontrar personas con vida*.

> ⚠️ La probabilidad de sobrevivientes **no se observa desde el satélite: se modela**.
> El satélite aporta la capa de daño (con latencia); el tiempo real lo dan los reportes de campo.

## Modelo

```
P_vida = sacudimiento(MMI) × colapso(tipo_edificio) × población_presente(hora)
         × supervivencia(huecos) × decaimiento_temporal(72 h) + boost_reportes_campo
```

La **hora importa**: a las 11:45 de un día laborable la población está en
oficinas/escuelas/comercios, no en viviendas. La ocupación se ajusta por hora.

## Fuentes de datos (todas gratuitas)

| Capa | Fuente | Estado |
|------|--------|--------|
| Sacudimiento (MMI) | USGS ShakeMap / PAGER | Conector de metadatos USGS (`core/data_sources.py`); raster ShakeMap = TODO |
| Daño | Copernicus EMS Rapid Mapping · Maxar/Vantor Open Data | A integrar tras activación |
| Población | Meta HRSL · WorldPop · GHSL | Sintético por ahora (`core/population.py`) |
| Edificios / recursos | OpenStreetMap / HOT | A integrar |
| Tiempo real | Reportes de campo | ✅ `data/field_reports.csv` |

> **Google Maps queda descartado** como fuente: sus Términos de Servicio prohíben la
> descarga masiva de tiles/imágenes, requiere facturación y es óptico (inútil de noche/nubes).

## Ejecutar (local)

```bash
cd ~/work_space_linux/probabilidad_de_vida
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py        # http://localhost:8501
```

## Tests

```bash
pip install pytest
pytest -q
```

## Estructura

```
app.py                 Página de inicio (KPIs, reloj 72h, resumen por zona)
pages/                 Una página por zona + reportes de campo (evita un mapa único pesado)
core/                  config · i18n · geo · scoring · data_sources · population · reports · pipeline · ui
config.yaml            Zonas, pesos del modelo y datos del sismo (editable EN CALIENTE)
locales/               es.json · en.json (UI en español, conmutable a inglés)
data/field_reports.csv Reportes de campo en vivo
.claude/memory.yaml    Memoria del proyecto (contexto multisesión)
```

## Configurar el evento real

Editar `config.yaml → sismo`: `origen_iso`, `magnitud`, `epicentro`, y opcionalmente
`usgs_event_id` con `usar_datos_reales: true` para traer metadatos de USGS.
Ajustar `pesos` recalibra el modelo sin tocar código (recarga en caliente).

## Despliegue público (Streamlit Community Cloud)

1. `git push` del repo a GitHub.
2. En [share.streamlit.io](https://share.streamlit.io) conectar el repo y elegir `app.py`.
3. URL pública en minutos.

## Roadmap

- [ ] Parseo del raster ShakeMap (grid.xml) de USGS para MMI real por punto.
- [ ] Ingesta de productos de daño de Copernicus EMS / Maxar STAC.
- [ ] Población real (Meta HRSL / WorldPop) y edificios OSM por zona.
- [ ] Capa de recursos (hospitales, vías, refugios) para acceso viable de brigadas.
- [ ] Auto-refresco y modo bajo ancho de banda (solo tabla) para campo.
