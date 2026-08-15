"""test_evidencia_latido — origen latido de monitor (feature 017).
Movido de `test_evidencia.py` en specs/023-evidencia-por-origen/
(T025).
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import latido
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


def test_latido_actual_sano_rancio_status_discrepante_ausente_e_inexistente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        heartbeats_dir = Path(tmp)

        def _escribe(job: str, epoch: float, status: str, detail: str) -> None:
            (heartbeats_dir / f"{job}.json").write_text(
                json.dumps({"job": job, "epoch": epoch, "status": status, "detail": detail})
            )

        ahora = time.time()
        _escribe("docker-monitor", ahora - 60, "ok", "40 contenedores")  # umbral 1800s
        _escribe("ha-monitor", ahora - 7200, "ok", "15 checks")  # umbral 3600s: rancio
        _escribe("dns-pi-monitor", ahora - 60, "error", "pi caído (fallback activo)")
        # verify-backups: sin fichero — simula "nunca ha latido"

        with patch.object(latido, "MONITOR_HEARTBEATS_DIR", heartbeats_dir):
            sano = latido._latido_actual("docker-monitor")
            rancio = latido._latido_actual("ha-monitor")
            status_discrepante = latido._latido_actual("dns-pi-monitor")
            ausente = latido._latido_actual("verify-backups")
            inexistente = latido._latido_actual("job-que-no-existe")

        check("latido reciente y sano ⇒ ok=True", sano is not None and sano["ok"] is True)
        check("latido rancio ⇒ ok=False", rancio is not None and rancio["ok"] is False)
        check(
            "status=error pero edad fresca ⇒ ok=True igualmente "
            "(research.md §3 de 017: ok nunca se combina con status)",
            status_discrepante is not None
            and status_discrepante["ok"] is True
            and status_discrepante["status"] == "error",
        )
        check(
            "fichero ausente ⇒ ok=False, age_s=None, detail='sin latido'",
            ausente is not None
            and ausente["ok"] is False
            and ausente["age_s"] is None
            and ausente["detail"] == "sin latido",
        )
        check("job inexistente entre los 8 devuelve None, sin lanzar", inexistente is None)


def test_congelar_latido_vivo_arma_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp_latidos, tempfile.TemporaryDirectory() as tmp_db:
        heartbeats_dir = Path(tmp_latidos)
        (heartbeats_dir / "docker-monitor.json").write_text(
            json.dumps(
                {"job": "docker-monitor", "epoch": time.time(), "status": "ok", "detail": "40 contenedores"}
            )
        )

        with patch.object(latido, "MONITOR_HEARTBEATS_DIR", heartbeats_dir):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = latido.congelar_latido_vivo(conn, "docker-monitor")
                inexistente = latido.congelar_latido_vivo(conn, "job-que-no-existe")

        check("componente = job pedido", episodio.componente == "docker-monitor")
        check("origen = latido", episodio.origen == "latido")
        check("es_critico siempre False", episodio.es_critico is False)
        check("en_vivo=True siempre (no existe modo diferido)", episodio.en_vivo is True)
        check(
            "latido_actual poblado con el estado real",
            episodio.snapshot_evidencia["latido_actual"] is not None
            and episodio.snapshot_evidencia["latido_actual"]["ok"] is True,
        )
        check(
            "job inexistente congela igual, con evidencia vacía",
            inexistente.snapshot_evidencia["latido_actual"] is None
            and inexistente.componente == "job-que-no-existe",
        )
