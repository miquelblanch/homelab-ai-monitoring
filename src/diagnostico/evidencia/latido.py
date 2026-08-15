"""latido — Evidencia del origen latido de monitor (feature 017:
specs/017-diagnostico-latidos/). Si ha latido, hace cuánto, y su
último detalle — el veredicto `ok` calculado únicamente por edad,
nunca combinado con el estado del último ciclo — solo en vivo, mismo
tipo de limitación real que los LaunchAgents. Ver research.md §2/§3 de
017.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ..model import Episodio
from ..store import insert_episodio

MONITOR_HEARTBEATS_DIR = Path(
    os.environ.get(
        "MONITOR_HEARTBEATS_DIR",
        "/Volumes/FastData/homelab/data/heartbeats",
    )
)  # research.md §2/§3 de 017 — mismo directorio que ya lee
# app.py::get_monitor_heartbeats() (fuera de este repo). Cada
# `<job>.json` se sobreescribe en cada ciclo, sin ningún historial.

# (job, etiqueta, antigüedad máxima en segundos) — mismos 8 jobs y
# mismos literales que app.py::MONITOR_JOBS (fuera de este repo,
# BRIEFING.md "Feature 017 — material de partida"). Deliberadamente
# distinta de heartbeat.py::DEFAULT_MANIFEST (7 jobs, no coincide del
# todo) — spec.md Assumptions.
MONITOR_JOBS = [
    ("docker-monitor", "Monitor de Docker", 1800),
    ("ha-monitor", "Monitor de Home Assistant", 3600),
    ("dns-pi-monitor", "Monitor DNS AdGuardHome", 3600),
    ("verify-backups", "Verificación de backups", 108000),
    ("telegram-monitor", "Canal de Telegram", 900),
    ("beszel-hosts", "Estado de hosts externos (Beszel)", 900),
    ("bautista-calendar", "Recordatorios de Nextcloud (calendario)", 108000),
    ("inventario-cobertura", "Inventario de cobertura (homelab-ai-monitoring)", 108000),
]

_MONITOR_JOBS_POR_NOMBRE = {job: (label, max_age_s) for job, label, max_age_s in MONITOR_JOBS}


def _latido_actual(job: str) -> dict | None:
    """Estado real del latido de `job` — mismo cálculo exacto que
    `app.py::get_monitor_heartbeats()` (research.md §3 de 017): `ok`
    depende ÚNICAMENTE de la edad del latido, nunca de `status` (un job
    a tiempo con `status="error"` sigue siendo `ok=True`, igual que en
    el dashboard). `None` si `job` no está entre los 8 vigilados — no
    es un error, mismo criterio que un identificador inexistente en
    cualquier otro origen."""
    if job not in _MONITOR_JOBS_POR_NOMBRE:
        return None
    label, max_age_s = _MONITOR_JOBS_POR_NOMBRE[job]

    path = MONITOR_HEARTBEATS_DIR / f"{job}.json"
    try:
        data = json.loads(path.read_text())
        age_s = datetime.now().timestamp() - data.get("epoch", 0)
        return {
            "job": job,
            "label": label,
            "detail": data.get("detail", ""),
            "status": data.get("status", "ok"),
            "ok": age_s <= max_age_s,
            "age_s": age_s,
            "max_age_s": max_age_s,
        }
    except Exception:
        return {
            "job": job,
            "label": label,
            "detail": "sin latido",
            "status": None,
            "ok": False,
            "age_s": None,
            "max_age_s": max_age_s,
        }


def _snapshot_latido_vacio() -> dict:
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
        "latido_actual": None,
    }


def congelar_latido_vivo(conn: sqlite3.Connection, job: str) -> Episodio:
    """Congela el estado actual del latido de `job` — único constructor
    de episodio de este origen, no existe modo diferido (research.md
    §2 de 017). `es_critico` siempre `False`."""
    ahora = datetime.now()
    estado = _latido_actual(job)
    snapshot = _snapshot_latido_vacio()
    snapshot.update(latido_actual=estado)

    episodio = Episodio(
        componente=job,
        origen="latido",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
