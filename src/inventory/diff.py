"""diff — Comparar dos ejecuciones del inventario: componentes de
alta/baja, y brechas nuevas/resueltas entre una ejecución y otra
concreta (`--since RUN_ID`, FR-013, FR-015).

Distinto de `primera_ejecucion_id` en `brechas` (que ya distingue nueva
de conocida frente a la ejecución inmediatamente relevante, en
`store.populate_brechas`): esto compara contra *cualquier* ejecución
pasada que Miquel elija, no solo la anterior — Clarification 2 (retención
total, comparar contra cualquier punto pasado).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from . import store


@dataclass
class Comparacion:
    ejecucion_actual_id: int
    ejecucion_previa_id: int
    componentes_nuevos: list[str] = field(default_factory=list)
    componentes_de_baja: list[str] = field(default_factory=list)
    brechas_nuevas: list[str] = field(default_factory=list)
    brechas_resueltas: list[str] = field(default_factory=list)


def compare_runs(
    conn: sqlite3.Connection, ejecucion_actual_id: int, ejecucion_previa_id: int
) -> Comparacion:
    actuales = {h["componente_id"]: h for h in store.hallazgos_de_ejecucion(conn, ejecucion_actual_id)}
    previos = {h["componente_id"]: h for h in store.hallazgos_de_ejecucion(conn, ejecucion_previa_id)}

    nuevos = [
        actuales[cid]["nombre_actual"] for cid in actuales.keys() - previos.keys()
    ]
    de_baja = [
        previos[cid]["nombre_actual"] for cid in previos.keys() - actuales.keys()
    ]

    brechas_actuales = {
        (b["componente_id"], b["tipo"]): b
        for b in store.brechas_de_ejecucion(conn, ejecucion_actual_id)
    }
    brechas_previas = {
        (b["componente_id"], b["tipo"]): b
        for b in store.brechas_de_ejecucion(conn, ejecucion_previa_id)
    }

    nuevas = [
        f"{b['nombre_actual']} ({b['tipo']})"
        for k, b in brechas_actuales.items()
        if k not in brechas_previas
    ]
    resueltas = [
        f"{b['nombre_actual']} ({b['tipo']})"
        for k, b in brechas_previas.items()
        if k not in brechas_actuales
    ]

    return Comparacion(
        ejecucion_actual_id=ejecucion_actual_id,
        ejecucion_previa_id=ejecucion_previa_id,
        componentes_nuevos=sorted(nuevos),
        componentes_de_baja=sorted(de_baja),
        brechas_nuevas=sorted(nuevas),
        brechas_resueltas=sorted(resueltas),
    )
