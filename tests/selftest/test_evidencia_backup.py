"""test_evidencia_backup — origen backup (feature 011). Movido de
`test_evidencia.py` en specs/023-evidencia-por-origen/ (T019).
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from diagnostico import store
from diagnostico.evidencia import backup
from tests.selftest import check


def _diag_db(tmp: str) -> Path:
    return Path(tmp) / "diagnostico.db"


_LOG_BACKUP_SANO = """\
========================================
 🚀 INICIO BACKUP: 2026-08-12 02:00:00
========================================
📦 Generando backups atómicos de Bases de Datos...
  ✅ Nextcloud MariaDB dump OK
  ✅ Immich PostgreSQL dump OK
🧠 Dump GBrain PostgreSQL...
  ✅ GBrain DB dump OK
🤖 Backup de ~/.hermes...
✅ Backup Hermes completado
Number of files: 100 (reg: 90, dir: 10)
Total transferred file size: 1.00M bytes
sent 1.00M bytes  received 500 bytes  10.00M bytes/sec
total size is 10.00M  speedup is 10.00
🧹 Limpiando archivos de dump temporales...
 ✅ RESUMEN FINAL: Duración 5m 0s — rsync completo
"""

_LOG_BACKUP_CON_FALLO = """\
========================================
 🚀 INICIO BACKUP: 2026-08-11 02:00:00
========================================
📦 Generando backups atómicos de Bases de Datos...
  ⚠️ Nextcloud MariaDB dump falló
  ✅ Immich PostgreSQL dump OK
rsync: some real io error happened (code 11)
Number of files: 50 (reg: 45, dir: 5)
sent 500K bytes  received 200 bytes  5.00M bytes/sec
total size is 5.00M  speedup is 5.00
🧹 Limpiando archivos de dump temporales...
 ❌ RESUMEN FINAL: Duración 2m 0s — rsync PARCIAL (código 23) — revisa el log
"""


def test_parsear_log_backup_sano() -> None:
    snap = backup._parsear_log_backup(_LOG_BACKUP_SANO)
    # Nextcloud, Immich, GBrain, "Backup Hermes completado" — RESUMEN FINAL excluido aparte.
    check("dumps recoge las 4 líneas de estado OK", len(snap["dumps"]) == 4)
    check(
        "rsync_stats recoge el bloque de estadísticas, no la lista de ficheros",
        any("Number of files" in l for l in snap["rsync_stats"])
        and any("total size is" in l for l in snap["rsync_stats"]),
    )
    check("resumen_final capturado", "RESUMEN FINAL" in snap["resumen_final"])
    check("rsync_estado = ok para un backup sano", snap["rsync_estado"] == "ok")
    check("sin anomalías en un backup sano", snap["anomalias"] == [])


def test_parsear_log_backup_con_fallo_no_duplica_en_anomalias() -> None:
    """Hallazgo I1 de /speckit-analyze (2026-08-12): una línea de dump
    fallido (⚠️) también coincidiría con un patrón de anomalía si no se
    excluyera explícitamente — sin la exclusión, se contaba dos veces."""
    snap = backup._parsear_log_backup(_LOG_BACKUP_CON_FALLO)
    check(
        "el dump fallido aparece en dumps",
        any("Nextcloud MariaDB dump falló" in l for l in snap["dumps"]),
    )
    check(
        "el dump fallido NO se duplica en anomalias",
        not any("Nextcloud MariaDB dump falló" in l for l in snap["anomalias"]),
    )
    check(
        "el error real de rsync sí aparece en anomalias",
        any("some real io error happened" in l for l in snap["anomalias"]),
    )
    check("rsync_estado = error para un backup parcial", snap["rsync_estado"] == "error")


def test_parsear_log_backup_acota_anomalias() -> None:
    lineas_error = "\n".join(f"rsync: fake error number {i}" for i in range(50))
    log_grande = _LOG_BACKUP_SANO + "\n" + lineas_error
    snap = backup._parsear_log_backup(log_grande)
    check(
        f"anomalias se acota a {backup.BACKUP_ANOMALIA_MAX_LINEAS}, no 50",
        len(snap["anomalias"]) == backup.BACKUP_ANOMALIA_MAX_LINEAS,
    )


def _escribir_log_backup(directorio: Path, nombre: str, contenido: str) -> None:
    (directorio / nombre).write_text(contenido)


def test_congelar_backup_vivo_arma_snapshot_con_evidencia_real() -> None:
    with tempfile.TemporaryDirectory() as tmp_logs, tempfile.TemporaryDirectory() as tmp_db:
        logs_dir = Path(tmp_logs)
        _escribir_log_backup(logs_dir, "backup_2026-08-11_02-00-00.log", _LOG_BACKUP_CON_FALLO)
        _escribir_log_backup(logs_dir, "backup_2026-08-12_02-00-00.log", _LOG_BACKUP_SANO)
        with patch.object(backup, "BACKUP_LOG_DIR", logs_dir):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = backup.congelar_backup_vivo(conn)

        check("origen = backup", episodio.origen == "backup")
        check("es_critico siempre False para backup", episodio.es_critico is False)
        check("en_vivo=True", episodio.en_vivo is True)
        check(
            "toma el log más reciente (12 de agosto), no el más antiguo",
            episodio.snapshot_evidencia["backup_log_path"].endswith("2026-08-12_02-00-00.log"),
        )
        check(
            "campos heredados de contenedor/disco/HA quedan a null",
            episodio.snapshot_evidencia["restart_history"] is None
            and episodio.snapshot_evidencia["ha_check"] is None
            and episodio.snapshot_evidencia["disk_metrics"] is None,
        )


def test_congelar_backup_vivo_sin_logs_no_lanza() -> None:
    with tempfile.TemporaryDirectory() as tmp_logs, tempfile.TemporaryDirectory() as tmp_db:
        with patch.object(backup, "BACKUP_LOG_DIR", Path(tmp_logs)):
            with store.connect(_diag_db(tmp_db)) as conn:
                episodio = backup.congelar_backup_vivo(conn)

        check("componente sigue siendo un momento ISO válido", "T" in episodio.componente)
        check(
            "toda la evidencia de backup queda en null, sin lanzar",
            episodio.snapshot_evidencia["backup_log_path"] is None
            and episodio.snapshot_evidencia["backup_dumps"] is None,
        )


def test_congelar_backup_historico_ventana_de_tolerancia() -> None:
    with tempfile.TemporaryDirectory() as tmp_logs, tempfile.TemporaryDirectory() as tmp_db:
        logs_dir = Path(tmp_logs)
        _escribir_log_backup(logs_dir, "backup_2026-08-11_02-00-00.log", _LOG_BACKUP_CON_FALLO)
        with patch.object(backup, "BACKUP_LOG_DIR", logs_dir):
            with store.connect(_diag_db(tmp_db)) as conn:
                dentro = backup.congelar_backup_historico(
                    conn, datetime(2026, 8, 11, 10, 0, 0)  # +8h, dentro de ±12h
                )
                fuera = backup.congelar_backup_historico(
                    conn, datetime(2026, 8, 9, 2, 0, 0)  # 2 días antes, fuera
                )

        check(
            "un momento dentro de ±12h encuentra el log real",
            dentro.snapshot_evidencia["backup_log_path"] is not None,
        )
        check(
            "un momento fuera de la ventana no lanza, congela con evidencia vacía",
            fuera.snapshot_evidencia["backup_log_path"] is None
            and fuera.snapshot_evidencia["backup_anomalias"] is None,
        )


def test_congelar_backup_historico_es_reproducible() -> None:
    """Base de SC-001 para backups: congelar dos veces el mismo momento
    produce la misma evidencia — el log ya escrito no cambia."""
    with tempfile.TemporaryDirectory() as tmp_logs, tempfile.TemporaryDirectory() as tmp_db:
        logs_dir = Path(tmp_logs)
        _escribir_log_backup(logs_dir, "backup_2026-08-12_02-00-00.log", _LOG_BACKUP_SANO)
        momento = datetime(2026, 8, 12, 4, 0, 0)
        with patch.object(backup, "BACKUP_LOG_DIR", logs_dir):
            with store.connect(_diag_db(tmp_db)) as conn:
                e1 = backup.congelar_backup_historico(conn, momento)
                e2 = backup.congelar_backup_historico(conn, momento)

        check(
            "dos congelados del mismo momento producen la misma evidencia",
            e1.snapshot_evidencia["backup_dumps"] == e2.snapshot_evidencia["backup_dumps"]
            and e1.snapshot_evidencia["backup_log_path"] == e2.snapshot_evidencia["backup_log_path"],
        )
        check("cada congelado es un episodio propio", e1.id != e2.id)
