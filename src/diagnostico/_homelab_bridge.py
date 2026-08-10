"""_homelab_bridge — puente hacia los scripts ya existentes del homelab.

Copia mínima deliberada de `inventory/_homelab_bridge.py` (research.md
§7): `diagnostico` e `inventory` son dos paquetes hermanos
independientes bajo `src/`, sin que ninguno dependa del otro. Solo lleva
lo que este feature necesita — ni siquiera las funciones de `ha_monitor`,
que `inventory` sí tiene y este feature no usa (no toca HA).

Mismo contrato que el original: si los scripts no están disponibles
(repo público clonado fuera del homelab), las funciones devuelven un
resultado inocuo en vez de lanzar excepción.
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
    import heartbeat as _heartbeat  # type: ignore[import-not-found]
except ImportError:
    _heartbeat = None

try:
    import docker_monitor as _docker_monitor  # type: ignore[import-not-found]
except ImportError:
    _docker_monitor = None


def get_secret(key: str, default: str = "") -> str:
    if _homelab_secrets is None:
        return default
    return _homelab_secrets.get(key, default)


def record_heartbeat(job: str, status: str = "ok", detail: str = "") -> bool | None:
    if _heartbeat is None:
        return None
    try:
        return _heartbeat.write(job, status=status, detail=detail)
    except Exception:
        return None


def docker_critical() -> set[str]:
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "CRITICAL", set()))
    except Exception:
        return set()


def docker_never_restart() -> set[str]:
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "NEVER_RESTART", set()))
    except Exception:
        return set()
