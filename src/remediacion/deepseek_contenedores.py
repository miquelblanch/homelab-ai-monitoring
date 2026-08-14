"""deepseek_contenedores — Pregunta propia de esta feature a DeepSeek:
dada la evidencia real de un contenedor no crítico caído, ¿aplica
`reiniciar_contenedor`, o ninguna acción de la lista cerrada resuelve
el caso? (specs/021-remediacion-contenedores/research.md §3)

Distinta, deliberadamente, de `diagnostico.deepseek.construir_prompt`
(que pregunta "¿cuál es la causa probable?", una pregunta abierta que
en 36/36 casos reales termina en `no_diagnosticable`) — reutiliza solo
la llamada HTTP pura (`diagnostico.deepseek.llamar_deepseek`), nunca
su lógica de negocio de hipótesis.

`REMEDIACION_DEEPSEEK_MOCK` (variable de entorno, JSON con
`accion_aplica`/`razonamiento`) sustituye la llamada real por una
respuesta ya parseada, controlada — nunca gasta presupuesto real ni
depende de que DeepSeek esté disponible (quickstart.md, todos los
escenarios salvo el 6).
"""

from __future__ import annotations

import json
import os


def construir_prompt_remediacion(episodio, acciones_candidatas: tuple[str, ...]) -> str:
    """Prompt específico de esta feature — "¿qué acción de esta lista
    aplica?", no "¿cuál es la causa?" (research.md §3)."""
    instrucciones = f"""\
Eres el módulo de remediación de un homelab doméstico. Tienes evidencia
real de un contenedor Docker no crítico que no está `running and
healthy`: su estado actual, métricas recientes, `docker inspect` y las
últimas líneas de sus logs.

Tu única pregunta es: dada esta evidencia, ¿alguna de las siguientes
acciones ya aprobadas resuelve el caso?

Acciones disponibles: {", ".join(acciones_candidatas)}

Reglas estrictas:
- NUNCA propongas ni menciones una acción que no esté en esa lista —
  si ninguna de ellas resuelve el caso, responde que ninguna aplica.
- Si la evidencia indica que el problema es externo al propio proceso
  del contenedor (p. ej. un recurso de red, disco, o dependencia que
  reiniciar no arreglaría), no recomiendes reiniciar solo porque el
  contenedor esté caído.
- Responde ÚNICAMENTE con un objeto JSON con esta forma exacta:
  {{"accion_aplica": "reiniciar_contenedor", "razonamiento": "..."}}
  o, si ninguna acción resuelve el caso:
  {{"accion_aplica": null, "razonamiento": "..."}}
"""
    return instrucciones + "\nEvidencia del episodio:\n" + json.dumps(
        episodio.snapshot_evidencia, ensure_ascii=False, default=str, indent=2
    )


def _accion_valida(valor: str | None) -> bool:
    """Valida `accion_aplica` contra la lista cerrada de acciones.py —
    import diferido para evitar un ciclo de importación (acciones.py
    importa este módulo a nivel de módulo)."""
    if valor is None:
        return True
    from . import acciones

    return valor in acciones.TIPOS_ACCION


def _validar_decision(parsed: dict, tokens_entrada: int = 0, tokens_salida: int = 0) -> dict | None:
    try:
        accion_aplica = parsed["accion_aplica"]
        razonamiento = parsed["razonamiento"]
    except (KeyError, TypeError):
        return None
    if not _accion_valida(accion_aplica):
        return None
    return {
        "accion_aplica": accion_aplica,
        "razonamiento": razonamiento,
        "tokens_entrada": tokens_entrada,
        "tokens_salida": tokens_salida,
    }


def parsear_respuesta_remediacion(respuesta: dict) -> dict | None:
    """Valida FR-003 antes de devolver nada — `None` si el contenido no
    es JSON válido, no tiene los campos esperados, o `accion_aplica` no
    está en la lista cerrada (nunca confía en un valor libre devuelto
    por el modelo). Mismo respaldo `content`/`reasoning_content` que
    `diagnostico.deepseek.parsear_respuesta` para el caso de un modelo
    de razonamiento que deja `content` vacío (research.md §3)."""
    try:
        mensaje = respuesta["choices"][0]["message"]
        contenido = mensaje.get("content") or mensaje.get("reasoning_content") or ""
        usage = respuesta.get("usage", {})
        tokens_entrada = int(usage.get("prompt_tokens", 0))
        tokens_salida = int(usage.get("completion_tokens", 0))
        parsed = json.loads(contenido)
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    return _validar_decision(parsed, tokens_entrada, tokens_salida)


def respuesta_mock() -> dict | None:
    """Lee `REMEDIACION_DEEPSEEK_MOCK` — `None` si no está presente, no
    es JSON válido, o no cumple el invariante FR-003. Sin coste
    asociado (nunca gasta presupuesto real)."""
    crudo = os.environ.get("REMEDIACION_DEEPSEEK_MOCK")
    if not crudo:
        return None
    try:
        parsed = json.loads(crudo)
    except ValueError:
        return None
    return _validar_decision(parsed)
