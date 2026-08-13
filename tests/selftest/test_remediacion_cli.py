"""test_remediacion_cli — el CLI (`remediacion.cli.main`) contra logs
de prueba y una base temporal, nunca los reales."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from remediacion import acciones, cli, store
from tests.selftest import check


def _db(tmp: str) -> Path:
    return Path(tmp) / "remediacion.db"


def _escribir(ruta: Path, tamano_bytes: int) -> None:
    ruta.write_bytes(b"x" * tamano_bytes)


def test_cli_comprobar_y_pendientes() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(store, "db_path", return_value=_db(db_dir)):
            codigo_comprobar = cli.main(["comprobar"])
            codigo_pendientes = cli.main(["pendientes"])

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


def test_cli_aprobar_rechazar_deshacer() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
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
