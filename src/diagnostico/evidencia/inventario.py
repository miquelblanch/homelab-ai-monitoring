"""inventario — Evidencia del origen inventario de cobertura (feature
013: specs/013-diagnostico-inventario/). Una brecha real de un
componente, en vivo en la ejecución más reciente o en diferido en una
ejecución pasada concreta — nunca de tipo `condicion_incumplida`.
Ver research.md §4/§5/§11 de 013.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from inventory import diff as inv_diff
from inventory import store as inv_store
from inventory.model import TIPOS_BRECHA

from ..model import Episodio
from ..store import insert_episodio

TIPOS_INVENTARIO_EN_ALCANCE = frozenset(TIPOS_BRECHA) - {"condicion_incumplida"}
# research.md §5 de 013 — `condicion_incumplida` solo ocurre hoy en
# `entidad_ha` y es el propio inventario re-detectando, con otras
# palabras, lo que el origen "ha" (010) ya diagnostica (FR-010).

INVENTARIO_COMPARACION_MAX_ENTRADAS = 30  # research.md §11 de 013 —
# límite defensivo real: el ancla de comparación de las cuatro brechas
# reales conocidas (#19/#28/#31/#52) resulta ser una ejecución con 0
# brechas registradas, así que un diff sin límite listaría hasta 319
# brechas como "nuevas".


def _hallazgo_de_componente(
    conn_inv: sqlite3.Connection, ejecucion_id: int, nombre: str
) -> dict | None:
    """El hallazgo de `nombre` en `ejecucion_id`, o `None` si ese
    nombre no aparece entre los componentes de esa ejecución
    (research.md §4 de 013). No es un error — spec.md Edge Cases."""
    for h in inv_store.hallazgos_de_ejecucion(conn_inv, ejecucion_id):
        if h["nombre_actual"] == nombre:
            return dict(h)
    return None


def _brecha_de_componente(
    conn_inv: sqlite3.Connection, ejecucion_id: int, nombre: str
) -> dict | None:
    """La brecha de `nombre` en `ejecucion_id`, o `None` si ese
    componente no tiene ninguna brecha activa en esa ejecución
    (research.md §4 de 013). **Sin filtrar por tipo** — devuelve
    cualquiera de los 6 tipos posibles si existe; el rechazo de
    `condicion_incumplida` es responsabilidad exclusiva de
    `_validar_tipo_brecha_inventario()`, filtrar aquí la dejaría sin
    nada que rechazar (hallazgo U1 de /speckit-analyze, 2026-08-12)."""
    for b in inv_store.brechas_de_ejecucion(conn_inv, ejecucion_id):
        if b["nombre_actual"] == nombre:
            return dict(b)
    return None


def _validar_tipo_brecha_inventario(brecha: dict | None) -> None:
    """Bloquea `condicion_incumplida` antes de congelar nada — un
    `ValueError`, no una evidencia vacía, porque es un rechazo
    explícito de alcance, no una ausencia de datos (FR-010, research.md
    §5 de 013, mismo patrón que `_validar_check_ha()` bloqueando la
    cerradura en 010)."""
    if brecha is not None and brecha["tipo"] == "condicion_incumplida":
        raise ValueError(
            "brecha de tipo 'condicion_incumplida' queda fuera del alcance de "
            "este feature (spec.md FR-010) — el origen 'ha' (feature 010) ya "
            "la diagnostica"
        )


def _comparacion_dict(comparacion: inv_diff.Comparacion) -> dict:
    """Envuelve cada lista de `Comparacion` en `{"total", "muestra"}`,
    acotada a `INVENTARIO_COMPARACION_MAX_ENTRADAS` (research.md §11 de
    013) — el modelo ve el volumen real sin recibir el listado
    completo."""
    def _cap(lista: list[str]) -> dict:
        return {"total": len(lista), "muestra": lista[:INVENTARIO_COMPARACION_MAX_ENTRADAS]}

    return {
        "ejecucion_actual_id": comparacion.ejecucion_actual_id,
        "ejecucion_previa_id": comparacion.ejecucion_previa_id,
        "componentes_nuevos": _cap(comparacion.componentes_nuevos),
        "componentes_de_baja": _cap(comparacion.componentes_de_baja),
        "brechas_nuevas": _cap(comparacion.brechas_nuevas),
        "brechas_resueltas": _cap(comparacion.brechas_resueltas),
    }


def _snapshot_inventario_vacio() -> dict:
    return {
        "disco": None,
        "restart_history": None,
        "container_metrics": None,
        "container_metrics_hourly": None,
        "disk_metrics": None,
        "docker_inspect": None,
        "docker_logs_tail": None,
        "ha_check": None,
        "ha_check_status": None,
        "ha_history": None,
        "ha_recorder_corrupt_files": None,
        "backup_log_path": None,
        "backup_dumps": None,
        "backup_rsync_stats": None,
        "backup_resumen_final": None,
        "backup_rsync_estado": None,
        "backup_anomalias": None,
        "relay_nombre": None,
        "relay_estado_actual": None,
        "relay_agregado": None,
        "inventario_ejecucion_id": None,
        "inventario_hallazgo": None,
        "inventario_brecha": None,
        "inventario_comparacion": None,
    }


def _armar_episodio_inventario(
    conn: sqlite3.Connection,
    conn_inv: sqlite3.Connection,
    nombre: str,
    ejecucion: sqlite3.Row | None,
    *,
    en_vivo: bool,
) -> Episodio:
    """Arma y persiste el episodio a partir de una ejecución ya
    localizada (o `None` si no existe) — compartido por
    `congelar_inventario_vivo`/`congelar_inventario_historico`, mismo
    patrón que `_congelar_backup()` de 011. `condicion_incumplida` se
    rechaza aquí, antes de persistir nada (FR-010)."""
    if ejecucion is not None:
        momento = datetime.fromisoformat(ejecucion["fecha"])
        hallazgo = _hallazgo_de_componente(conn_inv, ejecucion["id"], nombre)
        brecha = _brecha_de_componente(conn_inv, ejecucion["id"], nombre)
        _validar_tipo_brecha_inventario(brecha)  # brecha, si no es None,
        # ya está garantizado en TIPOS_INVENTARIO_EN_ALCANCE a partir de aquí

        comparacion = None
        if brecha is not None and brecha["primera_ejecucion_id"] > 1:
            comparacion = _comparacion_dict(
                inv_diff.compare_runs(
                    conn_inv, ejecucion["id"], brecha["primera_ejecucion_id"] - 1
                )
            )

        snapshot = _snapshot_inventario_vacio()
        snapshot.update(
            inventario_ejecucion_id=ejecucion["id"],
            inventario_hallazgo=hallazgo,
            inventario_brecha=brecha,
            inventario_comparacion=comparacion,
        )
    else:
        momento = datetime.now()
        snapshot = _snapshot_inventario_vacio()

    episodio = Episodio(
        componente=nombre,
        origen="inventario",
        es_critico=False,
        en_vivo=en_vivo,
        ventana_inicio=momento.isoformat(),
        ventana_fin=momento.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_inventario_vivo(conn: sqlite3.Connection, nombre: str) -> Episodio:
    """Congela el hallazgo actual de un componente del inventario, en
    la ejecución más reciente. `es_critico` siempre `False` (spec.md
    Assumptions) — no existe concepto de "componente crítico"."""
    with inv_store.connect() as conn_inv:
        ejecucion = inv_store.latest_ejecucion(conn_inv)
        return _armar_episodio_inventario(conn, conn_inv, nombre, ejecucion, en_vivo=True)


def congelar_inventario_historico(
    conn: sqlite3.Connection, nombre: str, ejecucion_id: int
) -> Episodio:
    """Congela el hallazgo de un componente del inventario en una
    ejecución pasada concreta. `ejecucion_id` inexistente no es un
    error — se congela igual, con evidencia vacía (research.md §9 de
    013)."""
    with inv_store.connect() as conn_inv:
        ejecucion = inv_store.get_ejecucion(conn_inv, ejecucion_id)
        return _armar_episodio_inventario(conn, conn_inv, nombre, ejecucion, en_vivo=False)
