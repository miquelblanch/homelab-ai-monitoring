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


# ── LOGS_VIGILADOS (lista cerrada real, ampliada 2026-08-13, research.md §7) ──


def test_logs_vigilados_lista_real() -> None:
    check("17 logs vigilados tras la ampliación", len(acciones.LOGS_VIGILADOS) == 17)

    nombres = [n for n, _, _ in acciones.LOGS_VIGILADOS]
    check("sin nombres duplicados", len(nombres) == len(set(nombres)))

    ficheros = [f for _, f, _ in acciones.LOGS_VIGILADOS]
    check("sin ficheros duplicados", len(ficheros) == len(set(ficheros)))
    check("los dos originales siguen presentes",
          "health-docker.log" in ficheros and "health-ha.log" in ficheros)
    check("un candidato real de la ampliación está presente",
          "dashboard-socat.log" in ficheros)

    CRITICOS = {
        "homeassistant", "vaultwarden", "nextcloud", "nextcloud-db",
        "nextcloud_redis", "immich_server", "immich_postgres",
        "pangolin-server", "gerbil", "traefik",
    }
    check(
        "ningún nombre de log coincide con un componente crítico (FR-012)",
        all(n not in CRITICOS for n in nombres),
    )
    check("todos los umbrales son positivos", all(u > 0 for _, _, u in acciones.LOGS_VIGILADOS))


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


def test_comprobar_rotar_log_modo_automatico_fallido_notifica() -> None:
    """FR-014 enmendado (research.md §11): un fallo real en modo
    automático sí notifica — pedido explícito de Miquel. La función de
    envío real (con la llamada de red) nunca se invoca aquí: se
    sustituye por un contador, mismo principio que el resto de tests
    de este módulo — nunca tocar Telegram de verdad desde --selftest."""
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)
        llamadas: list[tuple[str, str]] = []

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(acciones, "ejecutar_rotar_log", side_effect=OSError("disco lleno (simulado)")), \
             patch.object(acciones, "_notificar_fallo_automatico", side_effect=lambda c, d: llamadas.append((c, d))):
            with store.connect(_db(db_dir)) as conn:
                store.set_modo(conn, "rotar_log", "automatico")
                creados = acciones.comprobar_rotar_log(conn)

        check("modo automático + fallo real de rotación ⇒ estado fallido", creados[0].estado == "fallido")
        check("el fallo automático dispara exactamente un aviso", len(llamadas) == 1)
        check("el aviso lleva el componente que falló", llamadas[0][0] == "health-docker")


def test_comprobar_rotar_log_modo_automatico_exito_no_notifica() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)
        llamadas: list[tuple[str, str]] = []

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(acciones, "_notificar_fallo_automatico", side_effect=lambda c, d: llamadas.append((c, d))):
            with store.connect(_db(db_dir)) as conn:
                store.set_modo(conn, "rotar_log", "automatico")
                acciones.comprobar_rotar_log(conn)

        check("una rotación automática que sale bien no avisa por Telegram", llamadas == [])


def test_resolver_aprobacion_fallido_no_notifica() -> None:
    """Un fallo en modo manual no notifica — ya hay un humano mirando
    el resultado del propio comando `aprobar` (research.md §11)."""
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)
        llamadas: list[tuple[str, str]] = []

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]), \
             patch.object(acciones, "_notificar_fallo_automatico", side_effect=lambda c, d: llamadas.append((c, d))):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                ruta.unlink()
                resuelto = acciones.resolver_aprobacion(conn, creados[0].id)

        check("aprobación manual con fallo real también llega a fallido", resuelto.estado == "fallido")
        check("un fallo en modo manual nunca dispara el aviso automático", llamadas == [])


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


# ── escribir_snapshot (feature 020: specs/020-visor-remediacion/) ──


def test_escribir_snapshot_forma_correcta() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir, \
         tempfile.TemporaryDirectory() as snap_dir:
        _escribir(Path(logs_dir) / "health-docker.log", 11 * 1024 * 1024)
        # health-ha.log deliberadamente ausente — comprueba tamano_bytes=0
        _escribir(Path(logs_dir) / "health-docker.log.rotado-20260101T000000", 5 * 1024 * 1024)

        lista = [
            ("health-docker", "health-docker.log", 10 * 1024 * 1024),
            ("health-ha", "health-ha.log", 10 * 1024 * 1024),
        ]
        snap_path = Path(snap_dir) / "remediacion_estado.json"

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", lista), \
             patch.object(acciones, "_snapshot_path", return_value=snap_path):
            with store.connect(_db(db_dir)) as conn:
                acciones.escribir_snapshot(conn)

        import json
        payload = json.loads(snap_path.read_text())

        check("generado_en presente", "generado_en" in payload)
        check("modo_rotar_log presente, manual por defecto", payload["modo_rotar_log"] == "manual")
        check("2 entradas en logs, una por cada LOGS_VIGILADOS", len(payload["logs"]) == 2)

        por_nombre = {l["nombre"]: l for l in payload["logs"]}
        check("health-docker refleja el tamaño real y supera_umbral=True",
              por_nombre["health-docker"]["tamano_bytes"] == 11 * 1024 * 1024
              and por_nombre["health-docker"]["supera_umbral"] is True)
        check("health-ha ausente ⇒ tamano_bytes=0, supera_umbral=False",
              por_nombre["health-ha"]["tamano_bytes"] == 0
              and por_nombre["health-ha"]["supera_umbral"] is False)

        check(
            "total_activos_bytes suma solo los ficheros activos (11 MB + 0)",
            payload["total_activos_bytes"] == 11 * 1024 * 1024,
        )
        check(
            "total_con_rotaciones_bytes suma también la rotación archivada (11 + 5 MB)",
            payload["total_con_rotaciones_bytes"] == 16 * 1024 * 1024,
        )


def test_escribir_snapshot_crea_el_directorio_si_hace_falta() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta_en_subdir_inexistente = Path(logs_dir) / "no-existe" / "sub" / "remediacion_estado.json"
        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "_snapshot_path", return_value=ruta_en_subdir_inexistente):
            with store.connect(_db(db_dir)) as conn:
                acciones.escribir_snapshot(conn)
        check("crea los directorios intermedios y escribe el fichero", ruta_en_subdir_inexistente.exists())


def test_escribir_snapshot_nunca_lanza_si_no_puede_escribir() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        # "bloqueo" es un FICHERO, no un directorio — mkdir(parents=True)
        # sobre una ruta que lo atraviesa debe fallar con OSError real,
        # no con un directorio que simplemente no existía todavía.
        bloqueo = Path(logs_dir) / "bloqueo"
        bloqueo.write_text("no soy un directorio")
        ruta_imposible = bloqueo / "remediacion_estado.json"

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "_snapshot_path", return_value=ruta_imposible):
            with store.connect(_db(db_dir)) as conn:
                lanzo = False
                try:
                    acciones.escribir_snapshot(conn)
                except Exception:
                    lanzo = True
        check("un fallo real de escritura no propaga la excepción (contrato garantía 1)", lanzo is False)


# ── Retención de rotaciones (ROTACIONES_A_CONSERVAR, confirmado con Miquel 2026-08-13) ──


def test_purgar_rotaciones_antiguas_conserva_solo_las_4_mas_recientes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        ruta.write_bytes(b"actual")
        # 6 rotaciones falsas, con marcas de tiempo crecientes y conocidas —
        # más simple y determinista que rotar 6 veces de verdad.
        marcas = [f"2026010{i}T000000" for i in range(1, 7)]  # 20260101..20260106
        for marca in marcas:
            (Path(tmp) / f"prueba.log.rotado-{marca}").write_bytes(b"x")

        acciones._purgar_rotaciones_antiguas(ruta)

        restantes = sorted(p.name for p in Path(tmp).glob("prueba.log.rotado-*"))
        check("quedan exactamente 4 rotaciones", len(restantes) == 4)
        check(
            "sobreviven las 4 más recientes (03 a 06), se borran las 2 más antiguas (01, 02)",
            restantes == [f"prueba.log.rotado-2026010{i}T000000" for i in (3, 4, 5, 6)],
        )


def test_purgar_rotaciones_antiguas_con_pocas_no_borra_nada() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        ruta.write_bytes(b"actual")
        (Path(tmp) / "prueba.log.rotado-20260101T000000").write_bytes(b"x")
        (Path(tmp) / "prueba.log.rotado-20260102T000000").write_bytes(b"x")

        acciones._purgar_rotaciones_antiguas(ruta)

        restantes = list(Path(tmp).glob("prueba.log.rotado-*"))
        check("con menos de 4 rotaciones, no se borra ninguna", len(restantes) == 2)


def test_ejecutar_rotar_log_purga_automaticamente() -> None:
    """ejecutar_rotar_log() ya deja como mucho 4 rotaciones tras cada
    llamada, sin necesidad de invocar la purga aparte."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prueba.log"
        marcas = [f"2026010{i}T000000" for i in range(1, 5)]  # 4 rotaciones previas ya al límite
        for marca in marcas:
            (Path(tmp) / f"prueba.log.rotado-{marca}").write_bytes(b"x")
        _escribir(ruta, 1000)

        acciones.ejecutar_rotar_log(ruta)

        restantes = list(Path(tmp).glob("prueba.log.rotado-*"))
        check(
            "tras una rotación nueva con 4 ya existentes, sigue habiendo como mucho 4",
            len(restantes) == acciones.ROTACIONES_A_CONSERVAR,
        )


def test_resolver_deshacer_fichero_rotado_purgado() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir:
        ruta = Path(logs_dir) / "health-docker.log"
        _escribir(ruta, 11 * 1024 * 1024)

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", [("health-docker", "health-docker.log", 10 * 1024 * 1024)]):
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_rotar_log(conn)
                resuelto = acciones.resolver_aprobacion(conn, creados[0].id)
                # simula que la retención ya purgó este fichero rotado
                Path(resuelto.fichero_rotado).unlink()

                lanzo = False
                try:
                    acciones.resolver_deshacer(conn, creados[0].id)
                except ValueError:
                    lanzo = True

        check(
            "deshacer un intento cuyo fichero rotado ya se purgó falla con un mensaje claro, no un OSError crudo",
            lanzo is True,
        )
