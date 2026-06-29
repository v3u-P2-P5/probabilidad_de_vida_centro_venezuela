"""Cliente de IA por HTTP (API compatible con OpenAI) con streaming.

Sin Streamlit a propósito (testeable y reutilizable): recibe la api_key como
argumento. Las excepciones tipadas permiten que la UI degrade con un mensaje
claro en vez de romperse. NO contiene lógica de datos: solo transporte.
"""
import json

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"


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
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

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

    if r.status_code in (401, 402, 403):
        raise ChatAuthError(f"HTTP {r.status_code}")
    if r.status_code == 429:
        raise ChatRateLimitError("HTTP 429")
    if r.status_code >= 500:
        raise ChatUnavailable(f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise ChatError(f"HTTP {r.status_code}: {r.text[:200]}")

    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[5:].strip()
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
