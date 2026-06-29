"""Asistente IA con grounding (OpenRouter) — responde SOLO con datos reales.

MVP v1: inyecta un "context pack" factual (no tool-calling) y aplica defensa en
profundidad: clasificador de intención determinista para preguntas por el
paradero de personas, saneo de entrada, rate-limit por sesión y degradación
elegante si falta la clave o el servicio cae. La autorrefresco se desactiva para
no re-disparar la última llamada al modelo en cada ciclo.
"""
import os

import streamlit as st

from core.chat import (ChatAuthError, ChatError, ChatRateLimitError,
                       ChatUnavailable, stream_chat)
from core.chat_context import build_chat_context, reunification_links
from core.chat_prompt import classify_intent, sanitize_user_input, system_prompt
from core.config import load_config
from core.i18n import t
from core.ui import apply_chrome

config = load_config()
lang = apply_chrome(config, autorefresh=False)
chat_cfg = config.get("chat", {}) or {}


def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default) or os.environ.get(key, default)
    except Exception:
        return os.environ.get(key, default)


def _links_md(links) -> str:
    return "  \n".join(f"🔗 [{name}]({url})" for name, url in links)


st.title("💬 " + t("chat_titulo", lang))
st.caption(t("chat_cobertura", lang))
st.warning(t("chat_disclaimer", lang))
st.markdown(t("chat_intro", lang))

api_key = _secret("OPENROUTER_API_KEY")
links = reunification_links(config, lang)

# Sin clave o desactivado → degradar con elegancia (enlaza canales oficiales).
if not chat_cfg.get("activo", True) or not api_key:
    st.info(t("chat_sin_clave", lang))
    st.markdown(_links_md(links))
    st.stop()

# Estado de sesión (sobrevive a los reruns).
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("chat_calls", 0)

if st.sidebar.button(t("chat_limpiar", lang)):
    st.session_state.chat_history = []
    st.session_state.chat_calls = 0
    st.rerun()

with st.expander(t("chat_ejemplos_titulo", lang),
                 expanded=not st.session_state.chat_history):
    for k in ("chat_ejemplo_1", "chat_ejemplo_2", "chat_ejemplo_3"):
        st.markdown(f"- {t(k, lang)}")

# Historial.
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input(t("chat_placeholder", lang))
if prompt:
    prompt = sanitize_user_input(prompt, int(chat_cfg.get("max_input_chars", 600)))

if prompt:
    if st.session_state.chat_calls >= int(chat_cfg.get("rate_limit_por_sesion", 30)):
        st.warning(t("chat_rate_limit", lang))
        st.stop()

    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Guardrail #1 (determinista): paradero/estado de una persona → no se llama al
    # modelo; se deriva a los canales oficiales de reunificación.
    if classify_intent(prompt) == "paradero_persona":
        answer = (t("chat_rechazo_persona", lang) + "\n\n" + _links_md(links)
                  + "\n\n" + t("chat_aviso_emergencia", lang))
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
    else:
        st.session_state.chat_calls += 1
        context_block = build_chat_context(lang)
        api_messages = [{"role": "system", "content": system_prompt(lang, context_block)}]
        api_messages += st.session_state.chat_history[-6:]   # historial reciente

        model = chat_cfg.get("modelo", "anthropic/claude-3.5-sonnet")
        fallback = chat_cfg.get("modelo_fallback", "openai/gpt-4o-mini")
        referer = _secret("OPENROUTER_APP_URL")
        title = _secret("OPENROUTER_APP_TITLE")

        def _gen(model_id):
            return stream_chat(api_messages, api_key, model_id,
                               referer=referer, title=title,
                               temperature=float(chat_cfg.get("temperatura", 0.1)),
                               max_tokens=int(chat_cfg.get("max_tokens", 600)))

        with st.chat_message("assistant"):
            answer, err = None, None
            for model_id in (model, fallback):
                try:
                    answer = st.write_stream(_gen(model_id))
                    break
                except ChatAuthError:
                    err = "auth"; break
                except ChatRateLimitError:
                    err = "rate"; break
                except (ChatUnavailable, ChatError):
                    err = "api"; continue   # intenta el modelo de respaldo

            if answer:
                st.caption("ℹ️ " + t("chat_pie_ia", lang))
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            elif err == "auth":
                st.info(t("chat_sin_clave", lang))
                st.markdown(_links_md(links))
            elif err == "rate":
                st.warning(t("chat_rate_limit", lang))
            else:
                st.error(t("chat_error_api", lang))
