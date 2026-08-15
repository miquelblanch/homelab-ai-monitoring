"""test_evidencia_ha — origen Home Assistant (feature 010). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T018).
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import _compartido, ha
from tests.selftest import check

_CHECK_ENTIDAD = {
    "id": "bateria_interruptor_salon",
    "type": "entity_value_below",
    "entity": "sensor.interruptor_salon_battery",
    "ok_state": 20,
}
_CHECK_RECORDER = {
    "id": "ha_recorder_corrupto",
    "type": "recorder_corrupto",
    "contenedor": "homeassistant",
    "ruta": "/recorder",
}
_CHECK_API = {"id": "ha_api", "type": "api_ping"}

_HA_CHECKS_FAKE = [_CHECK_ENTIDAD, _CHECK_RECORDER, _CHECK_API]

_HA_ESTADO_OK_FAKE = {"ok": True, "detalle": "OK", "motivo": ""}


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


def test_congelar_ha_vivo_entidad_arma_snapshot_con_historial() -> None:
    historial_falso = [{"state": "18", "last_changed": "2026-08-12T10:00:00"}]
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_history", return_value=historial_falso):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "bateria_interruptor_salon")

        check("componente = check_id", episodio.componente == "bateria_interruptor_salon")
        check("origen = ha", episodio.origen == "ha")
        check("es_critico siempre False para HA", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "snapshot incluye el check resuelto y su historial",
            episodio.snapshot_evidencia["ha_check"] == _CHECK_ENTIDAD
            and episodio.snapshot_evidencia["ha_history"] == historial_falso,
        )
        check(
            "snapshot incluye el veredicto ya calculado de ha_monitor.check_status()",
            episodio.snapshot_evidencia["ha_check_status"] == _HA_ESTADO_OK_FAKE,
        )
        check(
            "campos de recorder/logs quedan a null para un check de entidad",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"] is None
            and episodio.snapshot_evidencia["docker_logs_tail"] is None,
        )
        check(
            "campos heredados de contenedor/disco quedan a null, no ausentes",
            episodio.snapshot_evidencia["restart_history"] is None
            and episodio.snapshot_evidencia["container_metrics"] is None
            and episodio.snapshot_evidencia["disk_metrics"] is None
            and episodio.snapshot_evidencia["docker_inspect"] is None,
        )


def test_congelar_ha_vivo_historial_se_acota_y_simplifica() -> None:
    """Hallazgo real de validación en vivo (2026-08-12, research.md §6):
    sin este límite, una entidad de alta frecuencia revienta el prompt
    (280.454 tokens en un caso real, sal_nivel) sin producir ningún
    diagnóstico."""
    historial_grande = [
        {
            "entity_id": "sensor.sal_descalcificador_sal_descalcificador",
            "state": str(i),
            "attributes": {"unit_of_measurement": "V", "device_class": "voltage"},
            "last_changed": f"2026-08-12T{i % 24:02d}:00:00",
            "last_updated": f"2026-08-12T{i % 24:02d}:00:00",
        }
        for i in range(200)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_history", return_value=historial_grande):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "bateria_interruptor_salon")

        historial = episodio.snapshot_evidencia["ha_history"]
        check(
            f"el historial se acota a {ha.HA_HISTORIAL_MAX_ENTRADAS} entradas, no 200",
            len(historial) == ha.HA_HISTORIAL_MAX_ENTRADAS,
        )
        check("se quedan las entradas más recientes, no las más antiguas", historial[-1]["state"] == "199")
        check(
            "attributes/entity_id no sobreviven a la simplificación",
            "attributes" not in historial[0] and "entity_id" not in historial[0],
        )


def test_congelar_ha_vivo_recorder_corrupto_con_ficheros() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_recorder_corrupt_files",
                           return_value=["home-assistant_v2.db.corrupt.20260812"]), \
             patch.object(_compartido, "_run_ro", return_value="log de homeassistant\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "ha_recorder_corrupto")

        check(
            "ficheros de corrupción presentes en el snapshot",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"]
            == ["home-assistant_v2.db.corrupt.20260812"],
        )
        check(
            "logs del contenedor presentes",
            episodio.snapshot_evidencia["docker_logs_tail"] == "log de homeassistant\n",
        )
        check("sin historial de entidad para este tipo de check", episodio.snapshot_evidencia["ha_history"] is None)


def test_congelar_ha_vivo_recorder_corrupto_sano_sin_ficheros() -> None:
    """SC-004: un check de recorder sano (sin ficheros de corrupción)
    también debe congelar evidencia real, no distinta de la de un
    episodio con corrupción salvo en el contenido — la lista vacía es
    un dato, no una ausencia."""
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_recorder_corrupt_files", return_value=[]), \
             patch.object(_compartido, "_run_ro", return_value=""):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "ha_recorder_corrupto")

        check(
            "sin ficheros de corrupción, la lista queda vacía, no null",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"] == [],
        )


def test_congelar_ha_vivo_api_ping_usa_logs_sin_entidad() -> None:
    """Clarifications 2026-08-12 (spec.md): ha_api no tiene entidad — su
    evidencia son los logs del contenedor homeassistant."""
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(_compartido, "_run_ro", return_value="api respondiendo con normalidad\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "ha_api")

        check("componente = ha_api", episodio.componente == "ha_api")
        check(
            "evidencia de ha_api son los logs del contenedor homeassistant",
            episodio.snapshot_evidencia["docker_logs_tail"] == "api respondiendo con normalidad\n",
        )
        check(
            "sin historial ni ficheros de corrupción para este tipo de check",
            episodio.snapshot_evidencia["ha_history"] is None
            and episodio.snapshot_evidencia["ha_recorder_corrupt_files"] is None,
        )


def test_congelar_ha_vivo_check_id_inexistente_no_lanza() -> None:
    """spec.md Edge Cases: un check_id que no existe en ha_monitor.CHECKS
    congela igual, con evidencia vacía — no es un error, a diferencia
    del bloqueo de cerradura."""
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_vivo(conn, "check_que_no_existe")

        check("componente = check_id aunque no exista", episodio.componente == "check_que_no_existe")
        check(
            "toda la evidencia de HA queda en null, sin lanzar",
            episodio.snapshot_evidencia["ha_check"] is None
            and episodio.snapshot_evidencia["ha_history"] is None
            and episodio.snapshot_evidencia["ha_recorder_corrupt_files"] is None
            and episodio.snapshot_evidencia["docker_logs_tail"] is None
            and episodio.snapshot_evidencia["ha_check_status"] is None,
        )


def test_congelar_ha_vivo_bloquea_los_tres_checks_de_cerradura() -> None:
    """FR-010: la cerradura queda fuera de alcance con un rechazo
    explícito (ValueError), no con una evidencia vacía."""
    for check_id in ha.CHECKS_HA_EXCLUIDOS_CERRADURA:
        with tempfile.TemporaryDirectory() as tmp:
            with store.connect(_diag_db(tmp)) as conn:
                fallo = False
                try:
                    ha.congelar_ha_vivo(conn, check_id)
                except ValueError:
                    fallo = True
                check(f"congelar_ha_vivo bloquea {check_id!r} (FR-010)", fallo)


def test_congelar_ha_historico_entidad_ventana_centrada_en_el_momento() -> None:
    momento = datetime(2026, 8, 10, 12, 0, 0)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_history", return_value=[]):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)

        ventana_esperada_h = 2 * ha.VENTANA_HA_ENTIDAD_HORAS
        inicio = datetime.fromisoformat(episodio.ventana_inicio)
        fin = datetime.fromisoformat(episodio.ventana_fin)
        check(
            "la ventana histórica está centrada en el momento pedido",
            (fin - inicio).total_seconds() == ventana_esperada_h * 3600,
        )
        check("en_vivo=False para un episodio histórico de HA", episodio.en_vivo is False)


def test_congelar_ha_historico_es_reproducible() -> None:
    """Base de SC-001 para HA: congelar dos veces el mismo
    CHECK_ID@MOMENTO de un check de entidad produce la misma ventana y
    el mismo historial."""
    momento = datetime(2026, 8, 10, 12, 0, 0)
    historial_falso = [{"state": "18", "last_changed": "2026-08-10T11:00:00"}]
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_history", return_value=historial_falso):
            with store.connect(_diag_db(tmp)) as conn:
                e1 = ha.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)
                e2 = ha.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)

        check(
            "dos congelados del mismo CHECK_ID@MOMENTO producen la misma ventana y evidencia",
            e1.snapshot_evidencia["ha_history"] == e2.snapshot_evidencia["ha_history"]
            and e1.ventana_inicio == e2.ventana_inicio
            and e1.ventana_fin == e2.ventana_fin,
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)


def test_congelar_ha_historico_recorder_corrupto_usa_estado_actual() -> None:
    """research.md §6 de 010: sin fuente de evidencia verdaderamente
    histórica para recorder_corrupto/api_ping — el snapshot lleva el
    estado *actual*, etiquetado con la ventana del momento pedido."""
    momento = datetime(2026, 1, 1, 0, 0, 0)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(ha.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(ha.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(ha.bridge, "ha_recorder_corrupt_files", return_value=["x.corrupt.1"]), \
             patch.object(_compartido, "_run_ro", return_value="logs\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = ha.congelar_ha_historico(conn, "ha_recorder_corrupto", momento)

        check(
            "evidencia de estado actual bajo la ventana etiquetada con el momento pedido",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"] == ["x.corrupt.1"]
            and episodio.ventana_inicio.startswith("2025-12-31")
            and episodio.ventana_fin.startswith("2026-01-01"),
        )


def test_congelar_ha_historico_bloquea_los_tres_checks_de_cerradura() -> None:
    momento = datetime(2026, 8, 10, 12, 0, 0)
    for check_id in ha.CHECKS_HA_EXCLUIDOS_CERRADURA:
        with tempfile.TemporaryDirectory() as tmp:
            with store.connect(_diag_db(tmp)) as conn:
                fallo = False
                try:
                    ha.congelar_ha_historico(conn, check_id, momento)
                except ValueError:
                    fallo = True
                check(f"congelar_ha_historico bloquea {check_id!r} (FR-010)", fallo)
