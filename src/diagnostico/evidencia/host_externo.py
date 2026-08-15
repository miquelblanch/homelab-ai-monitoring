"""host_externo — Evidencia del origen host físico externo vigilado por
Beszel (feature 014: specs/014-diagnostico-hosts-externos/). Uptime
Kuma o AdGuard Home, en vivo con el estado ya calculado, o en diferido
con la densidad de muestras de rendimiento que reportó al hub. Ver
research.md §2/§3/§4/§6/§7 de 014.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Episodio
from ..store import insert_episodio
from ._compartido import (
    BESZEL_HOSTS_JSON,
    BESZEL_HOSTS_MAX_AGE_S,
    BESZEL_HUB_VOLUME,
    _a_utc_madrid,
    _docker_bin,
    _resumen_system_stats,
)

HOSTS_EXTERNOS = {
    "Host de Uptime Kuma": "UptimeKuma",
    "Host de AdGuard Home (DNS primario)": "AdGuardHome",
}  # research.md §2 de 014 — mismos literales que
# scripts/beszel_hosts_monitor.py::HOSTS y app.py::EXTERNAL_HOSTS
# (fuera de este repo).

BESZEL_HOSTS_HEARTBEAT = Path(
    os.environ.get(
        "BESZEL_HOSTS_HEARTBEAT",
        "/Volumes/FastData/homelab/data/heartbeats/beszel-hosts.json",
    )
)  # research.md §3 de 014 — segunda mitad de la política de frescura.

VENTANA_HOST_EXTERNO_MINUTOS = 1440  # research.md §6 de 014 — ±24h,
# cubre 2-3 muestras "480m" esperadas en operación sana (cadencia real
# medida: una muestra cada 8h en ese nivel de retención).

_QUERY_SYSTEM_STATS = (
    "import sqlite3, json, sys; "
    "con = sqlite3.connect('/data/data.db'); "
    "rows = con.execute("
    "'SELECT created, type FROM system_stats "
    "WHERE system = (SELECT id FROM systems WHERE name = ?) "
    "AND created BETWEEN ? AND ? ORDER BY created', "
    "(sys.argv[1], sys.argv[2], sys.argv[3])).fetchall(); "
    "print(json.dumps(rows))"
)


def _host_externo_actual(nombre: str) -> dict | None:
    """Estado ya calculado de `nombre`, con la misma política de
    frescura de 900s (dato + latido a la vez) que ya usa
    `app.py::get_external_hosts()` (research.md §3 de 014). `None` si
    `nombre` no está en `HOSTS_EXTERNOS` — no es un error, mismo
    criterio que un `check_id`/`label` inexistente en orígenes
    anteriores."""
    if nombre not in HOSTS_EXTERNOS:
        return None
    beszel_name = HOSTS_EXTERNOS[nombre]
    ahora = datetime.now().timestamp()

    hosts_raw: dict = {}
    data_age_s = None
    try:
        data = json.loads(BESZEL_HOSTS_JSON.read_text())
        data_age_s = ahora - datetime.fromisoformat(data["generated_at"]).timestamp()
        hosts_raw = data.get("hosts", {})
    except (OSError, ValueError, KeyError):
        pass

    hb_age_s = None
    try:
        hb = json.loads(BESZEL_HOSTS_HEARTBEAT.read_text())
        hb_age_s = ahora - hb.get("epoch", 0)
    except (OSError, ValueError):
        pass

    fresh = (
        data_age_s is not None and data_age_s <= BESZEL_HOSTS_MAX_AGE_S
        and hb_age_s is not None and hb_age_s <= BESZEL_HOSTS_MAX_AGE_S
    )

    raw_status = hosts_raw.get(nombre, {}).get("status") if fresh else None
    if not fresh or raw_status is None:
        status = "sin_evidencia"
    elif raw_status == "up":
        status = "arriba"
    else:
        status = "caido"

    return {
        "nombre": nombre,
        "beszel_name": beszel_name,
        "status": status,
        "raw_status": raw_status,
        "data_age_s": data_age_s,
        "hb_age_s": hb_age_s,
    }


def _consultar_beszel_hub(
    beszel_name: str, inicio_utc: str, fin_utc: str
) -> list[tuple[str, str]] | None:
    """Consulta de solo lectura, parametrizada vía `sys.argv` (nunca
    interpolación de texto en SQL ni en el propio script — research.md
    §7 de 014), contra `system_stats` del hub de Beszel. Primera vez
    que este motor ejecuta `docker run` (arranca un contenedor nuevo),
    no solo `docker inspect`/`logs`/`ps` (`_run_ro()`, introspección de
    contenedores ya existentes) — mismo patrón ya en producción en
    `scripts/beszel_hosts_monitor.py::query_beszel()`. `None` ante
    cualquier fallo (Docker no disponible, timeout, código de salida
    distinto de 0) — nunca lanza. Distinto de `[]` (consulta con
    éxito, sin filas en la ventana)."""
    docker = _docker_bin()
    if docker is None:
        return None
    try:
        proc = subprocess.run(
            [
                docker, "run", "--rm",
                "-v", f"{BESZEL_HUB_VOLUME}:/data",
                "python:3.11-alpine",
                "python3", "-c", _QUERY_SYSTEM_STATS,
                beszel_name, inicio_utc, fin_utc,
            ],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if proc.returncode != 0:
        return None
    try:
        return [tuple(fila) for fila in json.loads(proc.stdout.strip())]
    except (ValueError, TypeError):
        return None


def _snapshot_host_externo_vacio() -> dict:
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
    }


def congelar_host_externo_vivo(conn: sqlite3.Connection, nombre: str) -> Episodio:
    """Congela el estado ya calculado de un host externo, en vivo.
    `es_critico` siempre `False` (spec.md Assumptions) — no existe
    concepto de "host crítico"."""
    ahora = datetime.now()
    estado = _host_externo_actual(nombre)
    snapshot = _snapshot_host_externo_vacio()
    snapshot.update(host_externo_actual=estado)

    episodio = Episodio(
        componente=nombre,
        origen="host_externo",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_host_externo_historico(
    conn: sqlite3.Connection, nombre: str, momento: datetime
) -> Episodio:
    """Congela la densidad de muestras de rendimiento de un host
    externo en una ventana ±`VENTANA_HOST_EXTERNO_MINUTOS` alrededor de
    `momento` (research.md §6 de 014). `componente` es siempre `nombre`
    pedido, nunca `nombre@momento` (research.md §2)."""
    inicio = momento - timedelta(minutes=VENTANA_HOST_EXTERNO_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_HOST_EXTERNO_MINUTOS)

    beszel_name = HOSTS_EXTERNOS.get(nombre)
    stats = None
    if beszel_name is not None:
        filas = _consultar_beszel_hub(
            beszel_name, _a_utc_madrid(inicio), _a_utc_madrid(fin)
        )
        # `None` (consulta fallida) se distingue de `[]` (consulta con
        # éxito, sin filas) — nunca se le pasa `None` a
        # _resumen_system_stats(), que espera una lista (research.md
        # §10 de 014, hallazgo real de /speckit-analyze, 2026-08-12).
        if filas is not None:
            stats = _resumen_system_stats(filas)
            stats["nombre"] = nombre
            stats["beszel_name"] = beszel_name

    snapshot = _snapshot_host_externo_vacio()
    snapshot.update(host_externo_stats=stats)

    episodio = Episodio(
        componente=nombre,
        origen="host_externo",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
