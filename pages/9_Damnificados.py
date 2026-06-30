"""Recursos verificados para damnificados del doble sismo Venezuela 2026."""
import streamlit as st

from core.config import load_config
from core.i18n import fuente_nombre, t
from core.ui import apply_chrome

config = load_config()
lang = apply_chrome(config)
cofu = config.get("fuentes", {})

st.title("🆘 " + t("damnificados_titulo", lang))
st.caption(t("damnificados_page_intro", lang))

EMERG = {
    "es": "📞 **Emergencias: [171](tel:171) o [911](tel:911)** · Protección Civil.",
    "en": "📞 **Emergencies: [171](tel:171) or [911](tel:911)** · Civil Protection.",
}
st.error(EMERG.get(lang, EMERG["es"]))

AVISO = {
    "es": (
        "⚠️ Las plataformas ciudadanas son iniciativas **no oficiales**, verificadas al 30 jun 2026. "
        "Útiles para reconectar familias y localizar recursos, pero no sustituyen a los canales oficiales. "
        "**Nunca compartas datos bancarios ni contraseñas** en estos sitios. Verifica la URL antes de ingresar datos personales."
    ),
    "en": (
        "⚠️ Citizen platforms are **non-official** initiatives, verified Jun 30 2026. "
        "Useful for reconnecting families and locating resources, but they do not replace official channels. "
        "**Never share banking details or passwords** on these sites. Verify the URL before entering personal data."
    ),
}
st.warning(AVISO.get(lang, AVISO["es"]))

# ── 1. SEÑAL DE VIDA ─────────────────────────────────────────────────────────
_senyal_hdr = {
    "es": "📡 Señal de vida — Que tu familia sepa que estás bien",
    "en": "📡 Life signal — Let your family know you're safe",
}
with st.expander(_senyal_hdr.get(lang, _senyal_hdr["es"]), expanded=True):
    if lang == "en":
        st.markdown(
            "**[Auxilio Venezuela — Life Signal](https://auxiliovenezuela.com/)**  \n"
            "Register your signal so your family knows you are safe, or search among 20,000+ registered signals. "
            "No advertising. Free volunteer initiative created by Venezuelans abroad."
        )
    else:
        st.markdown(
            "**[Auxilio Venezuela — Señal de Vida](https://auxiliovenezuela.com/)**  \n"
            "Registra tu señal para que tu familia sepa que estás bien, o busca entre más de 20.000 señales registradas. "
            "Sin publicidad. Iniciativa voluntaria y gratuita de venezolanos en el exterior."
        )

# ── 2. MAPAS CIUDADANOS EN TIEMPO REAL ────────────────────────────────────────
_mapas_hdr = {
    "es": "🗺️ Mapas ciudadanos — Refugios, hospitales y reportes de daños",
    "en": "🗺️ Citizen maps — Shelters, hospitals and damage reports",
}
with st.expander(_mapas_hdr.get(lang, _mapas_hdr["es"]), expanded=True):
    if lang == "en":
        _mapas = [
            (
                "Ayuda Venezuela App",
                "https://ayudavenezuela.app/",
                "Seismic dashboard, shelter and hospital maps, blood donation locator. "
                "Uses only Funvisis / 911 / Civil Protection data. Warns against sharing personal data publicly.",
            ),
            (
                "SOS Venezuela 2026",
                "https://sosvenezuela2026.com/",
                "Live damage map, missing persons directory, USGS data feed, first-aid guides "
                "and child registry in shelters. Community-verified.",
            ),
            (
                "Terremoto Venezuela App",
                "https://terremotovenezuela.app/",
                "Collaborative emergency and rescue map (Acceso Libre initiative). "
                "Tap a point to report or view zone status: people trapped, structural collapse, evacuation areas.",
            ),
            (
                "Recursos Venezuela",
                "https://recursosvenezuela.com/",
                "Emergency information hub: emergency numbers, donation platforms, supply collection centers, "
                "and family communication guides. Open data, community-verified.",
            ),
        ]
    else:
        _mapas = [
            (
                "Ayuda Venezuela App",
                "https://ayudavenezuela.app/",
                "Dashboard sísmico, mapa de refugios y hospitales, localizador de donación de sangre. "
                "Datos solo de Funvisis / 911 / Protección Civil. Advierte no compartir datos personales en público.",
            ),
            (
                "SOS Venezuela 2026",
                "https://sosvenezuela2026.com/",
                "Mapa de daños en vivo, directorio de desaparecidos, datos USGS en tiempo real, "
                "guías de primeros auxilios y registro de niños en refugios. Verificada por la comunidad.",
            ),
            (
                "Terremoto Venezuela App",
                "https://terremotovenezuela.app/",
                "Mapa colaborativo de emergencia y rescate (iniciativa Acceso Libre). "
                "Toca un punto para reportar o ver el estado de la zona: atrapados, derrumbes, áreas de evacuación.",
            ),
            (
                "Recursos Venezuela",
                "https://recursosvenezuela.com/",
                "Hub de información de emergencia: números de urgencia, plataformas de donación, "
                "centros de acopio y guías de comunicación familiar. Datos abiertos y verificados.",
            ),
        ]
    for nombre, url, desc in _mapas:
        st.markdown(f"🔗 **[{nombre}]({url})**  \n{desc}")
        st.write("")

# ── 3. ORGANIZACIONES CON RESPUESTA ACTIVA ────────────────────────────────────
_donac_hdr = {
    "es": "💚 Organizaciones con respuesta activa — Cómo donar",
    "en": "💚 Organizations with active response — How to donate",
}
with st.expander(_donac_hdr.get(lang, _donac_hdr["es"]), expanded=False):
    if lang == "en":
        st.markdown(
            "Donate only through organizations with confirmed operations in Venezuela. "
            "All links below were verified Jun 30, 2026."
        )
        _orgs_ext = [
            (
                "Direct Relief — Venezuela 2026",
                "https://directrelief.org/emergency/venezuela-earthquakes-2026/",
                "Coordinating medical supply delivery to affected areas. Specific Venezuela 2026 emergency page.",
            ),
            (
                "International Rescue Committee (IRC)",
                "https://rescue.org/article/how-help-survivors-earthquakes-venezuela",
                "Scaling up services in Venezuela. Operating in the country since 2021.",
            ),
            (
                "World Central Kitchen",
                "https://worldcentralkitchen.org/",
                "Emergency meal distribution. Check their site for Venezuela 2026 updates.",
            ),
        ]
    else:
        st.markdown(
            "Dona solo a través de organizaciones con operaciones confirmadas en Venezuela. "
            "Todos los enlaces de abajo fueron verificados el 30 jun 2026."
        )
        _orgs_ext = [
            (
                "Direct Relief — Venezuela 2026",
                "https://directrelief.org/emergency/venezuela-earthquakes-2026/",
                "Coordina entrega de suministros médicos en las zonas afectadas. Página específica Venezuela 2026.",
            ),
            (
                "International Rescue Committee (IRC)",
                "https://rescue.org/article/how-help-survivors-earthquakes-venezuela",
                "Amplía servicios en Venezuela. Opera en el país desde 2021.",
            ),
            (
                "World Central Kitchen",
                "https://worldcentralkitchen.org/",
                "Distribución de comidas en emergencias. Consulta su sitio para actualizaciones Venezuela 2026.",
            ),
        ]

    for key in ("cruz_roja_venezolana", "centros_ayuda_vzla", "caritas_venezuela"):
        if key in cofu:
            st.markdown(f"🔗 **[{fuente_nombre(cofu[key], lang)}]({cofu[key]['url']})**")

    for nombre, url, desc in _orgs_ext:
        st.markdown(f"🔗 **[{nombre}]({url})**  \n{desc}")
        st.write("")

st.markdown("---")
_footer = {
    "es": "ℹ️ Lista verificada al 30 jun 2026. Sin afiliación comercial con estos sitios. Si encuentras un enlace roto o sospechoso, [comunícalo aquí](mailto:alberto.millan.rst@gmail.com).",
    "en": "ℹ️ Links verified Jun 30, 2026. No commercial affiliation with these sites. If you find a broken or suspicious link, [report it here](mailto:alberto.millan.rst@gmail.com).",
}
st.caption(_footer.get(lang, _footer["es"]))
