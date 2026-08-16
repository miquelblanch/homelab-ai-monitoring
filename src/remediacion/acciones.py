"""acciones — El único tipo de acción de esta primera versión:
rotar_log. Condición determinista, sin DeepSeek (FR-013, research.md
§1 de specs/019-remediacion-automatica/).
"""

from __future__ import annotations

import json
import os
import sqlite3
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from diagnostico import evidencia as diagnostico_evidencia
from diagnostico import gasto as diagnostico_gasto
from diagnostico.deepseek import llamar_deepseek as diagnostico_llamar_deepseek

from . import _homelab_bridge as bridge
from . import clasificacion
from . import deepseek_agentes
from . import deepseek_contenedores
from .model import IntentoAgente, IntentoReinicio, IntentoRemediacion
from .store import (
    get_intento,
    get_intento_agente,
    get_intento_reinicio,
    get_modo,
    get_modo_contenedor,
    insert_intento,
    insert_intento_agente,
    insert_intento_reinicio,
    intento_agente_vigente,
    intento_reciente_pendiente_o_sin_evaluar,
    intento_reciente_pendiente_o_sin_evaluar_agente,
    intento_reinicio_vigente,
    intento_vigente as store_intento_vigente,
    pendiente_existente,
    sin_evaluar_consecutivos,
    sin_evaluar_consecutivos_agente,
    update_intento_agente_estado,
    update_intento_estado,
    update_intento_reinicio_estado,
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

# specs/021-remediacion-contenedores/ — segundo tipo de acción real. A
# diferencia de rotar_log, la decisión de si aplica no es una condición
# fija: la elige DeepSeek con evidencia real (deepseek_contenedores.py).
TIPO_ACCION_REINICIAR_CONTENEDOR = "reiniciar_contenedor"

# specs/026-reiniciar-agentes-relays/ — tercer tipo de acción real,
# mismo patrón que reiniciar_contenedor (DeepSeek decide, nunca una
# condición fija) pero por tipo de acción, no por instancia (FR-008 de
# 026): un LaunchAgent/LaunchDaemon no tiene eje crítico/no-crítico,
# así que no hace falta una tabla de configuración por-componente como
# configuracion_contenedor.
TIPO_ACCION_REINICIAR_AGENTE = "reiniciar_agente"

# Registro de todos los tipos de acción que existen en el código, sepan o no
# de ellos configuracion_accion todavía (esa tabla solo tiene fila para un
# tipo tras su primer get_modo()). Única fuente de verdad para "qué tipos
# de acción existen".
TIPOS_ACCION = (
    TIPO_ACCION_ROTAR_LOG,
    TIPO_ACCION_REINICIAR_CONTENEDOR,
    TIPO_ACCION_REINICIAR_AGENTE,
)

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


def _notificar_telegram(texto: str) -> bool:
    """Envío crudo compartido por todos los avisos de este paquete —
    nunca lanza, devuelve False si no se pudo enviar por cualquier
    motivo. Mismo patrón que `inventory.deliver._send_raw`."""
    token, chat_id = bridge.telegram_credentials()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _notificar_fallo_automatico(componente: str, detalle: str) -> bool:
    """Único aviso de rotar_log — solo cuando una rotación en modo
    automático falla (FR-014 enmendado, research.md §11 de 019). El
    éxito nunca notifica, ni tampoco un fallo en modo manual (ahí ya
    hay un humano mirando el resultado del propio comando)."""
    return _notificar_telegram(f"⚠️ remediación — rotar_log falló (automático)\n{componente}: {detalle}")


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
            if intento.estado == "fallido":
                _notificar_fallo_automatico(intento.componente, intento.detalle)

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


def _intento_vigente_a_dict(intento: IntentoReinicio | IntentoAgente | None) -> dict | None:
    if intento is None:
        return None
    return {
        "estado": intento.estado,
        "detalle": intento.detalle,
        "creado_en": intento.creado_en,
    }


def _snapshot_contenedores(conn: sqlite3.Connection) -> list[dict]:
    """Bloque `contenedores` del snapshot (specs/022-clasificacion-remediacion/,
    research.md §3): los 39 contenedores conocidos —no solo los
    evaluables—, con su clasificación derivada y su intento vigente si
    lo hay. Un fallo al procesar un contenedor concreto lo omite del
    array, no aborta el resto (contracts/cli.md garantía 20)."""
    criticos = bridge.docker_critical()
    never_restart = bridge.docker_never_restart()
    contenedores = []
    for c in bridge.listar_contenedores():
        nombre = c.get("name")
        if not nombre:
            continue
        try:
            es_critico = nombre in criticos
            es_never_restart = nombre in never_restart
            modo = None if (es_critico or es_never_restart) else get_modo_contenedor(conn, nombre)
            contenedores.append({
                "nombre": nombre,
                "critico": es_critico,
                "never_restart": es_never_restart,
                "clasificacion": clasificacion.clasificar_contenedor(
                    nombre, criticos, never_restart, modo
                ),
                "modo": modo,
                "intento_vigente": _intento_vigente_a_dict(
                    intento_reinicio_vigente(conn, nombre)
                ),
            })
        except Exception:
            continue
    return contenedores


def _snapshot_agentes(conn: sqlite3.Connection) -> list[dict]:
    """Bloque `agentes` del snapshot (specs/026-reiniciar-agentes-relays/,
    contracts/snapshot-json.md): los candidatos conocidos
    (`amsterdam9.*`/`com.homeassistant.*`), con su clasificación,
    estado del permiso `sudoers` para los que lo necesitan (FR-023), y
    su intento vigente si lo hay. Un fallo al procesar un agente
    concreto lo omite del array, no aborta el resto (garantía 9)."""
    modo = get_modo(conn, TIPO_ACCION_REINICIAR_AGENTE)
    agentes = []
    for a in bridge.listar_agentes_conocidos():
        label = a.get("label")
        if not label:
            continue
        try:
            requiere_sudo = bool(a.get("requiere_sudo"))
            sudoers_instalado = bridge.sudoers_permitido(label) if requiere_sudo else None
            agentes.append({
                "label": label,
                "tipo": "com.homeassistant" if requiere_sudo else "amsterdam9",
                "running": bool(a.get("running")),
                "clasificacion": clasificacion.clasificar_agente(label, modo),
                "sudoers_instalado": sudoers_instalado,
                "intento_vigente": _intento_vigente_a_dict(
                    intento_agente_vigente(conn, label)
                ),
            })
        except Exception:
            continue
    return agentes


def escribir_snapshot(conn: sqlite3.Connection) -> None:
    """Escribe `remediacion_estado.json` con el estado real de los 17
    logs vigilados, el modo vigente de `rotar_log` (feature 020), y —
    desde specs/022-clasificacion-remediacion/ — un bloque `contenedores`
    con la clasificación Manual/Automática/IA y el intento vigente de
    cada uno (research.md §3), para que el dashboard (sin acceso a
    REMEDIACION_LOGS_DIR ni a `remediacion.db`) pueda pintar la columna
    de Inventario y el estado real en Alarmas sin montar ningún volumen
    nuevo. Desde specs/026-reiniciar-agentes-relays/, también un bloque
    `agentes` (mismo nivel que `contenedores`), con `sudoers_instalado`
    para los `com.homeassistant.*` (FR-023). Incluye dos totales de
    logs (research.md §9 de 020): el de los ficheros activos, y el de
    activos + sus rotaciones archivadas. Nunca lanza: un fallo de
    escritura no debe tumbar `comprobar` (contracts/snapshot-json.md
    garantía 1; contracts/cli.md garantía 20)."""
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
        try:
            intento_vigente_log = _intento_vigente_a_dict(
                store_intento_vigente(conn, TIPO_ACCION_ROTAR_LOG, nombre)
            )
        except Exception:
            intento_vigente_log = None
        logs.append({
            "nombre": nombre,
            "tamano_bytes": tamano,
            "umbral_bytes": umbral_bytes,
            "supera_umbral": tamano > umbral_bytes,
            "clasificacion": clasificacion.clasificar_log(modo),
            "intento_vigente": intento_vigente_log,
        })
        total_activos += tamano
        total_con_rotaciones += tamano + rotaciones_bytes

    try:
        contenedores = _snapshot_contenedores(conn)
    except Exception:
        contenedores = []

    try:
        agentes = _snapshot_agentes(conn)
    except Exception:
        agentes = []

    payload = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "modo_rotar_log": modo,
        "total_activos_bytes": total_activos,
        "total_con_rotaciones_bytes": total_con_rotaciones,
        "logs": logs,
        "contenedores": contenedores,
        "agentes": agentes,
    }
    try:
        destino = _snapshot_path()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except OSError:
        pass


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────
#
# A diferencia de rotar_log, la decisión no es una condición fija: para
# cada contenedor no crítico caído se reúne evidencia real y se le
# pregunta a DeepSeek si reiniciar_contenedor aplica (research.md §1-§3).
#
# Desde specs/022-clasificacion-remediacion/, la evaluación también
# cubre los contenedores críticos — con el modo siempre forzado a
# "manual" (nunca se lee ni se admite "automatico" para ellos,
# Principio VII enmendado). La clasificación Manual/Automática/IA que
# se muestra en Inventario vive en el módulo puro `clasificacion.py`,
# no aquí — este fichero solo la consume al escribir el snapshot.

REMEDIACION_DEEPSEEK_MODEL_DEFAULT = "deepseek-v4-flash"

# Mismos valores por defecto que docker_monitor.CB_MAX_ATTEMPTS/
# CB_WINDOW_HOURS — configurables para poder probar el cortacircuito
# por CLI sin esperar 6 horas reales (contracts/cli.md de 021).
REMEDIACION_CB_MAX_INTENTOS = int(os.environ.get("REMEDIACION_CB_MAX_INTENTOS", "3"))
REMEDIACION_CB_VENTANA_HORAS = int(os.environ.get("REMEDIACION_CB_VENTANA_HORAS", "6"))

# FR-019 — contrapartida del Principio VII enmendado (constitution.md
# v2.0.0): mismo número que el cortacircuito por familiaridad, pero es
# un mecanismo independiente (no cuenta reinicios, cuenta evaluaciones
# sin poder decidir).
REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS = int(
    os.environ.get("REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS", "3")
)


def _modelo_deepseek() -> str:
    return os.environ.get("REMEDIACION_DEEPSEEK_MODEL", REMEDIACION_DEEPSEEK_MODEL_DEFAULT)


def _estimar_tokens_entrada(prompt: str) -> int:
    """Estimación previa a la llamada — ~4 caracteres por token, misma
    regla aproximada que ya usa `diagnostico.deepseek` (no se importa
    esa función privada, se replica la fórmula: solo decide si se
    llama o no, gasto.hay_presupuesto)."""
    return max(1, len(prompt) // 4)


def _notificar_sin_accion(contenedor: str, razonamiento: str) -> bool:
    """FR-009/FR-012d — DeepSeek concluyó que ninguna acción de la
    lista cerrada aplica: aviso con su razonamiento, no silencio."""
    return _notificar_telegram(
        f"ℹ️ remediación — {contenedor}: ninguna acción de la lista cerrada aplica\n{razonamiento}"
    )


def _notificar_cortacircuito(contenedor: str, detalle: str) -> bool:
    """FR-011/FR-012a — el cortacircuito impide un nuevo intento."""
    return _notificar_telegram(
        f"🔴 remediación — {contenedor} en bucle de reinicios\n{detalle}\n"
        f"⛔ Reinicio automático detenido — requiere intervención"
    )


def _notificar_sin_evaluar_persistente(contenedor: str, racha: int) -> bool:
    """FR-019 — contrapartida del Principio VII enmendado: una
    incapacidad persistente de evaluar (sin presupuesto, sin respuesta
    de DeepSeek) nunca queda en silencio."""
    return _notificar_telegram(
        f"⚠️ remediación — {contenedor}: {racha} evaluaciones seguidas sin poder "
        f"decidir (sin presupuesto o sin respuesta de DeepSeek) — revisar"
    )


def _crear_intento_reinicio(
    conn: sqlite3.Connection,
    contenedor: str,
    modo: str,
    episodio_id: int | None,
    estado: str,
    detalle: str,
    accion_recomendada: str | None = None,
    razonamiento: str | None = None,
    coste_eur: float | None = None,
) -> IntentoReinicio:
    """Crea y persiste un intento_reinicio — punto único de escritura
    para que el aviso de FR-019 (sin_evaluar persistente) se evalúe
    siempre, sin depender de que cada rama de evaluar_contenedor se
    acuerde de comprobarlo por separado."""
    intento = IntentoReinicio(
        contenedor=contenedor,
        modo_en_deteccion=modo,
        episodio_id=episodio_id,
        accion_recomendada=accion_recomendada,
        razonamiento_deepseek=razonamiento,
        coste_eur=coste_eur,
        estado=estado,
        detalle=detalle,
    )
    intento.id = insert_intento_reinicio(conn, intento)
    if estado == "sin_evaluar":
        racha = sin_evaluar_consecutivos(conn, contenedor)
        if racha >= REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS:
            _notificar_sin_evaluar_persistente(contenedor, racha)
    return intento


def evaluar_contenedor(
    conn_remediacion: sqlite3.Connection,
    conn_diagnostico: sqlite3.Connection,
    contenedor: str,
    modo_forzado: str | None = None,
) -> IntentoReinicio:
    """Orquesta la decisión de DeepSeek para un contenedor caído
    (data-model.md de 021, ampliado por 022): congelar_vivo →
    hay_presupuesto (o REMEDIACION_DEEPSEEK_MOCK) → llamar_deepseek →
    parsear → crea el intento_reinicio en el estado que corresponda.

    `modo_forzado` (specs/022-clasificacion-remediacion/, research.md
    §1): si no es `None`, se usa en vez de `get_modo_contenedor(...)`
    — la tabla `configuracion_contenedor` no se consulta en absoluto
    para este contenedor. El llamador (`comprobar_reiniciar_contenedor`)
    pasa `modo_forzado="manual"` para un contenedor crítico — nunca
    lee ni admite que sea `"automatico"` para él (FR-008, Principio
    VII). El llamador sigue siendo responsable de excluir NEVER_RESTART
    (FR-007) — esta función nunca lo comprueba porque nunca debería
    recibirlo."""
    modo = modo_forzado if modo_forzado is not None else get_modo_contenedor(conn_remediacion, contenedor)
    episodio = diagnostico_evidencia.congelar_vivo(conn_diagnostico, contenedor)

    mock = deepseek_contenedores.respuesta_mock()
    if mock is not None:
        parsed = mock
        coste: float | None = None
    else:
        prompt = deepseek_contenedores.construir_prompt_remediacion(episodio, TIPOS_ACCION)
        if not diagnostico_gasto.hay_presupuesto(
            conn_diagnostico, _estimar_tokens_entrada(prompt)
        ):
            return _crear_intento_reinicio(
                conn_remediacion, contenedor, modo, episodio.id,
                estado="sin_evaluar",
                detalle="sin presupuesto diario disponible para preguntar a DeepSeek",
            )
        respuesta = diagnostico_llamar_deepseek(prompt, _modelo_deepseek())
        if respuesta is None:
            return _crear_intento_reinicio(
                conn_remediacion, contenedor, modo, episodio.id,
                estado="sin_evaluar",
                detalle="DeepSeek no respondió o la llamada falló",
            )
        parsed = deepseek_contenedores.parsear_respuesta_remediacion(respuesta)
        if parsed is None:
            return _crear_intento_reinicio(
                conn_remediacion, contenedor, modo, episodio.id,
                estado="sin_evaluar",
                detalle="respuesta de DeepSeek inconsistente con el formato esperado",
            )
        coste = diagnostico_gasto.registrar_coste(
            conn_diagnostico, parsed["tokens_entrada"], parsed["tokens_salida"]
        )

    accion = parsed["accion_aplica"]
    razonamiento = parsed["razonamiento"]

    if accion is None:
        intento = _crear_intento_reinicio(
            conn_remediacion, contenedor, modo, episodio.id,
            estado="sin_accion", detalle=razonamiento,
            accion_recomendada=None, razonamiento=razonamiento, coste_eur=coste,
        )
        _notificar_sin_accion(contenedor, razonamiento)
        return intento

    # accion == TIPO_ACCION_REINICIAR_CONTENEDOR — única acción candidata hoy
    if modo == "manual":
        return _crear_intento_reinicio(
            conn_remediacion, contenedor, modo, episodio.id,
            estado="pendiente", detalle="pendiente de aprobación",
            accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
        )

    # modo == "automatico" (FR-008) — mismo cortacircuito que docker_monitor.py
    intentos_previos = bridge.recent_restart_attempts(
        conn_remediacion, contenedor, REMEDIACION_CB_VENTANA_HORAS
    )
    permite, motivo_breaker = bridge.breaker_decision(intentos_previos, REMEDIACION_CB_MAX_INTENTOS)
    if not permite:
        intento = _crear_intento_reinicio(
            conn_remediacion, contenedor, modo, episodio.id,
            estado="cortacircuito", detalle=motivo_breaker,
            accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
        )
        _notificar_cortacircuito(contenedor, motivo_breaker)
        return intento

    ejecutado = bridge.restart_container(contenedor, reason=razonamiento or "")
    estado_final = "ejecutado" if ejecutado else "fallido"
    detalle = "reiniciado y verificado" if ejecutado else "reinicio sin efecto — sigue caído"
    if ejecutado:
        # Dashboard "Pestaña Correcciones": declara "ia" solo tras
        # confirmar el reinicio — nunca antes (ver comentario en
        # _homelab_bridge.declarar_correccion_ia).
        bridge.declarar_correccion_ia("contenedores", "contenedor_caido", contenedor, razonamiento or "")
    return _crear_intento_reinicio(
        conn_remediacion, contenedor, modo, episodio.id,
        estado=estado_final, detalle=detalle,
        accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
    )


def comprobar_reiniciar_contenedor(
    conn_remediacion: sqlite3.Connection, conn_diagnostico: sqlite3.Connection
) -> list[IntentoReinicio]:
    """Recorre los contenedores que `docker_monitor.py` conoce, excluye
    solo NEVER_RESTART (FR-007 — nunca llega ni a la evidencia ni a
    DeepSeek; desde specs/022-clasificacion-remediacion/ los críticos
    ya NO se excluyen — FR-009), se queda con los que no están
    `running and healthy`, salta los que ya tienen un intento
    `pendiente`/`sin_evaluar` reciente (FR-008 de 019, mismo criterio
    "no duplicar"), y evalúa el resto. Para un contenedor crítico, el
    modo se fuerza siempre a `"manual"` (FR-008/FR-010 de 022) — nunca
    se consulta ni se admite `"automatico"` para él."""
    criticos = bridge.docker_critical()
    never_restart = bridge.docker_never_restart()
    creados: list[IntentoReinicio] = []

    for c in bridge.listar_contenedores():
        nombre = c.get("name")
        if not nombre or nombre in never_restart:
            continue
        if c.get("running") and c.get("healthy"):
            continue
        if intento_reciente_pendiente_o_sin_evaluar(conn_remediacion, nombre):
            continue
        modo_forzado = "manual" if nombre in criticos else None
        creados.append(
            evaluar_contenedor(conn_remediacion, conn_diagnostico, nombre, modo_forzado=modo_forzado)
        )

    return creados


def resolver_aprobacion_reinicio(conn: sqlite3.Connection, intento_id: int) -> IntentoReinicio:
    """User Story 2 de 021: aprueba un intento `pendiente` — ejecuta el
    reinicio en la misma llamada, con la misma verificación real que
    ya usa `docker_monitor.py` (FR-010)."""
    intento = get_intento_reinicio(conn, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")

    ejecutado = bridge.restart_container(intento.contenedor, reason=intento.razonamiento_deepseek or "")
    estado_final = "ejecutado" if ejecutado else "fallido"
    detalle = (
        "reiniciado y verificado (aprobado por Miquel)"
        if ejecutado
        else "reinicio sin efecto — sigue caído"
    )
    if ejecutado:
        # La decisión fue de DeepSeek — Miquel aprobó, pero quien
        # diagnosticó y decidió reiniciar no fue él. Clasificación "ia",
        # no "manual" (confirmado con Miquel el 2026-08-14).
        bridge.declarar_correccion_ia(
            "contenedores", "contenedor_caido", intento.contenedor,
            intento.razonamiento_deepseek or "",
        )
    update_intento_reinicio_estado(conn, intento_id, estado_final, detalle)
    return get_intento_reinicio(conn, intento_id)


def resolver_rechazo_reinicio(conn: sqlite3.Connection, intento_id: int) -> IntentoReinicio:
    """User Story 2 de 021: rechaza un intento `pendiente` — el
    contenedor no se toca, el razonamiento de DeepSeek se conserva."""
    intento = get_intento_reinicio(conn, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")
    update_intento_reinicio_estado(conn, intento_id, "rechazado", "rechazado por Miquel")
    return get_intento_reinicio(conn, intento_id)


# ── Agentes (specs/026-reiniciar-agentes-relays/) ────────────────────────
#
# Tercer tipo de acción real, mismo patrón que reiniciar_contenedor:
# DeepSeek decide con evidencia real, nunca una condición fija
# (deepseek_agentes.py). A diferencia de contenedores, el modo es por
# tipo de acción (configuracion_accion), no por instancia — un agente
# no tiene eje crítico/no-crítico (FR-008). Primera vez que este
# paquete ejecuta un comando de sistema (`launchctl`) directamente en
# vez de bridgear a un script privado — no existe ningún equivalente a
# docker_monitor.py para agentes (research.md §2).

# Más corto que el margen de contenedores (que esperan un arranque de
# imagen Docker) — relanzar un proceso nativo ya presente en disco
# debería ser casi inmediato; ajustar con datos reales si resulta
# insuficiente tras el primer despliegue (research.md §2b).
REMEDIACION_AGENTE_ESPERA_VERIFICACION_SEGUNDOS = float(
    os.environ.get("REMEDIACION_AGENTE_ESPERA_VERIFICACION_SEGUNDOS", "3")
)

# Medido contra la máquina real de producción (2026-08-16, T031): un
# `launchctl kickstart` tarda ~18s en devolver el control en este Mac
# — probablemente por la cantidad de jobs registrados en `launchd` en
# este homelab concreto. 15s (el valor original) cortaba en seco una
# operación que sí iba a terminar bien poco después — un `fallido`
# falso, no un problema real de la acción en sí. 30s deja margen real
# sobre el dato medido, no solo un número redondo.
REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS = int(
    os.environ.get("REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS", "30")
)


def _agente_activo_ahora(label: str) -> bool:
    """Consulta EN VIVO si `label` tiene un proceso activo ahora mismo
    — nunca releyendo `LAUNCHAGENTS_RAW`, que puede tener hasta 5
    minutos de desfase y por tanto no sirve para verificar algo que
    acaba de pasar hace segundos (research.md §2b, corregido tras
    `/speckit-analyze` hallazgo D1). `launchctl list <label>` (forma de
    un solo argumento, no la tabla completa) imprime el estado
    detallado de ese label concreto, con una línea `"PID" = <n>;`
    cuando hay un proceso activo. Cualquier fallo (label no encontrado,
    sin permiso, timeout) se trata como "no activo" — más seguro que
    "sin dato"."""
    try:
        resultado = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if resultado.returncode != 0:
        return False
    for linea in resultado.stdout.splitlines():
        clave, _, valor = linea.strip().partition("=")
        if clave.strip().strip('"') != "PID":
            continue
        if valor.strip().strip(";").strip().isdigit():
            return True
    return False


def ejecutar_reiniciar_agente(label: str, requiere_sudo: bool) -> bool:
    """Ejecuta `launchctl kickstart` y verifica EN VIVO que el proceso
    volvió a estar activo — el código de salida de `kickstart` nunca
    decide el resultado por sí solo (FR-006, research.md §2/§2b): un
    `kickstart` con éxito pero un crash-loop inmediato es `False`, no
    `True`. `REMEDIACION_TEST_FORZAR_FALLO_AGENTE` en el entorno fuerza
    `False` sin invocar `launchctl` en absoluto (hook de pruebas,
    quickstart.md Escenario 3)."""
    if os.environ.get("REMEDIACION_TEST_FORZAR_FALLO_AGENTE"):
        return False

    if requiere_sudo:
        # User Story 2 (T016): permiso sudo acotado al comando exacto
        # vía sudoers — nunca genérico (FR-005, SC-005). `-n`: si el
        # sudoers no está instalado o no cubre exactamente este
        # comando, falla inmediato en vez de colgarse esperando una
        # contraseña que nunca va a llegar (research.md §2).
        comando = ["sudo", "-n", "launchctl", "kickstart", "-k", f"system/{label}"]
    else:
        comando = ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"]

    try:
        # 30s, no 15 — medido contra la máquina real (2026-08-16): un
        # `kickstart` tarda ~18s en devolver el control en este Mac
        # (probablemente por la cantidad de jobs registrados en
        # `launchd`), con margen. La restricción SÍ es real, solo la
        # cifra estaba mal calibrada — 15s cortaba una operación que
        # de verdad iba a terminar bien 3s más tarde.
        subprocess.run(comando, capture_output=True, text=True, timeout=REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS)
    except (OSError, subprocess.TimeoutExpired):
        return False

    time.sleep(REMEDIACION_AGENTE_ESPERA_VERIFICACION_SEGUNDOS)
    # La verificación en vivo (research.md §2b) es la misma para las dos
    # ramas — sin sudo: confirmado contra la máquina real (T032,
    # 2026-08-16) que leer el estado de un LaunchDaemon root no
    # requiere privilegio, solo mutarlo lo requiere.
    return _agente_activo_ahora(label)


def _detalle_fallo_agente(label: str, requiere_sudo: bool) -> str:
    """Detalle real de un reinicio de agente fallido — distingue
    "permiso sudo no instalado" de un fallo genérico (contracts/cli.md
    garantía 22: "el motivo real", no un texto genérico siempre igual).
    Segunda llamada de solo lectura a `sudoers_permitido()` — barata,
    sin efecto secundario, solo en la rama de fallo."""
    if requiere_sudo and not bridge.sudoers_permitido(label):
        return "reinicio sin efecto — permiso sudo no instalado o no cubre este comando"
    return "reinicio sin efecto — sigue caído"


def _notificar_sin_accion_agente(label: str, razonamiento: str) -> bool:
    return _notificar_sin_accion(label, razonamiento)


def _notificar_cortacircuito_agente(label: str, detalle: str) -> bool:
    return _notificar_cortacircuito(label, detalle)


def _crear_intento_agente(
    conn: sqlite3.Connection,
    label: str,
    modo: str,
    episodio_id: int | None,
    estado: str,
    detalle: str,
    accion_recomendada: str | None = None,
    razonamiento: str | None = None,
    coste_eur: float | None = None,
) -> IntentoAgente:
    """Punto único de escritura de `intentos_agente` — mismo rol que
    `_crear_intento_reinicio()` para contenedores (`/speckit-analyze`
    hallazgo E1): si `estado == "sin_evaluar"`, comprueba la racha y
    dispara el aviso de fallo persistente (FR-014, contrapartida no
    negociable del Principio VII enmendado) — sin este punto único, el
    aviso podía quedar sin implementar si cada rama de `evaluar_agente`
    lo comprobaba (o no) por su cuenta."""
    intento = IntentoAgente(
        label=label,
        modo_en_deteccion=modo,
        episodio_id=episodio_id,
        accion_recomendada=accion_recomendada,
        razonamiento_deepseek=razonamiento,
        coste_eur=coste_eur,
        estado=estado,
        detalle=detalle,
    )
    intento.id = insert_intento_agente(conn, intento)
    if estado == "sin_evaluar":
        racha = sin_evaluar_consecutivos_agente(conn, label)
        if racha >= REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS:
            _notificar_sin_evaluar_persistente(label, racha)
    return intento


def evaluar_agente(
    conn_remediacion: sqlite3.Connection,
    conn_diagnostico: sqlite3.Connection,
    label: str,
    requiere_sudo: bool = False,
) -> IntentoAgente:
    """Orquesta la decisión de DeepSeek para un agente caído — mismo
    esqueleto exacto que `evaluar_contenedor()`, con
    `configuracion_accion` en vez de `configuracion_contenedor` (un
    agente no tiene eje crítico): `modo = get_modo(...)` →
    `congelar_agente_vivo` → presupuesto → `llamar_deepseek` → parsear
    → crea el intento en el estado que corresponda, siempre vía
    `_crear_intento_agente()` (nunca un INSERT directo)."""
    modo = get_modo(conn_remediacion, TIPO_ACCION_REINICIAR_AGENTE)
    episodio = diagnostico_evidencia.congelar_agente_vivo(conn_diagnostico, label)

    mock = deepseek_agentes.respuesta_mock()
    if mock is not None:
        parsed = mock
        coste: float | None = None
    else:
        prompt = deepseek_agentes.construir_prompt_agente(episodio, TIPOS_ACCION)
        if not diagnostico_gasto.hay_presupuesto(
            conn_diagnostico, _estimar_tokens_entrada(prompt)
        ):
            return _crear_intento_agente(
                conn_remediacion, label, modo, episodio.id,
                estado="sin_evaluar",
                detalle="sin presupuesto diario disponible para preguntar a DeepSeek",
            )
        respuesta = diagnostico_llamar_deepseek(prompt, _modelo_deepseek())
        if respuesta is None:
            return _crear_intento_agente(
                conn_remediacion, label, modo, episodio.id,
                estado="sin_evaluar",
                detalle="DeepSeek no respondió o la llamada falló",
            )
        parsed = deepseek_agentes.parsear_respuesta_agente(respuesta)
        if parsed is None:
            return _crear_intento_agente(
                conn_remediacion, label, modo, episodio.id,
                estado="sin_evaluar",
                detalle="respuesta de DeepSeek inconsistente con el formato esperado",
            )
        coste = diagnostico_gasto.registrar_coste(
            conn_diagnostico, parsed["tokens_entrada"], parsed["tokens_salida"]
        )

    accion = parsed["accion_aplica"]
    razonamiento = parsed["razonamiento"]

    if accion is None:
        intento = _crear_intento_agente(
            conn_remediacion, label, modo, episodio.id,
            estado="sin_accion", detalle=razonamiento,
            accion_recomendada=None, razonamiento=razonamiento, coste_eur=coste,
        )
        _notificar_sin_accion_agente(label, razonamiento)
        return intento

    # accion == TIPO_ACCION_REINICIAR_AGENTE — única acción candidata hoy
    if modo == "manual":
        return _crear_intento_agente(
            conn_remediacion, label, modo, episodio.id,
            estado="pendiente", detalle="pendiente de aprobación",
            accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
        )

    # modo == "automatico" — mismo cortacircuito compartido que contenedores
    # (Clarifications, sesión 2026-08-16: mismo umbral, sin configuración
    # independiente para esta acción)
    intentos_previos = bridge.recent_agent_restart_attempts(
        conn_remediacion, label, REMEDIACION_CB_VENTANA_HORAS
    )
    permite, motivo_breaker = bridge.breaker_decision(intentos_previos, REMEDIACION_CB_MAX_INTENTOS)
    if not permite:
        intento = _crear_intento_agente(
            conn_remediacion, label, modo, episodio.id,
            estado="cortacircuito", detalle=motivo_breaker,
            accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
        )
        _notificar_cortacircuito_agente(label, motivo_breaker)
        return intento

    ejecutado = ejecutar_reiniciar_agente(label, requiere_sudo=requiere_sudo)
    estado_final = "ejecutado" if ejecutado else "fallido"
    detalle = "reiniciado y verificado" if ejecutado else _detalle_fallo_agente(label, requiere_sudo)
    return _crear_intento_agente(
        conn_remediacion, label, modo, episodio.id,
        estado=estado_final, detalle=detalle,
        accion_recomendada=accion, razonamiento=razonamiento, coste_eur=coste,
    )


def comprobar_reiniciar_agente(
    conn_remediacion: sqlite3.Connection, conn_diagnostico: sqlite3.Connection
) -> list[IntentoAgente]:
    """Recorre los labels que `bridge.listar_agentes_conocidos()`
    conoce (`amsterdam9.*`/`com.homeassistant.*`, FR-012: nunca un
    label desconocido), se queda con los que no tienen proceso activo,
    salta los que ya tienen un intento `pendiente`/`sin_evaluar`
    reciente, y evalúa el resto — `requiere_sudo` se determina por
    prefijo del label."""
    creados: list[IntentoAgente] = []

    for agente in bridge.listar_agentes_conocidos():
        label = agente["label"]
        if agente["running"]:
            continue
        if intento_reciente_pendiente_o_sin_evaluar_agente(conn_remediacion, label):
            continue
        creados.append(
            evaluar_agente(
                conn_remediacion, conn_diagnostico, label,
                requiere_sudo=agente["requiere_sudo"],
            )
        )

    return creados


def resolver_aprobacion_agente(conn_remediacion: sqlite3.Connection, intento_id: int) -> IntentoAgente:
    """Aprueba un intento `pendiente` — ejecuta el reinicio en la misma
    llamada, con la misma verificación en vivo que ya usa
    `evaluar_agente` (FR-006)."""
    intento = get_intento_agente(conn_remediacion, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")

    requiere_sudo = intento.label.startswith("com.homeassistant.")
    ejecutado = ejecutar_reiniciar_agente(intento.label, requiere_sudo=requiere_sudo)
    estado_final = "ejecutado" if ejecutado else "fallido"
    detalle = (
        "reiniciado y verificado (aprobado por Miquel)"
        if ejecutado
        else _detalle_fallo_agente(intento.label, requiere_sudo)
    )
    update_intento_agente_estado(conn_remediacion, intento_id, estado_final, detalle)
    return get_intento_agente(conn_remediacion, intento_id)


def resolver_rechazo_agente(conn_remediacion: sqlite3.Connection, intento_id: int) -> IntentoAgente:
    """Rechaza un intento `pendiente` — el agente no se toca, el
    razonamiento de DeepSeek se conserva."""
    intento = get_intento_agente(conn_remediacion, intento_id)
    if intento is None:
        raise ValueError(f"intento {intento_id} no existe")
    if intento.estado != "pendiente":
        raise ValueError(f"intento {intento_id} no está pendiente (estado={intento.estado})")
    update_intento_agente_estado(conn_remediacion, intento_id, "rechazado", "rechazado por Miquel")
    return get_intento_agente(conn_remediacion, intento_id)
