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
    ("integracion", "Recordatorios de Nextcloud (Tareas/Calendario)"): (
        "BRIEFING.md Caso 4 / BARRIDO-2026-08-07.md hallazgo 2 — un fallo "
        "silencioso en la cadena ya se arregló, pero no está confirmado "
        "que cierre el caso del todo."
    ),
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
