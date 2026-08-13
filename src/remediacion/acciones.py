"""acciones — El único tipo de acción de esta primera versión:
rotar_log. Condición determinista, sin DeepSeek (FR-013, research.md
§1 de specs/019-remediacion-automatica/).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .model import IntentoRemediacion
from .store import (
    get_intento,
    get_modo,
    insert_intento,
    pendiente_existente,
    update_intento_estado,
)

_DEFAULT_SNAPSHOT_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json"
)


def _snapshot_path() -> Path:
    return Path(os.environ.get("REMEDIACION_SNAPSHOT_PATH", _DEFAULT_SNAPSHOT_PATH))

REMEDIACION_LOGS_DIR = Path(
    os.environ.get("REMEDIACION_LOGS_DIR", str(Path.home() / "Library/Logs"))
)  # research.md §3 — configurable para poder probar por CLI sin
# tocar los logs reales; los nombres de fichero de abajo NO son
# configurables (universo cerrado, mismo criterio que MONITOR_JOBS de
# la feature 017).

UMBRAL_ROTACION_BYTES_DEFAULT = int(
    os.environ.get("REMEDIACION_UMBRAL_ROTACION_BYTES", str(10 * 1024 * 1024))  # 10 MB
)

# (nombre, nombre_fichero, umbral_bytes) — lista cerrada, ampliada el
# 2026-08-13 (research.md §7 de 019) a los 17 logs reales que escriben
# los LaunchAgents `amsterdam9.*` en ~/Library/Logs (StandardOutPath/
# StandardErrorPath, confirmado por grep directo sobre los .plist
# reales — no una lista aproximada de `ls`). Excluye
# `~/.hermes/profiles/bautista/logs/`, ya cubierta por
# `rotate_hermes_logs.sh` (mecanismo distinto, research.md §7).
# Ninguno pertenece a un componente crítico (spec.md Assumptions,
# FR-012) — todos son logs de monitores/automatizaciones, no de los
# contenedores críticos en sí.
LOGS_VIGILADOS: list[tuple[str, str, int]] = [
    ("health-docker", "health-docker.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("health-ha", "health-ha.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("health-dns-pi", "health-dns-pi.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("health-dns-pi-err", "health-dns-pi.err.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("health-telegram", "health-telegram.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("dashboard-socat", "dashboard-socat.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("dashboard-socat-err", "dashboard-socat.err.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("dashboard-disk", "dashboard-disk.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("dashboard-disk-err", "dashboard-disk.err.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("hermes-dashboard", "hermes-dashboard.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("hermes-dashboard-err", "hermes-dashboard.err.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("beszel-hosts-reader", "beszel-hosts-reader.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("beszel-hosts-reader-err", "beszel-hosts-reader.err.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("gbrain-reindex", "gbrain-reindex.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("immich-album-sync", "immich-album-sync.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("inventario-cobertura", "inventario-cobertura.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("morning-report", "morning-report.log", UMBRAL_ROTACION_BYTES_DEFAULT),
]

TIPO_ACCION_ROTAR_LOG = "rotar_log"

# Registro de todos los tipos de acción que existen en el código, sepan o no
# de ellos configuracion_accion todavía (esa tabla solo tiene fila para un
# tipo tras su primer get_modo()). Única fuente de verdad para "qué tipos
# de acción existen" — extender aquí cuando se añada un segundo tipo.
TIPOS_ACCION = (TIPO_ACCION_ROTAR_LOG,)

# Mismo número que ya usa rotate_hermes_logs.sh (KEEP=4) para el otro
# mecanismo de rotación del homelab — sin este límite,
# ~/Library/Logs/ acumularía ficheros .rotado-* sin fin. Confirmado
# con Miquel el 2026-08-13.
ROTACIONES_A_CONSERVAR = 4


def _marca_tiempo_compacta() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _purgar_rotaciones_antiguas(ruta_original: Path) -> None:
    """Conserva como mucho ROTACIONES_A_CONSERVAR ficheros
    `<nombre>.rotado-*` para este log — borra los más antiguos por
    fecha (el formato `%Y%m%dT%H%M%S` ordena igual alfabéticamente que
    cronológicamente). Nunca lanza: un fallo al purgar no debe romper
    la rotación que ya se hizo."""
    try:
        rotaciones = sorted(ruta_original.parent.glob(f"{ruta_original.name}.rotado-*"))
        de_mas = len(rotaciones) - ROTACIONES_A_CONSERVAR
        for antigua in rotaciones[:de_mas] if de_mas > 0 else []:
            antigua.unlink(missing_ok=True)
    except OSError:
        pass


def ejecutar_rotar_log(ruta: Path) -> str:
    """Renombra `ruta` a `ruta.rotado-<marca>` y crea un fichero vacío
    nuevo en su lugar — nunca trunca ni borra (research.md §4,
    FR-009). Devuelve la ruta del fichero rotado, como texto. Purga
    las rotaciones más antiguas si ya hay más de
    ROTACIONES_A_CONSERVAR para este log (research.md §8 de 019)."""
    rotado = ruta.with_name(f"{ruta.name}.rotado-{_marca_tiempo_compacta()}")
    ruta.rename(rotado)
    ruta.touch()
    _purgar_rotaciones_antiguas(ruta)
    return str(rotado)


def deshacer_rotar_log(ruta_original: Path, ruta_rotada: Path) -> str | None:
    """Procedimiento de dos pasos (research.md §4): si `ruta_original`
    tiene contenido escrito después de la rotación, se conserva
    renombrándola aparte antes de restaurar — nunca se sobreescribe
    (FR-010). Devuelve la ruta del fichero de "tras-deshacer" si se
    creó uno, o `None` si no hizo falta."""
    conservado = None
    if ruta_original.exists() and ruta_original.stat().st_size > 0:
        conservado = ruta_original.with_name(
            f"{ruta_original.name}.tras-deshacer-{_marca_tiempo_compacta()}"
        )
        ruta_original.rename(conservado)
    ruta_rotada.rename(ruta_original)
    return str(conservado) if conservado is not None else None


def comprobar_rotar_log(conn: sqlite3.Connection) -> list[IntentoRemediacion]:
    """Recorre LOGS_VIGILADOS; para cada uno por encima de su umbral,
    sin ya un intento `pendiente` (FR-008), crea un intento — en modo
    manual queda `pendiente`; en modo automático se ejecuta en la
    misma llamada (FR-006/FR-007). Un fichero de la lista que no
    existe se ignora sin lanzar. Devuelve los intentos creados."""
    modo = get_modo(conn, TIPO_ACCION_ROTAR_LOG)
    creados: list[IntentoRemediacion] = []

    for nombre, nombre_fichero, umbral_bytes in LOGS_VIGILADOS:
        ruta = REMEDIACION_LOGS_DIR / nombre_fichero
        if not ruta.exists():
            continue
        tamano = ruta.stat().st_size
        if tamano <= umbral_bytes:
            continue
        if pendiente_existente(conn, TIPO_ACCION_ROTAR_LOG, nombre):
            continue

        detalle = f"{ruta} — {tamano} bytes, umbral {umbral_bytes} bytes"
        intento = IntentoRemediacion(
            tipo_accion=TIPO_ACCION_ROTAR_LOG,
            componente=nombre,
            ruta=str(ruta),
            modo_en_deteccion=modo,
            estado="pendiente",
            detalle=detalle,
        )
        intento_id = insert_intento(conn, intento)
        intento.id = intento_id

        if modo == "automatico":
            _resolver_ejecucion(conn, intento_id, ruta)
            intento = get_intento(conn, intento_id)

        creados.append(intento)

    return creados


def _resolver_ejecucion(conn: sqlite3.Connection, intento_id: int, ruta: Path) -> None:
    """Ejecuta la rotación real para `intento_id` y actualiza su
    estado — compartido por `aprobar` (User Story 2) y por el modo
    automático (User Story 4), mismo procedimiento en los dos casos."""
    try:
        fichero_rotado = ejecutar_rotar_log(ruta)
    except OSError as e:
        update_intento_estado(conn, intento_id, "fallido", f"no se pudo rotar: {e}")
        return
    update_intento_estado(
        conn, intento_id, "ejecutado", f"rotado a {fichero_rotado}", fichero_rotado
    )


def resolver_aprobacion(conn: sqlite3.Connection, intento_id: int) -> IntentoRemediacion:
    """User Story 2: aprueba un intento `pendiente` — ejecuta la
    rotación en la misma llamada. Exige que exista y esté `pendiente`
    (FR-006, Edge Cases de spec.md)."""
    intento = get_intento(conn, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")

    ruta = Path(intento.ruta)
    if not ruta.exists():
        update_intento_estado(conn, intento_id, "fallido", f"{ruta} ya no existe")
    else:
        _resolver_ejecucion(conn, intento_id, ruta)
    return get_intento(conn, intento_id)


def resolver_rechazo(conn: sqlite3.Connection, intento_id: int) -> IntentoRemediacion:
    """User Story 2: rechaza un intento `pendiente` — el fichero no se
    toca. Exige que exista y esté `pendiente`."""
    intento = get_intento(conn, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")
    update_intento_estado(conn, intento_id, "rechazado", "rechazado por Miquel")
    return get_intento(conn, intento_id)


def resolver_deshacer(conn: sqlite3.Connection, intento_id: int) -> IntentoRemediacion:
    """User Story 5: deshace un intento `ejecutado`. Exige que exista
    y esté `ejecutado` (FR-010, Edge Cases de spec.md), y que su
    fichero rotado todavía exista — la purga de retención
    (ROTACIONES_A_CONSERVAR, research.md §8 de 019) puede haberlo
    borrado si han pasado más de 4 rotaciones desde entonces."""
    intento = get_intento(conn, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "ejecutado":
        raise ValueError(f"intento {intento_id} no está ejecutado (estado={intento.estado})")
    if not intento.fichero_rotado:
        raise ValueError(f"intento {intento_id} no tiene fichero rotado registrado")
    if not Path(intento.fichero_rotado).exists():
        raise ValueError(
            f"intento {intento_id}: {intento.fichero_rotado} ya no existe "
            f"(purgado por retención — más de {ROTACIONES_A_CONSERVAR} rotaciones después)"
        )

    conservado = deshacer_rotar_log(Path(intento.ruta), Path(intento.fichero_rotado))
    detalle = "deshecho"
    if conservado:
        detalle += f" — contenido posterior conservado en {conservado}"
    update_intento_estado(conn, intento_id, "deshecho", detalle)
    return get_intento(conn, intento_id)


def escribir_snapshot(conn: sqlite3.Connection) -> None:
    """Escribe `remediacion_estado.json` con el estado real de los 17
    logs vigilados y el modo vigente de `rotar_log` — feature 020,
    para que el dashboard (sin acceso a REMEDIACION_LOGS_DIR) pueda
    leerlo sin montar ningún volumen nuevo (research.md §1/§2 de
    specs/020-visor-remediacion/). Incluye dos totales (research.md
    §9): el de los ficheros activos, y el de activos + sus rotaciones
    archivadas — para que Miquel vea de un vistazo cuánto ocupa todo
    junto, no solo log a log. Nunca lanza: un fallo de escritura no
    debe tumbar `comprobar` (contracts/snapshot-json.md, garantía 1)."""
    modo = get_modo(conn, TIPO_ACCION_ROTAR_LOG)
    logs = []
    total_activos = 0
    total_con_rotaciones = 0
    for nombre, nombre_fichero, umbral_bytes in LOGS_VIGILADOS:
        ruta = REMEDIACION_LOGS_DIR / nombre_fichero
        tamano = ruta.stat().st_size if ruta.exists() else 0
        rotaciones_bytes = sum(
            p.stat().st_size for p in ruta.parent.glob(f"{ruta.name}.rotado-*")
        )
        logs.append({
            "nombre": nombre,
            "tamano_bytes": tamano,
            "umbral_bytes": umbral_bytes,
            "supera_umbral": tamano > umbral_bytes,
        })
        total_activos += tamano
        total_con_rotaciones += tamano + rotaciones_bytes

    payload = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "modo_rotar_log": modo,
        "total_activos_bytes": total_activos,
        "total_con_rotaciones_bytes": total_con_rotaciones,
        "logs": logs,
    }
    try:
        destino = _snapshot_path()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except OSError:
        pass
