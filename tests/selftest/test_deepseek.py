"""test_deepseek — T021: el prompt incluye la cláusula "sin acción"
cuando `es_critico=True`, `parsear_respuesta` acepta una respuesta bien
formada y trata como fallo una mal formada (JSON inválido, o las dos
conclusiones a la vez), invariante FR-007 comprobado, y una respuesta con
evidencia suficiente produce más de una hipótesis (SC-003). Sin llamada
HTTP real en ningún caso — todo contra respuestas simuladas.
"""

from __future__ import annotations

import json

from diagnostico import deepseek
from tests.selftest import check


def _respuesta_deepseek(contenido: dict, tokens_entrada: int = 500, tokens_salida: int = 300) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(contenido, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": tokens_entrada, "completion_tokens": tokens_salida},
    }


def test_construir_prompt_incluye_clausula_sin_accion_si_es_critico() -> None:
    snapshot = {"restart_history": None, "container_metrics": []}
    prompt_critico = deepseek.construir_prompt(snapshot, es_critico=True)
    prompt_normal = deepseek.construir_prompt(snapshot, es_critico=False)

    check(
        "prompt de contenedor crítico incluye la cláusula de no proponer acciones",
        "NO propongas ninguna acción correctiva" in prompt_critico,
    )
    check(
        "prompt de contenedor no crítico no lleva esa cláusula",
        "NO propongas ninguna acción correctiva" not in prompt_normal,
    )


def test_parsear_respuesta_bien_formada_con_varias_hipotesis() -> None:
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "presión de memoria en la ventana del episodio",
        "hipotesis": [
            {"descripcion": "presión de memoria", "comprobacion": "memory_percent > 90% en la ventana",
             "desenlace": "confirmada"},
            {"descripcion": "fallo de red", "comprobacion": "sin errores de conexión en los logs",
             "desenlace": "descartada"},
        ],
    })
    parsed = deepseek.parsear_respuesta(respuesta)

    check("respuesta bien formada se acepta", parsed is not None)
    check("conclusion_tipo se conserva", parsed["conclusion_tipo"] == "causa_probable")
    check("SC-003: más de una hipótesis registrada", len(parsed["hipotesis"]) > 1)
    check("tokens reales de la respuesta, no estimados", parsed["tokens_entrada"] == 500)


def test_parsear_respuesta_no_diagnosticable_sin_confirmadas() -> None:
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "no_diagnosticable",
        "conclusion_texto": "sin evidencia suficiente para ninguna hipótesis",
        "hipotesis": [
            {"descripcion": "presión de memoria", "comprobacion": "métricas ya purgadas por retención",
             "desenlace": "sin_evidencia_suficiente"},
        ],
    })
    parsed = deepseek.parsear_respuesta(respuesta)
    check("no_diagnosticable sin ninguna confirmada se acepta", parsed is not None)


def test_parsear_respuesta_rechaza_json_invalido() -> None:
    respuesta = {
        "choices": [{"message": {"content": "esto no es JSON"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    check("contenido no-JSON se rechaza (None)", deepseek.parsear_respuesta(respuesta) is None)


def test_parsear_respuesta_rechaza_invariante_fr007_violado() -> None:
    # causa_probable sin ninguna hipótesis confirmada — viola FR-007
    respuesta_1 = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "algo",
        "hipotesis": [{"descripcion": "a", "comprobacion": "b", "desenlace": "descartada"}],
    })
    check(
        "causa_probable sin hipótesis confirmada viola FR-007 ⇒ se rechaza",
        deepseek.parsear_respuesta(respuesta_1) is None,
    )

    # no_diagnosticable con una hipótesis confirmada — también viola FR-007
    respuesta_2 = _respuesta_deepseek({
        "conclusion_tipo": "no_diagnosticable",
        "conclusion_texto": "algo",
        "hipotesis": [{"descripcion": "a", "comprobacion": "b", "desenlace": "confirmada"}],
    })
    check(
        "no_diagnosticable con hipótesis confirmada viola FR-007 ⇒ se rechaza",
        deepseek.parsear_respuesta(respuesta_2) is None,
    )


def test_parsear_respuesta_rechaza_desenlace_invalido() -> None:
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "algo",
        "hipotesis": [{"descripcion": "a", "comprobacion": "b", "desenlace": "quizas"}],
    })
    check("desenlace fuera del vocabulario se rechaza", deepseek.parsear_respuesta(respuesta) is None)
