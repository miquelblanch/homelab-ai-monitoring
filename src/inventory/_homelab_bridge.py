"""_homelab_bridge — puente hacia los scripts ya existentes del homelab.

`get_secret`, `telegram_credentials`, `docker_critical`,
`docker_never_restart` y el bootstrap de `HOMELAB_SCRIPTS_DIR` viven en
`_homelab_bridge_common.py` (compartido con `diagnostico` y
`remediacion` — research.md §1 de
specs/024-consolidar-bridge-homelab/); `record_heartbeat` vive en
`_homelab_bridge_heartbeat.py` (compartido solo con `diagnostico`,
nunca `remediacion` — ese paquete no importa `heartbeat.py` hoy y no
debe empezar a hacerlo como efecto colateral de este refactor).

`read_heartbeat()` y `available()` son exclusivas de este paquete pero
usan el handle `_heartbeat` importado de `_homelab_bridge_heartbeat`,
no uno propio — evita triplicar el mismo `try/import heartbeat`.

Las funciones de `ha_monitor` (feature 004) siguen aquí, exclusivas de
este paquete — `diagnostico/_homelab_bridge.py` tiene su propio import
de `ha_monitor`, idéntico pero deliberadamente no consolidado
(research.md §1 de 024: sin ninguna función compartida que envolver).

Contrato: si los scripts no están disponibles (repo público clonado
fuera del homelab, por ejemplo), las funciones devuelven un resultado
inocuo en vez de lanzar excepción — mismo principio "a prueba de
fallos" que el resto del homelab.
"""

from __future__ import annotations

import json
from pathlib import Path

from _homelab_bridge_common import (
    _homelab_secrets,
    docker_critical,
    docker_never_restart,
    get_secret,
    telegram_credentials,
)
from _homelab_bridge_heartbeat import _heartbeat, record_heartbeat

try:
    import ha_monitor as _ha_monitor  # type: ignore[import-not-found]
except ImportError:
    _ha_monitor = None


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


def ha_monitor_conditional_entities() -> set[str]:
    """Entidades de HA cuyo check en `ha_monitor.py` solo aplica si un
    contenedor está corriendo (campo `requires_container`) — feature 004.
    Vacío si `ha_monitor.py` no está disponible o todavía no tiene esas
    entradas (antes de desplegar la historia de Frigate); nunca lanza."""
    if _ha_monitor is None:
        return set()
    try:
        return {
            c["entity"] for c in getattr(_ha_monitor, "CHECKS", [])
            if c.get("requires_container")
        }
    except Exception:
        return set()


def ha_monitor_check_result(entity_id: str) -> dict | None:
    """Último resultado real (`{ok, down_since, label, motivo, detail}`)
    del check de `ha_monitor.py` para `entity_id`, leído de
    `ha_monitor_state.json` — feature 004. `None` si la entidad no está
    en `CHECKS`, si el módulo no está disponible, o si no hay dato
    todavía; nunca lanza."""
    if _ha_monitor is None:
        return None
    try:
        check_id = next(
            (c["id"] for c in getattr(_ha_monitor, "CHECKS", [])
             if c.get("entity") == entity_id),
            None,
        )
        if check_id is None:
            return None
        state_file = getattr(_ha_monitor, "STATE_FILE", None)
        if state_file is None:
            return None
        state = json.loads(Path(state_file).read_text())
        return state.get(check_id)
    except Exception:
        return None


def available() -> bool:
    """True si los dos módulos del homelab se pudieron importar."""
    return _homelab_secrets is not None and _heartbeat is not None


def read_heartbeat(job: str) -> dict | None:
    """Último latido de `job`, o `None` si nunca ha latido o el módulo no
    está disponible. Usado para comprobar si un monitor sigue vivo de
    verdad, no solo si existe el script (p. ej. `telegram_monitor.py`)."""
    if _heartbeat is None:
        return None
    try:
        return _heartbeat.read(job)
    except Exception:
        return None
