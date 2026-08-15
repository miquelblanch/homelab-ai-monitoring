"""test_evidencia_hub_beszel — origen hub de Beszel (feature 015).
Movido de `test_evidencia.py` en specs/023-evidencia-por-origen/
(T023).

**Punto crítico de esta migración** (research.md §3 de 023):
`_consultar_beszel_hub_todos_sistemas` se define en `hub_beszel.py`,
así que `patch.object(hub_beszel, "_consultar_beszel_hub_todos_sistemas", ...)`
es el único target que de verdad intercepta la llamada real.
`BESZEL_HOSTS_JSON` vive en `_compartido.py` pero `hub_beszel.py` la
importó a su propio namespace — el patch tiene que apuntar a
`hub_beszel.BESZEL_HOSTS_JSON`, no a `_compartido`.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from diagnostico import store
from diagnostico.evidencia import hub_beszel
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


def _escribir_json(path: Path, datos: dict) -> None:
    path.write_text(json.dumps(datos))


def _hub_systems_json(edades_s: dict[str, float]) -> dict:
    ahora_utc = datetime.now(ZoneInfo("UTC"))
    hub_systems = {
        nombre: (ahora_utc - timedelta(seconds=edad)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
        for nombre, edad in edades_s.items()
    }
    return {"generated_at": ahora_utc.isoformat(timespec="seconds"), "hosts": {}, "hub_systems": hub_systems}


def test_hub_beszel_actual_sano_con_uno_caducado_entre_varios() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        hosts_json = Path(tmp) / "beszel_hosts.json"
        _escribir_json(hosts_json, _hub_systems_json({
            "Mac Mini Server": 60, "AdGuardHome": 60, "UptimeKuma": 2000,
        }))
        with patch.object(hub_beszel, "BESZEL_HOSTS_JSON", hosts_json):
            estado = hub_beszel._hub_beszel_actual()

        check("3 sistemas presentes", len(estado["systems"]) == 3)
        check(
            "un sistema caducado entre varios frescos ⇒ sano=True (un solo sistema viejo no cuenta)",
            estado["sano"] is True,
        )


def test_hub_beszel_actual_no_sano_todos_caducados() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        hosts_json = Path(tmp) / "beszel_hosts.json"
        _escribir_json(hosts_json, _hub_systems_json({
            "Mac Mini Server": 2000, "AdGuardHome": 2500, "UptimeKuma": 3000,
        }))
        with patch.object(hub_beszel, "BESZEL_HOSTS_JSON", hosts_json):
            estado = hub_beszel._hub_beszel_actual()

        check("todos caducados a la vez ⇒ sano=False", estado["sano"] is False)


def test_hub_beszel_actual_sin_sistemas_no_sano() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        hosts_json = Path(tmp) / "beszel_hosts.json"
        _escribir_json(hosts_json, {"generated_at": "2026-08-12T00:00:00", "hosts": {}, "hub_systems": {}})
        with patch.object(hub_beszel, "BESZEL_HOSTS_JSON", hosts_json):
            estado = hub_beszel._hub_beszel_actual()

        check("sin ningún sistema registrado ⇒ sano=False, sin lanzar", estado == {"systems": [], "sano": False})


def test_congelar_hub_beszel_vivo_arma_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp_beszel, tempfile.TemporaryDirectory() as tmp_db:
        hosts_json = Path(tmp_beszel) / "beszel_hosts.json"
        _escribir_json(hosts_json, _hub_systems_json({"Mac Mini Server": 60}))

        with patch.object(hub_beszel, "BESZEL_HOSTS_JSON", hosts_json):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = hub_beszel.congelar_hub_beszel_vivo(conn)

        check("origen = hub_beszel", episodio.origen == "hub_beszel")
        check("es_critico siempre False", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "hub_beszel_actual poblado, hub_beszel_stats queda null",
            episodio.snapshot_evidencia["hub_beszel_actual"] is not None
            and episodio.snapshot_evidencia["hub_beszel_actual"]["sano"] is True
            and episodio.snapshot_evidencia["hub_beszel_stats"] is None,
        )
        check("componente es un momento ISO, sin identificador", "T" in episodio.componente)


def test_resumen_por_sistema() -> None:
    filas = [
        ("Mac Mini Server", "2026-08-02 08:00:00.000000", "120m"),
        ("Mac Mini Server", "2026-08-02 12:00:00.000000", "120m"),
        ("AdGuardHome", None, None),
        ("UptimeKuma", None, None),
    ]
    resumen = hub_beszel._resumen_por_sistema(filas)

    check(
        "Mac Mini Server con 2 muestras, los otros dos con 0",
        resumen["por_sistema"]["Mac Mini Server"]["total_muestras"] == 2
        and resumen["por_sistema"]["AdGuardHome"]["total_muestras"] == 0
        and resumen["por_sistema"]["UptimeKuma"]["total_muestras"] == 0,
    )
    check(
        "ausencia PARCIAL (Mac Mini sí tiene) ⇒ todos_sin_muestras=False",
        resumen["todos_sin_muestras"] is False,
    )

    filas_todas_vacias = [
        ("Mac Mini Server", None, None),
        ("AdGuardHome", None, None),
    ]
    resumen_vacio = hub_beszel._resumen_por_sistema(filas_todas_vacias)
    check("ausencia TOTAL ⇒ todos_sin_muestras=True", resumen_vacio["todos_sin_muestras"] is True)

    resumen_ninguno = hub_beszel._resumen_por_sistema([])
    check(
        "sin ningún sistema registrado (lista vacía) ⇒ todos_sin_muestras=False, no True",
        resumen_ninguno == {"por_sistema": {}, "todos_sin_muestras": False},
    )


def test_congelar_hub_beszel_historico_distingue_none_de_lista_y_es_reproducible() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        momento = datetime(2026, 8, 2, 12, 0, 0)
        filas_falsas = [
            ("Mac Mini Server", "2026-08-02 10:00:00.000000", "120m"),
            ("AdGuardHome", None, None),
        ]

        with patch.object(hub_beszel, "_consultar_beszel_hub_todos_sistemas", return_value=filas_falsas):
            with store.connect(Path(tmp) / "diagnostico1.db") as conn:
                e1 = hub_beszel.congelar_hub_beszel_historico(conn, momento)
                e2 = hub_beszel.congelar_hub_beszel_historico(conn, momento)

        with patch.object(hub_beszel, "_consultar_beszel_hub_todos_sistemas", return_value=None):
            with store.connect(Path(tmp) / "diagnostico2.db") as conn:
                consulta_fallida = hub_beszel.congelar_hub_beszel_historico(conn, momento)

        check(
            "dos congelados del mismo momento producen la misma evidencia",
            e1.snapshot_evidencia["hub_beszel_stats"] == e2.snapshot_evidencia["hub_beszel_stats"],
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
        check(
            "consulta con éxito ⇒ hub_beszel_stats con todos_sin_muestras=False (Mac Mini sí tiene)",
            e1.snapshot_evidencia["hub_beszel_stats"]["todos_sin_muestras"] is False,
        )
        check(
            "consulta fallida (None) ⇒ hub_beszel_stats=None, sin lanzar TypeError",
            consulta_fallida.snapshot_evidencia["hub_beszel_stats"] is None,
        )
        check("componente = momento pedido, sin identificador", e1.componente == momento.isoformat())
