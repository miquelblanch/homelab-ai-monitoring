"""test_deliver — límite de tamaño del mensaje de Telegram, descubierto
en la primera ejecución real (830 componentes, 385 brechas) y no
cubierto por ninguna tarea de `tasks.md` — se añade aquí directamente."""

from __future__ import annotations

import tempfile
from pathlib import Path

from inventory import deliver, store
from inventory.model import Brecha, Componente, Ejecucion, Hallazgo
from tests.selftest import check


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


def test_mensaje_con_muchas_brechas_no_supera_el_limite_de_telegram() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            run = store.insert_ejecucion(conn, Ejecucion(disparador="manual"))
            # Simula el caso real: cientos de entidades HA con la misma brecha.
            for i in range(400):
                cid = store.insert_componente(
                    conn, Componente(categoria="entidad_ha", nombre_actual=f"sensor.prueba_{i}")
                )
                h = store.insert_hallazgo(conn, _hallazgo_brecha(run, cid))
                store.insert_brecha(
                    conn,
                    Brecha(
                        hallazgo_id=h,
                        tipo="sin_declaracion",
                        primera_ejecucion_id=run,
                        contexto=f"sensor.prueba_{i} sin declaración",
                    ),
                )
            conn.execute(
                "UPDATE ejecuciones SET total_componentes = ?, total_brechas = ? WHERE id = ?",
                (400, 400, run),
            )
            conn.commit()

            texto = deliver.build_report_text(conn, run)
            check(
                f"400 brechas de la misma categoría se resumen, no listan ({len(texto)} caracteres)",
                len(texto) <= deliver.TELEGRAM_MAX_CHARS,
            )
            check(
                "el resumen agrupado menciona el conteo total",
                "400 brechas" in texto,
            )
