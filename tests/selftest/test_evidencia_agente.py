"""test_evidencia_agente — origen LaunchAgent (feature 016). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T024).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import agente
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


_LAUNCHAGENTS_RAW_FAKE = (
    "PID\tStatus\tLabel\n"
    "1234\t0\tamsterdam9.docker-monitor\n"
    "-\t0\tamsterdam9.morning-report\n"
    "-\t-15\tamsterdam9.rotate-hermes-logs\n"
)


def test_agente_actual_running_idle_error_e_inexistente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "launchagents_raw.txt"
        raw.write_text(_LAUNCHAGENTS_RAW_FAKE)

        with patch.object(agente, "LAUNCHAGENTS_RAW", raw):
            running = agente._agente_actual("amsterdam9.docker-monitor")
            idle = agente._agente_actual("amsterdam9.morning-report")
            error = agente._agente_actual("amsterdam9.rotate-hermes-logs")
            inexistente = agente._agente_actual("agente.que.no.existe")

        check("con proceso activo ⇒ status=running", running is not None and running["status"] == "running")
        check(
            "sin proceso, exit_code normal ⇒ status=idle",
            idle is not None and idle["status"] == "idle" and idle["running"] is False,
        )
        check(
            "sin proceso, exit_code anómalo ⇒ status=error",
            error is not None and error["status"] == "error" and error["running"] is False,
        )
        check("label inexistente devuelve None, sin lanzar", inexistente is None)


def test_congelar_agente_vivo_arma_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp_agentes, tempfile.TemporaryDirectory() as tmp_db:
        raw = Path(tmp_agentes) / "launchagents_raw.txt"
        raw.write_text(_LAUNCHAGENTS_RAW_FAKE)

        with patch.object(agente, "LAUNCHAGENTS_RAW", raw):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = agente.congelar_agente_vivo(conn, "amsterdam9.rotate-hermes-logs")
                inexistente = agente.congelar_agente_vivo(conn, "agente.que.no.existe")

        check("componente = label del agente", episodio.componente == "amsterdam9.rotate-hermes-logs")
        check("origen = agente", episodio.origen == "agente")
        check("es_critico siempre False", episodio.es_critico is False)
        check("en_vivo=True siempre (no existe modo diferido)", episodio.en_vivo is True)
        check(
            "agente_actual poblado con el estado real",
            episodio.snapshot_evidencia["agente_actual"] is not None
            and episodio.snapshot_evidencia["agente_actual"]["status"] == "error",
        )
        check(
            "label inexistente congela igual, con evidencia vacía",
            inexistente.snapshot_evidencia["agente_actual"] is None
            and inexistente.componente == "agente.que.no.existe",
        )
