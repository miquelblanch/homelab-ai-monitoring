"""_homelab_bridge — puente mínimo hacia `homelab_secrets.py`, que vive
fuera de este repositorio en la infraestructura privada del homelab
(`/Volumes/FastData/homelab/scripts/`). Mismo patrón que
`inventory._homelab_bridge` (research.md §6 de specs/001-...) — copiado
en vez de importado desde `inventory` porque `remediacion` es un
paquete independiente (research.md §2 de specs/019-.../) que no
importa nada de los otros dos.

Contrato: si el script no está disponible (repo público clonado fuera
del homelab, por ejemplo), `telegram_credentials()` devuelve un
resultado inocuo (cadenas vacías) en vez de lanzar excepción — research.md §11.
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


def telegram_credentials() -> tuple[str, str]:
    """(token, chat_id) — cadenas vacías si no se pudo resolver."""
    if _homelab_secrets is None:
        return "", ""
    try:
        return _homelab_secrets.telegram()
    except Exception:
        return "", ""
