"""_homelab_bridge — puente hacia `homelab_secrets.py` y
`docker_monitor.py`, que viven fuera de este repositorio en la
infraestructura privada del homelab
(`/Volumes/FastData/homelab/scripts/`).

`telegram_credentials` y `docker_never_restart` se reexportan tal cual
de `_homelab_bridge_common.py` (compartido con `diagnostico` e
`inventory` — research.md §1 de
specs/024-consolidar-bridge-homelab/). `docker_critical` NO se
reexporta tal cual: es una función local que envuelve la base
compartida y añade el hook de prueba exclusivo de este paquete
(`REMEDIACION_TEST_FORZAR_CRITICO`) — ese hook nunca debe quedar
alcanzable desde `diagnostico` ni `inventory` (research.md §3).

Este paquete deliberadamente **no** importa `heartbeat.py` ni
`ha_monitor.py` — no los necesita, y no debe empezar a hacerlo como
efecto colateral de este refactor (research.md §1: en Python, tomar un
nombre de un módulo ejecuta el módulo entero, así que el módulo
compartido que usa `remediacion` para lo que sí necesita no puede ser
el mismo que también intenta `import heartbeat`).

Desde specs/021-remediacion-contenedores/ (research.md §4), este bridge
también expone las funciones ya probadas de `docker_monitor.py` para el
reinicio de contenedores — nunca se reimplementan aquí.

Contrato: si el script no está disponible (repo público clonado fuera
del homelab, por ejemplo), las funciones de este módulo devuelven un
resultado inocuo (cadenas vacías, conjuntos vacíos, listas vacías,
`False`) en vez de lanzar excepción — research.md §11 de 019.
"""

from __future__ import annotations

import os
from pathlib import Path

from _homelab_bridge_common import (
    docker_critical as _docker_critical_base,
    docker_never_restart,
    telegram_credentials,
)

try:
    import docker_monitor as _docker_monitor  # type: ignore[import-not-found]
except ImportError:
    _docker_monitor = None


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────


def docker_critical() -> set[str]:
    """El conjunto real de `docker_monitor.CRITICAL` (base compartida,
    `_homelab_bridge_common.docker_critical()`), más los nombres de
    `REMEDIACION_TEST_FORZAR_CRITICO` (lista separada por comas) si esa
    variable está en el entorno — hook de pruebas exclusivo
    (specs/022-clasificacion-remediacion/, research.md §1b): permite
    validar el camino de contenedores críticos con uno de prueba
    desechable, sin tocar la lista real ni arriesgar uno de los 12
    reales. Nunca activo en producción. Función LOCAL a propósito, no
    una reexportación — es la única forma de que este hook exista solo
    aquí (specs/024-consolidar-bridge-homelab/research.md §3)."""
    criticos = _docker_critical_base()
    forzados = os.environ.get("REMEDIACION_TEST_FORZAR_CRITICO", "")
    if forzados:
        criticos |= {nombre.strip() for nombre in forzados.split(",") if nombre.strip()}
    return criticos


def listar_contenedores() -> list[dict]:
    """Todos los contenedores conocidos por `docker_monitor.py`, con su
    `status`/`health` reales — misma fuente de verdad que ya usa
    (`docker ps`), para no reimplementarla por separado (research.md
    §4). Lista vacía si el bridge no está disponible."""
    if _docker_monitor is None:
        return []
    try:
        return list(_docker_monitor.get_containers())
    except Exception:
        return []


def restart_container(name: str, reason: str = "") -> bool:
    """Bridge hacia `docker_monitor.restart_container()` — reutiliza la
    verificación real post-reinicio ya corregida (FR-010, research.md
    §4). `REMEDIACION_TEST_FORZAR_FALLO` en el entorno fuerza `False`
    sin tocar Docker — hook de pruebas para el cortacircuito
    (quickstart.md Escenario 5 de 021), nunca activo en producción."""
    if os.environ.get("REMEDIACION_TEST_FORZAR_FALLO"):
        return False
    if _docker_monitor is None:
        return False
    try:
        return bool(_docker_monitor.restart_container(name, reason))
    except Exception:
        return False


def breaker_decision(attempts: int, max_attempts: int = 3) -> tuple[bool, str]:
    """Bridge hacia `docker_monitor.breaker_decision()` — función pura,
    sin efectos secundarios (research.md §4)."""
    if _docker_monitor is None:
        return True, "docker_monitor no disponible — sin cortacircuito"
    try:
        return _docker_monitor.breaker_decision(attempts, max_attempts)
    except Exception:
        return True, "fallo al evaluar el cortacircuito — se permite el intento"


def recent_restart_attempts(conn_remediacion, contenedor: str, window_hours: int = 6) -> int:
    """Cuenta, en `intentos_reinicio` (nunca en `restart_history`,
    research.md §5), los intentos en estado "ejecutado" o "fallido" de
    `contenedor` dentro de las últimas `window_hours` horas — alimenta
    `breaker_decision()`."""
    from datetime import datetime, timedelta, timezone

    from . import store

    desde = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    intentos = store.intentos_recientes_contenedor(conn_remediacion, contenedor, desde)
    return sum(1 for i in intentos if i.estado in ("ejecutado", "fallido"))


# ── Pestaña Correcciones del dashboard (homelab-dashboard, 2026-08-14) ──
#
# Puente hacia el mecanismo ya existente del dashboard privado
# (`homelab-dashboard/scripts/app.py`, comentario "Pestaña Correcciones"):
# la clasificación de una alarma resuelta (manual/automática/IA) nunca se
# infiere, se declara — escribiendo una entrada en
# ALARM_MANUAL_CORRECTIONS_FILE antes de que la alarma desaparezca. Este
# paquete declara "ia" cuando ejecuta un reinicio que DeepSeek decidió —
# apruebe quien apruebe la propuesta en modo manual, la decisión fue de
# DeepSeek, no de quien pulsó aprobar. Se declara solo tras confirmar el
# reinicio (nunca antes): si el reinicio falla, no hay nada que declarar
# todavía, y una declaración "ia" que nadie llega a consumir podría
# atribuirle a la IA una corrección posterior que en realidad hizo otra
# cosa (research.md no cubre esto — hallazgo real de esta sesión).

_DEFAULT_ALARM_CORRECTIONS_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/alarm_manual_corrections.json"
)


def _alarm_corrections_path() -> Path:
    return Path(os.environ.get("REMEDIACION_ALARM_CORRECTIONS_PATH", _DEFAULT_ALARM_CORRECTIONS_PATH))


def declarar_correccion_ia(origen: str, tipo: str, componente: str, nota: str) -> bool:
    """Añade una declaración "ia" para que el dashboard clasifique así la
    próxima vez que la alarma (origen, tipo, componente) desaparezca —
    nunca lanza, `False` si no se pudo escribir (mismo principio "a
    prueba de fallos" que el resto de este módulo)."""
    import json

    ruta = _alarm_corrections_path()
    try:
        pendientes = json.loads(ruta.read_text()) if ruta.exists() else []
        pendientes.append({
            "origen": origen, "tipo": tipo, "componente": componente,
            "clasificacion": "ia", "nota": nota,
        })
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(pendientes, ensure_ascii=False))
        return True
    except Exception:
        return False
