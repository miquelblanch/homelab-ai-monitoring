"""test_inventario_renovar — 2026-11-07: las declaraciones caducadas que se
cumplen con prueba real (vigiladas y que llegan al dashboard) se renuevan
solas; las demás siguen caducadas. Y `--revisar` las renueva a mano.
Base temporal: no toca la del homelab."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from inventory import evaluate, store
from inventory.model import Componente
from inventory.sources import RawComponente
from tests.selftest import check


def _ev(**k) -> evaluate.EvaluacionParcial:
    base = dict(tiene_estado_declarado=True, estado_declarado_status="caducada", esta_vigilado=True,
                mecanismo_vigilancia="x", llega_a_dashboard="si", es_intencionado=False)
    base.update(k)
    return evaluate.EvaluacionParcial(**base)


def test_regla_de_renovacion() -> None:
    check("caducada, vigilada y llega al panel → se renueva", evaluate.se_renueva_sola(_ev()) is True)
    check("vigente → no hay nada que renovar", evaluate.se_renueva_sola(_ev(estado_declarado_status="vigente")) is False)
    check("sin vigilancia real → sigue caducada", evaluate.se_renueva_sola(_ev(esta_vigilado=False)) is False)
    check("no llega al panel → sigue caducada", evaluate.se_renueva_sola(_ev(llega_a_dashboard="no")) is False)
    check("intencionada → solo a mano", evaluate.se_renueva_sola(_ev(es_intencionado=True)) is False)


def test_caldera_y_derivadas_no_son_brecha() -> None:
    caldera = RawComponente(componente=Componente(categoria="entidad_ha", nombre_actual="number.x_heating_curve"),
                            meta={"platform": "mypyllant", "disabled_by": None})
    derivada = RawComponente(componente=Componente(categoria="entidad_ha", nombre_actual="switch.calefaccion_encendida"),
                             meta={"platform": "template", "disabled_by": None})
    otra = RawComponente(componente=Componente(categoria="entidad_ha", nombre_actual="switch.otra_cosa"),
                         meta={"platform": "template", "disabled_by": None})
    check("entidad de la caldera (mypyllant): vigilada por el padre", evaluate.is_intentional(caldera) is True)
    check("ayudante derivado: vigilado por su origen", evaluate.is_intentional(derivada) is True)
    check("un template cualquiera no se da por intencionado", evaluate.is_intentional(otra) is False)


def _raw(nombre: str) -> RawComponente:
    return RawComponente(componente=Componente(categoria="contenedor", nombre_actual=nombre), meta={})


def test_save_run_renueva_y_revisar_a_mano() -> None:
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(evaluate.bridge, "docker_never_restart", return_value={"pausado"}):
        db = Path(tmp) / "inventario.db"
        with store.connect(db) as conn:
            store.save_run(conn, [_raw("web"), _raw("pausado")], disparador="manual")
            conn.execute("UPDATE componentes SET last_reviewed_at = '2026-01-01'")
            conn.commit()

            run = store.save_run(conn, [_raw("web"), _raw("pausado")], disparador="manual")
            fechas = {r["nombre_actual"]: r["last_reviewed_at"] for r in
                      conn.execute("SELECT nombre_actual, last_reviewed_at FROM componentes")}
            brechas = conn.execute("SELECT total_brechas FROM ejecuciones WHERE id = ?", (run,)).fetchone()[0]
            check("contenedor vigilado y caducado: renovado hoy", fechas["web"] == date.today().isoformat())
            check("intencionado caducado: no se renueva solo", fechas["pausado"] == "2026-01-01")
            check("tras renovar, ninguna brecha", brechas == 0)

            hechos = store.revisar_por_nombre(conn, "pausado", date.today())
            fecha = conn.execute("SELECT last_reviewed_at FROM componentes WHERE nombre_actual = 'pausado'").fetchone()[0]
            check("--revisar encuentra el componente por su nombre", hechos == ["[contenedor] pausado"])
            check("--revisar lo marca revisado hoy", fecha == date.today().isoformat())
            check("--revisar con un nombre que no existe no toca nada", store.revisar_por_nombre(conn, "no-existe", date.today()) == [])
