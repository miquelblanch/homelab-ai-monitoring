"""evaluate — Las tres preguntas por componente (FR-007 a FR-010), la
caducidad a 90 días de una declaración (FR-007, Clarification 3), y qué
componentes están intencionadamente no vigilados (FR-012).

Las reglas de "¿está vigilado?" y "¿llega al dashboard?" están basadas en
hechos verificados durante `/speckit-plan`/`/speckit-analyze` de este
feature (research.md, contracts/entrega.md): el dashboard
(`docker/homelab-dashboard/scripts/app.py`) hoy solo tiene panel de
sistema, discos, contenedores en vivo, crons, LaunchAgents y relays
socat — nada de Home Assistant, nada de backups, nada del propio canal de
Telegram. Ese "no llega" no es un valor por defecto pesimista: es lo que
se comprobó leyendo el código real.

No hay ningún identificador de entidad de Home Assistant escrito aquí:
qué entidades comprueba `ha_monitor.py` se lee en vivo de
`ha_monitor.CHECKS` vía `_homelab_bridge` — nunca copiado a este repo
público (política de saneado, `CLAUDE.md` del proyecto).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import _homelab_bridge as bridge
from .model import DECLARACION_CADUCA_DIAS
from .sources import RawComponente


@dataclass
class EvaluacionParcial:
    tiene_estado_declarado: bool
    estado_declarado_status: str  # vigente | caducada | ausente
    esta_vigilado: bool
    mecanismo_vigilancia: str | None
    llega_a_dashboard: str  # si | no | sin_evidencia
    es_intencionado: bool


# Reglas fijas por nombre de pieza de infraestructura de monitorización
# (FR-004) — todas documentadas ya en CLAUDE.md, ninguna es un dato
# sensible.
_INFRA_MONITORIZACION_VIGILANCIA: dict[str, str | None] = {
    "docker_monitor.py": "amsterdam9.health (indirecto, vía LaunchAgent)",
    "ha_monitor.py": "amsterdam9.health (indirecto, vía LaunchAgent)",
    "verify_backups.py": "amsterdam9.health (indirecto, vía LaunchAgent)",
    "dns_pi_monitor.py": "amsterdam9.health (indirecto, vía LaunchAgent)",
    "heartbeat.py": "usado transitivamente por todos los monitores",
    "amsterdam9.health": None,  # nadie vigila al vigilante — hallazgo real
    "Beszel (hub)": None,  # Caso 3 de BRIEFING.md, sin resolver todavía
}


def is_declaration_stale(last_reviewed_at: date | None, today: date | None = None) -> bool:
    """FR-007, Clarification 3: caduca a los 90 días desde la última
    revisión confirmada. `None` (nunca revisada explícitamente) no cuenta
    como caducada aquí — la ausencia de fecha se resuelve como "vigente"
    en `evaluate_component` la primera vez que se ve un componente."""
    if last_reviewed_at is None:
        return False
    hoy = today or date.today()
    return (hoy - last_reviewed_at).days > DECLARACION_CADUCA_DIAS


def is_intentional(raw: RawComponente) -> bool:
    """FR-012: intencionadamente no vigilado — no es una brecha."""
    c = raw.componente
    if c.categoria == "contenedor":
        return c.nombre_actual in bridge.docker_never_restart()
    if c.categoria == "entidad_ha":
        return raw.meta.get("disabled_by") is not None
    return False


def _vigilancia_integracion(raw: RawComponente) -> tuple[bool, bool, str | None, str]:
    """Devuelve (tiene_estado_declarado, esta_vigilado, mecanismo, llega_a_dashboard)."""
    nombre = raw.componente.nombre_actual
    if nombre.startswith("Relay: "):
        return True, True, "dump_socat_status.py", "si"
    if nombre.startswith("Recordatorios de Nextcloud"):
        return False, False, None, "no"
    if nombre.startswith("Backup diario"):
        vigilado = bool(raw.meta.get("heartbeat_existe"))
        return True, vigilado, ("verify_backups.py" if vigilado else None), "no"
    if nombre.startswith("cron: "):
        return True, True, "heartbeat.py (manifest)", "si"
    # Resto: LaunchAgents amsterdam9.* — labels de launchd.
    return True, True, "amsterdam9.health", "si"


def _vigilancia_entidad_ha(raw: RawComponente) -> tuple[bool, bool, str | None]:
    checked = raw.componente.nombre_actual in bridge.ha_monitor_checked_entities()
    return checked, checked, ("ha_monitor.py" if checked else None)


def evaluate_component(
    raw: RawComponente, last_reviewed_at: date | None = None
) -> EvaluacionParcial:
    """Responde las tres preguntas para un componente recién descubierto
    por `sources.py`. Nunca deja un campo sin valor (FR-010) — cuando no
    hay evidencia suficiente, el valor explícito es "sin_evidencia", no
    un campo vacío."""
    c = raw.componente
    es_intencionado = is_intentional(raw)

    if c.categoria == "contenedor":
        declarado, vigilado, mecanismo, llega = True, True, "docker_monitor.py", "si"
    elif c.categoria == "integracion":
        declarado, vigilado, mecanismo, llega = _vigilancia_integracion(raw)
    elif c.categoria == "entidad_ha":
        declarado, vigilado, mecanismo = _vigilancia_entidad_ha(raw)
        llega = "no"  # comprobado: el dashboard no tiene panel de HA
    elif c.categoria == "host_externo":
        declarado, vigilado, mecanismo, llega = True, True, "Beszel (vía relay socat)", "no"
    elif c.categoria == "hermes":
        vigilado = bool(raw.meta.get("launchagent_cargado"))
        declarado, mecanismo, llega = (
            True,
            "amsterdam9.bautista.heartbeat" if vigilado else None,
            "no",
        )
    elif c.categoria == "telegram":
        declarado, vigilado, mecanismo, llega = False, False, None, "no"
    elif c.categoria == "infra_monitorizacion":
        mecanismo = _INFRA_MONITORIZACION_VIGILANCIA.get(c.nombre_actual)
        declarado, vigilado, llega = True, mecanismo is not None, "no"
    else:  # pragma: no cover - las categorías están cerradas en model.py
        declarado, vigilado, mecanismo, llega = False, False, None, "sin_evidencia"

    if not declarado:
        status = "ausente"
    elif is_declaration_stale(last_reviewed_at):
        status = "caducada"
    else:
        status = "vigente"

    return EvaluacionParcial(
        tiene_estado_declarado=declarado,
        estado_declarado_status=status,
        esta_vigilado=vigilado,
        mecanismo_vigilancia=mecanismo,
        llega_a_dashboard=llega,
        es_intencionado=es_intencionado,
    )


def classify_gap(ev: EvaluacionParcial, categoria: str) -> str:
    """Tipo de brecha — FR-011, data-model.md `brechas.tipo`. Solo se
    llama para hallazgos donde `es_brecha(ev)` ya dio True."""
    if categoria == "telegram":
        # Riesgo concentrado, no una brecha más — Edge Case de FR-006.
        return "riesgo_concentrado_telegram"
    if ev.estado_declarado_status == "ausente":
        return "sin_declaracion"
    if ev.estado_declarado_status == "caducada":
        return "declaracion_caducada"
    if not ev.esta_vigilado:
        return "sin_vigilancia"
    return "no_llega_a_dashboard"


def gap_context(ev: EvaluacionParcial, nombre: str, categoria: str, tipo: str) -> str:
    """Contexto explicativo suficiente para decidir sin reinvestigar
    (FR-011, SC-003)."""
    if tipo == "riesgo_concentrado_telegram":
        return (
            "Canal de entrega de Telegram sin vigilancia propia — si falla "
            "en silencio, invalida la entrega de casi todas las demás "
            "alertas del sistema, no solo las de este inventario."
        )
    if tipo == "sin_declaracion":
        return f"'{nombre}' ({categoria}) no tiene un estado esperado declarado."
    if tipo == "declaracion_caducada":
        return (
            f"'{nombre}' ({categoria}) tiene una declaración de estado "
            "esperado, pero no se ha revisado en más de 90 días."
        )
    if tipo == "sin_vigilancia":
        return f"'{nombre}' ({categoria}) no está vigilado por ningún mecanismo conocido."
    if tipo == "no_llega_a_dashboard":
        mecanismo = ev.mecanismo_vigilancia or "un mecanismo"
        return (
            f"'{nombre}' ({categoria}) está vigilado por {mecanismo}, pero un "
            "fallo real no llegaría al dashboard del homelab."
        )
    return f"'{nombre}' ({categoria}): brecha de cobertura sin clasificar."


def es_brecha(ev: EvaluacionParcial) -> bool:
    """Un componente intencionadamente no vigilado nunca es brecha
    (FR-012), aunque sus respuestas individuales no serían satisfactorias
    por sí solas."""
    if ev.es_intencionado:
        return False
    return (
        ev.estado_declarado_status != "vigente"
        or not ev.esta_vigilado
        or ev.llega_a_dashboard != "si"
    )
