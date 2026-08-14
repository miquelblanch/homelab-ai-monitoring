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


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────


def test_get_modo_contenedor_por_defecto_manual() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            modo = store.get_modo_contenedor(conn, "jellyfin_audio")
        check("contenedor nunca visto ⇒ modo manual por defecto (research.md §7 de 021)", modo == "manual")


def test_set_modo_contenedor_cambia_sin_afectar_a_otros() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            store.set_modo_contenedor(conn, "jellyfin_audio", "automatico")
        with store.connect(path) as conn:
            modo_a = store.get_modo_contenedor(conn, "jellyfin_audio")
            modo_b = store.get_modo_contenedor(conn, "syncthing")
        check("el contenedor cambiado queda en automático", modo_a == "automatico")
        check("un contenedor distinto no se ve afectado (Acceptance Scenario 2 de US5)", modo_b == "manual")


def test_listar_modos_contenedor_no_crea_filas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _db(tmp)
        with store.connect(path) as conn:
            store.set_modo_contenedor(conn, "jellyfin_audio", "automatico")
            modos = store.listar_modos_contenedor(conn, ("jellyfin_audio", "syncthing"))
            filas = conn.execute("SELECT COUNT(*) AS n FROM configuracion_contenedor").fetchone()["n"]
        check("refleja el modo real de cada uno", modos == [("jellyfin_audio", "automatico"), ("syncthing", "manual")])
        check("no crea fila para el que nunca se tocó", filas == 1)


def test_sin_evaluar_consecutivos() -> None:
    from remediacion.model import IntentoReinicio

    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            check("sin ningún intento, la racha es 0", store.sin_evaluar_consecutivos(conn, "test") == 0)

            for _ in range(2):
                store.insert_intento_reinicio(conn, IntentoReinicio(
                    contenedor="test", modo_en_deteccion="automatico",
                    estado="sin_evaluar", detalle="sin presupuesto",
                ))
            check("2 sin_evaluar seguidos ⇒ racha 2", store.sin_evaluar_consecutivos(conn, "test") == 2)

            store.insert_intento_reinicio(conn, IntentoReinicio(
                contenedor="test", modo_en_deteccion="automatico",
                estado="ejecutado", detalle="reiniciado",
            ))
            check("un intento resuelto rompe la racha", store.sin_evaluar_consecutivos(conn, "test") == 0)


def test_localizar_intento_distingue_las_dos_tablas() -> None:
    """Las dos tablas tienen AUTOINCREMENT independientes — un id de
    intentos_reinicio "puro" (sin ningún intento_remediacion con el
    mismo id) debe resolver a la tabla correcta; localizar_intento
    prioriza intentos_remediacion primero (contracts/cli.md de 021)."""
    from remediacion.model import IntentoReinicio, IntentoRemediacion

    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            id_remediacion = store.insert_intento(conn, IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                modo_en_deteccion="manual", estado="pendiente", detalle="x",
            ))
            ubicacion_remediacion = store.localizar_intento(conn, id_remediacion)
            ubicacion_inexistente = store.localizar_intento(conn, 999999)

        check("un id de rotar_log se localiza en 'remediacion'", ubicacion_remediacion[0] == "remediacion")
        check("un id inexistente en ninguna tabla ⇒ None", ubicacion_inexistente is None)

    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            # Sin ningún intento_remediacion en esta base — el id de
            # intentos_reinicio no puede colisionar con la otra tabla.
            id_reinicio = store.insert_intento_reinicio(conn, IntentoReinicio(
                contenedor="test", modo_en_deteccion="manual", estado="pendiente", detalle="x",
            ))
            ubicacion_reinicio = store.localizar_intento(conn, id_reinicio)
        check("un id de reinicio se localiza en 'reinicio'", ubicacion_reinicio[0] == "reinicio")


def test_ids_de_intentos_nunca_colisionan_entre_las_dos_tablas() -> None:
    """Bug real encontrado validando 021 en producción (2026-08-14):
    con intentos_remediacion ya poblada por 019/020, un intentos_reinicio
    nuevo con su propio AUTOINCREMENT (empezando en 1) colisionaba con
    un id ya existente de la otra tabla — localizar_intento() resolvía
    sobre la tabla equivocada. Los dos espacios de id deben ser
    disjuntos siempre, no solo cuando una de las dos tablas está vacía."""
    from remediacion.model import IntentoReinicio, IntentoRemediacion

    with tempfile.TemporaryDirectory() as tmp:
        with store.connect(_db(tmp)) as conn:
            # intentos_remediacion ya tiene 2 filas reales, como en producción —
            # sin la corrección, el próximo intentos_reinicio nacería con id=1.
            for _ in range(2):
                store.insert_intento(conn, IntentoRemediacion(
                    tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                    modo_en_deteccion="manual", estado="ejecutado", detalle="x",
                ))
            id_reinicio = store.insert_intento_reinicio(conn, IntentoReinicio(
                contenedor="test", modo_en_deteccion="manual", estado="pendiente", detalle="x",
            ))
            ubicacion = store.localizar_intento(conn, id_reinicio)

        check("el nuevo intento de reinicio no colisiona con los 2 ya existentes", id_reinicio > 2)
        check("localizar_intento lo encuentra en la tabla correcta", ubicacion[0] == "reinicio")

        with store.connect(Path(tmp) / "otra.db") as conn:
            # A la inversa: intentos_reinicio ya poblada, un rotar_log nuevo
            # tampoco debe colisionar.
            for _ in range(3):
                store.insert_intento_reinicio(conn, IntentoReinicio(
                    contenedor="test", modo_en_deteccion="manual", estado="ejecutado", detalle="x",
                ))
            id_remediacion = store.insert_intento(conn, IntentoRemediacion(
                tipo_accion="rotar_log", componente="health-docker", ruta="/tmp/x.log",
                modo_en_deteccion="manual", estado="pendiente", detalle="x",
            ))
        check("un rotar_log nuevo tampoco colisiona con reinicios ya existentes", id_remediacion > 3)
