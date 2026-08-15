"""hub_beszel — Evidencia del origen hub de Beszel (feature 015:
specs/015-diagnostico-hub-beszel/). En vivo si todos sus sistemas
registrados dejaron de reportar a la vez, o en diferido con la
densidad de muestras de cada sistema en una ventana. Ver research.md
§2/§3/§4/§5/§7/§10 de 015.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timedelta

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
