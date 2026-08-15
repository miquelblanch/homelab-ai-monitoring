"""agente — Evidencia del origen LaunchAgent (feature 016:
specs/016-diagnostico-agentes/). Si tiene un proceso activo y su
último código de salida — solo en vivo, sin ningún modo diferido: no
existe ninguna fuente de evidencia histórica real para LaunchAgents.
Ver research.md §2/§3 de 016.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ..model import Episodio
from ..store import insert_episodio

LAUNCHAGENTS_RAW = Path(
    os.environ.get(
        "LAUNCHAGENTS_RAW",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/launchagents_raw.txt",
    )
)  # research.md §3 de 016 — única fuente de evidencia, sin par
# histórico: se sobreescribe cada 5 min, sin ningún archivo (research.md §2).


def _agente_actual(label: str) -> dict | None:
    """Estado real de `label` en `LAUNCHAGENTS_RAW` — mismo cálculo
    exacto que `app.py::get_launchagents()` (research.md §3 de 016).
    `None` si `label` no aparece en el fichero — no es un error, mismo
    criterio que un identificador inexistente en cualquier otro
    origen."""
    try:
        lineas = LAUNCHAGENTS_RAW.read_text().splitlines()
    except OSError:
        return None

    for linea in lineas:
        partes = linea.split("\t")
        if len(partes) < 3:
            continue
        pid, exit_code, etiqueta = partes[0].strip(), partes[1].strip(), partes[2].strip()
        if etiqueta != label:
            continue
        running = pid != "-"
        ok = exit_code in ("0", "-")
        status = "running" if running else ("idle" if ok else "error")
        return {
            "label": label,
            "pid": pid,
            "exit_code": exit_code,
            "running": running,
            "status": status,
        }
    return None


def _snapshot_agente_vacio() -> dict:
    return {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": None,
        "ha_check": None,
        "ha_check_status": None,
        "ha_history": None,
        "ha_recorder_corrupt_files": None,
        "backup_log_path": None,
        "backup_dumps": None,
        "backup_rsync_stats": None,
        "backup_resumen_final": None,
        "backup_rsync_estado": None,
        "backup_anomalias": None,
        "relay_nombre": None,
        "relay_estado_actual": None,
        "relay_agregado": None,
        "inventario_ejecucion_id": None,
        "inventario_hallazgo": None,
        "inventario_brecha": None,
        "inventario_comparacion": None,
        "host_externo_actual": None,
        "host_externo_stats": None,
        "hub_beszel_actual": None,
        "hub_beszel_stats": None,
        "agente_actual": None,
    }


def congelar_agente_vivo(conn: sqlite3.Connection, label: str) -> Episodio:
    """Congela el estado actual de un LaunchAgent — único constructor
    de episodio de este origen, no existe modo diferido (research.md
    §2 de 016). `es_critico` siempre `False`."""
    ahora = datetime.now()
    estado = _agente_actual(label)
    snapshot = _snapshot_agente_vacio()
    snapshot.update(agente_actual=estado)

    episodio = Episodio(
        componente=label,
        origen="agente",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
