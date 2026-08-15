"""_homelab_bridge_heartbeat — el latido (`heartbeat.py`) compartido
entre `diagnostico` e `inventory` — nunca `remediacion`, que no lo
usa hoy. Separado de `_homelab_bridge_common.py` a propósito: si
viviera ahí, `remediacion` arrastraría un `import heartbeat` nuevo con
solo importar lo que sí necesita de ese módulo (en Python, importar un
nombre de un módulo ejecuta el módulo entero) — ver
specs/024-consolidar-bridge-homelab/research.md §1.

Mismo contrato "a prueba de fallos" que el resto: nunca lanza.
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
    import heartbeat as _heartbeat  # type: ignore[import-not-found]
except ImportError:
    _heartbeat = None


def record_heartbeat(job: str, status: str = "ok", detail: str = "") -> bool | None:
    if _heartbeat is None:
        return None
    try:
        return _heartbeat.write(job, status=status, detail=detail)
    except Exception:
        return None
