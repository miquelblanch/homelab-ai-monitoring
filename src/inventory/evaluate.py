"""evaluate — Las tres preguntas por componente (FR-007 a FR-010), la
caducidad a 90 días de una declaración (FR-007, Clarification 3), y qué
componentes están intencionadamente no vigilados (FR-012).

Las reglas de "¿está vigilado?" y "¿llega al dashboard?" están basadas en
hechos verificados leyendo el código real del dashboard
(`docker/homelab-dashboard/scripts/app.py`), no en supuestos. Estado a
2026-08-08: panel de sistema, discos, contenedores en vivo, crons,
LaunchAgents, relays socat, velocidad (speedtest-tracker), un panel de
Home Assistant y un panel "Estado de los monitores" (latido real de
docker_monitor.py, ha_monitor.py, dns_pi_monitor.py, verify_backups.py,
telegram_monitor.py, heartbeat.py transitivo, backup diario y los dos
LaunchAgents de Hermes/Bautista). El panel de HA solo muestra las ~15
entidades que `ha_monitor.py` vigila una a una (mismo criterio que
"vigilado" para esa categoría), no las ~300 restantes del registro. Los
hosts externos (Kuma, AdGuard) tienen sitio desde feature 002
(2026-08-08): `beszel_hosts_monitor.py` lee el estado del hub de Beszel
vía el volumen `beszel_hub_data` y lo expone en un panel del dashboard.

No hay ningún identificador de entidad de Home Assistant escrito aquí:
qué entidades comprueba `ha_monitor.py` se lee en vivo de
`ha_monitor.CHECKS` vía `_homelab_bridge` — nunca copiado a este repo
público (política de saneado, `CLAUDE.md` del proyecto).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from time import time

from . import _homelab_bridge as bridge
from .model import DECLARACION_CADUCA_DIAS
from .sources import ENTIDAD_HA_EXCEPCIONES_SEGURIDAD, RawComponente, entidad_ha_frigate

# Un latido de telegram_monitor.py más viejo que esto cuenta como "no vigila
# de verdad" — corre cada 5 min, así que 15 min ya son tres pasadas perdidas.
_TELEGRAM_HEARTBEAT_MAX_AGE_S = 15 * 60


@dataclass
class EvaluacionParcial:
    tiene_estado_declarado: bool
    estado_declarado_status: str  # vigente | caducada | ausente
    esta_vigilado: bool
    mecanismo_vigilancia: str | None
    llega_a_dashboard: str  # si | no | sin_evidencia
    es_intencionado: bool


# Los cuatro monitores que ya llaman a heartbeat.write() (2026-08-08, mismo
# arreglo que telegram_monitor.py) — nombre del job y antigüedad máxima
# tolerable, calcada de heartbeat.py::DEFAULT_MANIFEST para no tener dos
# fuentes de verdad sobre "cada cuánto corre cada uno".
_INFRA_HEARTBEAT_JOBS: dict[str, tuple[str, int]] = {
    "docker_monitor.py": ("docker-monitor", 1800),      # cada 5 min
    "ha_monitor.py": ("ha-monitor", 3600),               # cada 15 min
    "dns_pi_monitor.py": ("dns-pi-monitor", 3600),        # cada 15 min
    "verify_backups.py": ("verify-backups", 108000),      # diario + margen
}

# Piezas de infraestructura de monitorización sin latido propio todavía —
# FR-004. "amsterdam9.health" ya no está: no existe como LaunchAgent real
# (ver sources.py::monitoring_infra_components). "Beszel (hub)" tampoco
# está aquí desde feature 003: se decide por `raw.meta["hub_sano"]`
# (sources.py::_beszel_hub_sano), no por un mecanismo fijo de latido.
_INFRA_MONITORIZACION_VIGILANCIA: dict[str, str | None] = {
    "heartbeat.py": "usado transitivamente por todos los monitores",
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
        if raw.meta.get("disabled_by") is not None:
            return True
        # feature 005: metadatos personales de la app móvil (localización,
        # batería, red, modo kiosco...) — no son señal de salud de nada,
        # cambian todo el rato. Sin lectura nueva: platform ya viaja en
        # meta desde feature 001.
        if raw.meta.get("platform") == "mobile_app":
            return True
        # feature 004: entidades de ajuste/diagnóstico no son señales de
        # salud — salvo las excepciones de seguridad (evaluadas como
        # brecha normal) y las de Frigate (vigiladas por su propia
        # lógica condicionada al contenedor, no por esta regla).
        if (
            raw.meta.get("entity_category") in ("config", "diagnostic")
            and c.nombre_actual not in ENTIDAD_HA_EXCEPCIONES_SEGURIDAD
            and c.nombre_actual not in entidad_ha_frigate()
        ):
            return True
        return False
    return False


def _vigilancia_integracion(raw: RawComponente) -> tuple[bool, bool, str | None, str]:
    """Devuelve (tiene_estado_declarado, esta_vigilado, mecanismo, llega_a_dashboard)."""
    nombre = raw.componente.nombre_actual
    if nombre.startswith("Relay: "):
        return True, True, "dump_socat_status.py", "si"
    if nombre.startswith("Recordatorios de Nextcloud"):
        # Desde feature 003 (2026-08-09), bautista-calendar.sh registra su
        # propio latido al final de cada ejecución (con o sin eventos) —
        # mismo patrón de comprobación que el resto de latidos de este
        # fichero, no una suposición.
        vigilado, mecanismo = _vigilancia_por_heartbeat(
            "bautista-calendar", "bautista-calendar.sh (latido propio)", 108000,
        )
        return True, vigilado, mecanismo, ("si" if vigilado else "no")
    if nombre.startswith("Backup diario"):
        vigilado = bool(raw.meta.get("heartbeat_existe"))
        # El dashboard tiene panel "Estado de los monitores" desde
        # 2026-08-08 con el latido de backup_diario_nvme.sh.
        return True, vigilado, ("verify_backups.py" if vigilado else None), "si"
    if nombre.startswith("cron: "):
        return True, True, "heartbeat.py (manifest)", "si"
    # Resto: LaunchAgents amsterdam9.* — labels de launchd. Cargado de
    # verdad (comprobado por sources.py vía launchctl), pero sin un latido
    # propio que confirme que además hace su trabajo — no hay un
    # "amsterdam9.health" real que lo vigile (ver monitoring_infra_components).
    return True, True, "launchctl (cargado)", "si"


def _vigilancia_entidad_ha(raw: RawComponente) -> tuple[bool, bool, str | None]:
    """`declarado` = ¿está en `ha_monitor.CHECKS`? `vigilado` = ¿el
    último resultado real de ese check tiene `ok=true`? — no basta con
    estar en la lista (feature 004, `research.md` §4: antes `vigilado`
    era pura membresía, igual que `declarado`, así que un check
    declarado pero fallando nunca se distinguía de uno sano)."""
    entity_id = raw.componente.nombre_actual
    if entity_id not in bridge.ha_monitor_checked_entities():
        return False, False, None
    resultado = bridge.ha_monitor_check_result(entity_id)
    if resultado is None:
        return True, False, "ha_monitor.py"
    return True, bool(resultado.get("ok")), "ha_monitor.py"


def _vigilancia_por_heartbeat(
    job: str, mecanismo_ok: str, max_age_s: int
) -> tuple[bool, str | None]:
    """Comprueba un latido real en vez de asumir que algo vigila — mismo
    principio para cualquier monitor que llame a `heartbeat.write()`
    (telegram_monitor.py, y desde 2026-08-08 también docker_monitor.py,
    ha_monitor.py, dns_pi_monitor.py, verify_backups.py)."""
    hb = bridge.read_heartbeat(job)
    if hb is None:
        return False, None
    edad_s = time() - hb.get("epoch", 0)
    if edad_s > max_age_s:
        return False, None
    return True, mecanismo_ok


def _vigilancia_telegram() -> tuple[bool, str | None]:
    """FR-006: comprueba el latido real de `telegram_monitor.py`, no una
    suposición. Antes de que ese monitor existiera, esto era simplemente
    `False, None` — se actualizó al construirlo (2026-08-08), justo para
    que el inventario deje de reportar como abierta una brecha ya cerrada."""
    return _vigilancia_por_heartbeat(
        "telegram-monitor", "telegram_monitor.py (latido + Kuma/email)",
        _TELEGRAM_HEARTBEAT_MAX_AGE_S,
    )


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
        # El dashboard tiene panel de HA desde 2026-08-08, pero solo
        # muestra las ~15 entidades que ha_monitor.py vigila una a una
        # (mismo criterio que "vigilado" aquí) — el resto del registro
        # (~357 entidades) sigue sin aparecer en ningún sitio.
        llega = "si" if vigilado else "no"
    elif c.categoria == "host_externo":
        # Vigilados por Beszel vía relay socat (sin cambios). Desde feature
        # 002 (2026-08-08), scripts/beszel_hosts_monitor.py lee ese estado
        # del volumen del hub y lo expone en el dashboard — comprobado aquí
        # por el mismo patrón que el resto de la categoría
        # infra_monitorizacion: latido real, no una suposición de que el
        # mecanismo nuevo sigue vivo.
        llega_ok, _ = _vigilancia_por_heartbeat(
            "beszel-hosts", "beszel_hosts_monitor.py (latido propio)", 900,
        )
        declarado, vigilado, mecanismo = True, True, "Beszel (vía relay socat)"
        llega = "si" if llega_ok else "no"
    elif c.categoria == "hermes":
        vigilado = bool(raw.meta.get("launchagent_cargado"))
        declarado, mecanismo, llega = (
            True,
            "amsterdam9.bautista.heartbeat" if vigilado else None,
            # Panel "Estado de los monitores" desde 2026-08-08: muestra el
            # estado launchctl de ambos LaunchAgents de Hermes/Bautista.
            "si",
        )
    elif c.categoria == "telegram":
        vigilado, mecanismo = _vigilancia_telegram()
        # El mismo panel muestra el latido de telegram_monitor.py.
        declarado, llega = vigilado, "si"
    elif c.categoria == "infra_monitorizacion":
        if c.nombre_actual in _INFRA_HEARTBEAT_JOBS:
            job, max_age_s = _INFRA_HEARTBEAT_JOBS[c.nombre_actual]
            vigilado, mecanismo = _vigilancia_por_heartbeat(job, f"{job} (latido propio)", max_age_s)
        elif c.nombre_actual == "Beszel (hub)":
            # Desde feature 003 (2026-08-09): sources.py ya calculó si al
            # menos uno de los sistemas que Beszel vigila tiene dato
            # fresco (`_beszel_hub_sano`, mismo criterio que
            # get_beszel_hub_status() en app.py) — Caso 3 de BRIEFING.md,
            # cerrado.
            vigilado = bool(raw.meta.get("hub_sano"))
            mecanismo = "beszel_hosts_monitor.py (hub_systems)" if vigilado else None
        else:
            mecanismo = _INFRA_MONITORIZACION_VIGILANCIA.get(c.nombre_actual)
            vigilado = mecanismo is not None
        declarado = True
        # Los 4 latidos + heartbeat.py (transitivo) + Beszel (hub) están
        # en el panel "Estado de los monitores" desde 2026-08-08 /
        # 2026-08-09.
        llega = "si"
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
    if categoria == "telegram" and not ev.esta_vigilado:
        # Riesgo concentrado de verdad: nadie vigila el canal — Edge Case
        # de FR-006. Si ya está vigilado (telegram_monitor.py) pero sigue
        # siendo brecha, es por otra razón (p. ej. no llega al dashboard) —
        # se clasifica como cualquier otro componente, más abajo.
        return "riesgo_concentrado_telegram"
    if ev.estado_declarado_status == "ausente":
        return "sin_declaracion"
    if ev.estado_declarado_status == "caducada":
        return "declaracion_caducada"
    if not ev.esta_vigilado:
        # feature 004: un mecanismo presente pese a no estar vigilado
        # solo pasa cuando _vigilancia_entidad_ha() encontró el check
        # declarado pero su último resultado real falló — distinto de
        # "nadie lo comprueba" (research.md §4 de esa feature).
        if ev.mecanismo_vigilancia:
            return "condicion_incumplida"
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
    if tipo == "condicion_incumplida":
        mecanismo = ev.mecanismo_vigilancia or "un mecanismo"
        resultado = bridge.ha_monitor_check_result(nombre)
        detalle = resultado.get("detail") if resultado else None
        sufijo = f": {detalle}" if detalle else "."
        return (
            f"'{nombre}' ({categoria}) tiene un estado esperado declarado y "
            f"vigilado por {mecanismo}, pero su último resultado real no lo "
            f"cumple{sufijo}"
        )
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
