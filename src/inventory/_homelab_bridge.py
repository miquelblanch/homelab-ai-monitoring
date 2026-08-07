"""_homelab_bridge — puente hacia los scripts ya existentes del homelab.

Este feature reutiliza `homelab_secrets.py` (credenciales) y `heartbeat.py`
(latidos) en vez de duplicarlos — research.md §6-§7. Esos ficheros viven
fuera de este repositorio, en la infraestructura privada del homelab
(`/Volumes/FastData/homelab/scripts/`), así que no se pueden `import`
directamente como un paquete instalado: hace falta añadir esa ruta a
`sys.path`, mismo patrón que ya usa `docker_monitor.py`.

La ruta es configurable vía `HOMELAB_SCRIPTS_DIR` para no atarse a un único
layout de máquina — por defecto, la ruta documentada en el `CLAUDE.md`
general del homelab.

Contrato: si los scripts no están disponibles (repo público clonado fuera
del homelab, por ejemplo), `get_secret`/`send_telegram`/`record_heartbeat`
devuelven un resultado inocuo en vez de lanzar excepción — mismo principio
"a prueba de fallos" que el resto del homelab.
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
    import ha_monitor as _ha_monitor  # type: ignore[import-not-found]
except ImportError:
    _ha_monitor = None

try:
    import docker_monitor as _docker_monitor  # type: ignore[import-not-found]
except ImportError:
    _docker_monitor = None


def ha_monitor_checked_entities() -> set[str]:
    """Entidades de HA que `ha_monitor.py` comprueba individualmente —
    leído en vivo de `ha_monitor.CHECKS`, nunca copiado a este repo
    público (política de saneado, CLAUDE.md del proyecto)."""
    if _ha_monitor is None:
        return set()
    try:
        return {c["entity"] for c in getattr(_ha_monitor, "CHECKS", []) if "entity" in c}
    except Exception:
        return set()


def docker_never_restart() -> set[str]:
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "NEVER_RESTART", set()))
    except Exception:
        return set()


def docker_critical() -> set[str]:
    if _docker_monitor is None:
        return set()
    try:
        return set(getattr(_docker_monitor, "CRITICAL", set()))
    except Exception:
        return set()


def available() -> bool:
    """True si los dos módulos del homelab se pudieron importar."""
    return _homelab_secrets is not None and _heartbeat is not None


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


def record_heartbeat(job: str, status: str = "ok", detail: str = "") -> bool | None:
    if _heartbeat is None:
        return None
    try:
        return _heartbeat.write(job, status=status, detail=detail)
    except Exception:
        return None
