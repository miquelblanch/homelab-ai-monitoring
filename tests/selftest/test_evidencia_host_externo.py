"""test_evidencia_host_externo — origen host físico externo vigilado
por Beszel (feature 014). Movido de `test_evidencia.py` en
specs/023-evidencia-por-origen/ (T022).

**Punto crítico de esta migración** (research.md §3 de 023):
`_consultar_beszel_hub` se define en `host_externo.py`, así que
`patch.object(host_externo, "_consultar_beszel_hub", ...)` — nunca
sobre la fachada `evidencia` ni sobre `_compartido` — es el único
target que de verdad intercepta la llamada real dentro de
`congelar_host_externo_historico()`.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import _compartido, host_externo
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


def _escribir_json(path: Path, datos: dict) -> None:
    path.write_text(json.dumps(datos))


def _beszel_hosts_json(kuma_status: str, adguard_status: str, *, edad_s: float = 0.0) -> dict:
    generated_at = datetime.now().astimezone() - timedelta(seconds=edad_s)
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "hosts": {
            "Host de Uptime Kuma": {"status": kuma_status, "beszel_name": "UptimeKuma"},
            "Host de AdGuard Home (DNS primario)": {"status": adguard_status, "beszel_name": "AdGuardHome"},
        },
        "hub_systems": {},
    }


def _beszel_heartbeat(*, edad_s: float = 0.0) -> dict:
    epoch = datetime.now().timestamp() - edad_s
    return {"job": "beszel-hosts", "epoch": epoch, "status": "ok", "detail": "2 hosts escritos"}


def test_host_externo_actual_arriba_caido_sin_evidencia_e_inexistente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        hosts_json = Path(tmp) / "beszel_hosts.json"
        hb_json = Path(tmp) / "beszel-hosts.json"
        _escribir_json(hosts_json, _beszel_hosts_json("up", "down"))
        _escribir_json(hb_json, _beszel_heartbeat())

        with patch.object(host_externo, "BESZEL_HOSTS_JSON", hosts_json), \
             patch.object(host_externo, "BESZEL_HOSTS_HEARTBEAT", hb_json):
            arriba = host_externo._host_externo_actual("Host de Uptime Kuma")
            caido = host_externo._host_externo_actual("Host de AdGuard Home (DNS primario)")
            inexistente = host_externo._host_externo_actual("Host que no existe")

        check("host arriba", arriba is not None and arriba["status"] == "arriba")
        check("host caído", caido is not None and caido["status"] == "caido")
        check("nombre inexistente devuelve None, sin lanzar", inexistente is None)


def test_host_externo_actual_sin_evidencia_por_dato_o_latido_caducado() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        hosts_json = Path(tmp) / "beszel_hosts.json"
        hb_json = Path(tmp) / "beszel-hosts.json"

        # Dato fresco, latido caducado.
        _escribir_json(hosts_json, _beszel_hosts_json("up", "up"))
        _escribir_json(hb_json, _beszel_heartbeat(edad_s=2000))
        with patch.object(host_externo, "BESZEL_HOSTS_JSON", hosts_json), \
             patch.object(host_externo, "BESZEL_HOSTS_HEARTBEAT", hb_json):
            latido_caducado = host_externo._host_externo_actual("Host de Uptime Kuma")

        # Dato caducado, latido fresco.
        _escribir_json(hosts_json, _beszel_hosts_json("up", "up", edad_s=2000))
        _escribir_json(hb_json, _beszel_heartbeat())
        with patch.object(host_externo, "BESZEL_HOSTS_JSON", hosts_json), \
             patch.object(host_externo, "BESZEL_HOSTS_HEARTBEAT", hb_json):
            dato_caducado = host_externo._host_externo_actual("Host de Uptime Kuma")

        # Latido ausente.
        with patch.object(host_externo, "BESZEL_HOSTS_JSON", hosts_json), \
             patch.object(host_externo, "BESZEL_HOSTS_HEARTBEAT", Path(tmp) / "no-existe.json"):
            sin_latido = host_externo._host_externo_actual("Host de Uptime Kuma")

        check(
            "latido caducado ⇒ sin_evidencia, aunque el dato sea fresco",
            latido_caducado is not None and latido_caducado["status"] == "sin_evidencia",
        )
        check(
            "dato caducado ⇒ sin_evidencia, aunque el latido sea fresco",
            dato_caducado is not None and dato_caducado["status"] == "sin_evidencia",
        )
        check(
            "latido ausente ⇒ sin_evidencia, sin lanzar",
            sin_latido is not None and sin_latido["status"] == "sin_evidencia",
        )


def test_congelar_host_externo_vivo_arma_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp_beszel, tempfile.TemporaryDirectory() as tmp_db:
        hosts_json = Path(tmp_beszel) / "beszel_hosts.json"
        hb_json = Path(tmp_beszel) / "beszel-hosts.json"
        _escribir_json(hosts_json, _beszel_hosts_json("up", "down"))
        _escribir_json(hb_json, _beszel_heartbeat())

        with patch.object(host_externo, "BESZEL_HOSTS_JSON", hosts_json), \
             patch.object(host_externo, "BESZEL_HOSTS_HEARTBEAT", hb_json):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = host_externo.congelar_host_externo_vivo(conn, "Host de Uptime Kuma")

        check("componente = nombre del host", episodio.componente == "Host de Uptime Kuma")
        check("origen = host_externo", episodio.origen == "host_externo")
        check("es_critico siempre False", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "host_externo_actual poblado, host_externo_stats queda null",
            episodio.snapshot_evidencia["host_externo_actual"] is not None
            and episodio.snapshot_evidencia["host_externo_actual"]["status"] == "arriba"
            and episodio.snapshot_evidencia["host_externo_stats"] is None,
        )


def test_a_utc_madrid_invierno_y_verano() -> None:
    invierno = _compartido._a_utc_madrid(datetime(2026, 1, 15, 12, 0, 0))
    verano = _compartido._a_utc_madrid(datetime(2026, 8, 15, 12, 0, 0))

    check("CET (invierno, UTC+1): 12:00 local = 11:00 UTC", invierno.startswith("2026-01-15 11:00:00"))
    check("CEST (verano, UTC+2): 12:00 local = 10:00 UTC", verano.startswith("2026-08-15 10:00:00"))


def test_resumen_system_stats() -> None:
    filas = [
        ("2026-08-01 10:00:00.000000", "1m"),
        ("2026-08-01 09:00:00.000000", "1m"),
        ("2026-08-01 08:00:00.000000", "10m"),
    ]
    resumen = _compartido._resumen_system_stats(filas)
    vacio = _compartido._resumen_system_stats([])

    check(
        "recuento, primera y última correctas, por_tipo agregado",
        resumen["total_muestras"] == 3
        and resumen["primera"] == "2026-08-01 08:00:00.000000"
        and resumen["ultima"] == "2026-08-01 10:00:00.000000"
        and resumen["por_tipo"] == {"1m": 2, "10m": 1},
    )
    check(
        "lista vacía produce el resumen vacío, no None",
        vacio == {"total_muestras": 0, "primera": None, "ultima": None, "por_tipo": {}},
    )


def test_congelar_host_externo_historico_distingue_none_de_lista_vacia() -> None:
    """Hallazgo real de /speckit-analyze (2026-08-12, research.md §10
    de 014): `_consultar_beszel_hub()` puede devolver `None` (consulta
    fallida) o `[]` (consulta con éxito, sin filas) — dos casos
    distintos que no deben confundirse."""
    with tempfile.TemporaryDirectory() as tmp:
        momento = datetime(2026, 8, 2, 12, 0, 0)

        with patch.object(host_externo, "_consultar_beszel_hub", return_value=[]):
            with store.connect(Path(tmp) / "diagnostico1.db") as conn:
                sin_datos = host_externo.congelar_host_externo_historico(
                    conn, "Host de Uptime Kuma", momento
                )

        with patch.object(host_externo, "_consultar_beszel_hub", return_value=None):
            with store.connect(Path(tmp) / "diagnostico2.db") as conn:
                consulta_fallida = host_externo.congelar_host_externo_historico(
                    conn, "Host de Uptime Kuma", momento
                )

        with patch.object(host_externo, "_consultar_beszel_hub", return_value=[("x", "1m")]) as mock_consulta:
            with store.connect(Path(tmp) / "diagnostico3.db") as conn:
                nombre_inexistente = host_externo.congelar_host_externo_historico(
                    conn, "Host que no existe", momento
                )
            check(
                "nombre fuera de HOSTS_EXTERNOS no llega a consultar el hub",
                mock_consulta.call_count == 0,
            )

        check(
            "consulta con éxito sin filas ⇒ host_externo_stats con total_muestras=0",
            sin_datos.snapshot_evidencia["host_externo_stats"] == {
                "total_muestras": 0, "primera": None, "ultima": None, "por_tipo": {},
                "nombre": "Host de Uptime Kuma", "beszel_name": "UptimeKuma",
            },
        )
        check(
            "consulta fallida (None) ⇒ host_externo_stats=None, sin lanzar TypeError",
            consulta_fallida.snapshot_evidencia["host_externo_stats"] is None,
        )
        check(
            "nombre inexistente ⇒ host_externo_stats=None",
            nombre_inexistente.snapshot_evidencia["host_externo_stats"] is None,
        )
        check(
            "componente = NOMBRE solo, nunca incluye el momento (research.md §2)",
            sin_datos.componente == "Host de Uptime Kuma",
        )


def test_congelar_host_externo_historico_es_reproducible() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        momento = datetime(2026, 8, 2, 12, 0, 0)
        filas_falsas = [("2026-08-02 10:00:00.000000", "1m")]

        with patch.object(host_externo, "_consultar_beszel_hub", return_value=filas_falsas):
            with store.connect(Path(tmp) / "diagnostico.db") as conn:
                e1 = host_externo.congelar_host_externo_historico(conn, "Host de Uptime Kuma", momento)
                e2 = host_externo.congelar_host_externo_historico(conn, "Host de Uptime Kuma", momento)

        check(
            "dos congelados del mismo momento producen la misma evidencia",
            e1.snapshot_evidencia["host_externo_stats"] == e2.snapshot_evidencia["host_externo_stats"],
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
