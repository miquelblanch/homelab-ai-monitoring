"""_homelab_bridge_common — lo que los tres paquetes (`diagnostico`,
`inventory`, `remediacion`) importan hoy sin excepción de los scripts
privados del homelab: `homelab_secrets` y `docker_monitor`. Ver
specs/024-consolidar-bridge-homelab/research.md §1.

Deliberadamente NO importa `heartbeat` ni `ha_monitor` — esos scripts
solo los usan dos de los tres paquetes (nunca `remediacion`), así que
viven en `_homelab_bridge_heartbeat.py` o localmente en cada fachada,
para no arrastrar un `import` nuevo a un paquete que hoy no lo hace
(research.md §1).

Vive fuera de `diagnostico/`, `inventory/` y `remediacion/` a
propósito — un módulo neutral no privilegia a ningún paquete y no crea
una dependencia nueva de `remediacion` hacia `inventory` que hoy no
existe.

Contrato: si los scripts no están disponibles (repo público clonado
fuera del homelab, por ejemplo), las funciones devuelven un resultado
inocuo en vez de lanzar excepción — mismo principio "a prueba de
fallos" que ya tenían los tres ficheros por separado.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEFAULT_SCRIPTS_DIR = "/Volumes/FastData/homelab/scripts"
_SCRIPTS_DIR = Path(os.environ.get("HOMELAB_SCRIPTS_DIR", _DEFAULT_SCRIPTS_DIR))

if str(_SCRIPTS_DIR) not in sys.path and _SCRIPTS_DIR.is_dir():
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import homelab_secrets as _homelab_secrets  # type: ignore[import-not-found]
except ImportError:
    _homelab_secrets = None

try:
    import docker_monitor as _docker_monitor  # type: ignore[import-not-found]
except ImportError:
    _docker_monitor = None


def get_secret(key: str, default: str = "") -> str:
    if _homelab_secrets is None:
        return default
    return _homelab_secrets.get(key, default)


def telegram_credentials() -> tuple[str, str]:
    """(token, chat_id) — cadenas vacías si no se pudo resolver."""
    if _homelab_secrets is None:
        return "", ""
    try:
        return _homelab_secrets.telegram()
    except Exception:
        return "", ""


def docker_never_restart() -> set[str]:
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "NEVER_RESTART", set()))
    except Exception:
        return set()


def docker_critical() -> set[str]:
    """El conjunto real de `docker_monitor.CRITICAL` — base compartida
    por los tres paquetes. `remediacion` la envuelve con su propio
    hook de prueba (`REMEDIACION_TEST_FORZAR_CRITICO`) en su propia
    fachada, nunca aquí (specs/024-consolidar-bridge-homelab/research.md §3)."""
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "CRITICAL", set()))
    except Exception:
        return set()
