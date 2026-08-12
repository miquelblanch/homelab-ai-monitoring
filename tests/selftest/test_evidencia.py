"""test_evidencia — T013: forma del snapshot, `es_critico` fijado en el
momento de congelar, `congelar_historico`/`congelar_vivo` contra una
base `homelab.db` de prueba en un fichero temporal (nunca la real).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import evidencia, store
from tests.selftest import check

_SCHEMA_HOMELAB_FAKE = """
CREATE TABLE restart_history (
    id INTEGER PRIMARY KEY,
    container_name TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    result TEXT NOT NULL,
    reason TEXT,
    triggered_by TEXT DEFAULT 'auto'
);
CREATE TABLE container_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    container TEXT NOT NULL,
    status TEXT,
    health TEXT,
    cpu_percent REAL,
    memory_mb REAL,
    memory_percent REAL
);
CREATE TABLE disk_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    path TEXT NOT NULL,
    label TEXT,
    used_percent REAL,
    free_gb REAL
);
CREATE TABLE container_metrics_hourly (
    hour TEXT NOT NULL,
    container TEXT NOT NULL,
    samples INTEGER NOT NULL,
    cpu_avg REAL,
    cpu_max REAL,
    memory_avg_mb REAL,
    memory_max_mb REAL,
    healthy_ratio REAL
);
"""


def _fake_homelab_db(tmp: str) -> Path:
    db = Path(tmp) / "homelab_fake.db"
    conn = sqlite3.connect(db)
    conn.executescript(_SCHEMA_HOMELAB_FAKE)
    conn.execute(
        "INSERT INTO restart_history VALUES (16, 'beszel', 1775075365, 'success', "
        "'Container beszel restarted successfully', 'healer')"
    )
    # 1775075365 epoch ⇒ 2026-04-01T22:29:25 hora local — la muestra de
    # métricas tiene que caer dentro de la ventana de ±30 min alrededor de
    # ese momento (evidencia.VENTANA_METRICAS_MINUTOS) para que
    # `congelar_historico` la recoja.
    conn.execute(
        "INSERT INTO container_metrics (timestamp, container, status, health, "
        "cpu_percent, memory_mb, memory_percent) VALUES "
        "('2026-04-01T22:29:00', 'beszel', 'Up', '', 0.5, 30.0, 0.06)"
    )
    conn.execute(
        "INSERT INTO disk_metrics (timestamp, path, label, used_percent, free_gb) "
        "VALUES ('2026-04-01T22:29:00', '/', 'Sistema', 55.0, 200.0)"
    )
    conn.commit()
    conn.close()
    return db


def test_congelar_historico_arma_snapshot_con_evidencia_real() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db), \
             patch.object(evidencia.bridge, "docker_critical", return_value=set()):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_historico(conn, 16)

        check("episodio persistido con id", episodio.id is not None)
        check("contenedor correcto", episodio.componente == "beszel")
        check("es_critico=False (beszel no está en la lista crítica)", episodio.es_critico is False)
        check("en_vivo=False para un episodio histórico", episodio.en_vivo is False)
        check(
            "snapshot incluye la fila real de restart_history",
            episodio.snapshot_evidencia["restart_history"]["id"] == 16,
        )
        check(
            "snapshot incluye la ventana de container_metrics",
            len(episodio.snapshot_evidencia["container_metrics"]) == 1,
        )
        check(
            "snapshot en vivo queda vacío en un episodio histórico",
            episodio.snapshot_evidencia["docker_inspect"] is None
            and episodio.snapshot_evidencia["docker_logs_tail"] is None,
        )


def test_congelar_historico_usa_agregado_horario_si_no_hay_detalle() -> None:
    """Hallazgo real al preparar T030: los 49 reinicios de `beszel` son de
    marzo-mayo 2026, ya fuera de los 30 días de retención de
    `container_metrics` hoy — sin este respaldo, todo episodio antiguo
    concluiría `no_diagnosticable` por falta de datos que en realidad sí
    existen, agregados por hora."""
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        conn_fake = sqlite3.connect(homelab_db)
        conn_fake.execute(
            "INSERT INTO container_metrics_hourly VALUES "
            "('2026-04-01T22', 'beszel', 12, 0.4, 1.2, 28.0, 40.0, 1.0)"
        )
        conn_fake.commit()
        conn_fake.close()

        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db), \
             patch.object(evidencia.bridge, "docker_critical", return_value=set()), \
             patch.object(evidencia, "container_metrics_window", return_value=[]):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_historico(conn, 16)

        check(
            "sin detalle disponible, cae al agregado horario en vez de quedar vacío",
            len(episodio.snapshot_evidencia["container_metrics_hourly"]) == 1,
        )
        check(
            "container_metrics queda vacío cuando se usa el respaldo horario",
            episodio.snapshot_evidencia["container_metrics"] == [],
        )


def test_disk_metrics_near_descarta_muestras_fuera_de_la_ventana() -> None:
    """`disk_metrics` también tiene retención de 30 días — para un
    episodio de hace meses, las "3 más cercanas" pueden estar a meses de
    distancia. No deben colarse como si fueran evidencia real del
    momento del episodio (hallazgo real al preparar T030)."""
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)  # solo tiene una fila, cerca del episodio real
        conn_fake = sqlite3.connect(homelab_db)
        conn_fake.execute(
            "INSERT INTO disk_metrics (timestamp, path, label, used_percent, free_gb) "
            "VALUES ('2026-08-10T14:00:00', '/', 'Sistema', 60.0, 180.0)"
        )
        conn_fake.commit()
        conn_fake.close()

        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db):
            cerca = evidencia.disk_metrics_near(evidencia.datetime(2026, 4, 1, 22, 29, 25))

        check(
            "solo la muestra dentro de la ventana de tolerancia sobrevive, no la de meses después",
            len(cerca) == 1 and cerca[0]["timestamp"] == "2026-04-01T22:29:00",
        )


def test_congelar_historico_falla_si_no_existe_la_fila() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                fallo = False
                try:
                    evidencia.congelar_historico(conn, 999)
                except ValueError:
                    fallo = True
                check("restart_history_id inexistente lanza ValueError", fallo)


def test_es_critico_se_fija_en_el_momento_de_congelar() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db), \
             patch.object(evidencia.bridge, "docker_critical", return_value={"beszel"}):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_historico(conn, 16)

        check(
            "es_critico=True si el contenedor está en la lista crítica al congelar",
            episodio.es_critico is True,
        )


def test_congelar_vivo_arma_snapshot_sin_restart_history() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db), \
             patch.object(evidencia.bridge, "docker_critical", return_value=set()), \
             patch.object(evidencia, "_run_ro", return_value=""):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_vivo(conn, "beszel")

        check("episodio en vivo persistido con id", episodio.id is not None)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "snapshot histórico queda vacío en un episodio en vivo",
            episodio.snapshot_evidencia["restart_history"] is None,
        )
        check(
            "reutiliza container_metrics ya existentes, no inventa una fuente nueva",
            len(episodio.snapshot_evidencia["container_metrics"]) == 1,
        )


# ── Discos (feature 009: specs/009-diagnostico-discos/) ────────────────────


def test_congelar_disco_vivo_arma_snapshot_con_evidencia_de_disco() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_disco_vivo(conn, "Sistema")

        check("episodio de disco persistido con id", episodio.id is not None)
        check("componente = label del disco", episodio.componente == "Sistema")
        check("origen = disco", episodio.origen == "disco")
        check("es_critico siempre False para un disco", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "snapshot incluye la evidencia de disco",
            len(episodio.snapshot_evidencia["disk_metrics"]) == 1
            and episodio.snapshot_evidencia["disco"]["label"] == "Sistema",
        )
        check(
            "campos heredados de contenedor quedan a null, no ausentes",
            episodio.snapshot_evidencia["restart_history"] is None
            and episodio.snapshot_evidencia["container_metrics"] is None
            and episodio.snapshot_evidencia["container_metrics_hourly"] is None
            and episodio.snapshot_evidencia["docker_inspect"] is None
            and episodio.snapshot_evidencia["docker_logs_tail"] is None,
        )


def test_congelar_disco_historico_arma_ventana_alrededor_del_momento() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        momento = evidencia.datetime(2026, 4, 1, 22, 29, 25)
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                episodio = evidencia.congelar_disco_historico(conn, "Sistema", momento)

        check("componente = label del disco", episodio.componente == "Sistema")
        check("origen = disco", episodio.origen == "disco")
        check("en_vivo=False para un episodio histórico de disco", episodio.en_vivo is False)
        check(
            "la ventana histórica recoge la muestra real dentro de ±30 min",
            len(episodio.snapshot_evidencia["disk_metrics"]) == 1,
        )


def test_congelar_disco_historico_es_reproducible() -> None:
    """Base de SC-001 para discos: congelar dos veces el mismo
    LABEL@MOMENTO debe producir la misma ventana de evidencia."""
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        momento = evidencia.datetime(2026, 4, 1, 22, 29, 25)
        with patch.object(evidencia, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                e1 = evidencia.congelar_disco_historico(conn, "Sistema", momento)
                e2 = evidencia.congelar_disco_historico(conn, "Sistema", momento)

        check(
            "dos congelados del mismo LABEL@MOMENTO producen la misma ventana",
            e1.snapshot_evidencia["disk_metrics"] == e2.snapshot_evidencia["disk_metrics"]
            and e1.ventana_inicio == e2.ventana_inicio
            and e1.ventana_fin == e2.ventana_fin,
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)


# ── Home Assistant (feature 010: specs/010-diagnostico-ha/) ────────────────

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
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_history", return_value=historial_falso):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "bateria_interruptor_salon")

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
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_history", return_value=historial_grande):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "bateria_interruptor_salon")

        historial = episodio.snapshot_evidencia["ha_history"]
        check(
            f"el historial se acota a {evidencia.HA_HISTORIAL_MAX_ENTRADAS} entradas, no 200",
            len(historial) == evidencia.HA_HISTORIAL_MAX_ENTRADAS,
        )
        check("se quedan las entradas más recientes, no las más antiguas", historial[-1]["state"] == "199")
        check(
            "attributes/entity_id no sobreviven a la simplificación",
            "attributes" not in historial[0] and "entity_id" not in historial[0],
        )


def test_congelar_ha_vivo_recorder_corrupto_con_ficheros() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_recorder_corrupt_files",
                           return_value=["home-assistant_v2.db.corrupt.20260812"]), \
             patch.object(evidencia, "_run_ro", return_value="log de homeassistant\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "ha_recorder_corrupto")

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
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_recorder_corrupt_files", return_value=[]), \
             patch.object(evidencia, "_run_ro", return_value=""):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "ha_recorder_corrupto")

        check(
            "sin ficheros de corrupción, la lista queda vacía, no null",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"] == [],
        )


def test_congelar_ha_vivo_api_ping_usa_logs_sin_entidad() -> None:
    """Clarifications 2026-08-12 (spec.md): ha_api no tiene entidad — su
    evidencia son los logs del contenedor homeassistant."""
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia, "_run_ro", return_value="api respondiendo con normalidad\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "ha_api")

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
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_vivo(conn, "check_que_no_existe")

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
    for check_id in evidencia.CHECKS_HA_EXCLUIDOS_CERRADURA:
        with tempfile.TemporaryDirectory() as tmp:
            with store.connect(_diag_db(tmp)) as conn:
                fallo = False
                try:
                    evidencia.congelar_ha_vivo(conn, check_id)
                except ValueError:
                    fallo = True
                check(f"congelar_ha_vivo bloquea {check_id!r} (FR-010)", fallo)


def test_congelar_ha_historico_entidad_ventana_centrada_en_el_momento() -> None:
    momento = evidencia.datetime(2026, 8, 10, 12, 0, 0)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_history", return_value=[]):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)

        ventana_esperada_h = 2 * evidencia.VENTANA_HA_ENTIDAD_HORAS
        inicio = evidencia.datetime.fromisoformat(episodio.ventana_inicio)
        fin = evidencia.datetime.fromisoformat(episodio.ventana_fin)
        check(
            "la ventana histórica está centrada en el momento pedido",
            (fin - inicio).total_seconds() == ventana_esperada_h * 3600,
        )
        check("en_vivo=False para un episodio histórico de HA", episodio.en_vivo is False)


def test_congelar_ha_historico_es_reproducible() -> None:
    """Base de SC-001 para HA: congelar dos veces el mismo
    CHECK_ID@MOMENTO de un check de entidad produce la misma ventana y
    el mismo historial."""
    momento = evidencia.datetime(2026, 8, 10, 12, 0, 0)
    historial_falso = [{"state": "18", "last_changed": "2026-08-10T11:00:00"}]
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_history", return_value=historial_falso):
            with store.connect(_diag_db(tmp)) as conn:
                e1 = evidencia.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)
                e2 = evidencia.congelar_ha_historico(conn, "bateria_interruptor_salon", momento)

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
    momento = evidencia.datetime(2026, 1, 1, 0, 0, 0)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(evidencia.bridge, "ha_checks", return_value=_HA_CHECKS_FAKE), \
             patch.object(evidencia.bridge, "ha_check_status", return_value=_HA_ESTADO_OK_FAKE), \
             patch.object(evidencia.bridge, "ha_recorder_corrupt_files", return_value=["x.corrupt.1"]), \
             patch.object(evidencia, "_run_ro", return_value="logs\n"):
            with store.connect(_diag_db(tmp)) as conn:
                episodio = evidencia.congelar_ha_historico(conn, "ha_recorder_corrupto", momento)

        check(
            "evidencia de estado actual bajo la ventana etiquetada con el momento pedido",
            episodio.snapshot_evidencia["ha_recorder_corrupt_files"] == ["x.corrupt.1"]
            and episodio.ventana_inicio.startswith("2025-12-31")
            and episodio.ventana_fin.startswith("2026-01-01"),
        )


def test_congelar_ha_historico_bloquea_los_tres_checks_de_cerradura() -> None:
    momento = evidencia.datetime(2026, 8, 10, 12, 0, 0)
    for check_id in evidencia.CHECKS_HA_EXCLUIDOS_CERRADURA:
        with tempfile.TemporaryDirectory() as tmp:
            with store.connect(_diag_db(tmp)) as conn:
                fallo = False
                try:
                    evidencia.congelar_ha_historico(conn, check_id, momento)
                except ValueError:
                    fallo = True
                check(f"congelar_ha_historico bloquea {check_id!r} (FR-010)", fallo)
