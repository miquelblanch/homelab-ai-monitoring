"""test_remediacion_store — persistencia pura: configuración de acción
e intentos, contra una base sqlite en un fichero temporal (nunca la
real)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from remediacion import store
from remediacion.model import IntentoRemediacion
from tests.selftest import check


def _db(tmp: str) -> Path:
    return Path(tmp) / "remediacion.db"


def test_init_db_dos_veces_no_lanza() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        store.init_db(path)
        store.init_db(path)
        check("init_db() dos veces no lanza", path.exists())


def test_get_modo_por_defecto_manual() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            modo = store.get_modo(conn, "rotar_log")
        check("tipo de acción nunca visto ⇒ modo manual por defecto (FR-002)", modo == "manual")


def test_set_modo_cambia_y_persiste() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            store.set_modo(conn, "rotar_log", "automatico")
        with store.connect(path) as conn:
            modo = store.get_modo(conn, "rotar_log")
        check("set_modo() persiste entre conexiones", modo == "automatico")

        with store.connect(path) as conn:
            store.set_modo(conn, "rotar_log", "manual")
            modo = store.get_modo(conn, "rotar_log")
        check("set_modo() vuelve a manual sin problema", modo == "manual")


def test_listar_modos_tipo_nunca_visto_no_escribe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            modos = store.listar_modos(conn, ("rotar_log",))
        check("tipo nunca visto ⇒ manual en el listado", modos == [("rotar_log", "manual")])

        with store.connect(path) as conn:
            filas = conn.execute("SELECT COUNT(*) AS n FROM configuracion_accion").fetchone()
        check("listar_modos() no crea fila (a diferencia de get_modo)", filas["n"] == 0)


def test_listar_modos_respeta_modo_ya_fijado() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            store.set_modo(conn, "rotar_log", "automatico")
            modos = store.listar_modos(conn, ("rotar_log",))
        check("listar_modos() refleja un modo ya cambiado", modos == [("rotar_log", "automatico")])


def test_listar_modos_conserva_el_orden_de_tipos_conocidos() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            store.set_modo(conn, "b_tipo", "automatico")
            modos = store.listar_modos(conn, ("a_tipo", "b_tipo"))
        check(
            "listar_modos() sigue el orden de tipos_conocidos, no el alfabético de la tabla",
            modos == [("a_tipo", "manual"), ("b_tipo", "automatico")],
        )


def test_insert_y_get_intento() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            intento = IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                modo_en_deteccion="manual", estado="pendiente", detalle="11000000 bytes",
            )
            intento_id = store.insert_intento(conn, intento)
            recuperado = store.get_intento(conn, intento_id)

        check("insert_intento devuelve un id", intento_id is not None)
        check("get_intento recupera el mismo componente", recuperado.componente == "health-docker")
        check("estado inicial = pendiente", recuperado.estado == "pendiente")


def test_get_intento_inexistente_devuelve_none() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            check("id inexistente ⇒ None, sin lanzar", store.get_intento(conn, 999) is None)


def test_update_intento_estado() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            intento = IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-ha", ruta="/tmp/y.log",
                modo_en_deteccion="manual", estado="pendiente", detalle="detalle inicial",
            )
            intento_id = store.insert_intento(conn, intento)
            store.update_intento_estado(conn, intento_id, "ejecutado", "rotado a y.log.rotado-x", "y.log.rotado-x")
            actualizado = store.get_intento(conn, intento_id)

        check("estado actualizado", actualizado.estado == "ejecutado")
        check("fichero_rotado registrado", actualizado.fichero_rotado == "y.log.rotado-x")
        check("resuelto_en poblado", actualizado.resuelto_en is not None)


def test_pendiente_existente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            check("sin ningún intento, no hay pendiente",
                  store.pendiente_existente(conn, "rotar_log", "health-docker") is False)

            intento = IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                modo_en_deteccion="manual", estado="pendiente", detalle="x",
            )
            store.insert_intento(conn, intento)
            check("con un pendiente real, pendiente_existente=True (FR-008)",
                  store.pendiente_existente(conn, "rotar_log", "health-docker") is True)
            check("otro componente distinto, no hay pendiente",
                  store.pendiente_existente(conn, "rotar_log", "health-ha") is False)


def test_listar_pendientes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            for comp in ("health-docker", "health-ha"):
                store.insert_intento(conn, IntentoRemediacion(
                    tipo_accion="rotar_log", componente=comp, ruta=f"/tmp/{comp}.log",
                    modo_en_deteccion="manual", estado="pendiente", detalle="x",
                ))
            rechazado_id = store.insert_intento(conn, IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-ha", ruta="/tmp/otro.log",
                modo_en_deteccion="manual", estado="rechazado", detalle="x",
            ))
            pendientes = store.listar_pendientes(conn)

        check("solo los 2 pendientes reales, no el rechazado", len(pendientes) == 2)
        check("el rechazado no aparece",
              rechazado_id not in [p.id for p in pendientes])


def test_historial() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            for estado in ("ejecutado", "ejecutado", "rechazado", "fallido"):
                store.insert_intento(conn, IntentoRemediacion(
                    tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                    modo_en_deteccion="manual", estado=estado, detalle="x",
                ))
            conteo = store.historial(conn, "rotar_log")

        check("2 ejecutados", conteo.get("ejecutado") == 2)
        check("1 rechazado", conteo.get("rechazado") == 1)
        check("1 fallido", conteo.get("fallido") == 1)

        with store.connect(_db(tmp)) as conn:
            vacio = store.historial(conn, "otro_tipo_nunca_visto")
        check("tipo de acción sin ningún intento ⇒ historial vacío", vacio == {})
