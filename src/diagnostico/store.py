"""store — Persistencia SQLite del diagnóstico de episodios. Ver
data-model.md.

Base de datos propia (`diagnostico.db`), no las tablas de `homelab.db`
(que este módulo nunca escribe — ver el paquete `evidencia/`), en el
mismo directorio que `inventario.db` — cubierta por el backup nocturno
del homelab sin nada adicional que configurar (research.md §4).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .model import Diagnostico, Episodio, Hipotesis

_DEFAULT_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/diagnostico.db"
)


def db_path() -> Path:
    return Path(os.environ.get("DIAGNOSTICO_DB_PATH", _DEFAULT_DB_PATH))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    componente TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'contenedor',
    es_critico INTEGER NOT NULL,
    en_vivo INTEGER NOT NULL,
    restart_history_id INTEGER,
    ventana_inicio TEXT NOT NULL,
    ventana_fin TEXT NOT NULL,
    snapshot_evidencia TEXT NOT NULL,
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diagnosticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episodio_id INTEGER NOT NULL REFERENCES episodios(id),
    conclusion_tipo TEXT NOT NULL,
    conclusion_texto TEXT NOT NULL,
    modelo TEXT,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_salida INTEGER NOT NULL DEFAULT 0,
    coste_eur REAL NOT NULL DEFAULT 0.0,
    creado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_episodio ON diagnosticos(episodio_id);

CREATE TABLE IF NOT EXISTS hipotesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id INTEGER NOT NULL REFERENCES diagnosticos(id),
    orden INTEGER NOT NULL,
    descripcion TEXT NOT NULL,
    comprobacion TEXT NOT NULL,
    desenlace TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hipotesis_diagnostico ON hipotesis(diagnostico_id);

CREATE TABLE IF NOT EXISTS gasto_diario (
    dia TEXT PRIMARY KEY,
    coste_eur_acumulado REAL NOT NULL DEFAULT 0.0,
    limite_eur REAL NOT NULL
);
"""


def _migrar_episodios_contenedor_a_componente(conn: sqlite3.Connection) -> None:
    """feature 009: `episodios.contenedor` → `componente` + `origen`
    nuevo. Idempotente — solo actúa sobre una base ya existente de
    antes de este feature (comprobado con `PRAGMA table_info`, research.md
    §1 de specs/009-diagnostico-discos/). Sobre una base nueva, `_SCHEMA`
    ya crea las columnas correctas y esta función no tiene nada que
    hacer."""
    columnas = {row["name"] for row in conn.execute("PRAGMA table_info(episodios)")}
    if "origen" in columnas or "contenedor" not in columnas:
        return
    conn.execute("ALTER TABLE episodios RENAME COLUMN contenedor TO componente")
    conn.execute(
        "ALTER TABLE episodios ADD COLUMN origen TEXT NOT NULL DEFAULT 'contenedor'"
    )
    conn.commit()


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Conexión con las cuatro tablas garantizadas. No falla si el
    directorio no existe todavía — lo crea (mismo principio "a prueba de
    fallos" que `inventory/store.py`)."""
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        _migrar_episodios_contenedor_a_componente(conn)
        yield conn
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    """Crea el esquema si no existe. Idempotente."""
    with connect(path):
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Episodios ────────────────────────────────────────────────────────────


def insert_episodio(conn: sqlite3.Connection, episodio: Episodio) -> int:
    creado_en = episodio.creado_en or _now_iso()
    cur = conn.execute(
        """INSERT INTO episodios
           (componente, origen, es_critico, en_vivo, restart_history_id,
            ventana_inicio, ventana_fin, snapshot_evidencia, creado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            episodio.componente,
            episodio.origen,
            int(episodio.es_critico),
            int(episodio.en_vivo),
            episodio.restart_history_id,
            episodio.ventana_inicio,
            episodio.ventana_fin,
            json.dumps(episodio.snapshot_evidencia, ensure_ascii=False),
            creado_en,
        ),
    )
    conn.commit()
    return cur.lastrowid


def _episodio_from_row(row: sqlite3.Row) -> Episodio:
    return Episodio(
        id=row["id"],
        componente=row["componente"],
        origen=row["origen"],
        es_critico=bool(row["es_critico"]),
        en_vivo=bool(row["en_vivo"]),
        restart_history_id=row["restart_history_id"],
        ventana_inicio=row["ventana_inicio"],
        ventana_fin=row["ventana_fin"],
        snapshot_evidencia=json.loads(row["snapshot_evidencia"]),
        creado_en=row["creado_en"],
    )


def get_episodio(conn: sqlite3.Connection, episodio_id: int) -> Episodio | None:
    row = conn.execute(
        "SELECT * FROM episodios WHERE id = ?", (episodio_id,)
    ).fetchone()
    return _episodio_from_row(row) if row else None


# ── Diagnósticos e hipótesis ──────────────────────────────────────────────


def insert_diagnostico(conn: sqlite3.Connection, diagnostico: Diagnostico) -> int:
    creado_en = diagnostico.creado_en or _now_iso()
    cur = conn.execute(
        """INSERT INTO diagnosticos
           (episodio_id, conclusion_tipo, conclusion_texto, modelo,
            tokens_entrada, tokens_salida, coste_eur, creado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            diagnostico.episodio_id,
            diagnostico.conclusion_tipo,
            diagnostico.conclusion_texto,
            diagnostico.modelo,
            diagnostico.tokens_entrada,
            diagnostico.tokens_salida,
            diagnostico.coste_eur,
            creado_en,
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_hipotesis(conn: sqlite3.Connection, hipotesis: Hipotesis) -> int:
    cur = conn.execute(
        """INSERT INTO hipotesis
           (diagnostico_id, orden, descripcion, comprobacion, desenlace)
           VALUES (?, ?, ?, ?, ?)""",
        (
            hipotesis.diagnostico_id,
            hipotesis.orden,
            hipotesis.descripcion,
            hipotesis.comprobacion,
            hipotesis.desenlace,
        ),
    )
    conn.commit()
    return cur.lastrowid


def diagnosticos_de_episodio(conn: sqlite3.Connection, episodio_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM diagnosticos WHERE episodio_id = ? ORDER BY id",
        (episodio_id,),
    ).fetchall()


def hipotesis_de_diagnostico(conn: sqlite3.Connection, diagnostico_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM hipotesis WHERE diagnostico_id = ? ORDER BY orden",
        (diagnostico_id,),
    ).fetchall()


# ── Gasto diario ──────────────────────────────────────────────────────────


def get_gasto_diario(conn: sqlite3.Connection, dia: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM gasto_diario WHERE dia = ?", (dia,)
    ).fetchone()


def upsert_gasto_diario(
    conn: sqlite3.Connection, dia: str, coste_incremental_eur: float, limite_eur: float
) -> None:
    """Suma `coste_incremental_eur` al acumulado del día, creando la fila
    si no existe. El límite se congela por día (data-model.md): una vez
    creada la fila del día, `limite_eur` no se vuelve a sobrescribir aquí
    — cambiar el límite hoy no debe reescribir el histórico de días
    anteriores ni el de hoy si ya se fijó."""
    existing = get_gasto_diario(conn, dia)
    if existing is None:
        conn.execute(
            "INSERT INTO gasto_diario (dia, coste_eur_acumulado, limite_eur) VALUES (?, ?, ?)",
            (dia, coste_incremental_eur, limite_eur),
        )
    else:
        conn.execute(
            "UPDATE gasto_diario SET coste_eur_acumulado = coste_eur_acumulado + ? WHERE dia = ?",
            (coste_incremental_eur, dia),
        )
    conn.commit()
