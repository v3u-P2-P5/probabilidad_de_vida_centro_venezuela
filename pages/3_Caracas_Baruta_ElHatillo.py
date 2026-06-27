import streamlit as st
from core.ui import render_zone

st.set_page_config(page_title="Caracas — Baruta / El Hatillo", page_icon="🛰️", layout="wide")
render_zone("baruta_hatillo")
