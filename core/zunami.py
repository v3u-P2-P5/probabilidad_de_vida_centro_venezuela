"""Indicador de carga "Zunami": ciclo propio de figuras (corriendo, silla de
ruedas, bici, nado, remo) + un perro, en CSS, para REEMPLAZAR el ciclo nativo
de Streamlit. Motivo: el set nativo esta compilado en el frontend (no editable y
Streamlit Cloud lo reinstala), incluye un "hombre estatico" que no queremos, y no
permite anadir a Zunami. Aqui ocultamos el svg nativo y animamos una mascara CSS.
Paths Material (Apache-2.0) extraidos del bundle de Streamlit; perro propio.
"""
import urllib.parse

# (viewBox, path) de cada figura del ciclo. Zunami es la ultima.
FIGURAS = [
    ('0 0 24 24', 'M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1-4.9-1-.4 2 7 1.4z'),
    ('0 0 24 24', 'M15 17h-2c0 1.65-1.35 3-3 3s-3-1.35-3-3 1.35-3 3-3v-2c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5zm3-3.5h-1.86l1.67-3.67C18.42 8.5 17.44 7 15.96 7h-5.2c-.81 0-1.54.47-1.87 1.2L8.22 10l1.92.53.65-1.53H13l-1.83 4.1c-.6 1.33.39 2.9 1.85 2.9H18v5h2v-5.5c0-1.1-.9-2-2-2z'),
    ('0 0 24 24', 'M15.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM5 12c-2.8 0-5 2.2-5 5s2.2 5 5 5 5-2.2 5-5-2.2-5-5-5zm0 8.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5zm5.8-10l2.4-2.4.8.8c1.3 1.3 3 2.1 5.1 2.1V9c-1.5 0-2.7-.6-3.6-1.5l-1.9-1.9c-.5-.4-1-.6-1.6-.6s-1.1.2-1.4.6L7.8 8.4c-.4.4-.6.9-.6 1.4 0 .6.2 1.1.6 1.4L11 14v5h2v-6.2l-2.2-2.3zM19 12c-2.8 0-5 2.2-5 5s2.2 5 5 5 5-2.2 5-5-2.2-5-5-5zm0 8.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5z'),
    ('0 0 24 24', 'M10 8l-3.25 3.25c.31.12.56.27.77.39.37.23.59.36 1.15.36s.78-.13 1.15-.36c.46-.27 1.08-.64 2.19-.64s1.73.37 2.18.64c.37.22.6.36 1.15.36.55 0 .78-.13 1.15-.36.12-.07.26-.15.41-.23L10.48 5C8.93 3.45 7.5 2.99 5 3v2.5c1.82-.01 2.89.39 4 1.5l1 1zm12 8.5h-.02.02zm-16.65-1c.55 0 .78.14 1.15.36.45.27 1.07.64 2.18.64s1.73-.37 2.18-.64c.37-.23.59-.36 1.15-.36.55 0 .78.14 1.15.36.45.27 1.07.64 2.18.64s1.73-.37 2.18-.64c.37-.23.59-.36 1.15-.36.55 0 .78.14 1.15.36.45.27 1.06.63 2.16.64v-2c-.55 0-.78-.14-1.15-.36-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.18.64c-.37.23-.6.36-1.15.36s-.78-.14-1.15-.36c-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.18.64c-.37.23-.59.36-1.15.36-.55 0-.78-.14-1.15-.36-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.18.64c-.37.23-.59.36-1.15.36v2c1.11 0 1.73-.37 2.2-.64.37-.23.6-.36 1.15-.36zM18.67 18c-1.11 0-1.73.37-2.18.64-.37.23-.6.36-1.15.36-.55 0-.78-.14-1.15-.36-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.19.64c-.37.23-.59.36-1.15.36s-.78-.13-1.15-.36c-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.19.64c-.37.23-.59.36-1.15.36v2c1.11 0 1.73-.37 2.19-.64.37-.23.6-.36 1.15-.36.55 0 .78.13 1.15.36.45.27 1.07.64 2.18.64s1.73-.37 2.19-.64c.37-.23.59-.36 1.15-.36.55 0 .78.14 1.15.36.45.27 1.07.64 2.18.64s1.72-.37 2.18-.64c.37-.23.59-.36 1.15-.36.55 0 .78.14 1.15.36.45.27 1.07.64 2.18.64v-2c-.56 0-.78-.13-1.15-.36-.45-.27-1.07-.64-2.18-.64z'),
    ('0 0 24 24', 'M8.5 14.5L4 19l1.5 1.5L9 17h2l-2.5-2.5zM15 1c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 20.01L18 24l-2.99-3.01V19.5l-7.1-7.09c-.31.05-.61.07-.91.07v-2.16c1.66.03 3.61-.87 4.67-2.04l1.4-1.55c.19-.21.43-.38.69-.5.29-.14.62-.23.96-.23h.03C15.99 6.01 17 7.02 17 8.26v5.75c0 .84-.35 1.61-.92 2.16l-3.58-3.58v-2.27c-.63.52-1.43 1.02-2.29 1.39L16.5 18H18l3 3.01z'),
    ('0 0 64 48', 'M18,18L46,18Q50,18 50,24Q50,30 46,30L18,30Q14,30 14,24Q14,18 18,18ZM5,22a9,9 0 1,0 18,0a9,9 0 1,0 -18,0ZM2,21L11,21L11,28L2,28ZM12,15L8,4L19,13ZM45,19Q57,15 54,5Q51,12 44,21ZM19,29L23,29L20,45L16,45ZM26,29L30,29L27,45L23,45ZM37,29L41,29L44,45L40,45ZM44,29L48,29L51,45L47,45Z'),
]

_MS_POR_FIGURA = 200  # mismo ritmo que el indicador nativo de Streamlit


def _mask(viewbox: str, d: str) -> str:
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='" + viewbox +
           "'><path fill='#000' d='" + d + "'/></svg>")
    return "url(\"data:image/svg+xml," + urllib.parse.quote(svg, safe="") + "\")"


def running_indicator_css() -> str:
    """CSS que sustituye el running-man de Streamlit por el ciclo con Zunami."""
    n = len(FIGURAS)
    frames = []
    for i, (vb, d) in enumerate(FIGURAS):
        m = _mask(vb, d)
        frames.append(f"  {i * 100 / n:.4f}% {{ -webkit-mask-image:{m}; mask-image:{m}; }}")
    first = _mask(*FIGURAS[0])
    frames.append(f"  100% {{ -webkit-mask-image:{first}; mask-image:{first}; }}")
    dur = n * _MS_POR_FIGURA / 1000
    keyframes = "\n".join(frames)
    return f"""
[data-testid="stStatusWidgetRunningIcon"] svg {{ display: none !important; }}
[data-testid="stStatusWidgetRunningIcon"] {{
  width: 1.5rem !important; height: 1.5rem !important;
  display: inline-block; vertical-align: middle;
  background-color: currentColor !important; opacity: 0.6;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
  -webkit-mask-position: center; mask-position: center;
  -webkit-mask-size: contain; mask-size: contain;
  animation: zunami-cycle {dur:.2f}s step-end infinite;
}}
@keyframes zunami-cycle {{
{keyframes}
}}
"""

