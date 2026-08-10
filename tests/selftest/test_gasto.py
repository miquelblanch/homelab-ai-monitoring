"""test_gasto — T028: cálculo de coste a partir de tokens fijos,
`hay_presupuesto()` en los tres casos (por debajo / al límite / por
encima) usando la cifra concreta de `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`
(research.md §6, hallazgo B1), y reinicio del acumulado al cambiar de
día natural (Edge Case del spec).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import gasto, store
from tests.selftest import check


def test_calcular_coste_eur_a_partir_de_tokens_fijos() -> None:
    coste = gasto.calcular_coste_eur(1_000_000, 1_000_000)
    esperado = (
        gasto.PRECIOS_EUR_POR_MILLON_TOKENS["entrada"]
        + gasto.PRECIOS_EUR_POR_MILLON_TOKENS["salida"]
    )
    check("coste de 1M+1M tokens es la suma de los precios por millón", abs(coste - esperado) < 1e-9)
    check("cero tokens cuesta cero", gasto.calcular_coste_eur(0, 0) == 0.0)


def test_hay_presupuesto_por_debajo_del_limite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with patch.dict(os.environ, {"DIAGNOSTICO_LIMITE_EUR_DIA": "5.0"}):
            with store.connect(db) as conn:
                check(
                    "sin gasto acumulado hoy, hay presupuesto de sobra",
                    gasto.hay_presupuesto(conn, tokens_entrada_reales=500) is True,
                )


def test_hay_presupuesto_al_limite_ya_alcanzado() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with patch.dict(os.environ, {"DIAGNOSTICO_LIMITE_EUR_DIA": "5.0"}):
            with store.connect(db) as conn:
                store.upsert_gasto_diario(conn, gasto.dia_actual(), 5.0, gasto.limite_diario_eur())
                check(
                    "gasto ya igual al límite ⇒ no hay presupuesto para una llamada más",
                    gasto.hay_presupuesto(conn, tokens_entrada_reales=500) is False,
                )


def test_hay_presupuesto_por_encima_del_limite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with patch.dict(os.environ, {"DIAGNOSTICO_LIMITE_EUR_DIA": "5.0"}):
            with store.connect(db) as conn:
                store.upsert_gasto_diario(conn, gasto.dia_actual(), 8.0, gasto.limite_diario_eur())
                check(
                    "gasto ya por encima del límite ⇒ no hay presupuesto",
                    gasto.hay_presupuesto(conn, tokens_entrada_reales=500) is False,
                )


def test_hay_presupuesto_limite_cero_bloquea_todo() -> None:
    """FR-010, quickstart.md Escenario 3."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with patch.dict(os.environ, {"DIAGNOSTICO_LIMITE_EUR_DIA": "0.0"}):
            with store.connect(db) as conn:
                check(
                    "límite diario en 0.0 bloquea cualquier llamada nueva",
                    gasto.hay_presupuesto(conn, tokens_entrada_reales=1) is False,
                )


def test_gasto_se_reinicia_al_cambiar_de_dia_natural() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            store.upsert_gasto_diario(conn, "2026-08-10", 4.9, limite_eur=5.0)

            with patch.object(gasto, "dia_actual", return_value="2026-08-10"):
                gasto_dia_1 = gasto.gasto_hoy(conn)
            with patch.object(gasto, "dia_actual", return_value="2026-08-11"):
                gasto_dia_2 = gasto.gasto_hoy(conn)

        check("el gasto del día con acumulado se lee tal cual", gasto_dia_1 == 4.9)
        check("un día nuevo empieza en 0.0, no arrastra el acumulado de ayer", gasto_dia_2 == 0.0)


def test_registrar_coste_acumula_y_devuelve_el_coste_de_la_llamada() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            coste = gasto.registrar_coste(conn, tokens_entrada=1000, tokens_salida=500)
            acumulado = gasto.gasto_hoy(conn)

        check("registrar_coste devuelve el coste real de esa llamada", coste > 0.0)
        check("el acumulado del día refleja ese coste", abs(acumulado - coste) < 1e-9)
