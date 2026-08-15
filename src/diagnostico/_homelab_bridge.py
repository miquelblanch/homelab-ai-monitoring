"""_homelab_bridge — puente hacia los scripts ya existentes del homelab.

`get_secret`, `docker_critical`, `docker_never_restart` y el bootstrap
de `HOMELAB_SCRIPTS_DIR` viven en `_homelab_bridge_common.py`
(compartido con `inventory` y `remediacion` — research.md §1 de
specs/024-consolidar-bridge-homelab/); `record_heartbeat` vive en
`_homelab_bridge_heartbeat.py` (compartido solo con `inventory`, nunca
`remediacion`).

Las funciones de `ha_monitor` (desde feature 010,
specs/010-diagnostico-ha/) siguen aquí, exclusivas de este paquete —
`inventory/_homelab_bridge.py` tiene su propio import de `ha_monitor`,
idéntico pero deliberadamente no consolidado (research.md §1: sin
ninguna función compartida que envolver, solo duplicaría el handle por
cuatro líneas).

**Dependencia real hacia `inventory`** (no a través de este bridge):
desde feature 013 (specs/013-diagnostico-inventario/),
`diagnostico/evidencia/inventario.py` importa `inventory.diff`,
`inventory.store` e `inventory.model.TIPOS_BRECHA` directamente. Este
paquete y `inventory` **no son independientes** pese a lo que este
docstring afirmaba hasta specs/024-consolidar-bridge-homelab/
(research.md §4) — la relación es de solo lectura, nunca al revés
(`inventory` no importa de `diagnostico`), y sigue el mismo patrón ya
autorizado para `remediacion` → `diagnostico`
(specs/021-remediacion-contenedores/research.md §2).

Mismo contrato que siempre: si los scripts no están disponibles (repo
público clonado fuera del homelab), las funciones devuelven un
resultado inocuo en vez de lanzar excepción.
"""

from __future__ import annotations

from _homelab_bridge_common import (
    docker_critical,
    docker_never_restart,
    get_secret,
)
from _homelab_bridge_heartbeat import record_heartbeat

try:
    import ha_monitor as _ha_monitor  # type: ignore[import-not-found]
except ImportError:
    _ha_monitor = None


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
