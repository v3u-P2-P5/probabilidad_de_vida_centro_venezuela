# 🛰️ Mapa de Probabilidad de Vida — Caracas y La Guaira

Dashboard para **priorizar búsqueda y rescate (SAR)** tras un terremoto, estimando
por celda la *probabilidad relativa de encontrar personas con vida*.

> **Evento activo:** USGS `us6000t7zp` — **M7.5**, 28 km SE de Yumare, Venezuela
> (origen 2026-06-24T18:05 VET / 22:05Z UTC). PAGER en **alerta ROJA**.
> Exposición a licuefacción ~160.000 personas (rojo); a deslizamientos ~7.300 (naranja).

> ⚠️ La probabilidad de sobrevivientes **no se observa desde el satélite: se modela**.
> El satélite aporta la capa de daño (con latencia); el tiempo real lo dan los reportes de campo.

## Principio operativo (modo_operativo: true)

**Solo datos reales.** Si una capa no está disponible, la app la marca como
**NO DISPONIBLE** y lo advierte — **nunca** inventa datos ni muestra cifras sintéticas
como si fueran reales. El modo demostración (`modo_operativo: false`) usa datos
sintéticos siempre rotulados, para capacitación.

## Modelo

```
P_vida = sacudimiento(MMI) × colapso(tipo_edificio) × población_presente(hora)
         × supervivencia(huecos) × decaimiento_temporal(72 h) + boost_reportes_campo
```

La **hora importa**: a las 11:45 de un día laborable la población está en
oficinas/escuelas/comercios, no en viviendas. La ocupación se ajusta por hora.

## Fuentes de datos (todas gratuitas)

| Capa | Fuente | Estado | Enlace oficial |
|------|--------|--------|----------------|
| Sacudimiento (MMI) | USGS ShakeMap (grid.xml real, interpolado) | ✅ **en vivo** | [ShakeMap](https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp/shakemap/intensity) |
| Impacto / víctimas | USGS PAGER | ✅ **en vivo** | [PAGER](https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp/pager) |
| Deslizamientos / licuefacción | USGS Ground Failure | ✅ **en vivo** | [Ground failure](https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp/ground-failure) |
| Recursos (hospitales, bomberos, refugios) | OpenStreetMap (Overpass) | ✅ **en vivo** | [© OSM](https://www.openstreetmap.org/copyright) |
| Población | WorldPop / Meta HRSL | ⬇️ descargar una vez (`scripts/download_population.py`) | [WorldPop VEN](https://data.humdata.org/dataset/worldpop-population-density-for-venezuela-bolivarian-republic-of) |
| Daño (imágenes) | Copernicus EMS · Maxar Open Data | 🔗 enlaces + ranura de activación EMSR en `config.yaml` | [Copernicus EMS](https://rapidmapping.emergency.copernicus.eu/) · [Maxar](https://www.maxar.com/open-data) |
| Tiempo real (terreno) | Reportes de campo | ✅ `data/field_reports.csv` | — |

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

## Cargar la población real (recomendado)

```bash
python scripts/download_population.py     # WorldPop VEN 100m (CC-BY 4.0)
```
Sin este paso la app funciona con sacudimiento + tiempo + reportes, y advierte que
la capa de población no está cargada (no inventa población).

## Configurar el evento

Editar `config.yaml → sismo.usgs_event_id` (actual: `us6000t7zp`) con
`usar_datos_reales: true`. La app trae en vivo de USGS la magnitud, epicentro,
hora, ShakeMap, PAGER y ground-failure. `autorefresco_segundos` controla el
refresco en tiempo real; `pesos` recalibra el modelo sin tocar código.

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
