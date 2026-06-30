"""Cliente de IA por HTTP (API compatible con OpenAI) con streaming.

Sin Streamlit a propósito (testeable y reutilizable): recibe la api_key como
argumento. Las excepciones tipadas permiten que la UI degrade con un mensaje
claro en vez de romperse. NO contiene lógica de datos: solo transporte.
"""
import json

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Los valores de cabecera HTTP deben ser latin-1. Normaliza la puntuación
# tipográfica (— “ ” ’ …) y descarta lo no codificable, para que un título o
# URL con guion largo no rompa la petición (UnicodeEncodeError en http.client).
_PUNCT = {"—": "-", "–": "-", "‒": "-", "‘": "'", "’": "'",
          "“": '"', "”": '"', "…": "...", " ": " "}


def _latin1(value: str) -> str:
    if not value:
        return ""
    for bad, good in _PUNCT.items():
        value = value.replace(bad, good)
    return value.encode("latin-1", "ignore").decode("latin-1")


class ChatError(Exception):
    """Error genérico del asistente."""


class ChatAuthError(ChatError):
    """Falta la clave, es inválida (401/403) o no hay crédito (402)."""


class ChatRateLimitError(ChatError):
    """Límite de peticiones alcanzado (429)."""


class ChatUnavailable(ChatError):
    """El servicio no respondió (timeout / red / 5xx)."""


def stream_chat(messages, api_key, model, *, referer="", title="",
                temperature=0.1, max_tokens=600, timeout=(5, 60)):
    """Hace *yield* de los fragmentos de texto de la respuesta del modelo.

    `messages`: lista estilo OpenAI [{"role", "content"}, ...].
    Lanza ChatAuthError / ChatRateLimitError / ChatUnavailable según el fallo.
    Es un generador: la petición y la validación de estado ocurren al consumir
    el primer fragmento (por eso la UI debe envolver el consumo en try/except).
    """
    if not api_key:
        raise ChatAuthError("missing_api_key")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if referer:
        headers["HTTP-Referer"] = _latin1(referer)
    if title:
        headers["X-Title"] = _latin1(title)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    try:
        r = requests.post(API_URL, headers=headers, json=payload,
                          stream=True, timeout=timeout)
    except requests.RequestException as e:
        raise ChatUnavailable(str(e))

    if r.status_code in (401, 403):
        raise ChatAuthError(f"HTTP {r.status_code}")
    if r.status_code == 402:                       # sin crédito → permite caer al modelo de respaldo
        raise ChatUnavailable("HTTP 402 (sin credito)")
    if r.status_code == 429:
        raise ChatRateLimitError("HTTP 429")
    if r.status_code >= 500:
        raise ChatUnavailable(f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ChatError(f"HTTP {r.status_code}: {r.text[:200]}")

    # Decodificamos cada línea como UTF-8 explícitamente: ante 'text/event-stream'
    # sin charset, requests asume latin-1 y produce mojibake (p.ej. 'poblaciÃ³n').
    for raw in r.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
            delta = obj["choices"][0]["delta"].get("content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
        if delta:
            yield delta


def complete_chat(messages, api_key, model, **kw):
    """Versión no-streaming: concatena y devuelve el texto completo."""
    return "".join(stream_chat(messages, api_key, model, **kw))


def _json_default(o):
    """Serializa tipos numpy/NaN a JSON (null para NaN); resto → str."""
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            f = float(o)
            return None if f != f else f      # NaN → null
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    return str(o)


def _post_chat(messages, api_key, model, *, referer="", title="", temperature=0.0,
               max_tokens=700, tools=None, tool_choice="auto", timeout=(5, 60)):
    """Una llamada NO-streaming (para las rondas de tool-calling). Devuelve el JSON."""
    if not api_key:
        raise ChatAuthError("missing_api_key")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if referer:
        headers["HTTP-Referer"] = _latin1(referer)
    if title:
        headers["X-Title"] = _latin1(title)
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens, "stream": False}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as e:
        raise ChatUnavailable(str(e))
    if r.status_code in (401, 403):
        raise ChatAuthError(f"HTTP {r.status_code}")
    if r.status_code == 402:
        raise ChatUnavailable("HTTP 402 (sin credito)")
    if r.status_code == 429:
        raise ChatRateLimitError("HTTP 429")
    if r.status_code >= 500:
        raise ChatUnavailable(f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ChatError(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except Exception as e:
        raise ChatUnavailable(f"respuesta no JSON: {e}")


def agentic_chat(messages, api_key, model, tools, dispatch, *, referer="", title="",
                 temperature=0.0, max_tokens=700, max_iters=5, max_tools=8, timeout=(5, 60)):
    """Bucle de tool-calling: el modelo invoca skills reales y se reinyectan sus
    resultados (role:'tool'). Devuelve los mensajes ENRIQUECIDOS, listos para una
    última llamada en streaming que redacta la respuesta solo con esos datos.

    `dispatch(name, args)` ejecuta la skill y devuelve un dict serializable.
    Nunca deja la conversación a medias: si el modelo malforma los argumentos, se
    pasa {} ; si una skill falla, dispatch devuelve {disponible:false}.
    """
    api_messages = list(messages)
    tool_budget = max_tools
    for i in range(max_iters):
        force_none = (i == max_iters - 1)            # último round: que redacte ya
        resp = _post_chat(api_messages, api_key, model, referer=referer, title=title,
                          temperature=temperature, max_tokens=max_tokens, tools=tools,
                          tool_choice=("none" if force_none else "auto"), timeout=timeout)
        msg = (resp.get("choices") or [{}])[0].get("message", {}) or {}
        calls = msg.get("tool_calls") or []
        if not calls or tool_budget <= 0:
            break
        api_messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": calls})
        for tc in calls:
            if tool_budget <= 0:
                break
            tool_budget -= 1
            fn = tc.get("function") or {}
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
                if not isinstance(args, dict):
                    args = {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            result = dispatch(name, args)
            api_messages.append({"role": "tool", "tool_call_id": tc.get("id"), "name": name,
                                 "content": json.dumps(result, ensure_ascii=False,
                                                       default=_json_default)})
    return api_messages
