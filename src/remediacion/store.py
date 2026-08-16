"""store — Persistencia SQLite de la remediación. Ver data-model.md.

Base de datos propia (`remediacion.db`), sin relación de esquema con
`diagnostico.db` — paquete independiente (research.md §2 de
specs/019-remediacion-automatica/).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from . import _homelab_bridge as bridge
from .model import IntentoAgente, IntentoRemediacion, IntentoReinicio

_DEFAULT_DB_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion.db"
)


def db_path() -> Path:
    return Path(os.environ.get("REMEDIACION_DB_PATH", _DEFAULT_DB_PATH))


# specs/022-clasificacion-remediacion/, data-model.md — ventana en la
# que un intento ya resuelto sigue considerándose "vigente" para
# intento_reinicio_vigente(). Nombrada y configurable, mismo patrón
# que REMEDIACION_CB_VENTANA_HORAS/REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS
# de acciones.py (corregido tras /speckit-analyze, hallazgo C1: antes
# era un literal "5 minutos" sin nombrar).
REMEDIACION_INTENTO_VIGENTE_MINUTOS = int(
    os.environ.get("REMEDIACION_INTENTO_VIGENTE_MINUTOS", "5")
)


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

CREATE TABLE IF NOT EXISTS configuracion_contenedor (
    contenedor TEXT PRIMARY KEY,
    modo TEXT NOT NULL DEFAULT 'manual',
    actualizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intentos_reinicio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contenedor TEXT NOT NULL,
    modo_en_deteccion TEXT NOT NULL,
    episodio_id INTEGER,
    accion_recomendada TEXT,
    razonamiento_deepseek TEXT,
    coste_eur REAL,
    estado TEXT NOT NULL,
    detalle TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    resuelto_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_intentos_reinicio_contenedor_estado
    ON intentos_reinicio(contenedor, estado);

CREATE TABLE IF NOT EXISTS intentos_agente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    modo_en_deteccion TEXT NOT NULL,
    episodio_id INTEGER,
    accion_recomendada TEXT,
    razonamiento_deepseek TEXT,
    coste_eur REAL,
    estado TEXT NOT NULL,
    detalle TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    resuelto_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_intentos_agente_label_estado
    ON intentos_agente(label, estado);
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


def _siguiente_id_compartido(conn: sqlite3.Connection) -> int:
    """intentos_remediacion, intentos_reinicio e intentos_agente
    comparten un único espacio de id, calculado contra el máximo de
    las tres tablas en vez de fiarse del AUTOINCREMENT propio de cada
    una — si no, tres AUTOINCREMENT independientes, todos empezando en
    1, colisionan en cuanto dos tablas cualesquiera tienen filas, y
    localizar_intento() (que prueba las tablas en orden) resolvería
    sobre la tabla equivocada. Descubierto contra la base de producción
    real durante la validación de quickstart.md de 021 (2026-08-14) —
    con 019/020 ya en uso real, intentos_remediacion no empieza vacía.
    Ampliada de dos a tres tablas en specs/026-reiniciar-agentes-relays/
    (research.md §1, `/speckit-analyze` hallazgo del riesgo de mantener
    este cambio sincronizado con localizar_intento())."""
    max_a = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM intentos_remediacion").fetchone()["m"]
    max_b = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM intentos_reinicio").fetchone()["m"]
    max_c = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM intentos_agente").fetchone()["m"]
    return max(max_a, max_b, max_c) + 1


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


def listar_modos(
    conn: sqlite3.Connection, tipos_conocidos: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Modo vigente de cada tipo de `tipos_conocidos`, en ese orden — a
    diferencia de get_modo(), nunca escribe: un tipo sin fila todavía en
    configuracion_accion se reporta "manual" (mismo default que FR-002)
    sin crearla. Pensado para un listado, no para decidir una ejecución."""
    filas = dict(
        conn.execute("SELECT tipo_accion, modo FROM configuracion_accion").fetchall()
    )
    return [(tipo, filas.get(tipo, "manual")) for tipo in tipos_conocidos]


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
    nuevo_id = _siguiente_id_compartido(conn)
    conn.execute(
        """INSERT INTO intentos_remediacion
           (id, tipo_accion, componente, ruta, modo_en_deteccion, estado, detalle,
            fichero_rotado, creado_en, resuelto_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            nuevo_id,
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
    return nuevo_id


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


def intento_vigente(
    conn: sqlite3.Connection, tipo_accion: str, componente: str
) -> IntentoRemediacion | None:
    """El intento más reciente de (`tipo_accion`, `componente`) que
    sigue siendo relevante "ahora mismo" — mismo criterio exacto que
    `intento_reinicio_vigente()`/`intento_agente_vigente()`: en estado
    `pendiente` (nunca resuelto, sigue abierto — `rotar_log` no tiene
    `sin_evaluar`/`sin_accion`), o el `ejecutado`/`fallido`/`rechazado`/
    `deshecho` más reciente si su `resuelto_en` está dentro de
    `REMEDIACION_INTENTO_VIGENTE_MINUTOS`. `None` si no hay ninguno.
    **Añadida tras verificar `/speckit-tasks` T028 (specs/026-.../,
    2026-08-16)**: el bloque `logs[]` del snapshot nunca había tenido
    un equivalente a `intento_vigente` — research.md §9 de 026 daba por
    hecho que sí existía "desde 020", y no era cierto (FR-020 de 026
    exige que Correcciones pueda leerlo para los tres tipos de acción,
    no solo contenedores/agentes)."""
    row = conn.execute(
        "SELECT * FROM intentos_remediacion WHERE tipo_accion = ? AND componente = ? "
        "AND estado = 'pendiente' ORDER BY id DESC LIMIT 1",
        (tipo_accion, componente),
    ).fetchone()
    if row is not None:
        return _fila_a_intento(row)

    row = conn.execute(
        "SELECT * FROM intentos_remediacion WHERE tipo_accion = ? AND componente = ? "
        "AND estado IN ('ejecutado', 'fallido', 'rechazado', 'deshecho') "
        "ORDER BY id DESC LIMIT 1",
        (tipo_accion, componente),
    ).fetchone()
    if row is None or row["resuelto_en"] is None:
        return None
    try:
        resuelto_en = datetime.fromisoformat(row["resuelto_en"])
    except ValueError:
        return None
    ahora = datetime.now(resuelto_en.tzinfo) if resuelto_en.tzinfo else datetime.now()
    limite = timedelta(minutes=REMEDIACION_INTENTO_VIGENTE_MINUTOS)
    if ahora - resuelto_en > limite:
        return None
    return _fila_a_intento(row)


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


# ── Configuración de contenedor (specs/021-remediacion-contenedores/) ───


def get_modo_contenedor(conn: sqlite3.Connection, contenedor: str) -> str:
    """Modo vigente de `contenedor` — "manual" si nunca se ha visto
    antes (research.md §7 de 021: un contenedor nuevo, no cubierto por
    la migración inicial de los 26, empieza en manual). Crea la fila si
    hace falta, mismo patrón que get_modo()."""
    row = conn.execute(
        "SELECT modo FROM configuracion_contenedor WHERE contenedor = ?", (contenedor,)
    ).fetchone()
    if row is not None:
        return row["modo"]
    conn.execute(
        "INSERT INTO configuracion_contenedor (contenedor, modo, actualizado_en) "
        "VALUES (?, 'manual', ?)",
        (contenedor, _now_iso()),
    )
    conn.commit()
    return "manual"


def listar_modos_contenedor(
    conn: sqlite3.Connection, contenedores: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Modo vigente de cada contenedor de `contenedores`, en ese orden
    — a diferencia de get_modo_contenedor(), nunca escribe: uno sin
    fila todavía se reporta "manual" sin crearla. Pensado para un
    listado (comando `contenedores`), no para decidir una evaluación."""
    filas = dict(
        conn.execute("SELECT contenedor, modo FROM configuracion_contenedor").fetchall()
    )
    return [(c, filas.get(c, "manual")) for c in contenedores]


def set_modo_contenedor(conn: sqlite3.Connection, contenedor: str, modo: str) -> None:
    """Cambia el modo de `contenedor`. Guarda de escritura (FR-008,
    specs/022-clasificacion-remediacion/, research.md §2): un
    contenedor crítico nunca admite modo "automatico", ni siquiera si
    el llamador (cli.py) no lo hubiera rechazado ya — dos capas
    independientes de protección para la garantía NO NEGOCIABLE, no
    una sola. `"manual"` sobre un crítico sí se acepta sin error: no
    tiene efecto real (la tabla nunca se consulta para evaluarlo,
    `evaluar_contenedor` fuerza el modo en código — research.md §1),
    pero no hay ninguna razón para que falle un comando que no cambia
    nada peligroso."""
    if modo not in ("manual", "automatico"):
        raise ValueError(f"modo inválido: {modo!r}")
    if modo == "automatico" and contenedor in bridge.docker_critical():
        raise ValueError(f"{contenedor} es crítico — no admite modo automático")
    ahora = _now_iso()
    conn.execute(
        "INSERT INTO configuracion_contenedor (contenedor, modo, actualizado_en) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(contenedor) DO UPDATE SET modo = excluded.modo, "
        "actualizado_en = excluded.actualizado_en",
        (contenedor, modo, ahora),
    )
    conn.commit()


# ── Intentos de reinicio (specs/021-remediacion-contenedores/) ──────────


def insert_intento_reinicio(conn: sqlite3.Connection, intento: IntentoReinicio) -> int:
    creado_en = intento.creado_en or _now_iso()
    nuevo_id = _siguiente_id_compartido(conn)
    conn.execute(
        """INSERT INTO intentos_reinicio
           (id, contenedor, modo_en_deteccion, episodio_id, accion_recomendada,
            razonamiento_deepseek, coste_eur, estado, detalle, creado_en, resuelto_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            nuevo_id,
            intento.contenedor,
            intento.modo_en_deteccion,
            intento.episodio_id,
            intento.accion_recomendada,
            intento.razonamiento_deepseek,
            intento.coste_eur,
            intento.estado,
            intento.detalle,
            creado_en,
            intento.resuelto_en,
        ),
    )
    conn.commit()
    return nuevo_id


def _fila_a_intento_reinicio(row: sqlite3.Row) -> IntentoReinicio:
    return IntentoReinicio(
        id=row["id"],
        contenedor=row["contenedor"],
        modo_en_deteccion=row["modo_en_deteccion"],
        episodio_id=row["episodio_id"],
        accion_recomendada=row["accion_recomendada"],
        razonamiento_deepseek=row["razonamiento_deepseek"],
        coste_eur=row["coste_eur"],
        estado=row["estado"],
        detalle=row["detalle"],
        creado_en=row["creado_en"],
        resuelto_en=row["resuelto_en"],
    )


def get_intento_reinicio(conn: sqlite3.Connection, intento_id: int) -> IntentoReinicio | None:
    row = conn.execute(
        "SELECT * FROM intentos_reinicio WHERE id = ?", (intento_id,)
    ).fetchone()
    return _fila_a_intento_reinicio(row) if row is not None else None


def update_intento_reinicio_estado(
    conn: sqlite3.Connection, intento_id: int, estado: str, detalle: str
) -> None:
    conn.execute(
        "UPDATE intentos_reinicio SET estado = ?, detalle = ?, resuelto_en = ? WHERE id = ?",
        (estado, detalle, _now_iso(), intento_id),
    )
    conn.commit()


def intento_reciente_pendiente_o_sin_evaluar(conn: sqlite3.Connection, contenedor: str) -> bool:
    """Evita evaluar de nuevo un contenedor que ya tiene un intento sin
    resolver — mismo criterio de "no duplicar" que pendiente_existente()
    de rotar_log, ampliado a sin_evaluar (que tampoco es un desenlace
    final)."""
    row = conn.execute(
        "SELECT 1 FROM intentos_reinicio WHERE contenedor = ? "
        "AND estado IN ('pendiente', 'sin_evaluar') LIMIT 1",
        (contenedor,),
    ).fetchone()
    return row is not None


def listar_pendientes_reinicio(conn: sqlite3.Connection) -> list[IntentoReinicio]:
    rows = conn.execute(
        "SELECT * FROM intentos_reinicio WHERE estado = 'pendiente' ORDER BY id"
    ).fetchall()
    return [_fila_a_intento_reinicio(r) for r in rows]


def intentos_recientes_contenedor(
    conn: sqlite3.Connection, contenedor: str, desde_iso: str
) -> list[IntentoReinicio]:
    """Intentos de `contenedor` creados desde `desde_iso` (inclusive) —
    alimenta el cortacircuito (US3) y el contador de sin_evaluar
    consecutivos (FR-019)."""
    rows = conn.execute(
        "SELECT * FROM intentos_reinicio WHERE contenedor = ? AND creado_en >= ? "
        "ORDER BY id DESC",
        (contenedor, desde_iso),
    ).fetchall()
    return [_fila_a_intento_reinicio(r) for r in rows]


def sin_evaluar_consecutivos(conn: sqlite3.Connection, contenedor: str) -> int:
    """Cuenta los intentos_reinicio más recientes de `contenedor`, en
    orden descendente por id, mientras su estado sea "sin_evaluar" —
    se detiene en el primero que no lo sea, o devuelve 0 si no hay
    ninguno (FR-019)."""
    rows = conn.execute(
        "SELECT estado FROM intentos_reinicio WHERE contenedor = ? ORDER BY id DESC",
        (contenedor,),
    ).fetchall()
    racha = 0
    for row in rows:
        if row["estado"] != "sin_evaluar":
            break
        racha += 1
    return racha


def intento_reinicio_vigente(conn: sqlite3.Connection, contenedor: str) -> IntentoReinicio | None:
    """El intento más reciente de `contenedor` que sigue siendo
    relevante "ahora mismo" — specs/022-clasificacion-remediacion/,
    data-model.md: en estado `pendiente`/`sin_evaluar`/`sin_accion`
    (nunca resueltos, siguen abiertos), o el `ejecutado`/`fallido`/
    `rechazado` más reciente si su `resuelto_en` está dentro de
    `REMEDIACION_INTENTO_VIGENTE_MINUTOS`. `None` si no hay ninguno —
    solo lectura, sin efectos. Alimenta el campo `intento_vigente` del
    snapshot (User Story 3)."""
    row = conn.execute(
        "SELECT * FROM intentos_reinicio WHERE contenedor = ? "
        "AND estado IN ('pendiente', 'sin_evaluar', 'sin_accion') "
        "ORDER BY id DESC LIMIT 1",
        (contenedor,),
    ).fetchone()
    if row is not None:
        return _fila_a_intento_reinicio(row)

    row = conn.execute(
        "SELECT * FROM intentos_reinicio WHERE contenedor = ? "
        "AND estado IN ('ejecutado', 'fallido', 'rechazado') "
        "ORDER BY id DESC LIMIT 1",
        (contenedor,),
    ).fetchone()
    if row is None or row["resuelto_en"] is None:
        return None
    try:
        resuelto_en = datetime.fromisoformat(row["resuelto_en"])
    except ValueError:
        return None
    ahora = datetime.now(resuelto_en.tzinfo) if resuelto_en.tzinfo else datetime.now()
    limite = timedelta(minutes=REMEDIACION_INTENTO_VIGENTE_MINUTOS)
    if ahora - resuelto_en > limite:
        return None
    return _fila_a_intento_reinicio(row)


# ── Intentos de agente (specs/026-reiniciar-agentes-relays/) ────────────


def insert_intento_agente(conn: sqlite3.Connection, intento: IntentoAgente) -> int:
    creado_en = intento.creado_en or _now_iso()
    nuevo_id = _siguiente_id_compartido(conn)
    conn.execute(
        """INSERT INTO intentos_agente
           (id, label, modo_en_deteccion, episodio_id, accion_recomendada,
            razonamiento_deepseek, coste_eur, estado, detalle, creado_en, resuelto_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            nuevo_id,
            intento.label,
            intento.modo_en_deteccion,
            intento.episodio_id,
            intento.accion_recomendada,
            intento.razonamiento_deepseek,
            intento.coste_eur,
            intento.estado,
            intento.detalle,
            creado_en,
            intento.resuelto_en,
        ),
    )
    conn.commit()
    return nuevo_id


def _fila_a_intento_agente(row: sqlite3.Row) -> IntentoAgente:
    return IntentoAgente(
        id=row["id"],
        label=row["label"],
        modo_en_deteccion=row["modo_en_deteccion"],
        episodio_id=row["episodio_id"],
        accion_recomendada=row["accion_recomendada"],
        razonamiento_deepseek=row["razonamiento_deepseek"],
        coste_eur=row["coste_eur"],
        estado=row["estado"],
        detalle=row["detalle"],
        creado_en=row["creado_en"],
        resuelto_en=row["resuelto_en"],
    )


def get_intento_agente(conn: sqlite3.Connection, intento_id: int) -> IntentoAgente | None:
    row = conn.execute(
        "SELECT * FROM intentos_agente WHERE id = ?", (intento_id,)
    ).fetchone()
    return _fila_a_intento_agente(row) if row is not None else None


def update_intento_agente_estado(
    conn: sqlite3.Connection, intento_id: int, estado: str, detalle: str
) -> None:
    conn.execute(
        "UPDATE intentos_agente SET estado = ?, detalle = ?, resuelto_en = ? WHERE id = ?",
        (estado, detalle, _now_iso(), intento_id),
    )
    conn.commit()


def intento_reciente_pendiente_o_sin_evaluar_agente(conn: sqlite3.Connection, label: str) -> bool:
    """Evita evaluar de nuevo un agente que ya tiene un intento sin
    resolver — mismo criterio que `intento_reciente_pendiente_o_sin_evaluar`
    de contenedores."""
    row = conn.execute(
        "SELECT 1 FROM intentos_agente WHERE label = ? "
        "AND estado IN ('pendiente', 'sin_evaluar') LIMIT 1",
        (label,),
    ).fetchone()
    return row is not None


def listar_pendientes_agente(conn: sqlite3.Connection) -> list[IntentoAgente]:
    rows = conn.execute(
        "SELECT * FROM intentos_agente WHERE estado = 'pendiente' ORDER BY id"
    ).fetchall()
    return [_fila_a_intento_agente(r) for r in rows]


def intentos_recientes_agente(
    conn: sqlite3.Connection, label: str, desde_iso: str
) -> list[IntentoAgente]:
    """Intentos de `label` creados desde `desde_iso` (inclusive) —
    alimenta el cortacircuito compartido y el contador de sin_evaluar
    consecutivos (FR-009/FR-014)."""
    rows = conn.execute(
        "SELECT * FROM intentos_agente WHERE label = ? AND creado_en >= ? "
        "ORDER BY id DESC",
        (label, desde_iso),
    ).fetchall()
    return [_fila_a_intento_agente(r) for r in rows]


def sin_evaluar_consecutivos_agente(conn: sqlite3.Connection, label: str) -> int:
    """Cuenta los intentos_agente más recientes de `label`, en orden
    descendente por id, mientras su estado sea "sin_evaluar" — se
    detiene en el primero que no lo sea, o devuelve 0 si no hay
    ninguno (FR-014)."""
    rows = conn.execute(
        "SELECT estado FROM intentos_agente WHERE label = ? ORDER BY id DESC",
        (label,),
    ).fetchall()
    racha = 0
    for row in rows:
        if row["estado"] != "sin_evaluar":
            break
        racha += 1
    return racha


def intento_agente_vigente(conn: sqlite3.Connection, label: str) -> IntentoAgente | None:
    """El intento más reciente de `label` que sigue siendo relevante
    "ahora mismo" — mismo criterio que `intento_reinicio_vigente()`:
    en estado `pendiente`/`sin_evaluar`/`sin_accion` (nunca resueltos),
    o el `ejecutado`/`fallido`/`rechazado` más reciente si su
    `resuelto_en` está dentro de `REMEDIACION_INTENTO_VIGENTE_MINUTOS`.
    `None` si no hay ninguno."""
    row = conn.execute(
        "SELECT * FROM intentos_agente WHERE label = ? "
        "AND estado IN ('pendiente', 'sin_evaluar', 'sin_accion') "
        "ORDER BY id DESC LIMIT 1",
        (label,),
    ).fetchone()
    if row is not None:
        return _fila_a_intento_agente(row)

    row = conn.execute(
        "SELECT * FROM intentos_agente WHERE label = ? "
        "AND estado IN ('ejecutado', 'fallido', 'rechazado') "
        "ORDER BY id DESC LIMIT 1",
        (label,),
    ).fetchone()
    if row is None or row["resuelto_en"] is None:
        return None
    try:
        resuelto_en = datetime.fromisoformat(row["resuelto_en"])
    except ValueError:
        return None
    ahora = datetime.now(resuelto_en.tzinfo) if resuelto_en.tzinfo else datetime.now()
    limite = timedelta(minutes=REMEDIACION_INTENTO_VIGENTE_MINUTOS)
    if ahora - resuelto_en > limite:
        return None
    return _fila_a_intento_agente(row)


def localizar_intento(
    conn: sqlite3.Connection, intento_id: int
) -> tuple[str, IntentoRemediacion | IntentoReinicio | IntentoAgente] | None:
    """Busca `intento_id` primero en intentos_remediacion, luego en
    intentos_reinicio, luego en intentos_agente — para que
    pendientes/aprobar/rechazar/deshacer resuelvan sobre la tabla que
    corresponda (contracts/cli.md de 021, ampliado en 026)."""
    intento = get_intento(conn, intento_id)
    if intento is not None:
        return ("remediacion", intento)
    intento_reinicio = get_intento_reinicio(conn, intento_id)
    if intento_reinicio is not None:
        return ("reinicio", intento_reinicio)
    intento_agente = get_intento_agente(conn, intento_id)
    if intento_agente is not None:
        return ("agente", intento_agente)
    return None
