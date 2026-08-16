"""deepseek_agentes — Pregunta propia de esta feature a DeepSeek: dada
la evidencia real de un LaunchAgent/LaunchDaemon sin proceso activo,
¿aplica `reiniciar_agente`, o ninguna acción de la lista cerrada
resuelve el caso? (specs/026-reiniciar-agentes-relays/research.md §5)

Mismo patrón que `deepseek_contenedores.py` — módulo propio, distinto
de `diagnostico.deepseek.construir_prompt` (esa pregunta "¿cuál es la
causa probable?" es abierta; esta es "¿aplica esta acción, sí o no?").
Reutiliza la extracción de contenido/tokens ya compartida
(`diagnostico.deepseek._extraer_contenido_y_tokens`, consolidada en
025) — nunca la lógica de negocio de hipótesis.

`REMEDIACION_DEEPSEEK_MOCK` (la misma variable de entorno que ya usa
`deepseek_contenedores.py`) sustituye la llamada real por una
respuesta ya parseada — un solo mock activo por invocación de CLI,
nunca se llaman ambos flujos (contenedores/agentes) a la vez.
"""

from __future__ import annotations

import json
import os

from diagnostico.deepseek import _extraer_contenido_y_tokens


def construir_prompt_agente(episodio, acciones_candidatas: tuple[str, ...]) -> str:
    """Prompt específico de esta feature — "¿aplica reiniciar este
    agente?", no "¿cuál es la causa?" (research.md §5)."""
    instrucciones = f"""\
Eres el módulo de remediación de un homelab doméstico. Tienes evidencia
real de un LaunchAgent o LaunchDaemon (`launchd`, macOS) que no tiene un
proceso activo: su label, su PID actual (o "-" si no hay ninguno), y su
último código de salida.

Tu única pregunta es: dada esta evidencia, ¿alguna de las siguientes
acciones ya aprobadas resuelve el caso?

Acciones disponibles: {", ".join(acciones_candidatas)}

Reglas estrictas:
- NUNCA propongas ni menciones una acción que no esté en esa lista —
  si ninguna de ellas resuelve el caso, responde que ninguna aplica.
- Si la evidencia indica que el problema es externo al propio proceso
  (por ejemplo, un permiso del sistema que un reinicio no cambiaría),
  no recomiendes reiniciar solo porque el agente esté caído.
- Responde ÚNICAMENTE con un objeto JSON con esta forma exacta:
  {{"accion_aplica": "reiniciar_agente", "razonamiento": "..."}}
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


def parsear_respuesta_agente(respuesta: dict) -> dict | None:
    """Valida antes de devolver nada — `None` si el contenido no es
    JSON válido, no tiene los campos esperados, o `accion_aplica` no
    está en la lista cerrada. Mismo respaldo `content`/`reasoning_content`
    que `diagnostico.deepseek.parsear_respuesta`, vía la extracción
    compartida `_extraer_contenido_y_tokens` (025)."""
    try:
        parsed, tokens_entrada, tokens_salida = _extraer_contenido_y_tokens(respuesta)
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    return _validar_decision(parsed, tokens_entrada, tokens_salida)


def respuesta_mock() -> dict | None:
    """Lee `REMEDIACION_DEEPSEEK_MOCK` — `None` si no está presente, no
    es JSON válido, o no cumple el invariante de la lista cerrada. Sin
    coste asociado (nunca gasta presupuesto real)."""
    crudo = os.environ.get("REMEDIACION_DEEPSEEK_MOCK")
    if not crudo:
        return None
    try:
        parsed = json.loads(crudo)
    except ValueError:
        return None
    return _validar_decision(parsed)
