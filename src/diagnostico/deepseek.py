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
from . import gasto, store
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
Eres un diagnosticador de causas probables para episodios de contenedores
Docker en un homelab doméstico. A continuación tienes la evidencia real
congelada de un episodio (métricas, logs, estado del contenedor). No
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


def construir_prompt(snapshot: dict, es_critico: bool) -> str:
    prompt = _PROMPT_INSTRUCCIONES
    if es_critico:
        prompt += _PROMPT_CLAUSULA_CRITICO
    prompt += "\nEvidencia del episodio:\n"
    prompt += json.dumps(snapshot, ensure_ascii=False, default=str, indent=2)
    return prompt


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
    como una tercera categoría sin definir."""
    try:
        contenido = respuesta["choices"][0]["message"]["content"]
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
        if conclusion_tipo == "causa_probable" and not confirmadas:
            return None  # invariante FR-007: causa_probable exige >=1 confirmada
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
