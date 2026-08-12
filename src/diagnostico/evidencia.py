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
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from shutil import which
from zoneinfo import ZoneInfo

from inventory import diff as inv_diff
from inventory import store as inv_store
from inventory.model import TIPOS_BRECHA

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
    propio y SÍ lanza (mismo criterio que `inventory/sources.py`).

    `stderr` se combina con `stdout` (hallazgo real al validar
    specs/010-diagnostico-ha/ en vivo, 2026-08-12): `docker logs
    homeassistant` escribe su salida en stderr, no en stdout —
    capturando solo stdout, `docker_logs_tail("homeassistant")` volvía
    siempre `""` pese a haber logs reales, exactamente lo que
    `docker logs <contenedor>` sin redirección le mostraría a Miquel en
    una terminal. Sin efecto en `docker inspect`/`docker ps`, que ya
    escriben en stdout en el caso normal (`returncode == 0`)."""
    key = (cmd[0], cmd[1] if len(cmd) > 1 else "")
    if key not in _READONLY_ALLOWLIST:
        raise RuntimeError(
            f"comando fuera de la lista blanca de solo lectura: {cmd!r}"
        )
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=timeout,
        )
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


# ── Home Assistant (feature 010: specs/010-diagnostico-ha/) ────────────────

VENTANA_HA_ENTIDAD_HORAS = 12  # research.md §6 de 010 — más ancha que
# VENTANA_METRICAS_MINUTOS porque las entidades de HA solo registran un
# cambio de estado cuando ocurre, no se muestrean cada 5 minutos.

HA_HISTORIAL_MAX_ENTRADAS = 50  # research.md §6 de 010 (revisado tras
# hallazgo real de validación en vivo, 2026-08-12): sin este límite, una
# entidad de alta frecuencia (p. ej. `sal_nivel`, un sensor de voltaje
# que reporta cada pocos segundos, no un par de veces al día como una
# batería Zigbee) puede devolver miles de cambios de estado en la
# ventana — un caso real (1.962 entradas) llegó a 280.454 tokens de
# entrada sin producir ningún diagnóstico (finish_reason="length").
# Se quedan las entradas más recientes, no las más antiguas.

CHECKS_HA_EXCLUIDOS_CERRADURA = {
    "cerradura_up", "bateria_cerradura", "bateria_critica_cerradura",
}  # FR-010, research.md §7 de 010 — bloqueo explícito, no evidencia vacía.

_HA_API_CONTENEDOR = "homeassistant"  # research.md §5 de 010 — el check
# `ha_api` (tipo api_ping) no tiene entidad ni campo "contenedor" propio
# en ha_monitor.CHECKS (Clarifications 2026-08-12, spec.md FR-003).

_TIPOS_CHECK_HA_ENTIDAD = (
    "entity_state", "entity_available", "entity_value_below", "entity_age_below",
)


def ha_check_by_id(check_id: str) -> dict | None:
    """El dict de `check_id` en `ha_monitor.CHECKS`, o `None` si no
    existe o `ha_monitor.py` no está disponible — no es un error
    (spec.md Edge Cases): un `check_id` inexistente congela igual, con
    toda la evidencia de HA en `null` (research.md §3 de 010)."""
    return next((c for c in bridge.ha_checks() if c.get("id") == check_id), None)


def _simplificar_historial(historial: list[dict]) -> list[dict]:
    """Reduce cada entrada a `state`/`last_changed` y recorta a
    `HA_HISTORIAL_MAX_ENTRADAS`, quedándose con las más recientes
    (research.md §6 de 010). `entity_id` ya es redundante con
    `ha_check.entity`, y `attributes` repite en cada entrada metadata
    que no cambia (unidad, device_class, nombre) sin aportar señal
    diagnóstica nueva — quitarlo reduce el tamaño incluso en el caso
    normal, no solo en el caso extremo que motivó el límite de
    entradas."""
    recortado = historial[-HA_HISTORIAL_MAX_ENTRADAS:]
    return [{"state": e.get("state"), "last_changed": e.get("last_changed")} for e in recortado]


def ha_history_window(entity: str, inicio: datetime, fin: datetime) -> list[dict] | None:
    """Historial de `entity` en `[inicio, fin]`, vía la API REST de HA
    (research.md §4 de 010), acotado y simplificado por
    `_simplificar_historial()`. `None` si la API no respondió — distinto
    de `[]` (respondió, sin cambios en la ventana), mismo criterio que
    el resto del snapshot ya usa para "sin dato" vs. "dato vacío"."""
    historial = bridge.ha_history(entity, inicio.isoformat(), fin.isoformat())
    if historial is None:
        return None
    return _simplificar_historial(historial)


def _validar_check_ha(check_id: str) -> dict | None:
    """Bloquea los 3 checks de la cerradura (FR-010) antes de intentar
    resolver nada — un `ValueError`, no una evidencia vacía, porque es
    un rechazo explícito de alcance, no una ausencia de datos
    (research.md §7 de 010). Para cualquier otro `check_id`, delega en
    `ha_check_by_id()` (puede devolver `None`, y no es un error)."""
    if check_id in CHECKS_HA_EXCLUIDOS_CERRADURA:
        raise ValueError(
            f"check {check_id!r} de la cerradura queda fuera del alcance de "
            "este feature (spec.md FR-010) — su causa ya se investigó a mano"
        )
    return ha_check_by_id(check_id)


def _resolver_evidencia_ha(
    check: dict | None, inicio: datetime, fin: datetime
) -> tuple[list[dict] | None, list[str] | None, str | None]:
    """Evidencia según el tipo de check ya resuelto (o `None` si no se
    reconoce) — research.md §4 de 010. Devuelve
    `(ha_history, ha_recorder_corrupt_files, docker_logs_tail)`, cada
    uno `None` salvo el que corresponda al tipo."""
    if check is None:
        return None, None, None

    tipo = check.get("type")
    if tipo in _TIPOS_CHECK_HA_ENTIDAD:
        return ha_history_window(check["entity"], inicio, fin), None, None
    if tipo == "recorder_corrupto":
        corrupt_files = bridge.ha_recorder_corrupt_files(check["contenedor"], check["ruta"])
        return None, corrupt_files, docker_logs_tail(check["contenedor"])
    if tipo == "api_ping":
        return None, None, docker_logs_tail(_HA_API_CONTENEDOR)
    return None, None, None


def congelar_ha_vivo(conn: sqlite3.Connection, check_id: str) -> Episodio:
    """Congela el estado actual de un check de HA en vivo. `es_critico`
    siempre `False` (research.md §8 de 010) — no existe concepto de
    "check de HA crítico" (spec.md Assumptions)."""
    ahora = datetime.now()
    check = _validar_check_ha(check_id)
    inicio = ahora - timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    historial, corrupt_files, logs = _resolver_evidencia_ha(check, inicio, ahora)
    estado = bridge.ha_check_status(check) if check is not None else None

    snapshot = {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": logs,
        "ha_check": check,
        "ha_check_status": estado,
        "ha_history": historial,
        "ha_recorder_corrupt_files": corrupt_files,
    }

    episodio = Episodio(
        componente=check_id,
        origen="ha",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_ha_historico(conn: sqlite3.Connection, check_id: str, momento: datetime) -> Episodio:
    """Congela un momento pasado concreto de un check de HA. Para
    checks de entidad, ventana ±`VENTANA_HA_ENTIDAD_HORAS` alrededor de
    `momento` sobre el historial real de HA — estable entre llamadas
    repetidas (base de SC-001). Para `recorder_corrupto`/`api_ping`, no
    existe ninguna fuente de evidencia verdaderamente histórica — se
    congela el mismo estado *actual* que usaría `congelar_ha_vivo`, bajo
    la ventana etiquetada con `momento` — limitación aceptada, no un bug
    (research.md §6 de 010; spec.md Assumptions). `momento` se
    interpreta como hora local sin marca de zona, mismo criterio que
    `disk_metrics.timestamp` (research.md §9 de 010)."""
    check = _validar_check_ha(check_id)
    inicio = momento - timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    fin = momento + timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    historial, corrupt_files, logs = _resolver_evidencia_ha(check, inicio, fin)
    estado = bridge.ha_check_status(check) if check is not None else None

    snapshot = {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": logs,
        "ha_check": check,
        "ha_check_status": estado,
        "ha_history": historial,
        "ha_recorder_corrupt_files": corrupt_files,
    }

    episodio = Episodio(
        componente=check_id,
        origen="ha",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


# ── Backups (feature 011: specs/011-diagnostico-backups/) ──────────────────

BACKUP_LOG_DIR = Path(
    os.environ.get("BACKUP_LOG_DIR", "/Volumes/FastData/homelab/logs")
)  # research.md §5 de 011

VENTANA_BACKUP_HORAS = 12  # research.md §5 de 011 — tolerancia para
# encontrar el log más cercano a un MOMENTO_ISO; solo hay una ejecución
# por noche (02:00), así que basta con acertar la fecha aproximada.

BACKUP_ANOMALIA_MAX_LINEAS = 30  # research.md §3 de 011 — mismo
# criterio que HA_HISTORIAL_MAX_ENTRADAS de 010: el log más grande real
# retenido tiene 9.878 líneas, casi todas de la lista de ficheros
# cambiados de rsync sin valor diagnóstico; sin este límite, un log con
# muchos errores reales podría reventar el prompt igual que sal_nivel
# en 010.

_PATRON_NOMBRE_LOG_BACKUP = re.compile(r"backup_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.log$")
_PATRON_LINEA_DUMP = re.compile(r"^\s*[✅⚠️]")
_PATRON_LINEA_ANOMALIA = re.compile(r"rsync:|rsync error:|IO error|Permission denied")
_ETIQUETAS_RSYNC_STATS = (
    "Number of files:", "Number of created files:", "Number of deleted files:",
    "Number of regular files transferred:", "Total file size:",
    "Total transferred file size:", "Literal data:", "Matched data:",
    "File list size:", "File list generation time:", "File list transfer time:",
    "Total bytes sent:", "Total bytes received:",
)


def _listar_logs_backup() -> list[Path]:
    """Todos los `backup_*.log` de `BACKUP_LOG_DIR`, en orden
    lexicográfico ascendente — el propio formato del nombre
    (`YYYY-MM-DD_HH-MM-SS`) ya ordena cronológicamente sin necesidad de
    leer `mtime` (research.md §5 de 011)."""
    if not BACKUP_LOG_DIR.is_dir():
        return []
    return sorted(BACKUP_LOG_DIR.glob("backup_*.log"))


def _momento_de_log_backup(path: Path) -> datetime | None:
    m = _PATRON_NOMBRE_LOG_BACKUP.search(path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S")


def _log_backup_mas_reciente() -> Path | None:
    logs = _listar_logs_backup()
    return logs[-1] if logs else None


def _log_backup_cercano(momento: datetime) -> Path | None:
    """El log cuyo momento embebido en el nombre está más cerca de
    `momento`, dentro de `VENTANA_BACKUP_HORAS` — `None` si ninguno cae
    dentro de la ventana (research.md §5 de 011)."""
    tolerancia = timedelta(hours=VENTANA_BACKUP_HORAS)
    mejor: Path | None = None
    mejor_distancia: timedelta | None = None
    for log in _listar_logs_backup():
        momento_log = _momento_de_log_backup(log)
        if momento_log is None:
            continue
        distancia = abs(momento_log - momento)
        if distancia <= tolerancia and (mejor_distancia is None or distancia < mejor_distancia):
            mejor, mejor_distancia = log, distancia
    return mejor


def _parsear_log_backup(texto: str) -> dict:
    """Extrae piezas acotadas del log — nunca el texto completo
    (research.md §3 de 011). El log real más grande retenido (955 KB,
    9.878 líneas) es casi todo lista de ficheros de rsync sin valor
    diagnóstico; enviarlo entero repetiría el mismo reventón de prompt
    ya visto en 010 (`sal_nivel`, research.md §13 de 010)."""
    lineas = texto.splitlines()

    resumen_final = ""
    rsync_estado = "error"
    for linea in lineas:
        if "RESUMEN FINAL" in linea:
            resumen_final = linea.strip()
            rsync_estado = "ok" if "✅" in linea else "error"
            break

    dumps = [
        linea.strip() for linea in lineas
        if _PATRON_LINEA_DUMP.match(linea) and "RESUMEN FINAL" not in linea
    ]
    dumps_vistos = set(dumps)

    rsync_stats = [
        linea.strip() for linea in lineas
        if linea.strip().startswith(_ETIQUETAS_RSYNC_STATS)
        or (linea.strip().startswith("sent ") and "received" in linea)
        or linea.strip().startswith("total size is")
    ]

    # Excluye las líneas ya capturadas en `dumps` — `⚠️`/`❌` marcan
    # también un dump fallido, y sin esta exclusión esa misma línea se
    # contaba dos veces, gastando presupuesto de anomalías en contenido
    # ya presente en `dumps` (hallazgo I1 de /speckit-analyze, 2026-08-12).
    anomalias: list[str] = []
    for linea in lineas:
        limpia = linea.strip()
        if limpia in dumps_vistos:
            continue
        if _PATRON_LINEA_ANOMALIA.search(linea):
            anomalias.append(limpia)
            if len(anomalias) >= BACKUP_ANOMALIA_MAX_LINEAS:
                break

    return {
        "dumps": dumps,
        "rsync_stats": rsync_stats,
        "resumen_final": resumen_final,
        "rsync_estado": rsync_estado,
        "anomalias": anomalias,
    }


def _snapshot_backup_vacio() -> dict:
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
    }


def _congelar_backup(
    conn: sqlite3.Connection, log: Path | None, momento_solicitado: datetime, *, en_vivo: bool
) -> Episodio:
    """Arma y persiste el episodio a partir de un log ya localizado (o
    `None` si no se encontró ninguno) — compartido por
    `congelar_backup_vivo`/`congelar_backup_historico` porque el armado
    del snapshot es idéntico entre los dos, solo cambia cómo se
    localizó el log.

    `momento_solicitado` es el momento que Miquel pidió (ahora mismo
    para `--backup-vivo`, o el argumento de `--backup-historico`) — se
    usa como `componente`/ventana cuando no hay ningún log que
    encontrar, para que `mostrar` refleje lo que se pidió, no la hora a
    la que se ejecutó `congelar` (hallazgo real de validación en vivo,
    2026-08-12: sin esto, pedir un momento de 2020 mostraba la hora
    actual, no 2020, confuso de leer después)."""
    if log is not None:
        momento = _momento_de_log_backup(log) or momento_solicitado
        parsed = _parsear_log_backup(log.read_text(errors="ignore"))
        snapshot = _snapshot_backup_vacio()
        snapshot.update(
            backup_log_path=str(log),
            backup_dumps=parsed["dumps"],
            backup_rsync_stats=parsed["rsync_stats"],
            backup_resumen_final=parsed["resumen_final"],
            backup_rsync_estado=parsed["rsync_estado"],
            backup_anomalias=parsed["anomalias"],
        )
    else:
        momento = momento_solicitado
        snapshot = _snapshot_backup_vacio()

    episodio = Episodio(
        componente=momento.isoformat(),
        origen="backup",
        es_critico=False,
        en_vivo=en_vivo,
        ventana_inicio=momento.isoformat(),
        ventana_fin=momento.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_backup_vivo(conn: sqlite3.Connection) -> Episodio:
    """Congela el log de backup más reciente. `es_critico` siempre
    `False` (spec.md Assumptions) — no existe concepto de "backup
    crítico"."""
    ahora = datetime.now()
    return _congelar_backup(conn, _log_backup_mas_reciente(), ahora, en_vivo=True)


def congelar_backup_historico(conn: sqlite3.Connection, momento: datetime) -> Episodio:
    """Congela el log más cercano a `momento`, dentro de
    `VENTANA_BACKUP_HORAS`. `momento` se interpreta como hora local sin
    marca de zona, misma convención que discos/HA (research.md §8 de
    011)."""
    return _congelar_backup(conn, _log_backup_cercano(momento), momento, en_vivo=False)


# ── Relays socat (feature 012: specs/012-diagnostico-relays/) ──────────────

SOCAT_RELAYS_JSON = Path(
    os.environ.get(
        "SOCAT_RELAYS_JSON",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json",
    )
)  # research.md §3 de 012 — estado actual, sobreescrito cada 5 min.

DASHBOARD_SOCAT_LOG = Path(
    os.environ.get(
        "DASHBOARD_SOCAT_LOG", str(Path.home() / "Library/Logs/dashboard-socat.log")
    )
).expanduser()  # research.md §5 de 012 — primer fichero de evidencia
# fuera de /Volumes/FastData/homelab/: es el StandardOutPath del
# LaunchAgent amsterdam9.dashboard.socat.

VENTANA_RELAY_MINUTOS = 180  # research.md §5 de 012 — de los 17
# episodios reales identificados (2026-04-29 en adelante), 16 duran
# 52 min o menos; uno solo llega a ~595 min (10h, 2026-05-24). ±180
# min cubre los 16 enteros y muestra una porción amplia del largo.

RELAY_AGREGADO_MAX_LINEAS = 100  # research.md §5 de 012 — límite
# defensivo, no motivado por un caso real: a intervalos de 5 min, la
# propia ventana ya acota a ~72 líneas como máximo.

_PATRON_LINEA_RELAY = re.compile(r"\[(?P<ts>[^\]]+)\].*?(?P<ok>\d+)/(?P<total>\d+) ok")


def _relay_actual(nombre: str) -> dict | None:
    """La entrada de `nombre` en `socat_relays.json` ahora mismo —
    `None` si el fichero no existe o `nombre` no está entre los relays
    vigilados (research.md §3 de 012). No es un error — spec.md Edge
    Cases: el episodio se congela igual, con evidencia vacía."""
    if not SOCAT_RELAYS_JSON.is_file():
        return None
    try:
        datos = json.loads(SOCAT_RELAYS_JSON.read_text())
    except (OSError, ValueError):
        return None
    for relay in datos.get("relays", []):
        if relay.get("name") == nombre:
            return relay
    return None


def listar_nombres_relay() -> set[str]:
    """Los `name` de todos los relays que aparecen ahora mismo en
    `socat_relays.json` — usado por
    `deepseek._menciona_relay_concreto()` para comprobar que un
    diagnóstico en diferido no nombra un relay concreto sin evidencia
    real de cuál falló (FR-006, hallazgo F1 de /speckit-analyze,
    2026-08-12; research.md §10 de 012)."""
    if not SOCAT_RELAYS_JSON.is_file():
        return set()
    try:
        datos = json.loads(SOCAT_RELAYS_JSON.read_text())
    except (OSError, ValueError):
        return set()
    return {r["name"] for r in datos.get("relays", []) if "name" in r}


def _agregado_relays_ventana(
    momento: datetime, ventana_minutos: int = VENTANA_RELAY_MINUTOS
) -> list[dict]:
    """Recuento agregado ("N de M ok") de cada línea de
    `DASHBOARD_SOCAT_LOG` dentro de `[momento - ventana, momento +
    ventana]` — nunca el detalle de qué relay concreto, que no existe
    (research.md §5 de 012). Acotado a `RELAY_AGREGADO_MAX_LINEAS`."""
    if not DASHBOARD_SOCAT_LOG.is_file():
        return []
    tolerancia = timedelta(minutes=ventana_minutos)
    inicio = momento - tolerancia
    fin = momento + tolerancia

    try:
        texto = DASHBOARD_SOCAT_LOG.read_text(errors="ignore")
    except OSError:
        return []

    resultado: list[dict] = []
    for linea in texto.splitlines():
        m = _PATRON_LINEA_RELAY.search(linea)
        if not m:
            continue
        try:
            ts = datetime.fromisoformat(m.group("ts"))
        except ValueError:
            continue
        if inicio <= ts <= fin:
            resultado.append(
                {"momento": ts.isoformat(), "ok": int(m.group("ok")), "total": int(m.group("total"))}
            )
            if len(resultado) >= RELAY_AGREGADO_MAX_LINEAS:
                break
    return resultado


def _snapshot_relay_vacio() -> dict:
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
    }


def congelar_relay_vivo(conn: sqlite3.Connection, nombre: str) -> Episodio:
    """Congela el estado actual de un relay concreto, con detalle real
    (`socat_relays.json`). `es_critico` siempre `False` (spec.md
    Assumptions) — no existe concepto de "relay crítico"."""
    ahora = datetime.now()
    estado = _relay_actual(nombre)
    snapshot = _snapshot_relay_vacio()
    snapshot.update(relay_nombre=nombre, relay_estado_actual=estado)

    episodio = Episodio(
        componente=nombre,
        origen="relay",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_relay_historico(conn: sqlite3.Connection, momento: datetime) -> Episodio:
    """Congela la evidencia agregada de una ventana alrededor de
    `momento` — nunca el detalle de qué relay concreto falló, que no
    existe (research.md §2/§5 de 012). `componente` es siempre el
    momento pedido, incluso sin ningún dato en la ventana (research.md
    §9 de 012, lección de 011 aplicada por diseño)."""
    inicio = momento - timedelta(minutes=VENTANA_RELAY_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_RELAY_MINUTOS)
    agregado = _agregado_relays_ventana(momento)

    snapshot = _snapshot_relay_vacio()
    snapshot.update(relay_agregado=agregado)

    episodio = Episodio(
        componente=momento.isoformat(),
        origen="relay",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


# ── Inventario de cobertura (feature 013: specs/013-diagnostico-inventario/) ─

TIPOS_INVENTARIO_EN_ALCANCE = frozenset(TIPOS_BRECHA) - {"condicion_incumplida"}
# research.md §5 de 013 — `condicion_incumplida` solo ocurre hoy en
# `entidad_ha` y es el propio inventario re-detectando, con otras
# palabras, lo que el origen "ha" (010) ya diagnostica (FR-010).

INVENTARIO_COMPARACION_MAX_ENTRADAS = 30  # research.md §11 de 013 —
# límite defensivo real: el ancla de comparación de las cuatro brechas
# reales conocidas (#19/#28/#31/#52) resulta ser una ejecución con 0
# brechas registradas, así que un diff sin límite listaría hasta 319
# brechas como "nuevas".


def _hallazgo_de_componente(
    conn_inv: sqlite3.Connection, ejecucion_id: int, nombre: str
) -> dict | None:
    """El hallazgo de `nombre` en `ejecucion_id`, o `None` si ese
    nombre no aparece entre los componentes de esa ejecución
    (research.md §4 de 013). No es un error — spec.md Edge Cases."""
    for h in inv_store.hallazgos_de_ejecucion(conn_inv, ejecucion_id):
        if h["nombre_actual"] == nombre:
            return dict(h)
    return None


def _brecha_de_componente(
    conn_inv: sqlite3.Connection, ejecucion_id: int, nombre: str
) -> dict | None:
    """La brecha de `nombre` en `ejecucion_id`, o `None` si ese
    componente no tiene ninguna brecha activa en esa ejecución
    (research.md §4 de 013). **Sin filtrar por tipo** — devuelve
    cualquiera de los 6 tipos posibles si existe; el rechazo de
    `condicion_incumplida` es responsabilidad exclusiva de
    `_validar_tipo_brecha_inventario()`, filtrar aquí la dejaría sin
    nada que rechazar (hallazgo U1 de /speckit-analyze, 2026-08-12)."""
    for b in inv_store.brechas_de_ejecucion(conn_inv, ejecucion_id):
        if b["nombre_actual"] == nombre:
            return dict(b)
    return None


def _validar_tipo_brecha_inventario(brecha: dict | None) -> None:
    """Bloquea `condicion_incumplida` antes de congelar nada — un
    `ValueError`, no una evidencia vacía, porque es un rechazo
    explícito de alcance, no una ausencia de datos (FR-010, research.md
    §5 de 013, mismo patrón que `_validar_check_ha()` bloqueando la
    cerradura en 010)."""
    if brecha is not None and brecha["tipo"] == "condicion_incumplida":
        raise ValueError(
            "brecha de tipo 'condicion_incumplida' queda fuera del alcance de "
            "este feature (spec.md FR-010) — el origen 'ha' (feature 010) ya "
            "la diagnostica"
        )


def _comparacion_dict(comparacion: inv_diff.Comparacion) -> dict:
    """Envuelve cada lista de `Comparacion` en `{"total", "muestra"}`,
    acotada a `INVENTARIO_COMPARACION_MAX_ENTRADAS` (research.md §11 de
    013) — el modelo ve el volumen real sin recibir el listado
    completo."""
    def _cap(lista: list[str]) -> dict:
        return {"total": len(lista), "muestra": lista[:INVENTARIO_COMPARACION_MAX_ENTRADAS]}

    return {
        "ejecucion_actual_id": comparacion.ejecucion_actual_id,
        "ejecucion_previa_id": comparacion.ejecucion_previa_id,
        "componentes_nuevos": _cap(comparacion.componentes_nuevos),
        "componentes_de_baja": _cap(comparacion.componentes_de_baja),
        "brechas_nuevas": _cap(comparacion.brechas_nuevas),
        "brechas_resueltas": _cap(comparacion.brechas_resueltas),
    }


def _snapshot_inventario_vacio() -> dict:
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
    }


def _armar_episodio_inventario(
    conn: sqlite3.Connection,
    conn_inv: sqlite3.Connection,
    nombre: str,
    ejecucion: sqlite3.Row | None,
    *,
    en_vivo: bool,
) -> Episodio:
    """Arma y persiste el episodio a partir de una ejecución ya
    localizada (o `None` si no existe) — compartido por
    `congelar_inventario_vivo`/`congelar_inventario_historico`, mismo
    patrón que `_congelar_backup()` de 011. `condicion_incumplida` se
    rechaza aquí, antes de persistir nada (FR-010)."""
    if ejecucion is not None:
        momento = datetime.fromisoformat(ejecucion["fecha"])
        hallazgo = _hallazgo_de_componente(conn_inv, ejecucion["id"], nombre)
        brecha = _brecha_de_componente(conn_inv, ejecucion["id"], nombre)
        _validar_tipo_brecha_inventario(brecha)  # brecha, si no es None,
        # ya está garantizado en TIPOS_INVENTARIO_EN_ALCANCE a partir de aquí

        comparacion = None
        if brecha is not None and brecha["primera_ejecucion_id"] > 1:
            comparacion = _comparacion_dict(
                inv_diff.compare_runs(
                    conn_inv, ejecucion["id"], brecha["primera_ejecucion_id"] - 1
                )
            )

        snapshot = _snapshot_inventario_vacio()
        snapshot.update(
            inventario_ejecucion_id=ejecucion["id"],
            inventario_hallazgo=hallazgo,
            inventario_brecha=brecha,
            inventario_comparacion=comparacion,
        )
    else:
        momento = datetime.now()
        snapshot = _snapshot_inventario_vacio()

    episodio = Episodio(
        componente=nombre,
        origen="inventario",
        es_critico=False,
        en_vivo=en_vivo,
        ventana_inicio=momento.isoformat(),
        ventana_fin=momento.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_inventario_vivo(conn: sqlite3.Connection, nombre: str) -> Episodio:
    """Congela el hallazgo actual de un componente del inventario, en
    la ejecución más reciente. `es_critico` siempre `False` (spec.md
    Assumptions) — no existe concepto de "componente crítico"."""
    with inv_store.connect() as conn_inv:
        ejecucion = inv_store.latest_ejecucion(conn_inv)
        return _armar_episodio_inventario(conn, conn_inv, nombre, ejecucion, en_vivo=True)


def congelar_inventario_historico(
    conn: sqlite3.Connection, nombre: str, ejecucion_id: int
) -> Episodio:
    """Congela el hallazgo de un componente del inventario en una
    ejecución pasada concreta. `ejecucion_id` inexistente no es un
    error — se congela igual, con evidencia vacía (research.md §9 de
    013)."""
    with inv_store.connect() as conn_inv:
        ejecucion = inv_store.get_ejecucion(conn_inv, ejecucion_id)
        return _armar_episodio_inventario(conn, conn_inv, nombre, ejecucion, en_vivo=False)


# ── Hosts externos (feature 014: specs/014-diagnostico-hosts-externos/) ────

HOSTS_EXTERNOS = {
    "Host de Uptime Kuma": "UptimeKuma",
    "Host de AdGuard Home (DNS primario)": "AdGuardHome",
}  # research.md §2 de 014 — mismos literales que
# scripts/beszel_hosts_monitor.py::HOSTS y app.py::EXTERNAL_HOSTS
# (fuera de este repo).

BESZEL_HOSTS_JSON = Path(
    os.environ.get(
        "BESZEL_HOSTS_JSON",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/beszel_hosts.json",
    )
)  # research.md §3 de 014 — estado actual, sobreescrito cada 5 min.

BESZEL_HOSTS_HEARTBEAT = Path(
    os.environ.get(
        "BESZEL_HOSTS_HEARTBEAT",
        "/Volumes/FastData/homelab/data/heartbeats/beszel-hosts.json",
    )
)  # research.md §3 de 014 — segunda mitad de la política de frescura.

BESZEL_HOSTS_MAX_AGE_S = 900  # research.md §3 de 014 — mismo valor
# exacto que app.py::BESZEL_HOSTS_MAX_AGE_S, nunca recalculado.

BESZEL_HUB_VOLUME = "beszel_hub_data"  # research.md §7 de 014.

VENTANA_HOST_EXTERNO_MINUTOS = 1440  # research.md §6 de 014 — ±24h,
# cubre 2-3 muestras "480m" esperadas en operación sana (cadencia real
# medida: una muestra cada 8h en ese nivel de retención).

_MADRID_TZ = ZoneInfo("Europe/Madrid")

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


def _a_utc_madrid(momento: datetime) -> str:
    """Interpreta `momento` (naive) como hora de Europe/Madrid y lo
    convierte a UTC, en el mismo formato que `system_stats.created`
    (research.md §4 de 014) — primera conversión de huso horario de
    este motor: todas las fuentes anteriores ya estaban en hora local."""
    momento_madrid = momento.replace(tzinfo=_MADRID_TZ)
    momento_utc = momento_madrid.astimezone(ZoneInfo("UTC"))
    return momento_utc.strftime("%Y-%m-%d %H:%M:%S.%f")


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


def _docker_bin() -> str | None:
    """Ruta absoluta del cliente docker — mismo motivo que
    `beszel_hosts_monitor.py::docker_bin()`: launchd no hereda el PATH
    de la sesión interactiva. `None` si no se encuentra en ningún sitio
    conocido."""
    encontrado = which("docker")
    if encontrado:
        return encontrado
    for ruta in ("/opt/homebrew/bin/docker",
                 "/usr/local/bin/docker",
                 str(Path.home() / ".orbstack/bin/docker")):
        if Path(ruta).is_file():
            return ruta
    return None


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


def _resumen_system_stats(filas: list[tuple[str, str]]) -> dict:
    """Reduce la lista de `(created, type)` a densidad — recuento,
    primera, última, por tipo de resolución — nunca un booleano
    "caído" (FR-006a, research.md §5 de 014). `filas` vacía (consulta
    con éxito, sin datos) produce el resumen "vacío", no `None`."""
    if not filas:
        return {"total_muestras": 0, "primera": None, "ultima": None, "por_tipo": {}}
    por_tipo: dict[str, int] = {}
    for _, tipo in filas:
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
    creados = sorted(creado for creado, _ in filas)
    return {
        "total_muestras": len(filas),
        "primera": creados[0],
        "ultima": creados[-1],
        "por_tipo": por_tipo,
    }


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


# ── Hub de Beszel (feature 015: specs/015-diagnostico-hub-beszel/) ─────────

VENTANA_HUB_BESZEL_MINUTOS = 1440  # research.md §10 de 015 — mismo
# valor y misma justificación que VENTANA_HOST_EXTERNO_MINUTOS de 014.

_QUERY_SYSTEM_STATS_TODOS = (
    "import sqlite3, json, sys; "
    "con = sqlite3.connect('/data/data.db'); "
    "rows = con.execute("
    "'SELECT s.name, ss.created, ss.type FROM systems s "
    "LEFT JOIN system_stats ss ON ss.system = s.id "
    "AND ss.created BETWEEN ? AND ? "
    "ORDER BY s.name, ss.created', "
    "(sys.argv[1], sys.argv[2])).fetchall(); "
    "print(json.dumps(rows))"
)


def _hub_beszel_actual() -> dict:
    """Replica exactamente `app.py::get_beszel_hub_status()` —
    antigüedad de cada sistema que el hub tiene registrado, `sano`
    solo si no todos están caducados a la vez (research.md §3 de 015).
    Reutiliza `BESZEL_HOSTS_JSON`/`BESZEL_HOSTS_MAX_AGE_S`, ya
    definidas en 014 — sin duplicar constantes."""
    ahora = datetime.now().timestamp()
    hub_systems: dict = {}
    try:
        data = json.loads(BESZEL_HOSTS_JSON.read_text())
        hub_systems = data.get("hub_systems", {})
    except (OSError, ValueError):
        pass

    systems = []
    for nombre, updated_raw in hub_systems.items():
        try:
            updated_ts = datetime.fromisoformat(
                updated_raw.replace(" ", "T").replace("Z", "+00:00")
            ).timestamp()
            age_s = ahora - updated_ts
            stale = age_s > BESZEL_HOSTS_MAX_AGE_S
        except (ValueError, AttributeError):
            age_s, stale = None, True
        systems.append({"name": nombre, "age_s": age_s, "stale": stale})

    sano = bool(systems) and not all(s["stale"] for s in systems)
    return {"systems": systems, "sano": sano}


def _consultar_beszel_hub_todos_sistemas(
    inicio_utc: str, fin_utc: str
) -> list[tuple[str, str | None, str | None]] | None:
    """Generaliza `_consultar_beszel_hub()` — mismo patrón de `docker
    run` parametrizado, pero sin filtrar por sistema: `LEFT JOIN` para
    que un sistema sin ninguna muestra en la ventana siga apareciendo
    (research.md §4 de 015). `None` ante cualquier fallo, nunca lanza."""
    docker = _docker_bin()
    if docker is None:
        return None
    try:
        proc = subprocess.run(
            [
                docker, "run", "--rm",
                "-v", f"{BESZEL_HUB_VOLUME}:/data",
                "python:3.11-alpine",
                "python3", "-c", _QUERY_SYSTEM_STATS_TODOS,
                inicio_utc, fin_utc,
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


def _resumen_por_sistema(filas: list[tuple[str, str | None, str | None]]) -> dict:
    """Agrupa por nombre de sistema y reutiliza `_resumen_system_stats()`
    de 014 tal cual para cada uno; `todos_sin_muestras` se calcula en
    código, nunca se deja que el modelo lo infiera (research.md §5 de
    015)."""
    por_sistema_filas: dict[str, list[tuple[str, str]]] = {}
    for nombre, created, tipo in filas:
        por_sistema_filas.setdefault(nombre, [])
        if created is not None:
            por_sistema_filas[nombre].append((created, tipo))

    resumen = {
        nombre: _resumen_system_stats(muestras)
        for nombre, muestras in por_sistema_filas.items()
    }
    todos_sin_muestras = bool(resumen) and all(
        r["total_muestras"] == 0 for r in resumen.values()
    )
    return {"por_sistema": resumen, "todos_sin_muestras": todos_sin_muestras}


def _snapshot_hub_beszel_vacio() -> dict:
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
    }


def congelar_hub_beszel_vivo(conn: sqlite3.Connection) -> Episodio:
    """Congela el estado actual del hub de Beszel — sin argumento,
    solo existe un hub (research.md §2 de 015, mismo patrón que
    `congelar_backup_vivo()` de 011). `es_critico` siempre `False`."""
    ahora = datetime.now()
    estado = _hub_beszel_actual()
    snapshot = _snapshot_hub_beszel_vacio()
    snapshot.update(hub_beszel_actual=estado)

    episodio = Episodio(
        componente=ahora.isoformat(),
        origen="hub_beszel",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_hub_beszel_historico(conn: sqlite3.Connection, momento: datetime) -> Episodio:
    """Congela la densidad de muestras de todos los sistemas del hub
    en una ventana ±`VENTANA_HUB_BESZEL_MINUTOS` alrededor de `momento`
    (research.md §4/§10 de 015). Sin argumento de nombre — mismo
    patrón que `congelar_backup_historico()`."""
    inicio = momento - timedelta(minutes=VENTANA_HUB_BESZEL_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_HUB_BESZEL_MINUTOS)

    filas = _consultar_beszel_hub_todos_sistemas(
        _a_utc_madrid(inicio), _a_utc_madrid(fin)
    )
    # `None` (consulta fallida) se distingue de una lista (consulta con
    # éxito) — nunca se le pasa `None` a _resumen_por_sistema()
    # (research.md §7 de 015, mismo hallazgo real ya corregido en 014 §10).
    stats = None if filas is None else _resumen_por_sistema(filas)

    snapshot = _snapshot_hub_beszel_vacio()
    snapshot.update(hub_beszel_stats=stats)

    episodio = Episodio(
        componente=momento.isoformat(),
        origen="hub_beszel",
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
