"""contenedor — Evidencia del origen contenedor (feature 007:
specs/007-diagnostico-episodios/). Congelado en vivo o de un evento ya
cerrado de `restart_history`. Ver research.md §4/§5 de 007 y
data-model.md de specs/023-evidencia-por-origen/.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from .. import _homelab_bridge as bridge
from ..model import Episodio
from ..store import insert_episodio
from ._compartido import (
    VENTANA_METRICAS_MINUTOS,
    _connect_homelab_db,
    _run_ro,
    docker_logs_tail,
)


def restart_history_row(restart_history_id: int) -> dict | None:
    conn = _connect_homelab_db()
    try:
        row = conn.execute(
            "SELECT * FROM restart_history WHERE id = ?", (restart_history_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def container_metrics_window(container: str, inicio: datetime, fin: datetime) -> list[dict]:
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, status, health, cpu_percent, memory_mb, memory_percent
               FROM container_metrics
               WHERE container = ? AND timestamp BETWEEN ? AND ?
               ORDER BY timestamp""",
            (container, inicio.isoformat(), fin.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def container_metrics_hourly_window(container: str, inicio: datetime, fin: datetime) -> list[dict]:
    """Respaldo para episodios históricos fuera de los 30 días de
    retención de `container_metrics` (CLAUDE.md general del homelab) —
    `container_metrics_hourly` es la serie horaria permanente. Sin este
    respaldo, todo episodio de más de 30 días concluiría
    `no_diagnosticable` por falta de datos que en realidad sí existen,
    solo que agregados (hallazgo real al preparar T030 de tasks.md:
    los 49 reinicios de `beszel` son de marzo-mayo 2026, ya fuera de la
    ventana de detalle hoy)."""
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT hour, samples, cpu_avg, cpu_max, memory_avg_mb,
                      memory_max_mb, healthy_ratio
               FROM container_metrics_hourly
               WHERE container = ? AND hour BETWEEN ? AND ?
               ORDER BY hour""",
            (container, inicio.strftime("%Y-%m-%dT%H"), fin.strftime("%Y-%m-%dT%H")),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def container_metrics_recientes(container: str, limite: int = 12) -> list[dict]:
    """Últimas muestras disponibles — para el caso en vivo, donde no hay
    un timestamp de episodio alrededor del cual centrar la ventana."""
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, status, health, cpu_percent, memory_mb, memory_percent
               FROM container_metrics WHERE container = ?
               ORDER BY id DESC LIMIT ?""",
            (container, limite),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def disk_metrics_near(momento: datetime) -> list[dict]:
    """Las 3 muestras más próximas a `momento`, pero solo si caen dentro
    de la ventana de tolerancia — nunca las "más cercanas disponibles" a
    cualquier distancia. `disk_metrics` tiene la misma retención de 30
    días que `container_metrics`; sin este filtro, un episodio de hace
    meses recibiría datos de disco de HOY como si fueran evidencia
    "cercana" (hallazgo real al preparar T030: pasaba con los episodios
    de `beszel` de abril, casi 4 meses fuera de rango) — exactamente el
    tipo de correlación falsa que FR-007 prohíbe inducir."""
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, path, label, used_percent, free_gb,
                      ABS(strftime('%s', timestamp) - strftime('%s', ?)) AS distancia_s
               FROM disk_metrics
               ORDER BY distancia_s LIMIT 3""",
            (momento.isoformat(),),
        ).fetchall()
        tolerancia_s = VENTANA_METRICAS_MINUTOS * 60
        return [
            {k: r[k] for k in ("timestamp", "path", "label", "used_percent", "free_gb")}
            for r in rows
            if r["distancia_s"] <= tolerancia_s
        ]
    finally:
        conn.close()


def docker_inspect(contenedor: str) -> str:
    return _run_ro(["docker", "inspect", contenedor])


# ── Contenedores críticos (research.md §7, FR-013a) ────────────────────────


def es_critico(contenedor: str) -> bool:
    return contenedor in bridge.docker_critical()


# ── Congelado del snapshot (FR-001, FR-002) ────────────────────────────────


def congelar_historico(conn: sqlite3.Connection, restart_history_id: int) -> Episodio:
    """Congela un episodio ya cerrado de `restart_history`. Arma el
    `snapshot_evidencia` completo antes de persistir — a partir de ahí,
    `diagnosticar` nunca vuelve a tocar `homelab.db` para este episodio
    (FR-002)."""
    fila = restart_history_row(restart_history_id)
    if fila is None:
        raise ValueError(f"restart_history #{restart_history_id} no existe")

    contenedor = fila["container_name"]
    momento = datetime.fromtimestamp(fila["timestamp"])
    inicio = momento - timedelta(minutes=VENTANA_METRICAS_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_METRICAS_MINUTOS)

    detalle = container_metrics_window(contenedor, inicio, fin)
    snapshot = {
        "disco": None,
        "restart_history": fila,
        "container_metrics": detalle,
        # Respaldo si el episodio ya salió de los 30 días de retención de
        # `container_metrics` — lista vacía si tampoco hay agregado horario
        # (episodio anterior al 2026-04-17, o sin muestras en esa hora).
        "container_metrics_hourly": (
            [] if detalle else container_metrics_hourly_window(contenedor, inicio, fin)
        ),
        "disk_metrics": disk_metrics_near(momento),
        "docker_inspect": None,
        "docker_logs_tail": None,
    }

    episodio = Episodio(
        componente=contenedor,
        origen="contenedor",
        es_critico=es_critico(contenedor),
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=restart_history_id,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_vivo(conn: sqlite3.Connection, contenedor: str) -> Episodio:
    """Congela el estado actual de un contenedor en vivo: última ventana
    de métricas disponible + `docker inspect`/`docker logs` (no capturado
    todavía por la muestra de 5 min de `docker_monitor.py`)."""
    ahora = datetime.now()
    metrics = container_metrics_recientes(contenedor)
    inicio = metrics[0]["timestamp"] if metrics else ahora.isoformat()

    inspect_raw = docker_inspect(contenedor)
    snapshot = {
        "disco": None,
        "restart_history": None,
        "container_metrics": metrics,
        "container_metrics_hourly": [],  # no aplica en vivo — datos ya recientes
        "disk_metrics": disk_metrics_near(ahora),
        "docker_inspect": _parse_docker_inspect(inspect_raw),
        "docker_logs_tail": docker_logs_tail(contenedor),
    }

    episodio = Episodio(
        componente=contenedor,
        origen="contenedor",
        es_critico=es_critico(contenedor),
        en_vivo=True,
        ventana_inicio=inicio,
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def _parse_docker_inspect(raw: str) -> dict | list | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
