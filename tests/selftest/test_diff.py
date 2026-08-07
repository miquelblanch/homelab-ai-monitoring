"""test_diff — T035: nuevas vs conocidas entre ejecuciones (FR-013,
FR-015) y retención sin purga (FR-017, Clarification 2), contra una BD
temporal. Construye componentes/ejecuciones/hallazgos/brechas a mano con
`store.insert_*` para tener control total sobre el escenario, en vez de
depender de fuentes reales."""

from __future__ import annotations

import tempfile
from pathlib import Path

from inventory import diff, store
from inventory.model import Brecha, Componente, Ejecucion, Hallazgo
from tests.selftest import check


def _hallazgo_ok(ejecucion_id: int, componente_id: int) -> Hallazgo:
    return Hallazgo(
        ejecucion_id=ejecucion_id,
        componente_id=componente_id,
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="docker_monitor.py",
        llega_a_dashboard="si",
        es_brecha=False,
    )


def _hallazgo_brecha(ejecucion_id: int, componente_id: int) -> Hallazgo:
    return Hallazgo(
        ejecucion_id=ejecucion_id,
        componente_id=componente_id,
        tiene_estado_declarado=False,
        estado_declarado_status="ausente",
        esta_vigilado=False,
        mecanismo_vigilancia=None,
        llega_a_dashboard="no",
        es_brecha=True,
    )


def test_compare_runs_distingue_nuevas_resueltas_altas_bajas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            # Componentes: A (siempre ok), B (brecha->resuelta), C (solo run1, de baja), D (solo run2, nuevo).
            a = store.insert_componente(conn, Componente(categoria="contenedor", nombre_actual="A"))
            b = store.insert_componente(conn, Componente(categoria="contenedor", nombre_actual="B"))
            c = store.insert_componente(conn, Componente(categoria="contenedor", nombre_actual="C"))

            run1 = store.insert_ejecucion(conn, Ejecucion(disparador="manual"))
            h_a1 = store.insert_hallazgo(conn, _hallazgo_ok(run1, a))
            h_b1 = store.insert_hallazgo(conn, _hallazgo_brecha(run1, b))
            store.insert_brecha(
                conn,
                Brecha(hallazgo_id=h_b1, tipo="sin_declaracion", primera_ejecucion_id=run1, contexto="B"),
            )
            h_c1 = store.insert_hallazgo(conn, _hallazgo_ok(run1, c))
            conn.commit()

            d = store.insert_componente(conn, Componente(categoria="contenedor", nombre_actual="D"))
            run2 = store.insert_ejecucion(conn, Ejecucion(disparador="manual"))
            store.insert_hallazgo(conn, _hallazgo_ok(run2, a))
            store.insert_hallazgo(conn, _hallazgo_ok(run2, b))  # B ya no es brecha
            # C no aparece en run2 (de baja).
            h_d2 = store.insert_hallazgo(conn, _hallazgo_brecha(run2, d))
            store.insert_brecha(
                conn,
                Brecha(hallazgo_id=h_d2, tipo="sin_declaracion", primera_ejecucion_id=run2, contexto="D"),
            )
            conn.commit()

            comp = diff.compare_runs(conn, run2, run1)

            check("D es componente nuevo", comp.componentes_nuevos == ["D"])
            check("C es componente de baja", comp.componentes_de_baja == ["C"])
            check(
                "brecha de D es nueva",
                any("D" in b for b in comp.brechas_nuevas),
            )
            check(
                "brecha de B ya no aparece como nueva (fue resuelta, no repetida)",
                not any("B" in b for b in comp.brechas_nuevas),
            )
            check(
                "brecha de B aparece como resuelta",
                any("B" in b for b in comp.brechas_resueltas),
            )


def test_retencion_sin_purga() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            for _ in range(5):
                store.insert_ejecucion(conn, Ejecucion(disparador="manual"))
            conn.commit()
            total = conn.execute("SELECT COUNT(*) FROM ejecuciones").fetchone()[0]
            check(
                "las 5 ejecuciones siguen todas — nada se purga (FR-017, Clarification 2)",
                total == 5,
            )
