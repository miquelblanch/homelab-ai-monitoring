"""test_evidencia_disco — origen disco (feature 009). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T017).
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import _compartido, disco
from tests.selftest import check
from tests.selftest.fixtures.homelab_fake_db import fake_homelab_db as _fake_homelab_db


def test_congelar_disco_vivo_arma_snapshot_con_evidencia_de_disco() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        homelab_db = _fake_homelab_db(tmp)
        diag_db = Path(tmp) / "diagnostico.db"
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                episodio = disco.congelar_disco_vivo(conn, "Sistema")

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
        momento = datetime(2026, 4, 1, 22, 29, 25)
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                episodio = disco.congelar_disco_historico(conn, "Sistema", momento)

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
        momento = datetime(2026, 4, 1, 22, 29, 25)
        with patch.object(_compartido, "homelab_db_path", return_value=homelab_db):
            with store.connect(diag_db) as conn:
                e1 = disco.congelar_disco_historico(conn, "Sistema", momento)
                e2 = disco.congelar_disco_historico(conn, "Sistema", momento)

        check(
            "dos congelados del mismo LABEL@MOMENTO producen la misma ventana",
            e1.snapshot_evidencia["disk_metrics"] == e2.snapshot_evidencia["disk_metrics"]
            and e1.ventana_inicio == e2.ventana_inicio
            and e1.ventana_fin == e2.ventana_fin,
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
