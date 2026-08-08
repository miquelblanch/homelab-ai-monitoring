"""deliver — Entrega por los dos canales que ya existen (FR-018,
contracts/entrega.md), más el latido de respaldo (research.md §7).

No construye ninguna interfaz nueva: Telegram reutiliza el mismo patrón
que `telegram_notify.py`/`homelab_secrets.telegram()`, y el dashboard
recibe un fichero `inventario.json` que `docker/homelab-dashboard/scripts/app.py`
tiene que aprender a leer (T036, fuera de este repositorio — no lo hace
este módulo).
"""

from __future__ import annotations

import json
import os
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import _homelab_bridge as bridge
from . import store

_DASHBOARD_JSON_PATH = (
    "/Volumes/FastData/homelab/docker/homelab-orchestrator/data/inventario.json"
)


def dashboard_json_path() -> Path:
    return Path(os.environ.get("INVENTORY_DASHBOARD_JSON", _DASHBOARD_JSON_PATH))


# ── Telegram (contracts/entrega.md) ──────────────────────────────────────


def _send_raw(text: str) -> bool:
    """Mismo patrón que `telegram_notify.py`: POST a la API de Telegram,
    sin verificación de certificado (así está también en el resto del
    homelab). Nunca lanza excepción — un fallo de entrega no debe tumbar
    el resto del inventario (FR-016 no está en juego aquí, pero el
    principio "a prueba de fallos" del resto del homelab sí)."""
    token, chat_id = bridge.telegram_credentials()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except (urllib.error.URLError, OSError, ValueError):
        return False


TELEGRAM_MAX_CHARS = 4096  # límite real de la API sendMessage
_LIMITE_SEGURO = 3500  # margen bajo el límite real, para no rozarlo
_UMBRAL_DETALLE_POR_CATEGORIA = 15  # a partir de aquí, se resume en vez de listar


def build_report_text(
    conn: sqlite3.Connection, ejecucion_id: int, gaps_only: bool = False
) -> str:
    """FR-011, FR-018. El riesgo concentrado de Telegram (Edge Case de
    FR-006) va destacado aparte, al principio — nunca mezclado en la
    lista ordinaria de brechas (T027).

    Con volúmenes reales (cientos de entidades HA) un mensaje de una
    línea por brecha supera el límite de 4096 caracteres de la API de
    Telegram — descubierto en la primera ejecución real contra el
    homelab (830 componentes, 385 brechas). Por categoría: si caben
    pocas, se listan todas; si son muchas, se resumen con el conteo y se
    remite a `--gaps` o al dashboard para el detalle. Además hay un
    truncado duro como red de seguridad, por si el resumen agrupado
    todavía no cupiera."""
    ejecucion = store.get_ejecucion(conn, ejecucion_id)
    total = ejecucion["total_componentes"]
    total_brechas = ejecucion["total_brechas"]
    brechas = store.brechas_de_ejecucion(conn, ejecucion_id)

    riesgo = next((b for b in brechas if b["tipo"] == "riesgo_concentrado_telegram"), None)
    resto = [b for b in brechas if b is not riesgo]

    lineas = [f"📋 Inventario de cobertura — ejecución #{ejecucion_id}"]
    if riesgo is not None:
        lineas.append(f"⚠️ RIESGO CONCENTRADO: {riesgo['contexto']}")
    lineas.append(f"{total - total_brechas}/{total} componentes sin brecha")

    if gaps_only or resto:
        lineas.append("")
        lineas.append("Brechas:" if resto else "Sin más brechas.")

        por_categoria: dict[str, list] = {}
        for b in resto:
            por_categoria.setdefault(b["categoria"], []).append(b)

        for categoria, items in sorted(por_categoria.items(), key=lambda kv: -len(kv[1])):
            if len(items) <= _UMBRAL_DETALLE_POR_CATEGORIA:
                for b in items:
                    nueva = " [NUEVA]" if b["primera_ejecucion_id"] == ejecucion_id else ""
                    conocida = (
                        f" ({b['conocida_por_barrido_previo']})"
                        if b["conocida_por_barrido_previo"]
                        else ""
                    )
                    lineas.append(f"- {b['contexto']}{nueva}{conocida}")
            else:
                nuevas = sum(1 for b in items if b["primera_ejecucion_id"] == ejecucion_id)
                lineas.append(
                    f"- {categoria}: {len(items)} brechas ({nuevas} nuevas) "
                    "— detalle completo con --gaps o en el dashboard"
                )

    texto = "\n".join(lineas)
    if len(texto) > _LIMITE_SEGURO:
        texto = (
            texto[:_LIMITE_SEGURO].rsplit("\n", 1)[0]
            + "\n… (truncado — ver --gaps o el dashboard para el resto)"
        )
    return texto


def send_telegram(conn: sqlite3.Connection, ejecucion_id: int, gaps_only: bool = False) -> bool:
    return _send_raw(build_report_text(conn, ejecucion_id, gaps_only=gaps_only))


# ── Dashboard (contracts/entrega.md) ─────────────────────────────────────


def write_dashboard_json(conn: sqlite3.Connection, ejecucion_id: int) -> bool:
    """Escribe `inventario.json` — mismo patrón que `dump_socat_status.py`
    escribe `socat_relays.json`. `componentes` lleva el listado completo
    (no solo las brechas) para que el dashboard pueda mostrar el
    inventario entero, no únicamente lo que falla."""
    ejecucion = store.get_ejecucion(conn, ejecucion_id)
    if ejecucion is None:
        return False
    brechas = store.brechas_de_ejecucion(conn, ejecucion_id)
    hallazgos = store.hallazgos_de_ejecucion(conn, ejecucion_id)
    payload = {
        "ejecucion_id": ejecucion_id,
        "fecha": ejecucion["fecha"],
        "total_componentes": ejecucion["total_componentes"],
        "total_brechas": ejecucion["total_brechas"],
        "brechas": [
            {
                "componente": b["nombre_actual"],
                "categoria": b["categoria"],
                "tipo": b["tipo"],
                "contexto": b["contexto"],
                "nueva": b["primera_ejecucion_id"] == ejecucion_id,
                "conocida_por_barrido_previo": b["conocida_por_barrido_previo"],
            }
            for b in brechas
        ],
        "componentes": [
            {
                "nombre": h["nombre_actual"],
                "categoria": h["categoria"],
                "declarado": h["estado_declarado_status"],
                "vigilado": bool(h["esta_vigilado"]),
                "mecanismo": h["mecanismo_vigilancia"],
                "llega_a_dashboard": h["llega_a_dashboard"],
                "es_brecha": bool(h["es_brecha"]),
                "intencionado": bool(h["es_intencionadamente_no_vigilado"]),
            }
            for h in hallazgos
        ],
    }
    try:
        path = dashboard_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        return True
    except OSError:
        return False


# ── Latido de respaldo (research.md §7) ──────────────────────────────────


def record_heartbeat(persisted_ok: bool, delivered_ok: bool) -> None:
    """Solo se marca `ok` si persistencia y entrega tuvieron éxito
    (contracts/cli.md) — es la vía de detección de respaldo si Telegram
    falla en silencio (Edge Case, FR-006)."""
    status = "ok" if (persisted_ok and delivered_ok) else "fail"
    detail = "" if status == "ok" else (
        "persistencia falló" if not persisted_ok else "entrega falló"
    )
    bridge.record_heartbeat("inventario-cobertura", status=status, detail=detail)
