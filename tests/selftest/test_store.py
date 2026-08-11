"""test_store — T014 (esquema, episodios) y T022 (diagnósticos e
hipótesis, varios intentos por episodio)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from diagnostico import store
from diagnostico.model import Diagnostico, Episodio, Hipotesis
from tests.selftest import check


def test_init_db_es_idempotente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        store.init_db(db)
        store.init_db(db)  # segunda vez no debe fallar
        check("init_db() dos veces no lanza", True)


def test_insert_y_lectura_de_episodio() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            episodio = Episodio(
                componente="beszel",
                es_critico=False,
                en_vivo=False,
                ventana_inicio="2026-03-29T12:00:00",
                ventana_fin="2026-03-29T13:00:00",
                snapshot_evidencia={"restart_history": {"id": 16}, "container_metrics": []},
                restart_history_id=16,
            )
            episodio_id = store.insert_episodio(conn, episodio)
            leido = store.get_episodio(conn, episodio_id)
            inexistente = store.get_episodio(conn, 999)

        check("insert_episodio devuelve un id", episodio_id is not None)
        check("get_episodio recupera el mismo contenedor", leido.componente == "beszel")
        check(
            "snapshot_evidencia se conserva como dict de ida y vuelta (JSON)",
            leido.snapshot_evidencia["restart_history"]["id"] == 16,
        )
        check("get_episodio de un id inexistente devuelve None", inexistente is None)


def test_insert_diagnostico_e_hipotesis_de_ida_y_vuelta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            episodio_id = store.insert_episodio(
                conn,
                Episodio(
                    componente="beszel", es_critico=False, en_vivo=False,
                    ventana_inicio="a", ventana_fin="b", snapshot_evidencia={},
                ),
            )
            diagnostico_id = store.insert_diagnostico(
                conn,
                Diagnostico(
                    episodio_id=episodio_id,
                    conclusion_tipo="no_diagnosticable",
                    conclusion_texto="sin evidencia suficiente",
                    modelo="deepseek-chat",
                    tokens_entrada=100,
                    tokens_salida=50,
                    coste_eur=0.001,
                ),
            )
            store.insert_hipotesis(
                conn,
                Hipotesis(
                    diagnostico_id=diagnostico_id, orden=0,
                    descripcion="presión de memoria", comprobacion="cpu/mem normales en la ventana",
                    desenlace="descartada",
                ),
            )
            store.insert_hipotesis(
                conn,
                Hipotesis(
                    diagnostico_id=diagnostico_id, orden=1,
                    descripcion="fallo de red", comprobacion="sin logs ni métricas que lo respalden",
                    desenlace="sin_evidencia_suficiente",
                ),
            )

            diagnosticos = store.diagnosticos_de_episodio(conn, episodio_id)
            hipotesis = store.hipotesis_de_diagnostico(conn, diagnostico_id)

        check("un diagnóstico persistido para el episodio", len(diagnosticos) == 1)
        check("dos hipótesis persistidas, en orden", [h["orden"] for h in hipotesis] == [0, 1])
        check(
            "los desenlaces se conservan tal cual",
            [h["desenlace"] for h in hipotesis] == ["descartada", "sin_evidencia_suficiente"],
        )


def test_varios_diagnosticos_sobre_el_mismo_episodio_conviven() -> None:
    """SC-001: comparar dos intentos de diagnóstico sobre el mismo
    episodio exige que ambos se conserven, no que el segundo pise al
    primero (Principio VIII)."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            episodio_id = store.insert_episodio(
                conn,
                Episodio(
                    componente="beszel", es_critico=False, en_vivo=False,
                    ventana_inicio="a", ventana_fin="b", snapshot_evidencia={},
                ),
            )
            for _ in range(2):
                store.insert_diagnostico(
                    conn,
                    Diagnostico(
                        episodio_id=episodio_id,
                        conclusion_tipo="no_diagnosticable",
                        conclusion_texto="sin evidencia suficiente",
                    ),
                )
            diagnosticos = store.diagnosticos_de_episodio(conn, episodio_id)

        check("dos intentos de diagnóstico coexisten para el mismo episodio", len(diagnosticos) == 2)
        check("ambos con id distinto", diagnosticos[0]["id"] != diagnosticos[1]["id"])


def test_migracion_contenedor_a_componente_es_idempotente_y_no_pierde_datos() -> None:
    """feature 009 (research.md §1 de specs/009-diagnostico-discos/):
    una base ya escrita por 007, con el esquema antiguo (`contenedor`,
    sin `origen`), debe migrarse sola al conectar — sin perder la fila
    ya persistida, y sin fallar si se conecta dos veces."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico_viejo.db"
        # Esquema tal cual lo dejó 007, antes de este feature.
        conn_raw = sqlite3.connect(db)
        conn_raw.execute(
            """CREATE TABLE episodios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contenedor TEXT NOT NULL,
                es_critico INTEGER NOT NULL,
                en_vivo INTEGER NOT NULL,
                restart_history_id INTEGER,
                ventana_inicio TEXT NOT NULL,
                ventana_fin TEXT NOT NULL,
                snapshot_evidencia TEXT NOT NULL,
                creado_en TEXT NOT NULL
            )"""
        )
        conn_raw.execute(
            "INSERT INTO episodios (contenedor, es_critico, en_vivo, "
            "ventana_inicio, ventana_fin, snapshot_evidencia, creado_en) "
            "VALUES ('beszel', 0, 0, 'a', 'b', '{}', '2026-08-10T00:00:00+00:00')"
        )
        conn_raw.commit()
        conn_raw.close()

        with store.connect(db) as conn:
            episodio = store.get_episodio(conn, 1)
        with store.connect(db) as conn:  # segunda conexión no debe fallar
            episodio_otra_vez = store.get_episodio(conn, 1)

        check(
            "el episodio ya escrito por 007 se lee tras migrar, mismo componente",
            episodio is not None and episodio.componente == "beszel",
        )
        check("origen por defecto = contenedor tras migrar", episodio.origen == "contenedor")
        check(
            "conectar dos veces tras la migración no falla ni duplica",
            episodio_otra_vez is not None and episodio_otra_vez.id == episodio.id,
        )


def test_upsert_gasto_diario_acumula_sin_pisar() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "diagnostico.db"
        with store.connect(db) as conn:
            store.upsert_gasto_diario(conn, "2026-08-10", 0.5, limite_eur=5.0)
            store.upsert_gasto_diario(conn, "2026-08-10", 0.3, limite_eur=5.0)
            fila = store.get_gasto_diario(conn, "2026-08-10")

        check("el coste se acumula (0.5 + 0.3)", abs(fila["coste_eur_acumulado"] - 0.8) < 1e-9)
        check("el límite queda fijado", fila["limite_eur"] == 5.0)
