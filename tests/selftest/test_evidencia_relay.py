"""test_evidencia_relay — origen relay socat (feature 012). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T020).
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import relay
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


_SOCAT_RELAYS_FAKE = {
    "updated": "2026-08-12T18:19:12",
    "relays": [
        {"name": "Beszel AdGuard", "desc": "192.168.4.87:45877 → 192.168.4.174:45876", "ok": True},
        {"name": "HA Shelly", "desc": "192.168.4.87:80 → 192.168.4.153:80", "ok": False},
    ],
}

_DASHBOARD_SOCAT_LOG_FAKE = "\n".join([
    "[2026-05-24T02:00:00] socat_relays.json written — 10/10 ok",
    "[2026-05-24T05:00:00] socat_relays.json written — 9/10 ok",
    "[2026-05-24T08:00:00] socat_relays.json written — 9/10 ok",
    "[2026-05-24T11:00:00] socat_relays.json written — 9/10 ok",
    "[2026-05-24T14:00:00] socat_relays.json written — 10/10 ok",
]) + "\n"


def _escribir_json(path: Path, datos: dict) -> None:
    path.write_text(json.dumps(datos))


def test_relay_actual_existente_e_inexistente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        relays_json = Path(tmp) / "socat_relays.json"
        _escribir_json(relays_json, _SOCAT_RELAYS_FAKE)
        with patch.object(relay, "SOCAT_RELAYS_JSON", relays_json):
            existente = relay._relay_actual("Beszel AdGuard")
            inexistente = relay._relay_actual("Relay que no existe")

        check("relay existente devuelve su entrada real", existente == _SOCAT_RELAYS_FAKE["relays"][0])
        check("relay inexistente devuelve None, sin lanzar", inexistente is None)


def test_listar_nombres_relay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        relays_json = Path(tmp) / "socat_relays.json"
        _escribir_json(relays_json, _SOCAT_RELAYS_FAKE)
        with patch.object(relay, "SOCAT_RELAYS_JSON", relays_json):
            nombres = relay.listar_nombres_relay()

        check(
            "listar_nombres_relay recoge los nombres reales",
            nombres == {"Beszel AdGuard", "HA Shelly"},
        )


def test_congelar_relay_vivo_arma_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp_relays, tempfile.TemporaryDirectory() as tmp_db:
        relays_json = Path(tmp_relays) / "socat_relays.json"
        _escribir_json(relays_json, _SOCAT_RELAYS_FAKE)
        with patch.object(relay, "SOCAT_RELAYS_JSON", relays_json):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = relay.congelar_relay_vivo(conn, "HA Shelly")

        check("componente = nombre del relay", episodio.componente == "HA Shelly")
        check("origen = relay", episodio.origen == "relay")
        check("es_critico siempre False para relay", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "relay_estado_actual tiene el detalle real, relay_agregado queda null",
            episodio.snapshot_evidencia["relay_estado_actual"] == _SOCAT_RELAYS_FAKE["relays"][1]
            and episodio.snapshot_evidencia["relay_agregado"] is None,
        )
        check(
            "campos heredados de orígenes anteriores quedan a null",
            episodio.snapshot_evidencia["restart_history"] is None
            and episodio.snapshot_evidencia["ha_check"] is None
            and episodio.snapshot_evidencia["backup_log_path"] is None,
        )


def test_congelar_relay_vivo_nombre_inexistente_no_lanza() -> None:
    with tempfile.TemporaryDirectory() as tmp_relays, tempfile.TemporaryDirectory() as tmp_db:
        relays_json = Path(tmp_relays) / "socat_relays.json"
        _escribir_json(relays_json, _SOCAT_RELAYS_FAKE)
        with patch.object(relay, "SOCAT_RELAYS_JSON", relays_json):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = relay.congelar_relay_vivo(conn, "Relay que no existe")

        check("componente = nombre pedido aunque no exista", episodio.componente == "Relay que no existe")
        check(
            "relay_estado_actual queda null, sin lanzar",
            episodio.snapshot_evidencia["relay_estado_actual"] is None,
        )


def test_agregado_relays_ventana_dentro_y_fuera() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "dashboard-socat.log"
        log_path.write_text(_DASHBOARD_SOCAT_LOG_FAKE)
        momento = datetime(2026, 5, 24, 8, 0, 0)
        with patch.object(relay, "DASHBOARD_SOCAT_LOG", log_path):
            agregado = relay._agregado_relays_ventana(momento)

        check(
            "solo las 3 líneas dentro de ±180 min sobreviven (05:00, 08:00, 11:00)",
            len(agregado) == 3,
        )
        check(
            "cada entrada trae momento/ok/total/fallan",
            all(set(e.keys()) == {"momento", "ok", "total", "fallan"} for e in agregado),
        )
        check(
            "líneas sin detalle de nombre traen fallan=[] (histórico anterior al 2026-08-13)",
            all(e["fallan"] == [] for e in agregado),
        )
        check("la entrada del fallo real refleja 9 de 10", agregado[1]["ok"] == 9 and agregado[1]["total"] == 10)


def test_agregado_relays_ventana_acota_max_lineas() -> None:
    momento = datetime(2026, 1, 1, 0, 0, 0)
    lineas = [
        f"[2026-01-01T00:{i:02d}:00] socat_relays.json written — 10/10 ok"
        for i in range(0, 60, 1)
    ] * 3  # 180 líneas, todas dentro de la ventana de ±180 min
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "dashboard-socat.log"
        log_path.write_text("\n".join(lineas))
        with patch.object(relay, "DASHBOARD_SOCAT_LOG", log_path):
            agregado = relay._agregado_relays_ventana(momento)

        check(
            f"agregado se acota a {relay.RELAY_AGREGADO_MAX_LINEAS}, no 180",
            len(agregado) == relay.RELAY_AGREGADO_MAX_LINEAS,
        )


_DASHBOARD_SOCAT_LOG_CON_NOMBRES_FAKE = "\n".join([
    "[2026-08-13T10:00:00] socat_relays.json written — 10/10 ok",
    "[2026-08-13T10:05:00] socat_relays.json written — 8/10 ok — fallan: HA Shelly, Beszel AdGuard",
    "[2026-08-13T10:10:00] socat_relays.json written — 9/10 ok — fallan: HA Shelly",
    "[2026-08-13T10:15:00] socat_relays.json written — 10/10 ok",
]) + "\n"


def test_agregado_relays_ventana_parsea_fallan_desde_2026_08_13() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "dashboard-socat.log"
        log_path.write_text(_DASHBOARD_SOCAT_LOG_CON_NOMBRES_FAKE)
        momento = datetime(2026, 8, 13, 10, 10, 0)
        with patch.object(relay, "DASHBOARD_SOCAT_LOG", log_path):
            agregado = relay._agregado_relays_ventana(momento)

        check("las 4 líneas caen dentro de la ventana", len(agregado) == 4)
        check("línea sana ⇒ fallan=[]", agregado[0]["fallan"] == [])
        check(
            "línea con dos relays caídos ⇒ fallan los nombra a los dos",
            agregado[1]["fallan"] == ["HA Shelly", "Beszel AdGuard"],
        )
        check("línea con un solo relay caído ⇒ fallan=['HA Shelly']", agregado[2]["fallan"] == ["HA Shelly"])


def test_nombres_relay_evidenciados() -> None:
    agregado = [
        {"momento": "x", "ok": 10, "total": 10, "fallan": []},
        {"momento": "y", "ok": 8, "total": 10, "fallan": ["HA Shelly", "Beszel AdGuard"]},
        {"momento": "z", "ok": 9, "total": 10, "fallan": ["HA Shelly"]},
    ]
    check(
        "une los nombres de todas las entradas, sin duplicados",
        relay.nombres_relay_evidenciados(agregado) == {"HA Shelly", "Beszel AdGuard"},
    )
    check("agregado vacío o None ⇒ conjunto vacío, sin lanzar", relay.nombres_relay_evidenciados(None) == set())
    check("agregado=[] ⇒ conjunto vacío", relay.nombres_relay_evidenciados([]) == set())


def test_congelar_relay_historico_es_reproducible_y_usa_el_momento_pedido() -> None:
    with tempfile.TemporaryDirectory() as tmp_log, tempfile.TemporaryDirectory() as tmp_db:
        log_path = Path(tmp_log) / "dashboard-socat.log"
        log_path.write_text(_DASHBOARD_SOCAT_LOG_FAKE)
        momento = datetime(2026, 5, 24, 8, 0, 0)
        with patch.object(relay, "DASHBOARD_SOCAT_LOG", log_path):
            with store.connect(_diag_db(tmp_db)) as conn:
                e1 = relay.congelar_relay_historico(conn, momento)
                e2 = relay.congelar_relay_historico(conn, momento)

                # Sin ningún dato en la ventana — el componente debe seguir
                # siendo el momento PEDIDO, no datetime.now() (research.md §9).
                momento_lejano = datetime(2020, 1, 1, 0, 0, 0)
                e3 = relay.congelar_relay_historico(conn, momento_lejano)

        check(
            "dos congelados del mismo momento producen la misma evidencia agregada",
            e1.snapshot_evidencia["relay_agregado"] == e2.snapshot_evidencia["relay_agregado"],
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
        check(
            "sin datos en la ventana, componente = momento pedido, no la hora de congelar",
            e3.componente == momento_lejano.isoformat() and e3.snapshot_evidencia["relay_agregado"] == [],
        )
        check("origen = relay, relay_nombre queda null en diferido", e1.origen == "relay" and e1.snapshot_evidencia["relay_nombre"] is None)
