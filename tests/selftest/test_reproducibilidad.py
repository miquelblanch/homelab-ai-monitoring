"""test_reproducibilidad — T023, resuelve el hallazgo E2 de
/speckit-analyze (2026-08-10): con `llamar_deepseek` fijado a la misma
respuesta en dos invocaciones seguidas de `diagnosticar_episodio` sobre
el mismo episodio ya congelado, la tubería determinista (parseo →
persistencia) debe producir el mismo `conclusion_tipo` y el mismo
desenlace por hipótesis, en el mismo orden, las dos veces (SC-001).

La varianza real de DeepSeek en producción sigue siendo el hallazgo
aparte que el Edge Case del spec ya reconoce — esto prueba la parte que
el código puede garantizar, no la del modelo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import deepseek, store
from diagnostico.model import Episodio
from tests.selftest import check

_RESPUESTA_FIJA = {
    "choices": [{"message": {"content": json.dumps({
        "conclusion_tipo": "causa_probable",
        "conclusion_texto": "presión de memoria en la ventana del episodio",
        "hipotesis": [
            {"descripcion": "presión de memoria", "comprobacion": "memory_percent > 90%",
             "desenlace": "confirmada"},
            {"descripcion": "fallo de red", "comprobacion": "sin errores en los logs",
             "desenlace": "descartada"},
        ],
    }, ensure_ascii=False)}}],
    "usage": {"prompt_tokens": 500, "completion_tokens": 300},
}


def test_dos_diagnosticos_sobre_el_mismo_episodio_coinciden() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            episodio_id = store.insert_episodio(
                conn,
                Episodio(
                    contenedor="beszel", es_critico=False, en_vivo=False,
                    ventana_inicio="a", ventana_fin="b",
                    snapshot_evidencia={"restart_history": None, "container_metrics": []},
                ),
            )
            episodio = store.get_episodio(conn, episodio_id)

            with patch.object(deepseek.bridge, "get_secret", return_value="fake-key-for-test"), \
                 patch.object(deepseek, "llamar_deepseek", return_value=_RESPUESTA_FIJA):
                diagnostico_1, hipotesis_1 = deepseek.diagnosticar_episodio(conn, episodio)
                diagnostico_2, hipotesis_2 = deepseek.diagnosticar_episodio(conn, episodio)

        check(
            "SC-001: mismo conclusion_tipo en los dos intentos",
            diagnostico_1.conclusion_tipo == diagnostico_2.conclusion_tipo == "causa_probable",
        )
        check(
            "los dos intentos son diagnósticos distintos, ninguno pisa al otro (Principio VIII)",
            diagnostico_1.id != diagnostico_2.id,
        )
        check(
            "SC-001: mismo número de hipótesis en los dos intentos",
            len(hipotesis_1) == len(hipotesis_2) == 2,
        )
        check(
            "SC-001: mismo desenlace por hipótesis y en el mismo orden",
            [h.desenlace for h in hipotesis_1] == [h.desenlace for h in hipotesis_2]
            == ["confirmada", "descartada"],
        )
