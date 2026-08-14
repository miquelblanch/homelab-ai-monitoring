"""test_remediacion_acciones — comprobar/ejecutar/deshacer rotar_log
contra logs de prueba en un directorio temporal, nunca los reales de
~/Library/Logs/ (research.md §4/§5 de specs/019-remediacion-automatica/).

Desde el final del fichero: reiniciar_contenedor (021) — aprobar/
rechazar, modo automático con cortacircuito, sin_accion y sin_evaluar
persistente. `bridge.restart_container`/`breaker_decision` siempre
mockeados — ningún test toca Docker real."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from diagnostico.model import Episodio
from remediacion import _homelab_bridge as bridge
from remediacion import acciones, store
from remediacion.model import IntentoReinicio
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


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────


def _episodio(componente: str = "test-contenedor") -> Episodio:
    return Episodio(
        componente=componente, origen="contenedor", es_critico=False, en_vivo=True,
        ventana_inicio="2026-08-14T00:00:00", ventana_fin="2026-08-14T00:05:00",
        snapshot_evidencia={}, id=1,
    )


def _crear_pendiente_reinicio(conn, contenedor: str = "test-contenedor") -> IntentoReinicio:
    from remediacion.store import insert_intento_reinicio

    intento = IntentoReinicio(
        contenedor=contenedor, modo_en_deteccion="manual", estado="pendiente",
        detalle="pendiente de aprobación", accion_recomendada="reiniciar_contenedor",
        razonamiento_deepseek="prueba",
    )
    intento.id = insert_intento_reinicio(conn, intento)
    return intento


def test_pendiente_reinicio_no_toca_el_contenedor() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "restart_container") as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                _crear_pendiente_reinicio(conn)
        check("crear un pendiente nunca llama a restart_container", mock_restart.called is False)


def test_resolver_aprobacion_reinicio_ejecuta_y_verifica() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "restart_container", return_value=True) as mock_restart, \
             patch.object(acciones.bridge, "declarar_correccion_ia"):
            with store.connect(_db(db_dir)) as conn:
                pendiente = _crear_pendiente_reinicio(conn)
                resuelto = acciones.resolver_aprobacion_reinicio(conn, pendiente.id)

        check("aprobar pasa a ejecutado cuando restart_container verifica running", resuelto.estado == "ejecutado")
        check("se llamó a restart_container exactamente una vez", mock_restart.call_count == 1)


def test_resolver_aprobacion_reinicio_fallido() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "restart_container", return_value=False):
            with store.connect(_db(db_dir)) as conn:
                pendiente = _crear_pendiente_reinicio(conn)
                resuelto = acciones.resolver_aprobacion_reinicio(conn, pendiente.id)
        check("restart_container devuelve False ⇒ fallido, nunca ejecutado", resuelto.estado == "fallido")


def test_resolver_rechazo_reinicio_no_toca_el_contenedor() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "restart_container") as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                pendiente = _crear_pendiente_reinicio(conn)
                resuelto = acciones.resolver_rechazo_reinicio(conn, pendiente.id)

        check("rechazar pasa a rechazado", resuelto.estado == "rechazado")
        check("rechazar nunca llama a restart_container", mock_restart.called is False)


def test_resolver_reinicio_sobre_estado_equivocado_se_rechaza() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "restart_container", return_value=True):
            with store.connect(_db(db_dir)) as conn:
                pendiente = _crear_pendiente_reinicio(conn)
                acciones.resolver_rechazo_reinicio(conn, pendiente.id)

                lanzo = False
                try:
                    acciones.resolver_aprobacion_reinicio(conn, pendiente.id)
                except ValueError:
                    lanzo = True
        check("aprobar un intento de reinicio ya rechazado se rechaza", lanzo)


def test_evaluar_contenedor_modo_automatico_ejecuta_sin_pendiente() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with store.connect(_db(db_dir)) as conn:
            store.set_modo_contenedor(conn, "test-contenedor", "automatico")

        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}
                 )}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5},
             }), \
             patch.object(acciones.bridge, "recent_restart_attempts", return_value=0), \
             patch.object(acciones.bridge, "declarar_correccion_ia"), \
             patch.object(acciones.bridge, "restart_container", return_value=True) as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                pendientes = store.listar_pendientes_reinicio(conn)

        check("automático ejecuta directo, nunca pasa por pendiente (FR-008)", intento.estado == "ejecutado")
        check("sin ningún pendiente tras la ejecución automática", pendientes == [])
        check("restart_container se llamó exactamente una vez", mock_restart.call_count == 1)


def test_evaluar_contenedor_modo_automatico_sin_accion_nunca_reinicia() -> None:
    """Acceptance Scenario 2 de US3 — el modo automático nunca fuerza
    reiniciar_contenedor cuando DeepSeek dice que no ayudaría."""
    with tempfile.TemporaryDirectory() as db_dir:
        with store.connect(_db(db_dir)) as conn:
            store.set_modo_contenedor(conn, "test-contenedor", "automatico")

        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": None, "razonamiento": "problema externo"}
                 )}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5},
             }), \
             patch.object(acciones.bridge, "restart_container") as mock_restart, \
             patch.object(acciones, "_notificar_sin_accion") as mock_aviso:
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(conn, conn, "test-contenedor")

        check("sin_accion también en modo automático", intento.estado == "sin_accion")
        check("automático nunca reinicia si DeepSeek dice que no aplica", mock_restart.called is False)
        check("nunca reinicia en ningún modo (FR-009)", mock_aviso.called is True)


def test_cortacircuito_abre_al_cuarto_intento() -> None:
    """SC-006 — el cortacircuito se abre exactamente al 3er intento
    fallido dentro de la ventana, sin importar que la recomendación
    venga de DeepSeek en vez de una condición fija."""
    with tempfile.TemporaryDirectory() as db_dir:
        with store.connect(_db(db_dir)) as conn:
            store.set_modo_contenedor(conn, "test-contenedor", "automatico")

        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.0), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}
                 )}}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1},
             }), \
             patch.object(acciones.bridge, "restart_container", return_value=False) as mock_restart, \
             patch.object(acciones, "_notificar_cortacircuito") as mock_aviso:
            with store.connect(_db(db_dir)) as conn:
                estados = [
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor").estado
                    for _ in range(4)
                ]

        check("los 3 primeros intentos fallan de verdad", estados[:3] == ["fallido", "fallido", "fallido"])
        check("el 4º intento no llega a restart_container — cortacircuito", estados[3] == "cortacircuito")
        check("restart_container se llamó exactamente 3 veces, nunca una 4ª", mock_restart.call_count == 3)
        check("el cortacircuito avisa por Telegram", mock_aviso.called is True)


# ── FR-019: aviso por sin_evaluar persistente ──


def test_sin_evaluar_persistente_dispara_aviso_al_umbral() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        avisos: list[tuple[str, int]] = []
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=False), \
             patch.object(acciones, "_notificar_sin_evaluar_persistente",
                           side_effect=lambda c, r: avisos.append((c, r))):
            with store.connect(_db(db_dir)) as conn:
                for _ in range(2):
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                check("2 sin_evaluar seguidos, todavía sin alcanzar el umbral (3) ⇒ sin aviso", avisos == [])

                acciones.evaluar_contenedor(conn, conn, "test-contenedor")
        check("al 3er sin_evaluar consecutivo, se dispara el aviso (FR-019)", len(avisos) == 1 and avisos[0][1] == 3)


def test_sin_evaluar_persistente_se_resetea_con_una_evaluacion_real() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        avisos: list[tuple[str, int]] = []
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones, "_notificar_sin_evaluar_persistente",
                           side_effect=lambda c, r: avisos.append((c, r))):
            with store.connect(_db(db_dir)) as conn:
                with patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=False):
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")

                try:
                    os.environ["REMEDIACION_DEEPSEEK_MOCK"] = json.dumps(
                        {"accion_aplica": None, "razonamiento": "evaluación real, resetea la racha"}
                    )
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                finally:
                    os.environ.pop("REMEDIACION_DEEPSEEK_MOCK", None)

                racha = store.sin_evaluar_consecutivos(conn, "test-contenedor")

        check("una evaluación real (no sin_evaluar) resetea la racha a 0", racha == 0)
        check("nunca se llegó a avisar (la racha se rompió antes del umbral)", avisos == [])


# ── Pestaña Correcciones del dashboard: declaración "ia" (2026-08-14) ──


def test_declarar_correccion_ia_escribe_y_acumula() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "alarm_manual_corrections.json"
        with patch.object(bridge, "_alarm_corrections_path", return_value=ruta):
            ok1 = bridge.declarar_correccion_ia("contenedores", "contenedor_caido", "syncthing", "razón 1")
            ok2 = bridge.declarar_correccion_ia("contenedores", "contenedor_caido", "n8n", "razón 2")

        pendientes = json.loads(ruta.read_text())
        check("declarar_correccion_ia devuelve True al escribir", ok1 and ok2)
        check("se acumulan las dos declaraciones, no se pisan", len(pendientes) == 2)
        check("cada una lleva clasificacion=ia", all(p["clasificacion"] == "ia" for p in pendientes))
        check("conserva el componente y la nota", pendientes[0]["componente"] == "syncthing" and pendientes[0]["nota"] == "razón 1")


def test_declarar_correccion_ia_nunca_lanza_si_no_puede_escribir() -> None:
    ruta_imposible = Path("/root/sin-permiso/alarm_manual_corrections.json")
    with patch.object(bridge, "_alarm_corrections_path", return_value=ruta_imposible):
        lanzo = False
        try:
            resultado = bridge.declarar_correccion_ia("contenedores", "contenedor_caido", "x", "y")
        except Exception:
            lanzo = True
    check("un fallo de escritura no propaga la excepción", lanzo is False)
    check("y devuelve False", resultado is False)


def test_evaluar_contenedor_modo_automatico_declara_ia_solo_si_ejecuta() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with store.connect(_db(db_dir)) as conn:
            store.set_modo_contenedor(conn, "test-contenedor", "automatico")

        declaraciones: list[tuple] = []
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba ia"}
                 )}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5},
             }), \
             patch.object(acciones.bridge, "recent_restart_attempts", return_value=0), \
             patch.object(acciones.bridge, "declarar_correccion_ia",
                           side_effect=lambda *a: declaraciones.append(a) or True):
            with store.connect(_db(db_dir)) as conn:
                with patch.object(acciones.bridge, "restart_container", return_value=True):
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                check("reinicio ejecutado con éxito ⇒ declara ia exactamente una vez", len(declaraciones) == 1)
                check("con el componente y razonamiento correctos",
                      declaraciones[0][2] == "test-contenedor" and declaraciones[0][3] == "prueba ia")

            declaraciones.clear()
            with store.connect(_db(db_dir)) as conn:
                with patch.object(acciones.bridge, "restart_container", return_value=False):
                    acciones.evaluar_contenedor(conn, conn, "test-contenedor")
                check("reinicio fallido ⇒ nunca declara ia (evita atribuir una corrección que no pasó)",
                      declaraciones == [])


# ── Contenedores críticos + snapshot (specs/022-clasificacion-remediacion/) ──


def test_evaluar_contenedor_modo_forzado_ignora_configuracion() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with store.connect(_db(db_dir)) as conn:
            # Ningún modo fijado a propósito — si modo_forzado no se
            # respetara, get_modo_contenedor() devolvería "manual" de
            # todos modos (mismo resultado por casualidad), así que fijamos
            # "automatico" explícitamente para que la prueba sea real:
            # si evaluar_contenedor ignorase modo_forzado y leyera la
            # tabla, entraría en la rama automática y llamaría a
            # restart_container — lo que este test prohíbe con el mock.
            store.set_modo_contenedor(conn, "test-contenedor", "automatico")

        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio()), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba crítico"}
                 )}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5},
             }), \
             patch.object(acciones.bridge, "restart_container") as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                intento = acciones.evaluar_contenedor(
                    conn, conn, "test-contenedor", modo_forzado="manual"
                )

        check("modo_forzado='manual' crea pendiente aunque la tabla diga automático",
              intento.estado == "pendiente")
        check("modo_en_deteccion refleja el modo forzado, no el de la tabla",
              intento.modo_en_deteccion == "manual")
        check("nunca se ejecuta un reinicio cuando el modo está forzado a manual",
              mock_restart.called is False)


def test_comprobar_reiniciar_contenedor_incluye_criticos_como_pendiente() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "docker_critical", return_value={"test-critico"}), \
             patch.object(acciones.bridge, "docker_never_restart", return_value=set()), \
             patch.object(acciones.bridge, "listar_contenedores", return_value=[
                 {"name": "test-critico", "running": False, "healthy": False},
             ]), \
             patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio("test-critico")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.001), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba crítico caído"}
                 )}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5},
             }), \
             patch.object(acciones.bridge, "restart_container") as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_reiniciar_contenedor(conn, conn)

        check("un crítico caído sí se evalúa (FR-009, ya no excluido)", len(creados) == 1)
        check("crea pendiente, nunca ejecutado directamente (FR-008/FR-010)",
              creados[0].estado == "pendiente")
        check("modo_en_deteccion siempre manual para un crítico", creados[0].modo_en_deteccion == "manual")
        check("nunca se llama a restart_container para un crítico desde comprobar_reiniciar_contenedor",
              mock_restart.called is False)


def test_comprobar_reiniciar_contenedor_nunca_evalua_never_restart() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.bridge, "docker_critical", return_value=set()), \
             patch.object(acciones.bridge, "docker_never_restart", return_value={"frigate"}), \
             patch.object(acciones.bridge, "listar_contenedores", return_value=[
                 {"name": "frigate", "running": False, "healthy": False},
             ]), \
             patch.object(acciones.diagnostico_evidencia, "congelar_vivo") as mock_congelar:
            with store.connect(_db(db_dir)) as conn:
                creados = acciones.comprobar_reiniciar_contenedor(conn, conn)

        check("frigate (NEVER_RESTART) sigue excluido por completo (FR-007)", creados == [])
        check("ni siquiera se reúne evidencia para él", mock_congelar.called is False)


def test_evaluar_contenedor_critico_nunca_llega_a_cortacircuito() -> None:
    """Un crítico con modo forzado 'manual' entra siempre en la rama
    `if modo == "manual"` de evaluar_contenedor — nunca en la rama
    automática que consulta recent_restart_attempts/breaker_decision,
    así que repetir la evaluación varias veces nunca produce
    "cortacircuito" para él (a diferencia de un no crítico en
    automático, ver test_cortacircuito_abre_al_cuarto_intento)."""
    with tempfile.TemporaryDirectory() as db_dir:
        with patch.object(acciones.diagnostico_evidencia, "congelar_vivo", return_value=_episodio("test-critico")), \
             patch.object(acciones.diagnostico_gasto, "hay_presupuesto", return_value=True), \
             patch.object(acciones.diagnostico_gasto, "registrar_coste", return_value=0.0), \
             patch.object(acciones, "diagnostico_llamar_deepseek", return_value={
                 "choices": [{"message": {"content": json.dumps(
                     {"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}
                 )}}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1},
             }), \
             patch.object(acciones.bridge, "restart_container") as mock_restart:
            with store.connect(_db(db_dir)) as conn:
                estados = [
                    acciones.evaluar_contenedor(conn, conn, "test-critico", modo_forzado="manual").estado
                    for _ in range(5)
                ]

        check("las 5 evaluaciones repetidas crean 'pendiente', nunca 'cortacircuito'",
              all(e == "pendiente" for e in estados))
        check("restart_container nunca se llama para un crítico", mock_restart.called is False)


def test_escribir_snapshot_incluye_bloque_contenedores() -> None:
    with tempfile.TemporaryDirectory() as db_dir, tempfile.TemporaryDirectory() as snap_dir:
        snap_path = Path(snap_dir) / "remediacion_estado.json"

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(db_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", []), \
             patch.object(acciones, "_snapshot_path", return_value=snap_path), \
             patch.object(acciones.bridge, "docker_critical", return_value={"homeassistant"}), \
             patch.object(acciones.bridge, "docker_never_restart", return_value={"frigate"}), \
             patch.object(acciones.bridge, "listar_contenedores", return_value=[
                 {"name": "homeassistant"}, {"name": "frigate"}, {"name": "beszel"},
             ]):
            with store.connect(_db(db_dir)) as conn:
                store.set_modo_contenedor(conn, "beszel", "automatico")
                acciones.escribir_snapshot(conn)

        payload = json.loads(snap_path.read_text())
        por_nombre = {c["nombre"]: c for c in payload["contenedores"]}

        check("3 contenedores en el bloque", len(payload["contenedores"]) == 3)
        check("homeassistant: crítico, manual, modo null",
              por_nombre["homeassistant"]["critico"] is True
              and por_nombre["homeassistant"]["clasificacion"] == "manual"
              and por_nombre["homeassistant"]["modo"] is None)
        check("frigate: never_restart, manual, modo null",
              por_nombre["frigate"]["never_restart"] is True
              and por_nombre["frigate"]["clasificacion"] == "manual"
              and por_nombre["frigate"]["modo"] is None)
        check("beszel: no crítico, ia, modo automatico reflejado",
              por_nombre["beszel"]["critico"] is False
              and por_nombre["beszel"]["clasificacion"] == "ia"
              and por_nombre["beszel"]["modo"] == "automatico")
        check("sin ningún intento vigente, intento_vigente es null para los tres",
              all(c["intento_vigente"] is None for c in payload["contenedores"]))


def test_escribir_snapshot_refleja_intento_vigente() -> None:
    with tempfile.TemporaryDirectory() as db_dir, tempfile.TemporaryDirectory() as snap_dir:
        snap_path = Path(snap_dir) / "remediacion_estado.json"

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(db_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", []), \
             patch.object(acciones, "_snapshot_path", return_value=snap_path), \
             patch.object(acciones.bridge, "docker_critical", return_value=set()), \
             patch.object(acciones.bridge, "docker_never_restart", return_value=set()), \
             patch.object(acciones.bridge, "listar_contenedores", return_value=[{"name": "beszel"}]):
            with store.connect(_db(db_dir)) as conn:
                _crear_pendiente_reinicio(conn, "beszel")
                acciones.escribir_snapshot(conn)

        payload = json.loads(snap_path.read_text())
        entrada = payload["contenedores"][0]
        check("intento_vigente no nulo con un pendiente real", entrada["intento_vigente"] is not None)
        check("estado del intento vigente refleja el pendiente", entrada["intento_vigente"]["estado"] == "pendiente")


def test_escribir_snapshot_logs_incluyen_clasificacion() -> None:
    with tempfile.TemporaryDirectory() as logs_dir, tempfile.TemporaryDirectory() as db_dir, \
         tempfile.TemporaryDirectory() as snap_dir:
        snap_path = Path(snap_dir) / "remediacion_estado.json"
        lista = [("health-docker", "health-docker.log", 10 * 1024 * 1024)]

        with patch.object(acciones, "REMEDIACION_LOGS_DIR", Path(logs_dir)), \
             patch.object(acciones, "LOGS_VIGILADOS", lista), \
             patch.object(acciones, "_snapshot_path", return_value=snap_path), \
             patch.object(acciones.bridge, "listar_contenedores", return_value=[]):
            with store.connect(_db(db_dir)) as conn:
                acciones.escribir_snapshot(conn)
                payload_manual = json.loads(snap_path.read_text())

                store.set_modo(conn, acciones.TIPO_ACCION_ROTAR_LOG, "automatico")
                acciones.escribir_snapshot(conn)
                payload_automatico = json.loads(snap_path.read_text())

        check("modo manual ⇒ clasificacion=manual en el log", payload_manual["logs"][0]["clasificacion"] == "manual")
        check("modo automático ⇒ clasificacion=automatica en el log",
              payload_automatico["logs"][0]["clasificacion"] == "automatica")


def test_resolver_aprobacion_reinicio_declara_ia_solo_si_ejecuta() -> None:
    with tempfile.TemporaryDirectory() as db_dir:
        declaraciones: list[tuple] = []
        with patch.object(acciones.bridge, "declarar_correccion_ia",
                           side_effect=lambda *a: declaraciones.append(a) or True):
            with patch.object(acciones.bridge, "restart_container", return_value=True):
                with store.connect(_db(db_dir)) as conn:
                    pendiente = _crear_pendiente_reinicio(conn)
                    acciones.resolver_aprobacion_reinicio(conn, pendiente.id)
                check("aprobar y ejecutar con éxito declara ia", len(declaraciones) == 1)
                check("la nota es el razonamiento de DeepSeek, no un texto de Miquel",
                      declaraciones[0][3] == "prueba")

            declaraciones.clear()
            with patch.object(acciones.bridge, "restart_container", return_value=False):
                with store.connect(_db(db_dir)) as conn:
                    pendiente2 = _crear_pendiente_reinicio(conn, "otro-contenedor")
                    acciones.resolver_aprobacion_reinicio(conn, pendiente2.id)
                check("aprobar con fallo real nunca declara ia", declaraciones == [])
