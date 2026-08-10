"""beszel_baseline — T031, resuelve el hallazgo E1 de /speckit-analyze
(2026-08-10): tres episodios REALES de `beszel` (de los 49 reinicios
históricos), congelados el 2026-08-10 contra `homelab.db` de verdad con
`diagnostico.cli congelar --historico`, no inventados.

Los tres (`restart_history_id` 16, 17 y 25 — abril de 2026) resultaron
tener evidencia vacía en todas las fuentes hoy: ni `container_metrics`
(30 días de retención, ya purgado) ni `container_metrics_hourly`
(permanente pero solo desde 2026-04-17, y estos tres son de antes) ni
`disk_metrics` dentro de la ventana de tolerancia (evidencia.py,
disk_metrics_near). Es un hallazgo real de este momento, no una
casualidad elegida a mano: cualquier episodio de `beszel` anterior al
17 de abril tiene hoy exactamente esta misma forma vacía.

**Lo que esta fixture NO demuestra**: que DeepSeek de verdad concluye
`no_diagnosticable` para estos tres — eso exige una llamada real con
`DEEPSEEK_API_KEY` configurada (T030 de tasks.md, todavía pendiente:
no existe esa credencial en `.secrets/` en el momento de escribir esto).
Lo que sí demuestra `test_baseline_beszel.py` es que, dada una respuesta
ya `no_diagnosticable` (simulada), la tubería completa
(`diagnosticar_episodio` → parseo → persistencia) la conserva sin
alterarla para los tres — la parte que el código puede garantizar sin
gasto real, igual que `test_reproducibilidad.py` (E2).
"""

from __future__ import annotations

EPISODIOS_SIN_EVIDENCIA = [
    {
        "restart_history_id": 16,
        "contenedor": "beszel",
        "ventana_inicio": "2026-04-01T21:59:25",
        "ventana_fin": "2026-04-01T22:59:25",
        "snapshot_evidencia": {
            "restart_history": {
                "id": 16, "container_name": "beszel", "timestamp": 1775075365,
                "result": "success", "reason": "Container beszel restarted successfully",
                "triggered_by": "healer",
            },
            "container_metrics": [],
            "container_metrics_hourly": [],
            "disk_metrics": [],
            "docker_inspect": None,
            "docker_logs_tail": None,
        },
    },
    {
        "restart_history_id": 17,
        "contenedor": "beszel",
        "ventana_inicio": "2026-04-01T22:04:27",
        "ventana_fin": "2026-04-01T23:04:27",
        "snapshot_evidencia": {
            "restart_history": {
                "id": 17, "container_name": "beszel", "timestamp": 1775075667,
                "result": "success", "reason": "Container beszel restarted successfully",
                "triggered_by": "healer",
            },
            "container_metrics": [],
            "container_metrics_hourly": [],
            "disk_metrics": [],
            "docker_inspect": None,
            "docker_logs_tail": None,
        },
    },
    {
        "restart_history_id": 25,
        "contenedor": "beszel",
        "ventana_inicio": "2026-04-02T01:04:30",
        "ventana_fin": "2026-04-02T02:04:30",
        "snapshot_evidencia": {
            "restart_history": {
                "id": 25, "container_name": "beszel", "timestamp": 1775086470,
                "result": "success", "reason": "Container beszel restarted successfully",
                "triggered_by": "healer",
            },
            "container_metrics": [],
            "container_metrics_hourly": [],
            "disk_metrics": [],
            "docker_inspect": None,
            "docker_logs_tail": None,
        },
    },
]
