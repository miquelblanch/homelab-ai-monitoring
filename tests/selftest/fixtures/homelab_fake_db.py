"""homelab_fake_db — esquema mínimo de `homelab.db` en un fichero
temporal, usado por los tests de los orígenes contenedor y disco
(los dos que leen `homelab.db` vía `_compartido._connect_homelab_db`).
Movido de `test_evidencia.py` en specs/023-evidencia-por-origen/
(T016/T017) — antes vivía una sola vez porque ambos orígenes
compartían fichero de test; ahora vive en `fixtures/` para no acoplar
un test de origen a otro (research.md de 023, mismo criterio que
`_compartido.py` para el código de producción).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_HOMELAB_FAKE = """
CREATE TABLE restart_history (
    id INTEGER PRIMARY KEY,
    container_name TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    result TEXT NOT NULL,
    reason TEXT,
    triggered_by TEXT DEFAULT 'auto'
);
CREATE TABLE container_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    container TEXT NOT NULL,
    status TEXT,
    health TEXT,
    cpu_percent REAL,
    memory_mb REAL,
    memory_percent REAL
);
CREATE TABLE disk_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    path TEXT NOT NULL,
    label TEXT,
    used_percent REAL,
    free_gb REAL
);
CREATE TABLE container_metrics_hourly (
    hour TEXT NOT NULL,
    container TEXT NOT NULL,
    samples INTEGER NOT NULL,
    cpu_avg REAL,
    cpu_max REAL,
    memory_avg_mb REAL,
    memory_max_mb REAL,
    healthy_ratio REAL
);
"""


def fake_homelab_db(tmp: str) -> Path:
    db = Path(tmp) / "homelab_fake.db"
    conn = sqlite3.connect(db)
    conn.executescript(_SCHEMA_HOMELAB_FAKE)
    conn.execute(
        "INSERT INTO restart_history VALUES (16, 'beszel', 1775075365, 'success', "
        "'Container beszel restarted successfully', 'healer')"
    )
    # 1775075365 epoch ⇒ 2026-04-01T22:29:25 hora local — la muestra de
    # métricas tiene que caer dentro de la ventana de ±30 min alrededor de
    # ese momento (_compartido.VENTANA_METRICAS_MINUTOS) para que
    # `congelar_historico` la recoja.
    conn.execute(
        "INSERT INTO container_metrics (timestamp, container, status, health, "
        "cpu_percent, memory_mb, memory_percent) VALUES "
        "('2026-04-01T22:29:00', 'beszel', 'Up', '', 0.5, 30.0, 0.06)"
    )
    conn.execute(
        "INSERT INTO disk_metrics (timestamp, path, label, used_percent, free_gb) "
        "VALUES ('2026-04-01T22:29:00', '/', 'Sistema', 55.0, 200.0)"
    )
    conn.commit()
    conn.close()
    return db
