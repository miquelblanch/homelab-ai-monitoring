"""disco — Evidencia del origen disco (feature 009:
specs/009-diagnostico-discos/). Congelado en vivo o de un momento
pasado concreto. Ver research.md §3/§4 de 009.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..model import Episodio
from ..store import insert_episodio
from ._compartido import VENTANA_METRICAS_MINUTOS, _connect_homelab_db


def disk_metrics_window(label: str, inicio: datetime, fin: datetime) -> list[dict]:
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, path, label, used_percent, free_gb
               FROM disk_metrics
               WHERE label = ? AND timestamp BETWEEN ? AND ?
               ORDER BY timestamp""",
            (label, inicio.isoformat(), fin.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def disk_metrics_recientes(label: str, limite: int = 12) -> list[dict]:
    """Últimas muestras disponibles de un disco — para el caso en vivo,
    mismo patrón que `container_metrics_recientes()`."""
    conn = _connect_homelab_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, path, label, used_percent, free_gb
               FROM disk_metrics WHERE label = ?
               ORDER BY id DESC LIMIT ?""",
            (label, limite),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def _disco_path(label: str) -> str | None:
    conn = _connect_homelab_db()
    try:
        row = conn.execute(
            "SELECT path FROM disk_metrics WHERE label = ? ORDER BY id DESC LIMIT 1",
            (label,),
        ).fetchone()
        return row["path"] if row else None
    finally:
        conn.close()


def congelar_disco_vivo(conn: sqlite3.Connection, label: str) -> Episodio:
    """Congela el estado actual de un disco en vivo — últimas muestras
    de `disk_metrics` (research.md §3 de specs/009-diagnostico-discos/).
    `es_critico` siempre `False` — no existe concepto de "disco crítico"
    (spec.md, Assumptions; research.md §4)."""
    ahora = datetime.now()
    metrics = disk_metrics_recientes(label)
    inicio = metrics[0]["timestamp"] if metrics else ahora.isoformat()

    snapshot = {
        "disco": {"label": label, "path": _disco_path(label)},
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": metrics,
        "docker_inspect": None,
        "docker_logs_tail": None,
    }

    episodio = Episodio(
        componente=label,
        origen="disco",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=inicio,
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_disco_historico(conn: sqlite3.Connection, label: str, momento: datetime) -> Episodio:
    """Congela un momento pasado concreto de un disco — ventana ±30 min
    alrededor de `momento` sobre `disk_metrics` (research.md §3). No
    existe una tabla de eventos discretos de disco como
    `restart_history` — el propio momento es el identificador del
    episodio (spec.md, Assumptions). `momento` se interpreta como hora
    local sin marca de zona, misma convención que `disk_metrics.timestamp`
    (research.md §3, contracts/cli.md) — comparación directa, sin
    conversión."""
    inicio = momento - timedelta(minutes=VENTANA_METRICAS_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_METRICAS_MINUTOS)

    metrics = disk_metrics_window(label, inicio, fin)
    snapshot = {
        "disco": {"label": label, "path": _disco_path(label)},
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": metrics,
        "docker_inspect": None,
        "docker_logs_tail": None,
    }

    episodio = Episodio(
        componente=label,
        origen="disco",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
