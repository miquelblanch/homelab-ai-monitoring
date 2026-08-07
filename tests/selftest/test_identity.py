"""test_identity — T034: emparejamiento por identificador estable entre
ejecuciones (FR-015, Clarification 1), contra una BD temporal."""

from __future__ import annotations

import tempfile
from pathlib import Path

from inventory import identity, store
from inventory.model import Componente
from tests.selftest import check


def test_empareja_por_identificador_estable_aunque_cambie_el_nombre() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            cid = store.insert_componente(
                conn,
                Componente(
                    categoria="contenedor",
                    nombre_actual="nextcloud",
                    identificador_estable="nextcloud",
                ),
            )
            conn.commit()

            # Mismo identificador_estable, nombre_actual distinto (rename).
            encontrado = identity.match_component(conn, "contenedor", "nextcloud", "nextcloud-renombrado")
            check(
                "mismo identificador estable ⇒ mismo componente, aunque cambie el nombre",
                encontrado is not None and encontrado["id"] == cid,
            )


def test_sin_identificador_estable_es_baja_mas_alta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            store.insert_componente(
                conn,
                Componente(
                    categoria="entidad_ha",
                    nombre_actual="sensor.viejo_nombre",
                    identificador_estable=None,
                ),
            )
            conn.commit()

            encontrado = identity.match_component(
                conn, "entidad_ha", None, "sensor.nombre_nuevo"
            )
            check(
                "sin identificador estable, nombre distinto ⇒ no se empareja (baja+alta)",
                encontrado is None,
            )


def test_sin_identificador_estable_pero_mismo_nombre_si_empareja() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        with store.connect(db) as conn:
            cid = store.insert_componente(
                conn,
                Componente(
                    categoria="integracion",
                    nombre_actual="Recordatorios de Nextcloud (Tareas/Calendario)",
                    identificador_estable=None,
                ),
            )
            conn.commit()

            encontrado = identity.match_component(
                conn, "integracion", None, "Recordatorios de Nextcloud (Tareas/Calendario)"
            )
            check(
                "sin identificador estable, mismo nombre ⇒ mismo componente",
                encontrado is not None and encontrado["id"] == cid,
            )
