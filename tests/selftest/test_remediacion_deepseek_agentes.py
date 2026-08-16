"""test_remediacion_deepseek_agentes — prompt propio, parseo, el
soporte de REMEDIACION_DEEPSEEK_MOCK, y evaluar_agente() de extremo a
extremo (specs/026-reiniciar-agentes-relays/). `congelar_agente_vivo`,
`launchctl` y `llamar_deepseek` siempre mockeados — ningún test de
este módulo toca un LaunchAgent real ni la API real de DeepSeek."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico.model import Episodio
from remediacion import acciones, deepseek_agentes, store
from tests.selftest import check


def _episodio(componente: str = "amsterdam9.test-agente") -> Episodio:
    return Episodio(
        componente=componente,
        origen="agente",
        es_critico=False,
        en_vivo=True,
        ventana_inicio="2026-08-16T00:00:00",
        ventana_fin="2026-08-16T00:00:00",
        snapshot_evidencia={"agente_actual": {"label": componente, "pid": "-", "exit_code": "1", "running": False}},
        id=1,
    )


def _respuesta_deepseek(accion_aplica, razonamiento="prueba", tokens_entrada=10, tokens_salida=5) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(
            {"accion_aplica": accion_aplica, "razonamiento": razonamiento}
        )}}],
        "usage": {"prompt_tokens": tokens_entrada, "completion_tokens": tokens_salida},
    }


def _db(tmp: str) -> Path:
    return Path(tmp) / "remediacion.db"


def _limpiar_mock_env() -> None:
    os.environ.pop("REMEDIACION_DEEPSEEK_MOCK", None)


# ── construir_prompt_agente ──


def test_construir_prompt_incluye_evidencia_y_acciones() -> None:
    prompt = deepseek_agentes.construir_prompt_agente(_episodio(), ("reiniciar_agente",))
    check("el prompt menciona la acción candidata", "reiniciar_agente" in prompt)
    check("el prompt incluye la evidencia real serializada", "amsterdam9.test-agente" in prompt)
    check("el prompt no reutiliza el prompt de causa_probable", "causa probable" not in prompt.lower())


# ── parsear_respuesta_agente ──


def test_parsear_respuesta_agente_acepta_accion_valida() -> None:
    parsed = deepseek_agentes.parsear_respuesta_agente(
        _respuesta_deepseek("reiniciar_agente", "el proceso no responde")
    )
    check("acepta reiniciar_agente", parsed is not None and parsed["accion_aplica"] == "reiniciar_agente")
    check("conserva el razonamiento", parsed["razonamiento"] == "el proceso no responde")
    check("conserva los tokens de usage", parsed["tokens_entrada"] == 10 and parsed["tokens_salida"] == 5)


def test_parsear_respuesta_agente_acepta_null() -> None:
    parsed = deepseek_agentes.parsear_respuesta_agente(
        _respuesta_deepseek(None, "el problema es un permiso del sistema")
    )
    check("acepta accion_aplica null", parsed is not None and parsed["accion_aplica"] is None)


def test_parsear_respuesta_agente_rechaza_accion_fuera_de_lista() -> None:
    parsed = deepseek_agentes.parsear_respuesta_agente(
        _respuesta_deepseek("borrar_plist", "inventada")
    )
    check("una acción inventada se rechaza por completo", parsed is None)


def test_parsear_respuesta_agente_usa_reasoning_content_si_content_vacio() -> None:
    respuesta = {
        "choices": [{"message": {
            "content": "",
            "reasoning_content": json.dumps({"accion_aplica": None, "razonamiento": "vía reasoning_content"}),
        }}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    parsed = deepseek_agentes.parsear_respuesta_agente(respuesta)
    check("recupera la decisión de reasoning_content", parsed is not None and parsed["razonamiento"] == "vía reasoning_content")


def test_parsear_respuesta_agente_json_invalido_devuelve_none() -> None:
    respuesta = {"choices": [{"message": {"content": "esto no es json"}}], "usage": {}}
    check("contenido no-JSON ⇒ None, sin lanzar", deepseek_agentes.parsear_respuesta_agente(respuesta) is None)


def test_parsear_respuesta_agente_estructura_inesperada_devuelve_none() -> None:
    check("respuesta sin 'choices' ⇒ None, sin lanzar", deepseek_agentes.parsear_respuesta_agente({}) is None)


# ── respuesta_mock (REMEDIACION_DEEPSEEK_MOCK, compartida con contenedores) ──


def test_respuesta_mock_lee_env_var() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "reiniciar_agente", "razonamiento": "prueba: agente caído"}
        )
        parsed = deepseek_agentes.respuesta_mock()
    finally:
        _limpiar_mock_env()
    check("el mock se lee y valida correctamente", parsed is not None and parsed["accion_aplica"] == "reiniciar_agente")


def test_respuesta_mock_sin_env_var_devuelve_none() -> None:
    _limpiar_mock_env()
    check("sin REMEDIACION_DEEPSEEK_MOCK ⇒ None", deepseek_agentes.respuesta_mock() is None)


def test_respuesta_mock_accion_invalida_devuelve_none() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "borrar_plist", "razonamiento": "inventada"}
        )
        check("mock con acción fuera de la lista cerrada ⇒ None", deepseek_agentes.respuesta_mock() is None)
    finally:
        _limpiar_mock_env()


# ── evaluar_agente (orquestación completa, todo mockeado) ──


def test_evaluar_agente_recomienda_reiniciar_modo_manual() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_agente_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek",
                           return_value=_respuesta_deepseek("reiniciar_agente", "proceso colgado")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_agente(conn, conn, "amsterdam9.test-agente")

        check("modo manual ⇒ pendiente, nunca ejecuta solo", intento.estado == "pendiente")
        check("conserva la recomendación", intento.accion_recomendada == "reiniciar_agente")
        check("conserva el razonamiento", intento.razonamiento_deepseek == "proceso colgado")
        check("coste registrado", intento.coste_eur == 0.001)
        check("episodio_id enlazado", intento.episodio_id == 1)
        check("label correcto", intento.label == "amsterdam9.test-agente")


def test_evaluar_agente_ninguna_accion_aplica_no_reinicia() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        avisos: list[tuple[str, str]] = []
        with patch.object(acciones.diagnostico_evidencia, "congelar_agente_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek",
                           return_value=_respuesta_deepseek(None, "permiso del sistema, no el proceso")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "_notificar_sin_accion", side_effect=lambda c, r: avisos.append((c, r))):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_agente(conn, conn, "amsterdam9.test-agente")

        check("ninguna acción aplica ⇒ estado sin_accion, nunca reinicia", intento.estado == "sin_accion")
        check("dispara el aviso (FR-002)", len(avisos) == 1 and avisos[0][0] == "amsterdam9.test-agente")


def test_evaluar_agente_fallo_llamada_es_sin_evaluar_no_sin_accion() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_agente_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value=None), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_agente(conn, conn, "amsterdam9.test-agente")

        check("fallo de la llamada ⇒ sin_evaluar, nunca sin_accion", intento.estado == "sin_evaluar")
        check("sin acción recomendada registrada", intento.accion_recomendada is None)


def test_evaluar_agente_sin_presupuesto_es_sin_evaluar() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_agente_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=False), \
             patch.object(acciones, "diagnostico_llamar_deepseek") as mock_llamada:
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_agente(conn, conn, "amsterdam9.test-agente")

        check("sin presupuesto ⇒ sin_evaluar", intento.estado == "sin_evaluar")
        check("nunca se llega a llamar a DeepSeek sin presupuesto", mock_llamada.called is False)


def test_evaluar_agente_usa_mock_sin_gastar_presupuesto() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "reiniciar_agente", "razonamiento": "prueba vía mock"}
        )
        with tempfile.TemporaryDirectory() as db_dir:
            with patch.object(acciones.diagnostico_evidencia, "congelar_agente_vivo", return_value=_episodio()), \
                 patch.object(acciones.diagnostico_gasto, "hay_presupuesto") as mock_presupuesto, \
                 patch.object(acciones, "diagnostico_llamar_deepseek") as mock_llamada:
                with store.connect(_db(db_dir)) as conn:
                    intento = acciones.evaluar_agente(conn, conn, "amsterdam9.test-agente")

            check("el mock produce la decisión esperada", intento.accion_recomendada == "reiniciar_agente")
            check("con mock activo, nunca se comprueba presupuesto real", mock_presupuesto.called is False)
            check("con mock activo, nunca se llama a DeepSeek de verdad", mock_llamada.called is False)
            check("el intento vía mock no registra coste", intento.coste_eur is None)
    finally:
        _limpiar_mock_env()
