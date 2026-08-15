"""test_evidencia_inventario — origen inventario de cobertura (feature
013). Movido de `test_evidencia.py` en specs/023-evidencia-por-origen/
(T021).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import inventario
from inventory import diff as inv_diff
from inventory import store as inv_store
from inventory.model import Brecha, Componente, Ejecucion, Hallazgo
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


def _hallazgo_inv_ok(ejecucion_id: int, componente_id: int) -> Hallazgo:
    return Hallazgo(
        ejecucion_id=ejecucion_id,
        componente_id=componente_id,
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="algún_mecanismo.py",
        llega_a_dashboard="si",
        es_brecha=False,
    )


def _hallazgo_inv_brecha(ejecucion_id: int, componente_id: int) -> Hallazgo:
    return Hallazgo(
        ejecucion_id=ejecucion_id,
        componente_id=componente_id,
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="algún_mecanismo.py",
        llega_a_dashboard="no",
        es_brecha=True,
    )


def _construir_inventario_fake(conn_inv: sqlite3.Connection) -> dict:
    """Tres ejecuciones: run1 sana (ancla real), run2 introduce una
    brecha real de 'Agente Hermes/Bautista' y una de
    'condicion_incumplida' aparte, run3 la mantiene (misma
    `primera_ejecucion_id` que run2, imitando lo que haría
    `populate_brechas()` en producción). Mismo patrón de construcción a
    mano que `tests/selftest/test_diff.py`."""
    hermes = inv_store.insert_componente(
        conn_inv, Componente(categoria="hermes", nombre_actual="Agente Hermes/Bautista")
    )
    sano = inv_store.insert_componente(
        conn_inv, Componente(categoria="contenedor", nombre_actual="beszel")
    )
    cerradura = inv_store.insert_componente(
        conn_inv, Componente(categoria="entidad_ha", nombre_actual="cerradura_bateria_ha")
    )

    run1 = inv_store.insert_ejecucion(conn_inv, Ejecucion(disparador="manual"))
    inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_ok(run1, hermes))
    inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_ok(run1, sano))
    conn_inv.commit()

    run2 = inv_store.insert_ejecucion(conn_inv, Ejecucion(disparador="manual"))
    h_hermes2 = inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_brecha(run2, hermes))
    inv_store.insert_brecha(
        conn_inv,
        Brecha(
            hallazgo_id=h_hermes2, tipo="no_llega_a_dashboard",
            primera_ejecucion_id=run2, contexto="Agente Hermes/Bautista sin llegar al dashboard",
        ),
    )
    inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_ok(run2, sano))
    h_cerradura2 = inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_brecha(run2, cerradura))
    inv_store.insert_brecha(
        conn_inv,
        Brecha(
            hallazgo_id=h_cerradura2, tipo="condicion_incumplida",
            primera_ejecucion_id=run2, contexto="cerradura con condición incumplida",
        ),
    )
    conn_inv.commit()

    run3 = inv_store.insert_ejecucion(conn_inv, Ejecucion(disparador="manual"))
    h_hermes3 = inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_brecha(run3, hermes))
    inv_store.insert_brecha(
        conn_inv,
        Brecha(
            # primera_ejecucion_id sigue apuntando a run2 — la racha empezó
            # ahí, no en run3 (mismo criterio que populate_brechas real,
            # research.md §10 de 013).
            hallazgo_id=h_hermes3, tipo="no_llega_a_dashboard",
            primera_ejecucion_id=run2, contexto="sigue sin llegar al dashboard",
        ),
    )
    inv_store.insert_hallazgo(conn_inv, _hallazgo_inv_ok(run3, sano))
    conn_inv.commit()

    return {"run1": run1, "run2": run2, "run3": run3}


def test_hallazgo_y_brecha_de_componente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with inv_store.connect(Path(tmp) / "inventario.db") as conn_inv:
            runs = _construir_inventario_fake(conn_inv)

            con_brecha = inventario._hallazgo_de_componente(conn_inv, runs["run2"], "Agente Hermes/Bautista")
            brecha = inventario._brecha_de_componente(conn_inv, runs["run2"], "Agente Hermes/Bautista")
            sano = inventario._brecha_de_componente(conn_inv, runs["run2"], "beszel")
            inexistente = inventario._hallazgo_de_componente(conn_inv, runs["run2"], "no existe")

        check("hallazgo de un componente con brecha se encuentra", con_brecha is not None and con_brecha["es_brecha"])
        check("brecha real trae su tipo", brecha is not None and brecha["tipo"] == "no_llega_a_dashboard")
        check("componente sano no tiene brecha", sano is None)
        check("componente inexistente devuelve None, sin lanzar", inexistente is None)


def test_validar_tipo_brecha_inventario_rechaza_condicion_incumplida() -> None:
    lanzo = False
    try:
        inventario._validar_tipo_brecha_inventario({"tipo": "condicion_incumplida"})
    except ValueError:
        lanzo = True
    check("condicion_incumplida lanza ValueError (FR-010)", lanzo)

    try:
        inventario._validar_tipo_brecha_inventario({"tipo": "sin_declaracion"})
        inventario._validar_tipo_brecha_inventario(None)
        ok = True
    except ValueError:
        ok = False
    check("un tipo en alcance, o ninguna brecha, no lanza", ok)


def test_comparacion_dict_acota_a_max_entradas() -> None:
    comparacion = inv_diff.Comparacion(
        ejecucion_actual_id=2,
        ejecucion_previa_id=1,
        componentes_nuevos=[f"nuevo_{i}" for i in range(40)],
        componentes_de_baja=[],
        brechas_nuevas=[f"brecha_{i}" for i in range(319)],
        brechas_resueltas=[],
    )
    resultado = inventario._comparacion_dict(comparacion)

    check(
        "brechas_nuevas acotado a 30 entradas, con el total real",
        len(resultado["brechas_nuevas"]["muestra"]) == 30
        and resultado["brechas_nuevas"]["total"] == 319,
    )
    check(
        "una lista corta no se trunca de más",
        len(resultado["componentes_nuevos"]["muestra"]) == 30
        and resultado["componentes_nuevos"]["total"] == 40,
    )
    check("lista vacía queda vacía, total 0", resultado["componentes_de_baja"] == {"total": 0, "muestra": []})


def test_congelar_inventario_vivo_arma_snapshot_con_brecha_real() -> None:
    with tempfile.TemporaryDirectory() as tmp_inv, tempfile.TemporaryDirectory() as tmp_db:
        with inv_store.connect(Path(tmp_inv) / "inventario.db") as conn_inv:
            runs = _construir_inventario_fake(conn_inv)

        with patch.object(inv_store, "db_path", return_value=Path(tmp_inv) / "inventario.db"):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = inventario.congelar_inventario_vivo(conn, "Agente Hermes/Bautista")

        check("componente = nombre_actual", episodio.componente == "Agente Hermes/Bautista")
        check("origen = inventario", episodio.origen == "inventario")
        check("es_critico siempre False para inventario", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        snap = episodio.snapshot_evidencia
        check("congela la ejecución más reciente (run3)", snap["inventario_ejecucion_id"] == runs["run3"])
        check(
            "hallazgo y brecha reales presentes",
            snap["inventario_hallazgo"] is not None and snap["inventario_hallazgo"]["es_brecha"]
            and snap["inventario_brecha"]["tipo"] == "no_llega_a_dashboard",
        )
        check(
            "comparación ancla a primera_ejecucion_id - 1 (run1), no a ejecucion_id - 1 (run2)",
            snap["inventario_comparacion"] is not None
            and snap["inventario_comparacion"]["ejecucion_previa_id"] == runs["run1"],
        )


def test_congelar_inventario_vivo_componente_sano_y_nombre_inexistente() -> None:
    with tempfile.TemporaryDirectory() as tmp_inv, tempfile.TemporaryDirectory() as tmp_db:
        with inv_store.connect(Path(tmp_inv) / "inventario.db") as conn_inv:
            _construir_inventario_fake(conn_inv)

        with patch.object(inv_store, "db_path", return_value=Path(tmp_inv) / "inventario.db"):
            with store.connect(_diag_db(tmp_db)) as conn:
                sano = inventario.congelar_inventario_vivo(conn, "beszel")
                inexistente = inventario.congelar_inventario_vivo(conn, "componente que no existe")

        check(
            "componente sano: hallazgo presente, sin brecha ni comparación",
            sano.snapshot_evidencia["inventario_hallazgo"] is not None
            and not sano.snapshot_evidencia["inventario_hallazgo"]["es_brecha"]
            and sano.snapshot_evidencia["inventario_brecha"] is None
            and sano.snapshot_evidencia["inventario_comparacion"] is None,
        )
        check(
            "nombre inexistente: todo en null, sin lanzar",
            inexistente.snapshot_evidencia["inventario_hallazgo"] is None
            and inexistente.snapshot_evidencia["inventario_brecha"] is None,
        )


def test_congelar_inventario_historico_reproducible_y_ancla_correctamente() -> None:
    with tempfile.TemporaryDirectory() as tmp_inv, tempfile.TemporaryDirectory() as tmp_db:
        with inv_store.connect(Path(tmp_inv) / "inventario.db") as conn_inv:
            runs = _construir_inventario_fake(conn_inv)

        with patch.object(inv_store, "db_path", return_value=Path(tmp_inv) / "inventario.db"):
            with store.connect(_diag_db(tmp_db)) as conn:
                e1 = inventario.congelar_inventario_historico(conn, "Agente Hermes/Bautista", runs["run3"])
                e2 = inventario.congelar_inventario_historico(conn, "Agente Hermes/Bautista", runs["run3"])
                inexistente = inventario.congelar_inventario_historico(
                    conn, "Agente Hermes/Bautista", 999999
                )

        check(
            "dos congelados de la misma NOMBRE@EJECUCION_ID producen la misma evidencia",
            e1.snapshot_evidencia["inventario_brecha"] == e2.snapshot_evidencia["inventario_brecha"],
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
        check(
            "componente = NOMBRE solo, nunca incluye la ejecución (research.md §3)",
            e1.componente == "Agente Hermes/Bautista",
        )
        check(
            "ejecución pedida (run3) da comparación anclada a run1, no a run3-1 (run2)",
            e1.snapshot_evidencia["inventario_comparacion"]["ejecucion_previa_id"] == runs["run1"],
        )
        check(
            "EJECUCION_ID inexistente congela igual, con evidencia vacía",
            inexistente.snapshot_evidencia["inventario_hallazgo"] is None
            and inexistente.componente == "Agente Hermes/Bautista",
        )


def test_congelar_inventario_historico_condicion_incumplida_lanza() -> None:
    with tempfile.TemporaryDirectory() as tmp_inv, tempfile.TemporaryDirectory() as tmp_db:
        with inv_store.connect(Path(tmp_inv) / "inventario.db") as conn_inv:
            runs = _construir_inventario_fake(conn_inv)

        lanzo = False
        with patch.object(inv_store, "db_path", return_value=Path(tmp_inv) / "inventario.db"):
            with store.connect(_diag_db(tmp_db)) as conn:
                try:
                    inventario.congelar_inventario_historico(conn, "cerradura_bateria_ha", runs["run2"])
                except ValueError:
                    lanzo = True

        check("brecha condicion_incumplida se rechaza antes de congelar (FR-010)", lanzo)
