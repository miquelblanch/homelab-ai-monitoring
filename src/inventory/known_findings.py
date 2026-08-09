"""known_findings — Mapeo curado a mano entre componentes y los barridos
que ya los documentaron (`BARRIDO-*.md`). T039, hallazgo G1 de
`/speckit-analyze` — spec.md User Story 2, escenario 2.

Curado, no detección automática por texto: cruzar prosa libre contra
nombres de componente es frágil y desproporcionado para el volumen de
`BARRIDO-*.md` (spec.md, Assumptions). Se revisa a mano cada vez que se
cierre un barrido nuevo.

Clave: `(categoria, nombre_actual)` tal como los produce `sources.py`.
Valor: referencia corta al documento y al hallazgo.
"""

from __future__ import annotations

KNOWN_FINDINGS: dict[tuple[str, str], str] = {
    # Caso 4 (BRIEFING.md) — "los recordatorios de Tareas/Calendario de
    # Nextcloud no llegan por Telegram" — causa real encontrada y cerrada el
    # 2026-08-09, más profunda que las dos correcciones de
    # BARRIDO-2026-08-07 (el "" silencioso, los healthchecks): la cuenta de
    # automatización (admin_nc) usada por bautista-calendar.sh no tenía
    # NINGÚN calendario propio (`occ dav:list-calendars admin_nc` → "no
    # calendars") — el calendario real, "Personal", pertenece a miquel_nc y
    # nunca se había compartido. El mecanismo llevaba reportando "sin
    # eventos" fielmente cada día porque no miraba donde están los eventos
    # reales, no porque no hubiera ninguno. Arreglado compartiendo el
    # calendario Personal (solo lectura) con admin_nc vía el servicio interno
    # de Nextcloud (`OCA\DAV\CalDAV\Sharing\Service::shareWith`), sin generar
    # credenciales nuevas. Verificado en vivo: recordatorios_hoy() pasó de
    # "sin eventos" a mostrar un evento real existente en el calendario. La
    # app de Tareas (VTODO) no está instalada en esta instancia — nada
    # pendiente ahí por ahora.
    # Caso 3 (BRIEFING.md) — "Beszel no vigila bien 2 de sus 3 sistemas" —
    # se investigó y se cerró el 2026-08-09: la causa de red (relays socat,
    # 2026-08-07) ya estaba arreglada, pero beszel_hosts_monitor.py y
    # ha_monitor.py::_container_running() llamaban a "docker" a secas, que
    # falla bajo launchd (no hereda el PATH interactivo) — el mismo bug ya
    # resuelto una vez en immich_album_from_paths.py, nunca aplicado aquí.
    # beszel_hosts_monitor.py llevaba ~12h fallando el 100% de sus ciclos;
    # los 33 checks condicionados a Frigate de ha_monitor.py (feature 004)
    # llevaban el 100% de sus ciclos automáticos suprimidos como "parado —
    # no aplica" desde que se desplegaron ese mismo día, pese a que Frigate
    # estaba corriendo de verdad. Arreglado con la misma resolución de ruta
    # absoluta que ya usaba immich_album_from_paths.py. Sin entrada nueva
    # aquí: ya no es un hallazgo conocido, es una brecha cerrada.
}


def lookup(categoria: str, nombre_actual: str) -> str | None:
    return KNOWN_FINDINGS.get((categoria, nombre_actual))
