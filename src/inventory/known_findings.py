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
    ("infra_monitorizacion", "Beszel (hub)"): (
        "BRIEFING.md Caso 3 — Beszel no vigila bien 2 de sus 3 sistemas "
        "monitorizados. Sigue sin investigar (BARRIDO-2026-08-07)."
    ),
    ("host_externo", "Host de Uptime Kuma"): (
        "BRIEFING.md Caso 3 — uno de los dos sistemas que Beszel no "
        "vigila bien."
    ),
    ("host_externo", "Host de AdGuard Home (DNS primario)"): (
        "BRIEFING.md Caso 3 — uno de los dos sistemas que Beszel no "
        "vigila bien."
    ),
}


def lookup(categoria: str, nombre_actual: str) -> str | None:
    return KNOWN_FINDINGS.get((categoria, nombre_actual))
