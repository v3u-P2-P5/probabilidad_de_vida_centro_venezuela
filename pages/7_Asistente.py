"""Asistente IA con grounding (API compatible con OpenAI) — responde SOLO con datos reales.

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
from core.chat_prompt import (classify_intent, sanitize_user_input,
                              system_prompt, system_prompt_v2)
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
        history = st.session_state.chat_history[-6:]
        referer = _secret("OPENROUTER_APP_URL")
        title = _secret("OPENROUTER_APP_TITLE")
        temperature = float(chat_cfg.get("temperatura", 0.0))
        max_tokens = int(chat_cfg.get("max_tokens", 700))
        model = chat_cfg.get("modelo", "google/gemini-2.5-flash-lite")
        fallback = chat_cfg.get("modelo_fallback", "")
        tools_cfg = chat_cfg.get("tools", {}) or {}
        tools_on = bool(tools_cfg.get("activo", False))
        modelos_tools = tools_cfg.get("modelos_con_tools", [])

        def _messages_v1():
            ctx_block = build_chat_context(lang)
            return [{"role": "system", "content": system_prompt(lang, ctx_block)}] + history

        with st.chat_message("assistant"):
            answer, err = None, None

            # Camino AGÉNTICO (skills/tool-calling) con modelos que soportan tools.
            if tools_on:
                from core.chat import agentic_chat
                from core.chat_tools import TOOLS_SCHEMA, dispatch
                base_v2 = [{"role": "system", "content": system_prompt_v2(lang)}] + history
                for model_id in [m for m in (model, fallback) if m in modelos_tools]:
                    try:
                        enriched = agentic_chat(
                            base_v2, api_key, model_id, TOOLS_SCHEMA, dispatch,
                            referer=referer, title=title, temperature=temperature,
                            max_tokens=max_tokens,
                            max_iters=int(tools_cfg.get("max_iteraciones", 5)),
                            max_tools=int(tools_cfg.get("max_tools_por_turno", 8)))
                        answer = st.write_stream(stream_chat(
                            enriched, api_key, model_id, referer=referer, title=title,
                            temperature=temperature, max_tokens=max_tokens))
                        err = None
                        break
                    except ChatAuthError:
                        err = "auth"; break
                    except ChatRateLimitError:
                        err = "rate"; continue
                    except (ChatUnavailable, ChatError):
                        err = "api"; continue

            # Camino v1 (context-pack) si tools off, modelo no apto o todos fallaron.
            if answer is None and err != "auth":
                for model_id in (model, fallback):
                    if not model_id:
                        continue
                    try:
                        answer = st.write_stream(stream_chat(
                            _messages_v1(), api_key, model_id, referer=referer, title=title,
                            temperature=temperature, max_tokens=max_tokens))
                        err = None
                        break
                    except ChatAuthError:
                        err = "auth"; break
                    except ChatRateLimitError:
                        err = "rate"; continue
                    except (ChatUnavailable, ChatError):
                        err = "api"; continue

            if answer:
                st.caption("ℹ️ " + t("chat_pie_ia", lang))
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            elif err == "auth":
                st.info(t("chat_sin_clave", lang))
                st.markdown(_links_md(links))
            elif err == "rate":
                st.warning(t("chat_ocupado", lang))
            else:
                st.error(t("chat_error_api", lang))
