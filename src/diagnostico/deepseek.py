"""deepseek — Formula hipótesis de causa probable y las contrasta contra
la evidencia congelada, en una sola llamada a DeepSeek (FR-004 a FR-008,
research.md §2/§3). Orquesta también el ciclo completo de `diagnosticar`
(cortacircuitos de gasto, llamada, parseo, persistencia) — mismo patrón
que `inventory.deliver` orquesta la entrega para `inventory.cli`.

Nunca ejecuta ni propone una acción correctiva (FR-012/FR-013a): cuando
`episodio.es_critico` es cierto, el propio prompt se lo prohíbe
explícitamente al modelo.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

from . import _homelab_bridge as bridge
from . import evidencia, gasto, store
from .model import CONCLUSION_TIPOS, DESENLACES, Diagnostico, Episodio, Hipotesis

_ENDPOINT = "https://api.deepseek.com/chat/completions"
_DEFAULT_MODEL = "deepseek-v4-flash"

# Límite duro de tokens de salida enviado como `max_tokens` — también es
# el número exacto que usa `gasto.hay_presupuesto()` para estimar el
# coste antes de llamar (research.md §6, hallazgo B1 de /speckit-analyze:
# cifra concreta, no un margen "prudente" sin definir).
DIAGNOSTICO_DEEPSEEK_MAX_TOKENS = int(
    os.environ.get("DIAGNOSTICO_DEEPSEEK_MAX_TOKENS", "2000")
)

_PROMPT_INSTRUCCIONES = """\
Eres un diagnosticador de causas probables para episodios de un homelab
doméstico — puede ser un contenedor Docker caído, un disco con uso alto
(feature 009: specs/009-diagnostico-discos/), un check de Home Assistant
(feature 010: specs/010-diagnostico-ha/) — una entidad con batería baja o
estado inesperado, su recorder corrupto, o su API sin responder — un
backup nocturno fallido o parcial (feature 011:
specs/011-diagnostico-backups/) — el rsync general, o algún dump de base
de datos —, o un relay `socat` caído (feature 012:
specs/012-diagnostico-relays/). A continuación tienes la evidencia real
congelada de un episodio (métricas, logs, estado del contenedor, del
disco, de Home Assistant, del backup, o del relay, según cuál sea). No
tienes ninguna fuente de evidencia adicional a la que acudir — toda la
evidencia disponible ya está aquí.

Formula varias hipótesis de causa probable (más de una si la evidencia lo
permite) y contrasta cada una contra la evidencia dada en este mismo
turno. Nunca inventes una causa sin evidencia real que la respalde: si la
evidencia no basta para ninguna hipótesis, dilo explícitamente en vez de
forzar una conclusión.

Responde ÚNICAMENTE con un JSON con esta forma exacta:
{
  "conclusion_tipo": "causa_probable" | "no_diagnosticable",
  "conclusion_texto": "prosa breve de la causa probable, o de por qué no se puede diagnosticar",
  "hipotesis": [
    {"descripcion": "...", "comprobacion": "cómo se contrastó contra la evidencia de arriba",
     "desenlace": "confirmada" | "descartada" | "sin_evidencia_suficiente"}
  ]
}

"desenlace":"confirmada" significa específicamente que ESA hipótesis ES
la causa probable del episodio — no que la comprobación en sí se haya
completado, ni que el contenedor esté "confirmado como sano". Si una
comprobación simplemente descarta una causa (por ejemplo, "las métricas
no muestran presión de recursos"), eso es "descartada", nunca
"confirmada". Si "conclusion_tipo" es "causa_probable", debe haber
exactamente una hipótesis con "desenlace":"confirmada" (la causa
encontrada). Si es "no_diagnosticable" — incluido el caso de un
contenedor que aparenta estar sano y sin ningún episodio real que
explicar — NINGUNA hipótesis puede tener "desenlace":"confirmada": todas
deben ser "descartada" o "sin_evidencia_suficiente".
"""

_PROMPT_CLAUSULA_CRITICO = """\

Este contenedor está en la lista de contenedores críticos del homelab.
No existe ninguna remediación automática para él y este diagnóstico NO
va a desencadenar ninguna acción. NO propongas ninguna acción correctiva
ni la menciones en "conclusion_texto" ni en ninguna "comprobacion" —
limítate a describir la causa probable o la falta de evidencia.
"""

_PROMPT_CLAUSULA_HA_ESTADO = """\

El campo "ha_check_status" es el veredicto YA CALCULADO de si este check
concreto de Home Assistant está fallando ahora mismo (mismo cálculo que
ya hace ha_monitor.py cada 15 minutos) — no lo recalcules tú a partir
del resto de la evidencia. Si "ha_check_status.ok" es true, este check
está sano: concluye "no_diagnosticable" — no hay ningún episodio real de
ESTE check que explicar, aunque el resto de la evidencia (logs del
contenedor, compartidos por otros muchos checks e integraciones de Home
Assistant) muestre problemas reales de otras partes del sistema. Esos
problemas pueden ser reales, pero no son la causa de este check en
concreto, que no está fallando.
"""


_PROMPT_CLAUSULA_RELAY_AGREGADO = """\

El campo "relay_agregado" es evidencia de CUÁNTOS de los relays
vigilados fallaban en cada instante de esta ventana, nunca de CUÁL en
concreto — ese detalle nunca se archivó y no existe. NO nombres, ni en
"conclusion_texto" ni en ninguna "comprobacion", ningún relay concreto
como la causa de este episodio — como mucho, describe el patrón
agregado (cuántos caían, durante cuánto tiempo) y trátalo como una
limitación real de la evidencia, no algo que puedas deducir.
"""


def construir_prompt(snapshot: dict, es_critico: bool) -> str:
    prompt = _PROMPT_INSTRUCCIONES
    if es_critico:
        prompt += _PROMPT_CLAUSULA_CRITICO
    if snapshot.get("ha_check_status") is not None:
        prompt += _PROMPT_CLAUSULA_HA_ESTADO
    if snapshot.get("relay_agregado") is not None:
        prompt += _PROMPT_CLAUSULA_RELAY_AGREGADO
    prompt += "\nEvidencia del episodio:\n"
    prompt += json.dumps(snapshot, ensure_ascii=False, default=str, indent=2)
    return prompt


def _menciona_relay_concreto(parsed: dict, nombres: set[str]) -> bool:
    """Comprueba si la respuesta ya parseada nombra literalmente uno de
    `nombres` — usado solo para episodios de relay en diferido, donde
    esa información no existe (FR-006, hallazgo F1 de /speckit-analyze,
    2026-08-12; research.md §10 de specs/012-diagnostico-relays/)."""
    if not nombres:
        return False
    textos = [parsed.get("conclusion_texto", "") or ""]
    for h in parsed.get("hipotesis", []):
        textos.append(h.get("descripcion", "") or "")
        textos.append(h.get("comprobacion", "") or "")
    texto_completo = " ".join(textos).lower()
    return any(nombre.lower() in texto_completo for nombre in nombres)


def _estimar_tokens_entrada(prompt: str) -> int:
    """Estimación previa a la llamada — ~4 caracteres por token, regla
    aproximada habitual. El valor real llega en `usage` tras la
    respuesta; esto solo decide si se llama o no (gasto.hay_presupuesto)."""
    return max(1, len(prompt) // 4)


def llamar_deepseek(prompt: str, modelo: str) -> dict | None:
    """Llamada HTTP pura — sin persistencia, sin lógica de negocio
    (research.md §3). `None` si no hay credencial o si la llamada falla
    por cualquier motivo de red/HTTP; nunca lanza."""
    api_key = bridge.get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    body = json.dumps(
        {
            "model": modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": DIAGNOSTICO_DEEPSEEK_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }
    ).encode()

    req = urllib.request.Request(
        _ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(
            req, context=ssl.create_default_context(), timeout=90
        ) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def parsear_respuesta(respuesta: dict) -> dict | None:
    """Valida el invariante FR-007 antes de devolver nada. `None` si el
    contenido no es JSON válido o no cumple el invariante — se trata
    igual que "DeepSeek no responde" en los Edge Cases del spec, nunca
    como una tercera categoría sin definir.

    `content` vacío con `reasoning_content` poblado (hallazgo real al
    validar specs/010-diagnostico-ha/ en vivo, 2026-08-12): el modelo de
    razonamiento a veces escribe la respuesta completa en
    `reasoning_content` y nunca la vuelve a escribir en `content`, pese
    a `finish_reason: "stop"` — el mismo síntoma que el CLAUDE.md general
    del homelab ya documenta para el backend local de los crons de
    Bautista (`qwen/qwen3.5-9b`), aquí en el propio DeepSeek de la nube.
    Sin este respaldo, esas respuestas —completas y válidas, solo en el
    campo equivocado— se descartaban como "inconsistentes" y quemaban
    gasto real sin producir ningún diagnóstico. Si `reasoning_content`
    tampoco es JSON válido (p. ej. narrativa de razonamiento sin la
    respuesta final, o la generación se cortó por `max_tokens` antes de
    llegar a ella), `json.loads` falla igual que antes y se devuelve
    `None` — este respaldo nunca empeora el caso ya manejado."""
    try:
        mensaje = respuesta["choices"][0]["message"]
        contenido = mensaje.get("content") or mensaje.get("reasoning_content") or ""
        usage = respuesta.get("usage", {})
        tokens_entrada = int(usage.get("prompt_tokens", 0))
        tokens_salida = int(usage.get("completion_tokens", 0))

        parsed = json.loads(contenido)
        conclusion_tipo = parsed["conclusion_tipo"]
        conclusion_texto = parsed["conclusion_texto"]
        hipotesis = parsed.get("hipotesis", [])

        if conclusion_tipo not in CONCLUSION_TIPOS:
            return None
        for h in hipotesis:
            if h.get("desenlace") not in DESENLACES:
                return None
            if not h.get("descripcion") or not h.get("comprobacion"):
                return None

        confirmadas = [h for h in hipotesis if h["desenlace"] == "confirmada"]
        if conclusion_tipo == "causa_probable" and len(confirmadas) != 1:
            return None  # invariante FR-007: causa_probable exige EXACTAMENTE
            # una confirmada, igual que le exige el prompt (_PROMPT_INSTRUCCIONES)
            # — no solo "al menos una". Antes de /speckit-analyze 2026-08-11
            # (hallazgo I2) esto solo rechazaba el caso vacío, aceptando en
            # silencio una respuesta con dos o más "confirmada" a la vez pese
            # a que el prompt pide una sola causa.
        if conclusion_tipo == "no_diagnosticable" and confirmadas:
            return None  # invariante FR-007: no_diagnosticable exige ninguna

        return {
            "conclusion_tipo": conclusion_tipo,
            "conclusion_texto": conclusion_texto,
            "hipotesis": hipotesis,
            "tokens_entrada": tokens_entrada,
            "tokens_salida": tokens_salida,
        }
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def _tokens_de_respuesta_fallida(respuesta: dict) -> tuple[int, int]:
    usage = respuesta.get("usage", {}) if isinstance(respuesta, dict) else {}
    try:
        return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
    except (TypeError, ValueError):
        return 0, 0


def diagnosticar_episodio(
    conn, episodio: Episodio
) -> tuple[Diagnostico, list[Hipotesis]]:
    """Orquesta el ciclo completo de un intento de diagnóstico: carga el
    snapshot ya congelado (nunca vuelve a consultar homelab.db/Docker,
    FR-002), aplica el cortacircuitos de gasto (FR-010), llama a
    DeepSeek si hay presupuesto, parsea, persiste el diagnóstico y sus
    hipótesis, y registra el coste real."""
    modelo = os.environ.get("DIAGNOSTICO_DEEPSEEK_MODEL", _DEFAULT_MODEL)
    prompt = construir_prompt(episodio.snapshot_evidencia, episodio.es_critico)

    def _persistir_sin_llamada(motivo: str, tokens_entrada: int = 0, tokens_salida: int = 0,
                                coste_eur: float = 0.0) -> tuple[Diagnostico, list[Hipotesis]]:
        diagnostico = Diagnostico(
            episodio_id=episodio.id,
            conclusion_tipo="no_diagnosticable",
            conclusion_texto=motivo,
            modelo=modelo,
            tokens_entrada=tokens_entrada,
            tokens_salida=tokens_salida,
            coste_eur=coste_eur,
        )
        diagnostico.id = store.insert_diagnostico(conn, diagnostico)
        return diagnostico, []

    if not gasto.hay_presupuesto(conn, _estimar_tokens_entrada(prompt)):
        return _persistir_sin_llamada("no se puede diagnosticar sin superar el límite de gasto diario")

    if not bridge.get_secret("DEEPSEEK_API_KEY"):
        return _persistir_sin_llamada("sin credencial DEEPSEEK_API_KEY configurada")

    respuesta = llamar_deepseek(prompt, modelo)
    if respuesta is None:
        return _persistir_sin_llamada("DeepSeek no respondió o la llamada falló")

    parsed = parsear_respuesta(respuesta)
    if parsed is None:
        # La llamada sí ocurrió (hay coste real que registrar) aunque el
        # contenido no cumpliera el formato/invariante esperado.
        tokens_entrada, tokens_salida = _tokens_de_respuesta_fallida(respuesta)
        coste = gasto.registrar_coste(conn, tokens_entrada, tokens_salida)
        return _persistir_sin_llamada(
            "respuesta de DeepSeek inconsistente con el formato esperado",
            tokens_entrada, tokens_salida, coste,
        )

    # FR-006 validado en código, no solo pedido en el prompt (hallazgo
    # F1 de /speckit-analyze, 2026-08-12; research.md §10 de
    # specs/012-diagnostico-relays/) — mismo tratamiento que una
    # respuesta inconsistente: la llamada sí ocurrió, se registra el
    # coste real, pero se rechaza el contenido.
    if episodio.origen == "relay" and episodio.snapshot_evidencia.get("relay_agregado") is not None:
        if _menciona_relay_concreto(parsed, evidencia.listar_nombres_relay()):
            coste = gasto.registrar_coste(conn, parsed["tokens_entrada"], parsed["tokens_salida"])
            return _persistir_sin_llamada(
                "respuesta de DeepSeek nombra un relay concreto en un episodio en "
                "diferido, sin evidencia real de cuál falló — rechazada (FR-006)",
                parsed["tokens_entrada"], parsed["tokens_salida"], coste,
            )

    coste = gasto.registrar_coste(conn, parsed["tokens_entrada"], parsed["tokens_salida"])
    diagnostico = Diagnostico(
        episodio_id=episodio.id,
        conclusion_tipo=parsed["conclusion_tipo"],
        conclusion_texto=parsed["conclusion_texto"],
        modelo=modelo,
        tokens_entrada=parsed["tokens_entrada"],
        tokens_salida=parsed["tokens_salida"],
        coste_eur=coste,
    )
    diagnostico.id = store.insert_diagnostico(conn, diagnostico)

    hipotesis_objs: list[Hipotesis] = []
    for i, h in enumerate(parsed["hipotesis"]):
        hip = Hipotesis(
            diagnostico_id=diagnostico.id,
            orden=i,
            descripcion=h["descripcion"],
            comprobacion=h["comprobacion"],
            desenlace=h["desenlace"],
        )
        hip.id = store.insert_hipotesis(conn, hip)
        hipotesis_objs.append(hip)

    return diagnostico, hipotesis_objs
