"""evidencia — Reúne evidencia real del homelab para un episodio y la
congela en un snapshot (FR-002, FR-003). Ver research.md §4/§5.

Lee `homelab.db` con una conexión normal (`sqlite3.connect()`, sin
`mode=ro` — research.md §4: la URI de solo lectura falla contra el
fichero real, montado sobre un volumen de red). La disciplina de "nunca
escribir" es de convención de código: este módulo solo ejecuta `SELECT`
contra esa base.

Los subprocesos de Docker usan la misma lista blanca de solo lectura que
`inventory/sources.py` (T040 de feature 001), ampliada con
`("docker", "logs")` — research.md §5.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from . import _homelab_bridge as bridge
from .model import Episodio
from .store import insert_episodio

_DEFAULT_HOMELAB_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/homelab.db"
)

VENTANA_METRICAS_MINUTOS = 30  # research.md §5, alrededor de un episodio histórico
DOCKER_LOGS_TAIL = 200  # research.md §5


def homelab_db_path() -> Path:
    return Path(os.environ.get("HOMELAB_DB_PATH", _DEFAULT_HOMELAB_DB_PATH))


def _connect_homelab_db(path: Path | None = None) -> sqlite3.Connection:
    """Conexión normal, nunca `mode=ro` (research.md §4). Solo `SELECT`
    se ejecuta contra esta conexión en todo este módulo."""
    conn = sqlite3.connect(path or homelab_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ── Lista blanca de subprocesos de solo lectura (research.md §5) ──────────

_READONLY_ALLOWLIST = {
    ("docker", "ps"),
    ("docker", "inspect"),
    ("docker", "logs"),
}


def _run_ro(cmd: list[str], timeout: int = 15) -> str:
    """Ejecuta un subcomando de solo lectura. Nunca lanza excepción por
    fallos de entorno (docker caído, comando ausente...) — devuelve "".
    Si el comando no está en la lista blanca, es un error de programación
    propio y SÍ lanza (mismo criterio que `inventory/sources.py`)."""
    key = (cmd[0], cmd[1] if len(cmd) > 1 else "")
    if key not in _READONLY_ALLOWLIST:
        raise RuntimeError(
            f"comando fuera de la lista blanca de solo lectura: {cmd!r}"
        )
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ── Lectores de homelab.db (research.md §4/§5) ─────────────────────────────


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


def docker_logs_tail(contenedor: str, lineas: int = DOCKER_LOGS_TAIL) -> str:
    return _run_ro(["docker", "logs", "--tail", str(lineas), contenedor])


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


# ── Discos (feature 009: specs/009-diagnostico-discos/) ────────────────────


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


def _parse_docker_inspect(raw: str) -> dict | list | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
