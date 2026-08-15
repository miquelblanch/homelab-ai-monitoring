"""relay — Evidencia del origen relay `socat` (feature 012:
specs/012-diagnostico-relays/). En vivo con detalle real por relay, o
en diferido con evidencia agregada — nunca cuál relay concreto salvo
que el log lo traiga desde el 2026-08-13. Ver research.md §3/§5/§10 de
012.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Episodio
from ..store import insert_episodio

SOCAT_RELAYS_JSON = Path(
    os.environ.get(
        "SOCAT_RELAYS_JSON",
        "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json",
    )
)  # research.md §3 de 012 — estado actual, sobreescrito cada 5 min.

DASHBOARD_SOCAT_LOG = Path(
    os.environ.get(
        "DASHBOARD_SOCAT_LOG", str(Path.home() / "Library/Logs/dashboard-socat.log")
    )
).expanduser()  # research.md §5 de 012 — primer fichero de evidencia
# fuera de /Volumes/FastData/homelab/: es el StandardOutPath del
# LaunchAgent amsterdam9.dashboard.socat.

VENTANA_RELAY_MINUTOS = 180  # research.md §5 de 012 — de los 17
# episodios reales identificados (2026-04-29 en adelante), 16 duran
# 52 min o menos; uno solo llega a ~595 min (10h, 2026-05-24). ±180
# min cubre los 16 enteros y muestra una porción amplia del largo.

RELAY_AGREGADO_MAX_LINEAS = 100  # research.md §5 de 012 — límite
# defensivo, no motivado por un caso real: a intervalos de 5 min, la
# propia ventana ya acota a ~72 líneas como máximo.

_PATRON_LINEA_RELAY = re.compile(
    r"\[(?P<ts>[^\]]+)\].*?(?P<ok>\d+)/(?P<total>\d+) ok(?: — fallan: (?P<fallan>.+))?"
)
# `dump_socat_status.py` (fuera de este repo) empezó a loguear qué
# relay concreto falla, no solo el recuento, el 2026-08-13 — a
# petición explícita de Miquel tras encontrar que la limitación de
# "nunca cuál relay concreto" documentada en 012 era corregible hacia
# adelante. Las líneas de antes de esa fecha no llevan "fallan" y
# siguen sin nombre — el grupo es opcional a propósito, nunca inventa
# un nombre para una línea antigua.


def _relay_actual(nombre: str) -> dict | None:
    """La entrada de `nombre` en `socat_relays.json` ahora mismo —
    `None` si el fichero no existe o `nombre` no está entre los relays
    vigilados (research.md §3 de 012). No es un error — spec.md Edge
    Cases: el episodio se congela igual, con evidencia vacía."""
    if not SOCAT_RELAYS_JSON.is_file():
        return None
    try:
        datos = json.loads(SOCAT_RELAYS_JSON.read_text())
    except (OSError, ValueError):
        return None
    for relay in datos.get("relays", []):
        if relay.get("name") == nombre:
            return relay
    return None


def listar_nombres_relay() -> set[str]:
    """Los `name` de todos los relays que aparecen ahora mismo en
    `socat_relays.json` — usado por
    `deepseek._menciona_relay_concreto()` para comprobar que un
    diagnóstico en diferido no nombra un relay concreto sin evidencia
    real de cuál falló (FR-006, hallazgo F1 de /speckit-analyze,
    2026-08-12; research.md §10 de 012)."""
    if not SOCAT_RELAYS_JSON.is_file():
        return set()
    try:
        datos = json.loads(SOCAT_RELAYS_JSON.read_text())
    except (OSError, ValueError):
        return set()
    return {r["name"] for r in datos.get("relays", []) if "name" in r}


def _agregado_relays_ventana(
    momento: datetime, ventana_minutos: int = VENTANA_RELAY_MINUTOS
) -> list[dict]:
    """Recuento agregado ("N de M ok") de cada línea de
    `DASHBOARD_SOCAT_LOG` dentro de `[momento - ventana, momento +
    ventana]`, con el nombre de los relays caídos en esa línea cuando
    el propio log lo trae — solo desde el 2026-08-13
    (`dump_socat_status.py` no lo registraba antes; ver
    `_PATRON_LINEA_RELAY`). `"fallan"` es `[]` para cualquier línea sin
    ese detalle: sigue sin inventarse nada para el histórico anterior.
    Acotado a `RELAY_AGREGADO_MAX_LINEAS`."""
    if not DASHBOARD_SOCAT_LOG.is_file():
        return []
    tolerancia = timedelta(minutes=ventana_minutos)
    inicio = momento - tolerancia
    fin = momento + tolerancia

    try:
        texto = DASHBOARD_SOCAT_LOG.read_text(errors="ignore")
    except OSError:
        return []

    resultado: list[dict] = []
    for linea in texto.splitlines():
        m = _PATRON_LINEA_RELAY.search(linea)
        if not m:
            continue
        try:
            ts = datetime.fromisoformat(m.group("ts"))
        except ValueError:
            continue
        if inicio <= ts <= fin:
            fallan_raw = m.group("fallan")
            fallan = [n.strip() for n in fallan_raw.split(",")] if fallan_raw else []
            resultado.append({
                "momento": ts.isoformat(), "ok": int(m.group("ok")), "total": int(m.group("total")),
                "fallan": fallan,
            })
            if len(resultado) >= RELAY_AGREGADO_MAX_LINEAS:
                break
    return resultado


def nombres_relay_evidenciados(agregado: list[dict] | None) -> set[str]:
    """Nombres de relay que sí aparecen como caídos en alguna entrada
    de `relay_agregado` — usado por `deepseek.py` para permitir que un
    diagnóstico en diferido nombre un relay concreto SOLO cuando hay
    evidencia real de que fue justo ese el que falló en la ventana.
    Vacío para cualquier episodio congelado antes del 2026-08-13 (el
    log no traía el detalle todavía) o si en la ventana no cayó ningún
    relay con nombre conocido."""
    if not agregado:
        return set()
    nombres: set[str] = set()
    for entrada in agregado:
        nombres.update(entrada.get("fallan", []))
    return nombres


def _snapshot_relay_vacio() -> dict:
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
    }


def congelar_relay_vivo(conn: sqlite3.Connection, nombre: str) -> Episodio:
    """Congela el estado actual de un relay concreto, con detalle real
    (`socat_relays.json`). `es_critico` siempre `False` (spec.md
    Assumptions) — no existe concepto de "relay crítico"."""
    ahora = datetime.now()
    estado = _relay_actual(nombre)
    snapshot = _snapshot_relay_vacio()
    snapshot.update(relay_nombre=nombre, relay_estado_actual=estado)

    episodio = Episodio(
        componente=nombre,
        origen="relay",
        es_critico=False,
        en_vivo=True,
        ventana_inicio=ahora.isoformat(),
        ventana_fin=ahora.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio


def congelar_relay_historico(conn: sqlite3.Connection, momento: datetime) -> Episodio:
    """Congela la evidencia agregada de una ventana alrededor de
    `momento` — con el nombre de los relays caídos cuando el log lo
    trae (desde el 2026-08-13; antes de esa fecha, o si el log no
    llegó a registrar el fallo, sigue sin haber ningún nombre —
    research.md §2/§5 de 012). `componente` es siempre el momento
    pedido, incluso sin ningún dato en la ventana (research.md §9 de
    012, lección de 011 aplicada por diseño)."""
    inicio = momento - timedelta(minutes=VENTANA_RELAY_MINUTOS)
    fin = momento + timedelta(minutes=VENTANA_RELAY_MINUTOS)
    agregado = _agregado_relays_ventana(momento)

    snapshot = _snapshot_relay_vacio()
    snapshot.update(relay_agregado=agregado)

    episodio = Episodio(
        componente=momento.isoformat(),
        origen="relay",
        es_critico=False,
        en_vivo=False,
        ventana_inicio=inicio.isoformat(),
        ventana_fin=fin.isoformat(),
        snapshot_evidencia=snapshot,
        restart_history_id=None,
    )
    episodio.id = insert_episodio(conn, episodio)
    return episodio
