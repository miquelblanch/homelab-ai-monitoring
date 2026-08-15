"""backup — Evidencia del origen backup (feature 011:
specs/011-diagnostico-backups/). El log de una ejecución de
`backup_diario_nvme.sh`, en vivo o de un momento pasado dentro de la
ventana de retención. Ver research.md §3/§5/§8 de 011.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Episodio
from ..store import insert_episodio

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
