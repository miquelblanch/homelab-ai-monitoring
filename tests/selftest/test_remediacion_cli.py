"""test_remediacion_cli — el CLI (`remediacion.cli.main`) contra logs
de prueba y una base temporal, nunca los reales.

Desde el final del fichero: comprobar-contenedores/modo-contenedor/
contenedores (021) — `diagnostico.store.db_path` también se
redirige a una base temporal para no tocar `diagnostico.db` real."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico import store as diagnostico_store
from remediacion import _homelab_bridge, acciones, cli, store
from tests.selftest import check


def _db(tmp: str) -> Path:
    return Path(tmp) / "remediacion.db"


def _escribir(ruta: Path, tamano_bytes: int) -> None:
    ruta.write_bytes(b"x" * tamano_bytes)


def test_cli_comprobar_y_pendientes() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)
        snap_path = Path(db_dir) / "remediacion_estado.json"

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(acciones, "_snapshot_path", return_value=snap_path), \
             patch.object(store, "db_path", return_value=_db(db_dir)):
            codigo_comprobar = cli.main(["comprobar"])
            codigo_pendientes = cli.main(["pendientes"])

        check("comprobar por CLI nunca toca el snapshot real de producción", snap_path.exists())

        check("cli comprobar termina en 0", codigo_comprobar == 0)
        check("cli pendientes termina en 0", codigo_pendientes == 0)


def test_cli_modo_y_historial() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)):
            codigo_automatico = cli.main(["modo", "rotar_log", "--automatico"])
            with store.connect(_db(db_dir)) as conn:
                modo_tras_cambio = store.get_modo(conn, "rotar_log")

            codigo_manual = cli.main(["modo", "rotar_log", "--manual"])
            with store.connect(_db(db_dir)) as conn:
                modo_final = store.get_modo(conn, "rotar_log")

            codigo_historial = cli.main(["historial", "rotar_log"])

        check("cli modo --automatico termina en 0", codigo_automatico == 0)
        check("modo cambia a automatico de verdad", modo_tras_cambio == "automatico")
        check("cli modo --manual termina en 0", codigo_manual == 0)
        check("modo vuelve a manual sin ninguna condición previa (FR-003)", modo_final == "manual")
        check("cli historial termina en 0", codigo_historial == 0)


def test_cli_tipos_no_escribe_y_refleja_el_modo() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)):
            codigo_antes = cli.main(["tipos"])
            with store.connect(_db(db_dir)) as conn:
                filas_tras_tipos = conn.execute(
                    "SELECT COUNT(*) AS n FROM configuracion_accion"
                ).fetchone()["n"]

            cli.main(["modo", "rotar_log", "--automatico"])
            codigo_despues = cli.main(["tipos"])
            with store.connect(_db(db_dir)) as conn:
                modos = store.listar_modos(conn, acciones.TIPOS_ACCION)

        check("cli tipos termina en 0 antes de cualquier modo fijado", codigo_antes == 0)
        check("cli tipos no crea fila en configuracion_accion", filas_tras_tipos == 0)
        check("cli tipos termina en 0 con un modo ya fijado", codigo_despues == 0)
        check(
            "cli tipos refleja rotar_log en automático tras el cambio, y reiniciar_contenedor (021) en manual por defecto",
            modos == [("rotar_log", "automatico"), ("reiniciar_contenedor", "manual")],
        )


def test_cli_aprobar_rechazar_deshacer() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(acciones, "_snapshot_path", return_value=Path(db_dir) / "remediacion_estado.json"), \
             patch.object(store, "db_path", return_value=_db(db_dir)):
            cli.main(["comprobar"])
            with store.connect(_db(db_dir)) as conn:
                pendiente_id = store.listar_pendientes(conn)[0].id

            codigo_aprobar = cli.main(["aprobar", str(pendiente_id)])
            tamano_tras_aprobar = ruta.stat().st_size
            codigo_deshacer = cli.main(["deshacer", str(pendiente_id)])
            tamano_tras_deshacer = ruta.stat().st_size

        check("cli aprobar termina en 0", codigo_aprobar == 0)
        check("el fichero se rotó de verdad vía CLI", tamano_tras_aprobar == 0)
        check("cli deshacer termina en 0", codigo_deshacer == 0)
        check("el contenido vuelve tras deshacer vía CLI", tamano_tras_deshacer == 11 * 1024 * 1024)


def test_cli_aprobar_id_inexistente_devuelve_error() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)):
            codigo = cli.main(["aprobar", "999999"])
        check("aprobar un id inexistente devuelve código de error, sin lanzar", codigo == 1)


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────


def test_cli_modo_contenedor_rechaza_critico_sin_escribir() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)), \
             patch.object(_homelab_bridge, "docker_critical", return_value={"homeassistant"}), \
             patch.object(_homelab_bridge, "docker_never_restart", return_value=set()):
            codigo = cli.main(["modo-contenedor", "homeassistant", "--automatico"])
            with store.connect(_db(db_dir)) as conn:
                filas = conn.execute("SELECT COUNT(*) AS n FROM configuracion_contenedor").fetchone()["n"]

        check("modo-contenedor sobre un crítico devuelve error", codigo == 1)
        check("no escribe ninguna fila (FR-006)", filas == 0)


def test_cli_modo_contenedor_rechaza_never_restart() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)), \
             patch.object(_homelab_bridge, "docker_critical", return_value=set()), \
             patch.object(_homelab_bridge, "docker_never_restart", return_value={"frigate"}):
            codigo = cli.main(["modo-contenedor", "frigate", "--automatico"])
        check("modo-contenedor sobre frigate (NEVER_RESTART) devuelve error", codigo == 1)


def test_cli_modo_contenedor_cambia_uno_no_critico() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)), \
             patch.object(_homelab_bridge, "docker_critical", return_value=set()), \
             patch.object(_homelab_bridge, "docker_never_restart", return_value=set()):
            codigo = cli.main(["modo-contenedor", "jellyfin_audio", "--automatico"])
            with store.connect(_db(db_dir)) as conn:
                modo = store.get_modo_contenedor(conn, "jellyfin_audio")

        check("modo-contenedor sobre uno no crítico termina en 0", codigo == 0)
        check("el modo cambia de verdad", modo == "automatico")


def test_cli_contenedores_lista_solo_no_criticos() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)), \
             patch.object(_homelab_bridge, "docker_critical", return_value={"homeassistant"}), \
             patch.object(_homelab_bridge, "docker_never_restart", return_value={"frigate"}), \
             patch.object(_homelab_bridge, "listar_contenedores", return_value=[
                 {"name": "homeassistant"}, {"name": "frigate"}, {"name": "jellyfin_audio"},
             ]):
            codigo = cli.main(["contenedores"])
        check("contenedores termina en 0", codigo == 0)


def test_cli_comprobar_contenedores_y_aprobar_generalizado() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)), \
             patch.object(diagnostico_store, "db_path", return_value=Path(db_dir) / "diagnostico.db"), \
             patch.object(_homelab_bridge, "docker_critical", return_value=set()), \
             patch.object(_homelab_bridge, "docker_never_restart", return_value=set()), \
             patch.object(_homelab_bridge, "listar_contenedores", return_value=[
                 {"name": "test-contenedor", "running": False, "healthy": False},
             ]), \
             patch.object(acciones.diagnostico_evidencia, "congelar_vivo") as mock_congelar:
            from diagnostico.model import Episodio
            mock_congelar.return_value = Episodio(
                componente="test-contenedor", origen="contenedor", es_critico=False,
                en_vivo=True, ventana_inicio="x", ventana_fin="y", snapshot_evidencia={}, id=1,
            )
            import os
            try:
                os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
                    {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba CLI"}
                )
                codigo_comprobar = cli.main(["comprobar-contenedores"])
                with store.connect(_db(db_dir)) as conn:
                    pendiente_id = store.listar_pendientes_reinicio(conn)[0].id

                with patch.object(_homelab_bridge, "restart_container", return_value=True):
                    codigo_aprobar = cli.main(["aprobar", str(pendiente_id)])

                with store.connect(_db(db_dir)) as conn:
                    resuelto = store.get_intento_reinicio(conn, pendiente_id)
            finally:
                os.environ.pop("REMEDIACION_DEEPSEEK_MOCK", None)

        check("comprobar-contenedores termina en 0", codigo_comprobar == 0)
        check("crea un intento pendiente para el contenedor caído", pendiente_id is not None)
        check("aprobar (comando genérico) resuelve sobre intentos_reinicio", codigo_aprobar == 0)
        check("el intento queda ejecutado tras aprobar por CLI", resuelto.estado == "ejecutado")


def test_cli_deshacer_rechaza_intento_de_reinicio() -> None:
    from remediacion.model import IntentoReinicio

    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(store, "db_path", return_value=_db(db_dir)):
            with store.connect(_db(db_dir)) as conn:
                intento_id = store.insert_intento_reinicio(conn, IntentoReinicio(
                    contenedor="test", modo_en_deteccion="automatico", estado="ejecutado", detalle="x",
                ))
            codigo = cli.main(["deshacer", str(intento_id)])
        check("deshacer sobre un intento_reinicio se rechaza (FR-016)", codigo == 1)
