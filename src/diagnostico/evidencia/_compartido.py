"""_compartido — mecanismo real que usan varios orígenes de evidencia
a la vez (research.md §2 de specs/023-evidencia-por-origen/): conexión
a `homelab.db`, subprocesos de solo lectura de Docker, y localización
del cliente `docker` para el hub de Beszel. No es un origen más — ver
FR-006 de specs/023-evidencia-por-origen/spec.md.

Lee `homelab.db` con una conexión normal (`sqlite3.connect()`, sin
`mode=ro` — research.md §4 de 007: la URI de solo lectura falla contra
el fichero real, montado sobre un volumen de red). La disciplina de
"nunca escribir" es de convención de código: este módulo solo ejecuta
`SELECT` contra esa base.

Los subprocesos de Docker usan la misma lista blanca de solo lectura
que `inventory/sources.py` (T040 de feature 001), ampliada con
`("docker", "logs")` — research.md §5 de 007.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from shutil import which
from zoneinfo import ZoneInfo

_DEFAULT_HOMELAB_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/homelab.db"
)

VENTANA_METRICAS_MINUTOS = 30  # research.md §5 de 007, alrededor de un
# episodio histórico — compartida por contenedor (007) y disco (009).
DOCKER_LOGS_TAIL = 200  # research.md §5 de 007

BESZEL_HUB_VOLUME = "beszel_hub_data"  # research.md §7 de 014 —
# compartida por host_externo (014) y hub_beszel (015).

BESZEL_HOSTS_JSON = Path(
    os.environ.get(
        "BESZEL_HOSTS_JSON",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/beszel_hosts.json",
    )
)  # research.md §3 de 014 — estado actual, sobreescrito cada 5 min.
# Compartida por host_externo (014) y hub_beszel (015, sección
# "hub_systems" del mismo fichero).

BESZEL_HOSTS_MAX_AGE_S = 900  # research.md §3 de 014 — mismo valor
# exacto que app.py::BESZEL_HOSTS_MAX_AGE_S, nunca recalculado.
# Compartida por host_externo (014) y hub_beszel (015).

_MADRID_TZ = ZoneInfo("Europe/Madrid")


def homelab_db_path() -> Path:
    return Path(os.environ.get("HOMELAB_DB_PATH", _DEFAULT_HOMELAB_DB_PATH))


def _connect_homelab_db(path: Path | None = None) -> sqlite3.Connection:
    """Conexión normal, nunca `mode=ro` (research.md §4 de 007). Solo
    `SELECT` se ejecuta contra esta conexión en todo este motor."""
    conn = sqlite3.connect(path or homelab_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ── Lista blanca de subprocesos de solo lectura (research.md §5 de 007) ────

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


def docker_logs_tail(contenedor: str, lineas: int = DOCKER_LOGS_TAIL) -> str:
    return _run_ro(["docker", "logs", "--tail", str(lineas), contenedor])


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


def _a_utc_madrid(momento: datetime) -> str:
    """Interpreta `momento` (naive) como hora de Europe/Madrid y lo
    convierte a UTC, en el mismo formato que `system_stats.created`
    (research.md §4 de 014) — compartida por host_externo (014) y
    hub_beszel (015), las dos únicas fuentes que consultan el hub de
    Beszel."""
    momento_madrid = momento.replace(tzinfo=_MADRID_TZ)
    momento_utc = momento_madrid.astimezone(ZoneInfo("UTC"))
    return momento_utc.strftime("%Y-%m-%d %H:%M:%S.%f")


def _resumen_system_stats(filas: list[tuple[str, str]]) -> dict:
    """Reduce la lista de `(created, type)` a densidad — recuento,
    primera, última, por tipo de resolución — nunca un booleano
    "caído" (FR-006a, research.md §5 de 014). `filas` vacía (consulta
    con éxito, sin datos) produce el resumen "vacío", no `None`.
    Compartida por host_externo (014, uso directo) y hub_beszel (015,
    vía `_resumen_por_sistema()`, una vez por sistema registrado)."""
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
