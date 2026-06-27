import streamlit as st
from core.ui import render_zone

st.set_page_config(page_title="Caracas — Sucre / Petare", page_icon="🛰️", layout="wide")
render_zone("sucre_petare")
