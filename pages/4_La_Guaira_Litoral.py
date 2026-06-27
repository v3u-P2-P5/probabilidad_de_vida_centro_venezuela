import streamlit as st
from core.ui import render_zone

st.set_page_config(page_title="La Guaira — Litoral", page_icon="🛰️", layout="wide")
render_zone("la_guaira")
