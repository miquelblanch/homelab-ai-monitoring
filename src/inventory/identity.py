"""identity — Emparejar un componente con el ya conocido de ejecuciones
anteriores (FR-015, Clarification 1 del spec).

Regla: por `identificador_estable` cuando la fuente lo ofrece —el nombre
de contenedor/servicio para Docker (nunca el ID interno, que cambia en
cada recreación), `unique_id` para una entidad HA, la label de launchd
para un LaunchAgent, el `id` de un cron de Hermes (research.md §3). Si la
fuente no ofrece ninguno, se empareja por nombre exacto; un cambio de
nombre sin identificador estable se trata como baja+alta, tal como prevé
el spec explícitamente.
"""

from __future__ import annotations

import sqlite3


def match_component(
    conn: sqlite3.Connection,
    categoria: str,
    identificador_estable: str | None,
    nombre_actual: str,
) -> sqlite3.Row | None:
    if identificador_estable:
        row = conn.execute(
            "SELECT * FROM componentes WHERE categoria = ? AND identificador_estable = ?",
            (categoria, identificador_estable),
        ).fetchone()
        if row is not None:
            return row
    return conn.execute(
        "SELECT * FROM componentes WHERE categoria = ? AND nombre_actual = ? "
        "AND identificador_estable IS NULL",
        (categoria, nombre_actual),
    ).fetchone()
