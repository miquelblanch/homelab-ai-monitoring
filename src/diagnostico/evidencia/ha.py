"""ha — Evidencia del origen Home Assistant (feature 010:
specs/010-diagnostico-ha/). Un check de entidad, de recorder corrupto,
o de disponibilidad de la API, en vivo o de un momento pasado
concreto. Ver research.md §4/§5/§6/§7 de 010.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from .. import _homelab_bridge as bridge
from ..model import Episodio
from ..store import insert_episodio
from ._compartido import docker_logs_tail

VENTANA_HA_ENTIDAD_HORAS = 12  # research.md §6 de 010 — más ancha que
# VENTANA_METRICAS_MINUTOS porque las entidades de HA solo registran un
# cambio de estado cuando ocurre, no se muestrean cada 5 minutos.

HA_HISTORIAL_MAX_ENTRADAS = 50  # research.md §6 de 010 (revisado tras
# hallazgo real de validación en vivo, 2026-08-12): sin este límite, una
# entidad de alta frecuencia (p. ej. `sal_nivel`, un sensor de voltaje
# que reporta cada pocos segundos, no un par de veces al día como una
# batería Zigbee) puede devolver miles de cambios de estado en la
# ventana — un caso real (1.962 entradas) llegó a 280.454 tokens de
# entrada sin producir ningún diagnóstico (finish_reason="length").
# Se quedan las entradas más recientes, no las más antiguas.

CHECKS_HA_EXCLUIDOS_CERRADURA = {
    "cerradura_up", "bateria_cerradura", "bateria_critica_cerradura",
}  # FR-010, research.md §7 de 010 — bloqueo explícito, no evidencia vacía.

_HA_API_CONTENEDOR = "homeassistant"  # research.md §5 de 010 — el check
# `ha_api` (tipo api_ping) no tiene entidad ni campo "contenedor" propio
# en ha_monitor.CHECKS (Clarifications 2026-08-12, spec.md FR-003).

_TIPOS_CHECK_HA_ENTIDAD = (
    "entity_state", "entity_available", "entity_value_below", "entity_age_below",
)


def ha_check_by_id(check_id: str) -> dict | None:
    """El dict de `check_id` en `ha_monitor.CHECKS`, o `None` si no
    existe o `ha_monitor.py` no está disponible — no es un error
    (spec.md Edge Cases): un `check_id` inexistente congela igual, con
    toda la evidencia de HA en `null` (research.md §3 de 010)."""
    return next((c for c in bridge.ha_checks() if c.get("id") == check_id), None)


def _simplificar_historial(historial: list[dict]) -> list[dict]:
    """Reduce cada entrada a `state`/`last_changed` y recorta a
    `HA_HISTORIAL_MAX_ENTRADAS`, quedándose con las más recientes
    (research.md §6 de 010). `entity_id` ya es redundante con
    `ha_check.entity`, y `attributes` repite en cada entrada metadata
    que no cambia (unidad, device_class, nombre) sin aportar señal
    diagnóstica nueva — quitarlo reduce el tamaño incluso en el caso
    normal, no solo en el caso extremo que motivó el límite de
    entradas."""
    recortado = historial[-HA_HISTORIAL_MAX_ENTRADAS:]
    return [{"state": e.get("state"), "last_changed": e.get("last_changed")} for e in recortado]


def ha_history_window(entity: str, inicio: datetime, fin: datetime) -> list[dict] | None:
    """Historial de `entity` en `[inicio, fin]`, vía la API REST de HA
    (research.md §4 de 010), acotado y simplificado por
    `_simplificar_historial()`. `None` si la API no respondió — distinto
    de `[]` (respondió, sin cambios en la ventana), mismo criterio que
    el resto del snapshot ya usa para "sin dato" vs. "dato vacío"."""
    historial = bridge.ha_history(entity, inicio.isoformat(), fin.isoformat())
    if historial is None:
        return None
    return _simplificar_historial(historial)


def _validar_check_ha(check_id: str) -> dict | None:
    """Bloquea los 3 checks de la cerradura (FR-010) antes de intentar
    resolver nada — un `ValueError`, no una evidencia vacía, porque es
    un rechazo explícito de alcance, no una ausencia de datos
    (research.md §7 de 010). Para cualquier otro `check_id`, delega en
    `ha_check_by_id()` (puede devolver `None`, y no es un error)."""
    if check_id in CHECKS_HA_EXCLUIDOS_CERRADURA:
        raise ValueError(
            f"check {check_id!r} de la cerradura queda fuera del alcance de "
            "este feature (spec.md FR-010) — su causa ya se investigó a mano"
        )
    return ha_check_by_id(check_id)


def _resolver_evidencia_ha(
    check: dict | None, inicio: datetime, fin: datetime
) -> tuple[list[dict] | None, list[str] | None, str | None]:
    """Evidencia según el tipo de check ya resuelto (o `None` si no se
    reconoce) — research.md §4 de 010. Devuelve
    `(ha_history, ha_recorder_corrupt_files, docker_logs_tail)`, cada
    uno `None` salvo el que corresponda al tipo."""
    if check is None:
        return None, None, None

    tipo = check.get("type")
    if tipo in _TIPOS_CHECK_HA_ENTIDAD:
        return ha_history_window(check["entity"], inicio, fin), None, None
    if tipo == "recorder_corrupto":
        corrupt_files = bridge.ha_recorder_corrupt_files(check["contenedor"], check["ruta"])
        return None, corrupt_files, docker_logs_tail(check["contenedor"])
    if tipo == "api_ping":
        return None, None, docker_logs_tail(_HA_API_CONTENEDOR)
    return None, None, None


def congelar_ha_vivo(conn: sqlite3.Connection, check_id: str) -> Episodio:
    """Congela el estado actual de un check de HA en vivo. `es_critico`
    siempre `False` (research.md §8 de 010) — no existe concepto de
    "check de HA crítico" (spec.md Assumptions)."""
    ahora = datetime.now()
    check = _validar_check_ha(check_id)
    inicio = ahora - timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    historial, corrupt_files, logs = _resolver_evidencia_ha(check, inicio, ahora)
    estado = bridge.ha_check_status(check) if check is not None else None

    snapshot = {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": logs,
        "ha_check": check,
        "ha_check_status": estado,
        "ha_history": historial,
        "ha_recorder_corrupt_files": corrupt_files,
    }

    episodio = Episodio(
        componente=check_id,
        origen="ha",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_ha_historico(conn: sqlite3.Connection, check_id: str, momento: datetime) -> Episodio:
    """Congela un momento pasado concreto de un check de HA. Para
    checks de entidad, ventana ±`VENTANA_HA_ENTIDAD_HORAS` alrededor de
    `momento` sobre el historial real de HA — estable entre llamadas
    repetidas (base de SC-001). Para `recorder_corrupto`/`api_ping`, no
    existe ninguna fuente de evidencia verdaderamente histórica — se
    congela el mismo estado *actual* que usaría `congelar_ha_vivo`, bajo
    la ventana etiquetada con `momento` — limitación aceptada, no un bug
    (research.md §6 de 010; spec.md Assumptions). `momento` se
    interpreta como hora local sin marca de zona, mismo criterio que
    `disk_metrics.timestamp` (research.md §9 de 010)."""
    check = _validar_check_ha(check_id)
    inicio = momento - timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    fin = momento + timedelta(hours=VENTANA_HA_ENTIDAD_HORAS)
    historial, corrupt_files, logs = _resolver_evidencia_ha(check, inicio, fin)
    estado = bridge.ha_check_status(check) if check is not None else None

    snapshot = {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": logs,
        "ha_check": check,
        "ha_check_status": estado,
        "ha_history": historial,
        "ha_recorder_corrupt_files": corrupt_files,
    }

    episodio = Episodio(
        componente=check_id,
        origen="ha",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
