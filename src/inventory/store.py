"""store — Persistencia SQLite del inventario. Ver data-model.md.

Base de datos propia (no reutiliza las tablas de `homelab.db`), en el
mismo directorio — así que queda cubierta por el backup nocturno del
homelab sin nada adicional que configurar (research.md §2).

Las cuatro tablas son **append-only**: ninguna función de este módulo
borra ni actualiza una fila de `ejecuciones`, `hallazgos` o `brechas`
salvo el propio proceso de emparejamiento de `componentes` (que sí
actualiza `nombre_actual`/`last_reviewed_at` de un componente que ya
existía — nunca borra su historial). FR-017, Clarification 2.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

from . import evaluate, identity
from .model import Brecha, Componente, Ejecucion, Hallazgo
from .sources import RawComponente

_DEFAULT_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/inventario.db"
)


def db_path() -> Path:
    return Path(os.environ.get("INVENTORY_DB_PATH", _DEFAULT_DB_PATH))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS componentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    nombre_actual TEXT NOT NULL,
    identificador_estable TEXT,
    origen_sin_id_estable INTEGER NOT NULL DEFAULT 1,
    es_intencionadamente_no_vigilado INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT,
    primera_ejecucion_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_componentes_identificador
    ON componentes(categoria, identificador_estable);
CREATE INDEX IF NOT EXISTS idx_componentes_nombre
    ON componentes(categoria, nombre_actual);

CREATE TABLE IF NOT EXISTS ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    disparador TEXT NOT NULL,
    total_componentes INTEGER NOT NULL DEFAULT 0,
    total_brechas INTEGER NOT NULL DEFAULT 0,
    es_linea_base_referencia INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hallazgos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id INTEGER NOT NULL REFERENCES ejecuciones(id),
    componente_id INTEGER NOT NULL REFERENCES componentes(id),
    tiene_estado_declarado INTEGER NOT NULL,
    estado_declarado_status TEXT NOT NULL,
    esta_vigilado INTEGER NOT NULL,
    mecanismo_vigilancia TEXT,
    llega_a_dashboard TEXT NOT NULL,
    es_brecha INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_hallazgos_ejecucion ON hallazgos(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_hallazgos_componente ON hallazgos(componente_id);

CREATE TABLE IF NOT EXISTS brechas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hallazgo_id INTEGER NOT NULL REFERENCES hallazgos(id),
    tipo TEXT NOT NULL,
    primera_ejecucion_id INTEGER NOT NULL REFERENCES ejecuciones(id),
    conocida_por_barrido_previo TEXT,
    contexto TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_brechas_hallazgo ON brechas(hallazgo_id);
"""


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Conexión con las cuatro tablas garantizadas. No falla si el
    directorio no existe todavía — lo crea (mismo principio "a prueba de
    fallos" que metrics_db.py, salvo errores de permisos reales)."""
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        yield conn
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    """Crea el esquema si no existe. Idempotente."""
    with connect(path):
        pass


# ── Inserciones de bajo nivel ───────────────────────────────────────────────


def insert_ejecucion(conn: sqlite3.Connection, ejecucion: Ejecucion) -> int:
    cur = conn.execute(
        """INSERT INTO ejecuciones
           (fecha, disparador, total_componentes, total_brechas, es_linea_base_referencia)
           VALUES (?, ?, ?, ?, ?)""",
        (
            ejecucion.fecha.isoformat(),
            ejecucion.disparador,
            ejecucion.total_componentes,
            ejecucion.total_brechas,
            int(ejecucion.es_linea_base_referencia),
        ),
    )
    return cur.lastrowid


def insert_componente(conn: sqlite3.Connection, c: Componente) -> int:
    cur = conn.execute(
        """INSERT INTO componentes
           (categoria, nombre_actual, identificador_estable, origen_sin_id_estable,
            es_intencionadamente_no_vigilado, last_reviewed_at, primera_ejecucion_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            c.categoria,
            c.nombre_actual,
            c.identificador_estable,
            int(c.origen_sin_id_estable),
            int(c.es_intencionadamente_no_vigilado),
            c.last_reviewed_at.isoformat() if c.last_reviewed_at else None,
            c.primera_ejecucion_id,
        ),
    )
    return cur.lastrowid


def update_componente_visto(
    conn: sqlite3.Connection, componente_id: int, nombre_actual: str
) -> None:
    """Actualiza el nombre visible de un componente ya conocido — nunca
    borra su historial de hallazgos (Clarification 1)."""
    conn.execute(
        "UPDATE componentes SET nombre_actual = ? WHERE id = ?",
        (nombre_actual, componente_id),
    )


def insert_hallazgo(conn: sqlite3.Connection, h: Hallazgo) -> int:
    cur = conn.execute(
        """INSERT INTO hallazgos
           (ejecucion_id, componente_id, tiene_estado_declarado,
            estado_declarado_status, esta_vigilado, mecanismo_vigilancia,
            llega_a_dashboard, es_brecha)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            h.ejecucion_id,
            h.componente_id,
            int(h.tiene_estado_declarado),
            h.estado_declarado_status,
            int(h.esta_vigilado),
            h.mecanismo_vigilancia,
            h.llega_a_dashboard,
            int(h.es_brecha),
        ),
    )
    return cur.lastrowid


def insert_brecha(conn: sqlite3.Connection, b: Brecha) -> int:
    cur = conn.execute(
        """INSERT INTO brechas
           (hallazgo_id, tipo, primera_ejecucion_id, conocida_por_barrido_previo, contexto)
           VALUES (?, ?, ?, ?, ?)""",
        (
            b.hallazgo_id,
            b.tipo,
            b.primera_ejecucion_id,
            b.conocida_por_barrido_previo,
            b.contexto,
        ),
    )
    return cur.lastrowid


def latest_ejecucion(conn: sqlite3.Connection, exclude_id: int | None = None) -> sqlite3.Row | None:
    query = "SELECT * FROM ejecuciones"
    params: tuple = ()
    if exclude_id is not None:
        query += " WHERE id != ?"
        params = (exclude_id,)
    query += " ORDER BY id DESC LIMIT 1"
    return conn.execute(query, params).fetchone()


def get_ejecucion(conn: sqlite3.Connection, ejecucion_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM ejecuciones WHERE id = ?", (ejecucion_id,)
    ).fetchone()


def hallazgos_de_ejecucion(conn: sqlite3.Connection, ejecucion_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT h.*, c.categoria, c.nombre_actual, c.identificador_estable,
                  c.es_intencionadamente_no_vigilado
           FROM hallazgos h JOIN componentes c ON c.id = h.componente_id
           WHERE h.ejecucion_id = ?""",
        (ejecucion_id,),
    ).fetchall()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def save_run(
    conn: sqlite3.Connection,
    raw_componentes: list[RawComponente],
    disparador: str = "manual",
) -> int:
    """Persiste una ejecución completa: resuelve cada componente contra lo
    ya conocido (mismo emparejamiento simple de `find_componente` — el
    emparejamiento robusto a renombrados vive en `identity.py`, US3),
    evalúa las tres preguntas, y guarda componentes + hallazgos. FR-017.

    NO crea filas de `brechas` todavía — eso es `populate_brechas()`
    (evaluate.classify_gap/gap_context, US2), porque clasificar el tipo de
    brecha y su contexto es una preocupación distinta de "¿hay brecha o
    no?" (FR-010) que sí se calcula aquí.
    """
    ejecucion = Ejecucion(disparador=disparador)
    ejecucion_id = insert_ejecucion(conn, ejecucion)

    total_brechas = 0
    hoy = date.today()
    for raw in raw_componentes:
        c = raw.componente
        existing = identity.match_component(
            conn, c.categoria, c.identificador_estable, c.nombre_actual
        )
        if existing is not None:
            componente_id = existing["id"]
            update_componente_visto(conn, componente_id, c.nombre_actual)
            last_reviewed_at = _parse_date(existing["last_reviewed_at"])
        else:
            c.primera_ejecucion_id = ejecucion_id
            c.last_reviewed_at = hoy  # primera vez que se declara = revisión inicial
            componente_id = insert_componente(conn, c)
            last_reviewed_at = None  # evaluate_component ya lo trata como "recién declarado"

        ev = evaluate.evaluate_component(raw, last_reviewed_at)
        es_brecha = evaluate.es_brecha(ev)
        if es_brecha:
            total_brechas += 1

        insert_hallazgo(
            conn,
            Hallazgo(
                ejecucion_id=ejecucion_id,
                componente_id=componente_id,
                tiene_estado_declarado=ev.tiene_estado_declarado,
                estado_declarado_status=ev.estado_declarado_status,
                esta_vigilado=ev.esta_vigilado,
                mecanismo_vigilancia=ev.mecanismo_vigilancia,
                llega_a_dashboard=ev.llega_a_dashboard,
                es_brecha=es_brecha,
            ),
        )

    conn.execute(
        "UPDATE ejecuciones SET total_componentes = ?, total_brechas = ? WHERE id = ?",
        (len(raw_componentes), total_brechas, ejecucion_id),
    )
    conn.commit()
    return ejecucion_id


def populate_brechas(conn: sqlite3.Connection, ejecucion_id: int) -> int:
    """Crea las filas de `brechas` para los hallazgos de una ejecución que
    son brecha (FR-011, US2). Determina `primera_ejecucion_id` mirando si
    el mismo componente ya tuvo el mismo tipo de brecha en una ejecución
    anterior — así se distingue brecha nueva de conocida (FR-015) sin
    depender todavía de `identity.py` (eso refina el emparejamiento de
    *componentes* con nombre cambiado, no la continuidad de una brecha ya
    ligada al mismo `componente_id`)."""
    from . import evaluate, known_findings

    creadas = 0
    for h in hallazgos_de_ejecucion(conn, ejecucion_id):
        if not h["es_brecha"]:
            continue
        ev = evaluate.EvaluacionParcial(
            tiene_estado_declarado=bool(h["tiene_estado_declarado"]),
            estado_declarado_status=h["estado_declarado_status"],
            esta_vigilado=bool(h["esta_vigilado"]),
            mecanismo_vigilancia=h["mecanismo_vigilancia"],
            llega_a_dashboard=h["llega_a_dashboard"],
            es_intencionado=False,  # ya filtrado: si fuera intencionado, es_brecha sería falso
        )
        tipo = evaluate.classify_gap(ev, h["categoria"])
        contexto = evaluate.gap_context(ev, h["nombre_actual"], h["categoria"], tipo)

        previa = conn.execute(
            """SELECT b.primera_ejecucion_id FROM brechas b
               JOIN hallazgos h2 ON h2.id = b.hallazgo_id
               WHERE h2.componente_id = ? AND b.tipo = ? AND h2.ejecucion_id != ?
               ORDER BY b.id DESC LIMIT 1""",
            (h["componente_id"], tipo, ejecucion_id),
        ).fetchone()
        primera_ejecucion_id = previa["primera_ejecucion_id"] if previa else ejecucion_id

        insert_brecha(
            conn,
            Brecha(
                hallazgo_id=h["id"],
                tipo=tipo,
                primera_ejecucion_id=primera_ejecucion_id,
                conocida_por_barrido_previo=known_findings.lookup(
                    h["categoria"], h["nombre_actual"]
                ),
                contexto=contexto,
            ),
        )
        creadas += 1
    conn.commit()
    return creadas


def brechas_de_ejecucion(conn: sqlite3.Connection, ejecucion_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT b.*, h.componente_id, c.nombre_actual, c.categoria
           FROM brechas b
           JOIN hallazgos h ON h.id = b.hallazgo_id
           JOIN componentes c ON c.id = h.componente_id
           WHERE h.ejecucion_id = ?""",
        (ejecucion_id,),
    ).fetchall()
