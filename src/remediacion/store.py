"""store — Persistencia SQLite de la remediación. Ver data-model.md.

Base de datos propia (`remediacion.db`), sin relación de esquema con
`diagnostico.db` — paquete independiente (research.md §2 de
specs/019-remediacion-automatica/).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .model import IntentoRemediacion

_DEFAULT_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion.db"
)


def db_path() -> Path:
    return Path(os.environ.get("REMEDIACION_DB_PATH", _DEFAULT_DB_PATH))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS configuracion_accion (
    tipo_accion TEXT PRIMARY KEY,
    modo TEXT NOT NULL DEFAULT 'manual',
    actualizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intentos_remediacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_accion TEXT NOT NULL,
    componente TEXT NOT NULL,
    ruta TEXT NOT NULL,
    modo_en_deteccion TEXT NOT NULL,
    estado TEXT NOT NULL,
    detalle TEXT NOT NULL,
    fichero_rotado TEXT,
    creado_en TEXT NOT NULL,
    resuelto_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_intentos_tipo_estado
    ON intentos_remediacion(tipo_accion, estado);
"""


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Conexión con las dos tablas garantizadas. No falla si el
    directorio no existe todavía — lo crea (mismo principio "a prueba
    de fallos" que `diagnostico/store.py`)."""
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Configuración de acción ─────────────────────────────────────────────


def get_modo(conn: sqlite3.Connection, tipo_accion: str) -> str:
    """Modo vigente de `tipo_accion` — "manual" si nunca se ha visto
    antes (FR-002: nunca empieza en automático). Crea la fila si hace
    falta, para que un tipo de acción nuevo no exija un alta previa."""
    row = conn.execute(
        "SELECT modo FROM configuracion_accion WHERE tipo_accion = ?", (tipo_accion,)
    ).fetchone()
    if row is not None:
        return row["modo"]
    conn.execute(
        "INSERT INTO configuracion_accion (tipo_accion, modo, actualizado_en) "
        "VALUES (?, 'manual', ?)",
        (tipo_accion, _now_iso()),
    )
    conn.commit()
    return "manual"


def set_modo(conn: sqlite3.Connection, tipo_accion: str, modo: str) -> None:
    """Cambia el modo de `tipo_accion` — sin ninguna condición previa
    (FR-003): la decisión es siempre de Miquel, nunca del sistema."""
    if modo not in ("manual", "automatico"):
        raise ValueError(f"modo inválido: {modo!r}")
    ahora = _now_iso()
    conn.execute(
        "INSERT INTO configuracion_accion (tipo_accion, modo, actualizado_en) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(tipo_accion) DO UPDATE SET modo = excluded.modo, "
        "actualizado_en = excluded.actualizado_en",
        (tipo_accion, modo, ahora),
    )
    conn.commit()


# ── Intentos de remediación ─────────────────────────────────────────────


def insert_intento(conn: sqlite3.Connection, intento: IntentoRemediacion) -> int:
    creado_en = intento.creado_en or _now_iso()
    cur = conn.execute(
        """INSERT INTO intentos_remediacion
           (tipo_accion, componente, ruta, modo_en_deteccion, estado, detalle,
            fichero_rotado, creado_en, resuelto_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            intento.tipo_accion,
            intento.componente,
            intento.ruta,
            intento.modo_en_deteccion,
            intento.estado,
            intento.detalle,
            intento.fichero_rotado,
            creado_en,
            intento.resuelto_en,
        ),
    )
    conn.commit()
    return cur.lastrowid


def _fila_a_intento(row: sqlite3.Row) -> IntentoRemediacion:
    return IntentoRemediacion(
        id=row["id"],
        tipo_accion=row["tipo_accion"],
        componente=row["componente"],
        ruta=row["ruta"],
        modo_en_deteccion=row["modo_en_deteccion"],
        estado=row["estado"],
        detalle=row["detalle"],
        fichero_rotado=row["fichero_rotado"],
        creado_en=row["creado_en"],
        resuelto_en=row["resuelto_en"],
    )


def get_intento(conn: sqlite3.Connection, intento_id: int) -> IntentoRemediacion | None:
    row = conn.execute(
        "SELECT * FROM intentos_remediacion WHERE id = ?", (intento_id,)
    ).fetchone()
    return _fila_a_intento(row) if row is not None else None


def update_intento_estado(
    conn: sqlite3.Connection,
    intento_id: int,
    estado: str,
    detalle: str,
    fichero_rotado: str | None = None,
) -> None:
    conn.execute(
        "UPDATE intentos_remediacion SET estado = ?, detalle = ?, "
        "fichero_rotado = COALESCE(?, fichero_rotado), resuelto_en = ? WHERE id = ?",
        (estado, detalle, fichero_rotado, _now_iso(), intento_id),
    )
    conn.commit()


def pendiente_existente(conn: sqlite3.Connection, tipo_accion: str, componente: str) -> bool:
    """FR-008: si ya hay un intento `pendiente` para este componente,
    no se crea uno nuevo."""
    row = conn.execute(
        "SELECT 1 FROM intentos_remediacion "
        "WHERE tipo_accion = ? AND componente = ? AND estado = 'pendiente' LIMIT 1",
        (tipo_accion, componente),
    ).fetchone()
    return row is not None


def listar_pendientes(
    conn: sqlite3.Connection, tipo_accion: str | None = None
) -> list[IntentoRemediacion]:
    if tipo_accion is None:
        rows = conn.execute(
            "SELECT * FROM intentos_remediacion WHERE estado = 'pendiente' ORDER BY id"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM intentos_remediacion WHERE estado = 'pendiente' "
            "AND tipo_accion = ? ORDER BY id",
            (tipo_accion,),
        ).fetchall()
    return [_fila_a_intento(r) for r in rows]


def historial(conn: sqlite3.Connection, tipo_accion: str) -> dict[str, int]:
    """Recuento de intentos por estado para `tipo_accion` — informativo,
    nunca bloqueante (FR-004)."""
    rows = conn.execute(
        "SELECT estado, count(*) AS n FROM intentos_remediacion "
        "WHERE tipo_accion = ? GROUP BY estado",
        (tipo_accion,),
    ).fetchall()
    return {r["estado"]: r["n"] for r in rows}
