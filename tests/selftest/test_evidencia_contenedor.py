"""test_evidencia_contenedor — origen contenedor (feature 007): forma
del snapshot, `es_critico` fijado en el momento de congelar,
`congelar_historico`/`congelar_vivo` contra una base `homelab.db` de
prueba en un fichero temporal (nunca la real). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T016).
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import _compartido, contenedor
from tests.selftest import check
from tests.selftest.fixtures.homelab_fake_db import fake_homelab_db as _fake_homelab_db


def test_congelar_historico_arma_snapshot_con_evidencia_real() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db), \
             patch.object(contenedor.bridge, "docker_critical", return_value=set()):
            with store.connect(diag_db) as conn:
                episodio = contenedor.congelar_historico(conn, 16)

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
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db), \
             patch.object(contenedor.bridge, "docker_critical", return_value=set()), \
             patch.object(contenedor, "container_metrics_window", return_value=[]):
            with store.connect(diag_db) as conn:
                episodio = contenedor.congelar_historico(conn, 16)

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
    momento del episodio (hallazgo real al preparar T030). Vive en
    contenedor.py pese al nombre — solo lo usa este origen
    (research.md §2 de 023)."""
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)  # solo tiene una fila, cerca del episodio real
        conn_fake = sqlite3.connect(homelab_db)
        conn_fake.execute(
            "INSERT INTO disk_metrics (timestamp, path, label, used_percent, free_gb) "
            "VALUES ('2026-08-10T14:00:00', '/', 'Sistema', 60.0, 180.0)"
        )
        conn_fake.commit()
        conn_fake.close()

        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db):
            cerca = contenedor.disk_metrics_near(datetime(2026, 4, 1, 22, 29, 25))

        check(
            "solo la muestra dentro de la ventana de tolerancia sobrevive, no la de meses después",
            len(cerca) == 1 and cerca[0]["timestamp"] == "2026-04-01T22:29:00",
        )


def test_congelar_historico_falla_si_no_existe_la_fila() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                fallo = False
                try:
                    contenedor.congelar_historico(conn, 999)
                except ValueError:
                    fallo = True
                check("restart_history_id inexistente lanza ValueError", fallo)


def test_es_critico_se_fija_en_el_momento_de_congelar() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db), \
             patch.object(contenedor.bridge, "docker_critical", return_value={"beszel"}):
            with store.connect(diag_db) as conn:
                episodio = contenedor.congelar_historico(conn, 16)

        check(
            "es_critico=True si el contenedor está en la lista crítica al congelar",
            episodio.es_critico is True,
        )


def test_congelar_vivo_arma_snapshot_sin_restart_history() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db), \
             patch.object(contenedor.bridge, "docker_critical", return_value=set()), \
             patch.object(contenedor, "_run_ro", return_value=""):
            with store.connect(diag_db) as conn:
                episodio = contenedor.congelar_vivo(conn, "beszel")

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
