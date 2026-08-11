"""test_baseline_beszel — T031, resuelve el hallazgo E1 de
/speckit-analyze (2026-08-10): re-verifica la línea base de `beszel`
(FR-011, SC-002, Principio IX) sin gasto real y sin depender de que
`homelab.db` conserve esas filas más allá de su retención — usa los tres
snapshots reales congelados en `fixtures/beszel_baseline.py`.

Con `llamar_deepseek` mockeado para devolver una respuesta
`no_diagnosticable` (la conclusión honesta que corresponde a evidencia
vacía, no una que el modelo real haya confirmado — ver el docstring de
la fixture), comprueba que la tubería completa persiste esa conclusión
para los tres sin alterarla. Si en el futuro cambia el prompt o el
formato de respuesta y esta prueba deja de pasar, es una señal real de
que algo en la tubería determinista se rompió — no sustituye ejecutar
`diagnosticar` de verdad (T030) una vez haya `DEEPSEEK_API_KEY`.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import deepseek, store
from diagnostico.model import Episodio
from tests.selftest import check
from tests.selftest.fixtures.beszel_baseline import EPISODIOS_SIN_EVIDENCIA

_RESPUESTA_NO_DIAGNOSTICABLE = {
    "choices": [{"message": {"content": json.dumps({
        "conclusion_tipo": "no_diagnosticable",
        "conclusion_texto": "sin métricas, logs ni datos de disco en la ventana del episodio",
        "hipotesis": [
            {"descripcion": "presión de memoria o CPU en el momento del reinicio",
             "comprobacion": "container_metrics y container_metrics_hourly vacíos para esta ventana",
             "desenlace": "sin_evidencia_suficiente"},
        ],
    }, ensure_ascii=False)}}],
    "usage": {"prompt_tokens": 400, "completion_tokens": 120},
}


def test_los_tres_episodios_sin_evidencia_concluyen_no_diagnosticable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            episodio_ids = []
            for caso in EPISODIOS_SIN_EVIDENCIA:
                episodio_id = store.insert_episodio(
                    conn,
                    Episodio(
                        componente=caso["contenedor"], es_critico=False, en_vivo=False,
                        ventana_inicio=caso["ventana_inicio"], ventana_fin=caso["ventana_fin"],
                        snapshot_evidencia=caso["snapshot_evidencia"],
                        restart_history_id=caso["restart_history_id"],
                    ),
                )
                episodio_ids.append(episodio_id)

            with patch.object(deepseek.bridge, "get_secret", return_value="fake-key-for-test"), \
                 patch.object(deepseek, "llamar_deepseek", return_value=_RESPUESTA_NO_DIAGNOSTICABLE):
                conclusiones = []
                for episodio_id in episodio_ids:
                    episodio = store.get_episodio(conn, episodio_id)
                    diagnostico, _ = deepseek.diagnosticar_episodio(conn, episodio)
                    conclusiones.append(diagnostico.conclusion_tipo)

        check(
            "los tres episodios reales sin evidencia concluyen no_diagnosticable (FR-011/SC-002)",
            conclusiones == ["no_diagnosticable"] * 3,
        )
