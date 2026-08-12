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


def test_construir_prompt_disco_nunca_lleva_clausula_de_critico() -> None:
    """feature 009: es_critico siempre False para un episodio de disco
    (research.md §4 de specs/009-diagnostico-discos/) — el prompt debe
    comportarse exactamente igual que para un contenedor no crítico."""
    snapshot_disco = {
        "disco": {"label": "FastData", "path": "/Volumes/FastData"},
        "disk_metrics": [],
    }
    prompt = deepseek.construir_prompt(snapshot_disco, es_critico=False)
    check(
        "prompt de episodio de disco no lleva la cláusula de contenedor crítico",
        "NO propongas ninguna acción correctiva" not in prompt,
    )


def test_construir_prompt_backup_nunca_lleva_clausula_de_critico() -> None:
    """feature 011: es_critico siempre False para un episodio de backup
    (research.md §7 de specs/011-diagnostico-backups/)."""
    snapshot_backup = {
        "backup_log_path": "/Volumes/FastData/homelab/logs/backup_2026-08-12_02-00-00.log",
        "backup_resumen_final": "Duración 17m 36s — rsync completo",
    }
    prompt = deepseek.construir_prompt(snapshot_backup, es_critico=False)
    check(
        "prompt de episodio de backup no lleva la cláusula de contenedor crítico",
        "NO propongas ninguna acción correctiva" not in prompt,
    )
    check("prompt generalizado menciona backup", "backup" in prompt)


def test_parsear_respuesta_backup_con_varias_hipotesis() -> None:
    """Hallazgo C1 de /speckit-analyze (2026-08-12, SC-002 de
    specs/011-diagnostico-backups/): mismo patrón que
    test_parsear_respuesta_disco_con_varias_hipotesis (009) y
    test_parsear_respuesta_ha_con_varias_hipotesis (010) — el motor
    generalizado debe seguir aceptando más de una hipótesis también
    para un episodio de backup."""
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "el dump de MariaDB falló por falta de espacio temporal",
        "hipotesis": [
            {"descripcion": "disco de origen sin espacio para el dump temporal",
             "comprobacion": "el log muestra el dump fallido justo antes del rsync principal",
             "desenlace": "confirmada"},
            {"descripcion": "credencial de MariaDB caducada",
             "comprobacion": "el resto de dumps de esa misma noche completaron sin problema",
             "desenlace": "descartada"},
        ],
    })
    parsed = deepseek.parsear_respuesta(respuesta)

    check("respuesta de backup bien formada se acepta", parsed is not None)
    check("SC-002: más de una hipótesis registrada para un episodio de backup", len(parsed["hipotesis"]) > 1)


def test_construir_prompt_ha_nunca_lleva_clausula_de_critico() -> None:
    """feature 010: es_critico siempre False para un episodio de HA
    (research.md §8 de specs/010-diagnostico-ha/) — mismo criterio que
    ya vale para disco."""
    snapshot_ha = {
        "ha_check": {"id": "bateria_interruptor_salon", "type": "entity_value_below"},
        "ha_history": [{"state": "18", "last_changed": "2026-08-12T10:00:00"}],
    }
    prompt = deepseek.construir_prompt(snapshot_ha, es_critico=False)
    check(
        "prompt de episodio de HA no lleva la cláusula de contenedor crítico",
        "NO propongas ninguna acción correctiva" not in prompt,
    )
    check(
        "prompt generalizado menciona Home Assistant",
        "Home Assistant" in prompt,
    )
    check(
        "la evidencia de HA del snapshot llega al prompt",
        '"bateria_interruptor_salon"' in prompt,
    )


def test_construir_prompt_ha_incluye_clausula_de_estado_solo_si_hay_check_status() -> None:
    """Hallazgo real de validación en vivo (2026-08-12): sin esta
    cláusula, un check de HA sano (ha_check_status.ok=True) podía
    diagnosticarse como causa_probable citando ruido real pero no
    relacionado de los logs del contenedor (compartidos por 111 checks).
    La cláusula solo debe aparecer en episodios de HA con el veredicto ya
    resuelto — nunca en uno de contenedor o disco."""
    snapshot_ha_sano = {
        "ha_check": {"id": "ha_api", "type": "api_ping"},
        "ha_check_status": {"ok": True, "detalle": "OK", "motivo": ""},
        "docker_logs_tail": "ERROR no relacionado de otra integración",
    }
    prompt_ha = deepseek.construir_prompt(snapshot_ha_sano, es_critico=False)
    check(
        "prompt de episodio de HA con check_status incluye la cláusula de estado",
        "ha_check_status" in prompt_ha and "no hay ningún episodio real de" in prompt_ha,
    )

    snapshot_ha_inexistente = {"ha_check": None, "ha_check_status": None}
    prompt_sin_estado = deepseek.construir_prompt(snapshot_ha_inexistente, es_critico=False)
    check(
        "sin ha_check_status resuelto (check inexistente), no se incluye la cláusula",
        "no hay ningún episodio real de" not in prompt_sin_estado,
    )

    snapshot_contenedor = {"restart_history": None, "container_metrics": []}
    prompt_contenedor = deepseek.construir_prompt(snapshot_contenedor, es_critico=False)
    check(
        "un episodio de contenedor (sin ha_check_status) no lleva la cláusula de HA",
        "no hay ningún episodio real de" not in prompt_contenedor,
    )


def test_parsear_respuesta_ha_con_varias_hipotesis() -> None:
    """SC-002 de specs/010-diagnostico-ha/: el motor generalizado debe
    seguir aceptando más de una hipótesis también para un episodio de
    HA, no solo para uno de contenedor o de disco (mismo patrón que
    test_parsear_respuesta_disco_con_varias_hipotesis, 009 T008)."""
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "batería del interruptor por debajo del umbral desde hace días",
        "hipotesis": [
            {"descripcion": "pila agotada por edad",
             "comprobacion": "el historial muestra una caída sostenida sin recuperación",
             "desenlace": "confirmada"},
            {"descripcion": "fallo de comunicación Zigbee",
             "comprobacion": "el resto de entidades del mismo bridge siguen reportando con normalidad",
             "desenlace": "descartada"},
        ],
    })
    parsed = deepseek.parsear_respuesta(respuesta)

    check("respuesta de HA bien formada se acepta", parsed is not None)
    check("SC-002: más de una hipótesis registrada para un episodio de HA", len(parsed["hipotesis"]) > 1)


def test_parsear_respuesta_disco_con_varias_hipotesis() -> None:
    """hallazgo U1 de /speckit-analyze (2026-08-11, SC-002 de
    specs/009-diagnostico-discos/): el motor generalizado debe seguir
    aceptando más de una hipótesis también para un episodio de disco,
    no solo para uno de contenedor (ya cubierto por el test de abajo)."""
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "el disco crece por backups sin rotar",
        "hipotesis": [
            {"descripcion": "backups acumulados sin rotación",
             "comprobacion": "used_percent sube de forma sostenida en la ventana",
             "desenlace": "confirmada"},
            {"descripcion": "logs sin rotar",
             "comprobacion": "no hay proceso de logrotate reciente en la evidencia",
             "desenlace": "descartada"},
        ],
    })
    parsed = deepseek.parsear_respuesta(respuesta)

    check("respuesta de disco bien formada se acepta", parsed is not None)
    check("SC-002: más de una hipótesis registrada para un episodio de disco", len(parsed["hipotesis"]) > 1)


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


def test_parsear_respuesta_usa_reasoning_content_si_content_vacio() -> None:
    """Hallazgo real al validar specs/010-diagnostico-ha/ en vivo
    (2026-08-12): un modelo de razonamiento puede dejar `content` vacío
    y escribir la respuesta completa en `reasoning_content` pese a
    `finish_reason: "stop"` — mismo síntoma que el backend local
    documentado en el CLAUDE.md general del homelab. Sin este respaldo,
    una respuesta completa y válida se descartaba como inconsistente."""
    contenido_json = json.dumps({
        "conclusion_tipo": "no_diagnosticable",
        "conclusion_texto": "transición momentánea sin más contexto",
        "hipotesis": [
            {"descripcion": "fallo transitorio de red",
             "comprobacion": "un único cambio de estado sin logs que lo expliquen",
             "desenlace": "sin_evidencia_suficiente"},
        ],
    }, ensure_ascii=False)
    respuesta = {
        "choices": [{
            "message": {"role": "assistant", "content": "", "reasoning_content": contenido_json},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 80},
    }
    parsed = deepseek.parsear_respuesta(respuesta)
    check("content vacío con reasoning_content válido se recupera, no se descarta", parsed is not None)
    check(
        "la conclusión recuperada es la que llevaba reasoning_content",
        parsed is not None and parsed["conclusion_tipo"] == "no_diagnosticable",
    )


def test_parsear_respuesta_content_vacio_y_reasoning_content_no_json_se_rechaza() -> None:
    """El respaldo de reasoning_content nunca empeora el caso ya
    manejado: si tampoco es JSON válido (p. ej. la generación se cortó
    por max_tokens antes de llegar a la respuesta final), se rechaza
    igual que antes de este respaldo."""
    respuesta = {
        "choices": [{
            "message": {
                "role": "assistant", "content": "",
                "reasoning_content": "Estoy pensando en las hipótesis posibles, primero...",
            },
            "finish_reason": "length",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 2000},
    }
    check(
        "reasoning_content truncado y no-JSON se rechaza igual que antes",
        deepseek.parsear_respuesta(respuesta) is None,
    )


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


def test_parsear_respuesta_rechaza_mas_de_una_confirmada() -> None:
    # hallazgo I2 (/speckit-analyze 2026-08-11): el prompt exige EXACTAMENTE
    # una "confirmada" para causa_probable — dos a la vez contradice al
    # propio prompt y la semántica singular de FR-007 ("una causa probable").
    # Antes de esta corrección, parsear_respuesta solo rechazaba el caso
    # vacío y aceptaba dos o más en silencio.
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "algo",
        "hipotesis": [
            {"descripcion": "a", "comprobacion": "b", "desenlace": "confirmada"},
            {"descripcion": "c", "comprobacion": "d", "desenlace": "confirmada"},
        ],
    })
    check(
        "causa_probable con dos hipótesis confirmada a la vez viola FR-007 ⇒ se rechaza",
        deepseek.parsear_respuesta(respuesta) is None,
    )


def test_parsear_respuesta_rechaza_desenlace_invalido() -> None:
    respuesta = _respuesta_deepseek({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "algo",
        "hipotesis": [{"descripcion": "a", "comprobacion": "b", "desenlace": "quizas"}],
    })
    check("desenlace fuera del vocabulario se rechaza", deepseek.parsear_respuesta(respuesta) is None)
