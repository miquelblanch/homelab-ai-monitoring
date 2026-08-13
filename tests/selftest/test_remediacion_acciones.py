"""test_remediacion_acciones — comprobar/ejecutar/deshacer rotar_log
contra logs de prueba en un directorio temporal, nunca los reales de
~/Library/Logs/ (research.md §4/§5 de specs/019-remediacion-automatica/)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from remediacion import acciones, store
from tests.selftest import check


def _db(tmp: str) -> Path:
    return Path(tmp) / "remediacion.db"


def _escribir(ruta: Path, tamano_bytes: int) -> None:
    ruta.write_bytes(b"x" * tamano_bytes)


# ── ejecutar_rotar_log / deshacer_rotar_log (lógica de ficheros pura) ──


def test_ejecutar_rotar_log_conserva_contenido() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        _escribir(ruta, 1000)
        contenido_original = ruta.read_bytes()

        rotado = Path(acciones.ejecutar_rotar_log(ruta))

        check("el fichero rotado conserva el contenido íntegro", rotado.read_bytes() == contenido_original)
        check("el fichero original queda vacío, no borrado", ruta.exists() and ruta.stat().st_size == 0)
        check("nunca se trunca el fichero rotado", rotado.stat().st_size == 1000)


def test_deshacer_rotar_log_caso_simple() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        _escribir(ruta, 1000)
        contenido_original = ruta.read_bytes()
        rotado = Path(acciones.ejecutar_rotar_log(ruta))

        conservado = acciones.deshacer_rotar_log(ruta, rotado)

        check("sin nada escrito después, no hace falta conservar nada", conservado is None)
        check("el fichero original recupera su contenido íntegro", ruta.read_bytes() == contenido_original)
        check("el fichero rotado ya no existe con su nombre de rotado", not rotado.exists())


def test_deshacer_rotar_log_no_pierde_lo_escrito_despues() -> None:
    """El caso que exige el paso extra (research.md §4, SC-004): algo
    se escribió en el fichero original tras la rotación — deshacer no
    debe destruirlo nunca."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        _escribir(ruta, 1000)
        contenido_original = ruta.read_bytes()
        rotado = Path(acciones.ejecutar_rotar_log(ruta))

        contenido_nuevo = b"linea escrita despues de la rotacion"
        ruta.write_bytes(contenido_nuevo)

        conservado = acciones.deshacer_rotar_log(ruta, rotado)

        check("se conserva lo escrito después, en un fichero aparte", conservado is not None)
        check(
            "el contenido posterior sobrevive íntegro",
            Path(conservado).read_bytes() == contenido_nuevo,
        )
        check(
            "el original vuelve a tener el contenido de antes de rotar",
            ruta.read_bytes() == contenido_original,
        )


# ── comprobar_rotar_log (modo manual y automático) ──


def test_comprobar_rotar_log_modo_manual_crea_pendiente() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)  # 11 MB > 10 MB

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)

        check("un log por encima del umbral crea un intento", len(creados) == 1)
        check("modo por defecto manual ⇒ queda pendiente", creados[0].estado == "pendiente")
        check(
            "el fichero no se toca solo con comprobar",
            (Path(logs_dir) / "health-docker.log").stat().st_size == 11 * 1024 * 1024,
        )


def test_comprobar_rotar_log_por_debajo_del_umbral_no_crea_nada() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 1024)  # 1 KB, muy por debajo

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)

        check("por debajo del umbral, ningún intento nuevo", creados == [])


def test_comprobar_rotar_log_fichero_ausente_se_ignora() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        # ningún fichero health-docker.log creado en logs_dir
        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)

        check("fichero ausente de la lista vigilada se ignora, sin lanzar", creados == [])


def test_comprobar_rotar_log_no_duplica_pendiente() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                primera = acciones.comprobar_rotar_log(conn)
                segunda = acciones.comprobar_rotar_log(conn)

        check("la primera comprobación crea 1 intento", len(primera) == 1)
        check("la segunda no duplica mientras siga pendiente (FR-008)", segunda == [])


def test_comprobar_rotar_log_modo_automatico_ejecuta_directo() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                store.set_modo(conn, "rotar_log", "automatico")
                creados = acciones.comprobar_rotar_log(conn)
                pendientes = store.listar_pendientes(conn)

        check("modo automático ejecuta en la misma llamada", len(creados) == 1)
        check("el intento nace ya ejecutado, nunca pasa por pendiente (FR-007)",
              creados[0].estado == "ejecutado")
        check("sin ningún pendiente tras la ejecución automática", pendientes == [])
        check(
            "el fichero se rotó de verdad",
            (Path(logs_dir) / "health-docker.log").stat().st_size == 0,
        )


# ── resolver_aprobacion / resolver_rechazo / resolver_deshacer ──


def test_resolver_aprobacion_ejecuta_y_conserva_contenido() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                resuelto = acciones.resolver_aprobacion(conn, creados[0].id)

        check("aprobar pasa a ejecutado directamente (sin estado 'aprobado')", resuelto.estado == "ejecutado")
        check("el fichero rotado quedó registrado", resuelto.fichero_rotado is not None)
        check("el original quedó vacío", ruta.stat().st_size == 0)


def test_resolver_rechazo_no_toca_el_fichero() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                resuelto = acciones.resolver_rechazo(conn, creados[0].id)

        check("rechazar pasa a rechazado", resuelto.estado == "rechazado")
        check("el fichero sigue intacto", ruta.stat().st_size == 11 * 1024 * 1024)


def test_resolver_sobre_estado_equivocado_se_rechaza() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                intento_id = creados[0].id
                acciones.resolver_rechazo(conn, intento_id)

                lanzo_en_aprobar = False
                try:
                    acciones.resolver_aprobacion(conn, intento_id)
                except ValueError:
                    lanzo_en_aprobar = True

                lanzo_en_rechazar_de_nuevo = False
                try:
                    acciones.resolver_rechazo(conn, intento_id)
                except ValueError:
                    lanzo_en_rechazar_de_nuevo = True

                lanzo_en_deshacer = False
                try:
                    acciones.resolver_deshacer(conn, intento_id)
                except ValueError:
                    lanzo_en_deshacer = True

        check("aprobar un ya rechazado se rechaza", lanzo_en_aprobar)
        check("rechazar dos veces se rechaza", lanzo_en_rechazar_de_nuevo)
        check("deshacer algo que nunca se ejecutó se rechaza", lanzo_en_deshacer)


def test_resolver_deshacer_completo() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)
        contenido_original = ruta.read_bytes()

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                intento_id = creados[0].id
                acciones.resolver_aprobacion(conn, intento_id)
                deshecho = acciones.resolver_deshacer(conn, intento_id)

        check("deshacer pasa a deshecho", deshecho.estado == "deshecho")
        check("el contenido original vuelve íntegro", ruta.read_bytes() == contenido_original)


def test_resolver_aprobacion_fichero_ya_no_existe() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                ruta.unlink()  # el fichero desaparece entre medias (Edge Cases de spec.md)
                resuelto = acciones.resolver_aprobacion(conn, creados[0].id)

        check("fichero desaparecido entre medias ⇒ fallido, sin lanzar", resuelto.estado == "fallido")
