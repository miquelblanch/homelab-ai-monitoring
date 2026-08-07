"""sources — Adaptadores de lectura, uno por familia de componente
(FR-001 a FR-006). Todos son de solo lectura: ninguno modifica nada del
homelab (FR-016) — `_run_ro()` solo permite subcomandos de una lista
blanca (ver T040, tests/selftest/test_no_mutation.py).

Cada adaptador devuelve `list[RawComponente]`: un `Componente` (model.py)
más un diccionario `meta` de contexto propio de la fuente, que usa
`evaluate.py` para responder las tres preguntas — el `meta` no se
persiste tal cual, es efímero de una sola ejecución.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .model import Componente

# ── Rutas reales del homelab (ver research.md) ──────────────────────────────

HA_ENTITY_REGISTRY = Path(
    os.environ.get(
        "HA_ENTITY_REGISTRY",
        "/Volumes/FastData/docker/homeassistant/.storage/core.entity_registry",
    )
)
SOCAT_RELAYS_JSON = Path(
    os.environ.get(
        "SOCAT_RELAYS_JSON",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json",
    )
)
BACKUP_HEARTBEAT = Path(
    os.environ.get("BACKUP_HEARTBEAT", "/Volumes/Storage/backup/.backup-heartbeat")
)
HERMES_CRON_JOBS = Path(
    os.environ.get(
        "HERMES_CRON_JOBS",
        str(Path.home() / ".hermes/profiles/bautista/cron/jobs.json"),
    )
)
HERMES_GATEWAY_LABEL = "ai.hermes.gateway-bautista"


@dataclass
class RawComponente:
    componente: Componente
    meta: dict = field(default_factory=dict)


# ── Subprocess de solo lectura, con lista blanca (FR-016, T040) ────────────

_READONLY_ALLOWLIST = {
    ("docker", "ps"),
    ("docker", "inspect"),
    ("launchctl", "list"),
}


def _run_ro(cmd: list[str], timeout: int = 15) -> str:
    """Ejecuta un subcomando de solo lectura. Nunca lanza excepción por
    fallos de entorno (docker caído, comando ausente...) — devuelve "".
    Si el comando no está en la lista blanca, es un error de programación
    (bug propio, no un fallo de entorno) y SÍ lanza — así T040 lo detecta
    en vez de dejar pasar en silencio un futuro `docker restart` por
    accidente."""
    key = (cmd[0], cmd[1] if len(cmd) > 1 else "")
    if key not in _READONLY_ALLOWLIST:
        raise RuntimeError(
            f"comando fuera de la lista blanca de solo lectura: {cmd!r} — FR-016"
        )
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ── FR-001: contenedores Docker ──────────────────────────────────────────


def docker_components() -> list[RawComponente]:
    out = _run_ro(["docker", "ps", "-a", "--format", "{{json .}}"])
    items: list[RawComponente] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        nombre = c.get("Names", "").lstrip("/")
        if not nombre:
            continue
        labels = _parse_labels(c.get("Labels", ""))
        compose_service = labels.get("com.docker.compose.service")
        # Estable entre recreaciones: el nombre de servicio compose si
        # existe, si no el propio nombre del contenedor — nunca el ID
        # interno de Docker, que cambia en cada recreación (research.md §3).
        identificador = compose_service or nombre
        items.append(
            RawComponente(
                componente=Componente(
                    categoria="contenedor",
                    nombre_actual=nombre,
                    identificador_estable=identificador,
                ),
                meta={"status": c.get("Status", ""), "state": c.get("State", "")},
            )
        )
    return items


def _parse_labels(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, _, v = pair.partition("=")
            result[k] = v
    return result


# ── FR-002: integraciones no-contenedor ─────────────────────────────────


def relay_components() -> list[RawComponente]:
    if not SOCAT_RELAYS_JSON.is_file():
        return []
    try:
        data = json.loads(SOCAT_RELAYS_JSON.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    items: list[RawComponente] = []
    for relay in data.get("relays", []):
        nombre = relay.get("name")
        if not nombre:
            continue
        items.append(
            RawComponente(
                componente=Componente(
                    categoria="integracion",
                    nombre_actual=f"Relay: {nombre}",
                ),
                meta={"ok": relay.get("ok"), "desc": relay.get("desc", "")},
            )
        )
    return items


def nextcloud_reminder_components() -> list[RawComponente]:
    # Granularidad de integración (no entidad por entidad, FR-002) — un
    # único componente. Caso 4 de BRIEFING.md: no se sabe todavía por qué
    # no llegan por Telegram; este inventario no lo diagnostica, solo
    # comprueba su cobertura.
    return [
        RawComponente(
            componente=Componente(
                categoria="integracion",
                nombre_actual="Recordatorios de Nextcloud (Tareas/Calendario)",
            ),
            meta={},
        )
    ]


def backup_components() -> list[RawComponente]:
    existe = BACKUP_HEARTBEAT.is_file()
    return [
        RawComponente(
            componente=Componente(
                categoria="integracion",
                nombre_actual="Backup diario (backup_diario_nvme.sh)",
            ),
            meta={"heartbeat_existe": existe},
        )
    ]


def launchagent_components() -> list[RawComponente]:
    items: list[RawComponente] = []
    out = _run_ro(["launchctl", "list"])
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        label = parts[2].strip()
        if not (
            label.startswith("amsterdam9.")
            or label == HERMES_GATEWAY_LABEL
            or label.startswith("com.homeassistant.")
        ):
            continue
        if label == HERMES_GATEWAY_LABEL:
            # El agente Hermes/Bautista es su propio componente (FR-006).
            continue
        items.append(
            RawComponente(
                componente=Componente(
                    categoria="integracion",
                    nombre_actual=label,
                    identificador_estable=label,  # las labels de launchd ya son estables
                ),
                meta={"pid": parts[0].strip(), "status": parts[1].strip()},
            )
        )

    if HERMES_CRON_JOBS.is_file():
        try:
            jobs = json.loads(HERMES_CRON_JOBS.read_text()).get("jobs", [])
        except (OSError, json.JSONDecodeError):
            jobs = []
        for job in jobs:
            nombre = job.get("name")
            if not nombre:
                continue
            items.append(
                RawComponente(
                    componente=Componente(
                        categoria="integracion",
                        nombre_actual=f"cron: {nombre}",
                        identificador_estable=job.get("id"),
                    ),
                    meta={"skill": job.get("skill")},
                )
            )
    return items


# ── FR-003: entidades de Home Assistant, cualquier dominio ──────────────


def ha_entity_components() -> list[RawComponente]:
    if not HA_ENTITY_REGISTRY.is_file():
        return []
    try:
        registry = json.loads(HA_ENTITY_REGISTRY.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    items: list[RawComponente] = []
    for entity in registry.get("data", {}).get("entities", []):
        entity_id = entity.get("entity_id")
        if not entity_id:
            continue
        items.append(
            RawComponente(
                componente=Componente(
                    categoria="entidad_ha",
                    nombre_actual=entity_id,
                    identificador_estable=entity.get("unique_id"),
                ),
                meta={
                    "platform": entity.get("platform"),
                    "disabled_by": entity.get("disabled_by"),
                    "entity_category": entity.get("entity_category"),
                },
            )
        )
    return items


# ── FR-004: la propia infraestructura de monitorización ─────────────────


def monitoring_infra_components() -> list[RawComponente]:
    # Los scripts/pipelines de monitorización en sí mismos — no lo que
    # vigilan (eso son los componentes de las otras familias).
    nombres = [
        "docker_monitor.py",
        "ha_monitor.py",
        "verify_backups.py",
        "dns_pi_monitor.py",
        "heartbeat.py",
        "amsterdam9.health",
        "Beszel (hub)",
    ]
    return [
        RawComponente(
            componente=Componente(
                categoria="infra_monitorizacion",
                nombre_actual=nombre,
            ),
            meta={},
        )
        for nombre in nombres
    ]


# ── FR-005: hosts físicos distintos del Mac Mini ─────────────────────────


def external_host_components() -> list[RawComponente]:
    # Identificados por el software que alojan, no por IP — spec.md
    # Assumptions, política de saneado del repo.
    nombres = [
        "Host de Uptime Kuma",
        "Host de AdGuard Home (DNS primario)",
    ]
    return [
        RawComponente(
            componente=Componente(categoria="host_externo", nombre_actual=nombre),
            meta={},
        )
        for nombre in nombres
    ]


# ── FR-006: Hermes/Bautista y el canal de Telegram, por separado ────────


def hermes_and_telegram_components() -> list[RawComponente]:
    out = _run_ro(["launchctl", "list"])
    hermes_activo = any(
        line.split("\t")[2].strip() == HERMES_GATEWAY_LABEL
        for line in out.splitlines()
        if line.count("\t") >= 2
    )
    return [
        RawComponente(
            componente=Componente(
                categoria="hermes",
                nombre_actual="Agente Hermes/Bautista",
                identificador_estable=HERMES_GATEWAY_LABEL,
            ),
            meta={"launchagent_cargado": hermes_activo},
        ),
        RawComponente(
            componente=Componente(
                categoria="telegram",
                nombre_actual="Canal de entrega de Telegram",
            ),
            meta={},
        ),
    ]


# ── Todas las familias juntas (User Story 1) ─────────────────────────────

ALL_ADAPTERS = (
    docker_components,
    relay_components,
    nextcloud_reminder_components,
    backup_components,
    launchagent_components,
    ha_entity_components,
    monitoring_infra_components,
    external_host_components,
    hermes_and_telegram_components,
)


def all_components() -> list[RawComponente]:
    items: list[RawComponente] = []
    for adapter in ALL_ADAPTERS:
        items.extend(adapter())
    return items
