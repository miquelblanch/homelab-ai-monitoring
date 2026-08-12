"""_homelab_bridge — puente hacia los scripts ya existentes del homelab.

Copia mínima deliberada de `inventory/_homelab_bridge.py` (research.md
§7): `diagnostico` e `inventory` son dos paquetes hermanos
independientes bajo `src/`, sin que ninguno dependa del otro. Solo lleva
lo que este feature necesita.

Desde feature 010 (specs/010-diagnostico-ha/) sí incluye las funciones
de `ha_monitor` — mismo patrón que `inventory/_homelab_bridge.py` ya
usa para ese módulo (research.md §3 de 010), añadido aquí porque hasta
ahora ningún feature de `diagnostico` tocaba HA.

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

try:
    import ha_monitor as _ha_monitor  # type: ignore[import-not-found]
except ImportError:
    _ha_monitor = None


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


# ── Home Assistant (feature 010: specs/010-diagnostico-ha/) ────────────────


def ha_checks() -> list[dict]:
    """`ha_monitor.CHECKS` tal cual, nunca copiado a este repo público
    (research.md §3 de 010) — `[]` si `ha_monitor.py` no está
    disponible."""
    if _ha_monitor is None:
        return []
    try:
        return list(getattr(_ha_monitor, "CHECKS", []))
    except Exception:
        return []


def ha_history(entity_id: str, inicio_iso: str, fin_iso: str) -> list[dict] | None:
    """Historial de cambios de estado de `entity_id` en `[inicio_iso,
    fin_iso]`, vía `ha_monitor.ha_get_detallado()` (research.md §4 —
    reutiliza credenciales, timeout y distinción de errores ya resueltos
    por ese módulo, sin reimplementar la llamada HTTP). `None` si
    `ha_monitor.py` no está disponible o la llamada falla."""
    if _ha_monitor is None:
        return None
    try:
        datos, _motivo = _ha_monitor.ha_get_detallado(
            f"/api/history/period/{inicio_iso}"
            f"?filter_entity_id={entity_id}&end_time={fin_iso}"
        )
        if datos is None:
            return None
        return datos[0] if datos else []
    except Exception:
        return None


def ha_check_status(check: dict) -> dict | None:
    """Resultado ya calculado de `ha_monitor.check_status(check)` — el
    mismo veredicto (ok/fallo, detalle, motivo) que ese módulo ya
    computa cada 15 minutos para el informe real (research.md §10 de
    010, hallazgo real de validación en vivo, 2026-08-12). Sin esto, el
    modelo tiene que reconstruir por su cuenta si el check está
    fallando ahora mismo a partir de logs ruidosos compartidos por 111
    checks, o de aritmética de fechas — y a veces lo hace mal o se
    pierde razonando. `None` si `ha_monitor.py` no está disponible o la
    llamada falla; nunca lanza."""
    if _ha_monitor is None:
        return None
    try:
        ok, detalle, motivo = _ha_monitor.check_status(check)
        return {"ok": ok, "detalle": detalle, "motivo": motivo}
    except Exception:
        return None


def ha_recorder_corrupt_files(contenedor: str, ruta: str) -> list[str]:
    """Ficheros `*.corrupt.*` presentes ahora mismo en `ruta` dentro de
    `contenedor`, vía `ha_monitor._recorder_corrupt_files()` (función
    privada, reutilizada igual que `ha_monitor_check_result()` ya lee el
    `STATE_FILE` "privado" de ese mismo módulo, research.md §4 de 010).
    `[]` si `ha_monitor.py` no está disponible."""
    if _ha_monitor is None:
        return []
    try:
        return _ha_monitor._recorder_corrupt_files(contenedor, ruta)
    except Exception:
        return []
