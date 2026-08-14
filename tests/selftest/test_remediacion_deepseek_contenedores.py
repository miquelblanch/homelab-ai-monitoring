"""test_remediacion_deepseek_contenedores — prompt propio, parseo, el
soporte de REMEDIACION_DEEPSEEK_MOCK, y evaluar_contenedor() de
extremo a extremo (specs/021-remediacion-contenedores/). `congelar_vivo`
y `llamar_deepseek` siempre mockeados — ningún test de este módulo
llama a Docker real ni a la API real de DeepSeek."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico.model import Episodio
from remediacion import acciones, deepseek_contenedores, store
from tests.selftest import check


def _episodio(componente: str = "test-contenedor") -> Episodio:
    return Episodio(
        componente=componente,
        origen="contenedor",
        es_critico=False,
        en_vivo=True,
        ventana_inicio="2026-08-14T00:00:00",
        ventana_fin="2026-08-14T00:05:00",
        snapshot_evidencia={"docker_logs_tail": "connection refused: 192.168.4.99:1234"},
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


# ── construir_prompt_remediacion ──


def test_construir_prompt_incluye_evidencia_y_acciones() -> None:
    prompt = deepseek_contenedores.construir_prompt_remediacion(
        _episodio(), ("reiniciar_contenedor",)
    )
    check("el prompt menciona la acción candidata", "reiniciar_contenedor" in prompt)
    check("el prompt incluye la evidencia real serializada", "192.168.4.99:1234" in prompt)
    check("el prompt no reutiliza el prompt de causa_probable", "causa probable" not in prompt.lower())


# ── parsear_respuesta_remediacion ──


def test_parsear_respuesta_remediacion_acepta_accion_valida() -> None:
    parsed = deepseek_contenedores.parsear_respuesta_remediacion(
        _respuesta_deepseek("reiniciar_contenedor", "el proceso no responde")
    )
    check("acepta reiniciar_contenedor", parsed is not None and parsed["accion_aplica"] == "reiniciar_contenedor")
    check("conserva el razonamiento", parsed["razonamiento"] == "el proceso no responde")
    check("conserva los tokens de usage", parsed["tokens_entrada"] == 10 and parsed["tokens_salida"] == 5)


def test_parsear_respuesta_remediacion_acepta_null() -> None:
    parsed = deepseek_contenedores.parsear_respuesta_remediacion(
        _respuesta_deepseek(None, "el problema es externo")
    )
    check("acepta accion_aplica null", parsed is not None and parsed["accion_aplica"] is None)


def test_parsear_respuesta_remediacion_rechaza_accion_fuera_de_lista() -> None:
    """FR-003 — nunca confía en un valor libre devuelto por el modelo."""
    parsed = deepseek_contenedores.parsear_respuesta_remediacion(
        _respuesta_deepseek("borrar_volumen", "inventada")
    )
    check("una acción inventada se rechaza por completo", parsed is None)


def test_parsear_respuesta_remediacion_usa_reasoning_content_si_content_vacio() -> None:
    """Mismo respaldo que diagnostico.deepseek.parsear_respuesta
    (research.md §3): un modelo de razonamiento puede dejar `content`
    vacío y escribir la respuesta completa en `reasoning_content`."""
    respuesta = {
        "choices": [{"message": {
            "content": "",
            "reasoning_content": json.dumps({"accion_aplica": None, "razonamiento": "vía reasoning_content"}),
        }}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    parsed = deepseek_contenedores.parsear_respuesta_remediacion(respuesta)
    check("recupera la decisión de reasoning_content", parsed is not None and parsed["razonamiento"] == "vía reasoning_content")


def test_parsear_respuesta_remediacion_json_invalido_devuelve_none() -> None:
    respuesta = {"choices": [{"message": {"content": "esto no es json"}}], "usage": {}}
    check("contenido no-JSON ⇒ None, sin lanzar", deepseek_contenedores.parsear_respuesta_remediacion(respuesta) is None)


def test_parsear_respuesta_remediacion_estructura_inesperada_devuelve_none() -> None:
    check("respuesta sin 'choices' ⇒ None, sin lanzar", deepseek_contenedores.parsear_respuesta_remediacion({}) is None)


# ── respuesta_mock (REMEDIACION_DEEPSEEK_MOCK) ──


def test_respuesta_mock_lee_env_var() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba: contenedor caído"}
        )
        parsed = deepseek_contenedores.respuesta_mock()
    finally:
        _limpiar_mock_env()
    check("el mock se lee y valida correctamente", parsed is not None and parsed["accion_aplica"] == "reiniciar_contenedor")


def test_respuesta_mock_sin_env_var_devuelve_none() -> None:
    _limpiar_mock_env()
    check("sin REMEDIACION_DEEPSEEK_MOCK ⇒ None", deepseek_contenedores.respuesta_mock() is None)


def test_respuesta_mock_json_invalido_devuelve_none() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = "no es json"
        check("mock con JSON inválido ⇒ None, sin lanzar", deepseek_contenedores.respuesta_mock() is None)
    finally:
        _limpiar_mock_env()


def test_respuesta_mock_accion_invalida_devuelve_none() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "borrar_volumen", "razonamiento": "inventada"}
        )
        check("mock con acción fuera de la lista cerrada ⇒ None (FR-003)", deepseek_contenedores.respuesta_mock() is None)
    finally:
        _limpiar_mock_env()


# ── evaluar_contenedor (orquestación completa, todo mockeado) ──


def test_evaluar_contenedor_recomienda_reiniciar_modo_manual() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek",
                           return_value=_respuesta_deepseek("reiniciar_contenedor", "proceso colgado")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

        check("modo manual ⇒ pendiente, nunca ejecuta solo", intento.estado == "pendiente")
        check("conserva la recomendación", intento.accion_recomendada == "reiniciar_contenedor")
        check("conserva el razonamiento", intento.razonamiento_deepseek == "proceso colgado")
        check("coste registrado", intento.coste_eur == 0.001)
        check("episodio_id enlazado", intento.episodio_id == 1)


def test_evaluar_contenedor_ninguna_accion_aplica_no_reinicia() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        avisos: list[tuple[str, str]] = []
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek",
                           return_value=_respuesta_deepseek(None, "el problema es de red externa")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "_notificar_sin_accion", side_effect=lambda c, r: avisos.append((c, r))):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

        check("ninguna acción aplica ⇒ estado sin_accion, nunca reinicia", intento.estado == "sin_accion")
        check("dispara el aviso de US4", len(avisos) == 1 and avisos[0][0] == "test-contenedor")


def test_evaluar_contenedor_fallo_llamada_es_sin_evaluar_no_sin_accion() -> None:
    """FR-015 — un fallo de la llamada nunca se confunde con 'ninguna acción aplica'."""
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value=None), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True):
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

        check("fallo de la llamada ⇒ sin_evaluar, nunca sin_accion", intento.estado == "sin_evaluar")
        check("sin acción recomendada registrada", intento.accion_recomendada is None)


def test_evaluar_contenedor_sin_presupuesto_es_sin_evaluar() -> None:
    """FR-014/Edge Cases — sin presupuesto, no hay llamada, y queda distinguible de 'sin_accion'."""
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=False) as mock_presupuesto, \
             patch.object(acciones, "diagnostico_llamar_deepseek") as mock_llamada:
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

        check("sin presupuesto ⇒ sin_evaluar", intento.estado == "sin_evaluar")
        check("nunca se llega a llamar a DeepSeek sin presupuesto (SC-004)", mock_llamada.called is False)


def test_evaluar_contenedor_usa_mock_sin_gastar_presupuesto() -> None:
    try:
        os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
            {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba vía mock"}
        )
        with tempfile.TemporaryDirectory() as db_dir:
            with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
                 patch.object(acciones.diagnostico_gasto, "hay_presupuesto") as mock_presupuesto, \
                 patch.object(acciones, "diagnostico_llamar_deepseek") as mock_llamada:
                with store.connect(_db(db_dir)) as conn:
                    intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

            check("el mock produce la decisión esperada", intento.accion_recomendada == "reiniciar_contenedor")
            check("con mock activo, nunca se comprueba presupuesto real", mock_presupuesto.called is False)
            check("con mock activo, nunca se llama a DeepSeek de verdad", mock_llamada.called is False)
            check("el intento vía mock no registra coste", intento.coste_eur is None)
    finally:
        _limpiar_mock_env()
