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
