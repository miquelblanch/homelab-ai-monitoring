# Contrato — `remediacion_estado.json`

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Sin CLI ni endpoint nuevo — el contrato es el propio fichero JSON que
`remediacion.cli comprobar` escribe en `/data`, y que `app.py` lee.

## Productor

`escribir_snapshot(conn)` en `src/remediacion/acciones.py`, llamada al
final de `_run_comprobar()` (`cli.py`) — cada ejecución de `comprobar`
(manual o vía el LaunchAgent de 15 min) deja el snapshot al día.

## Consumidor

`get_remediacion_estado()` en `homelab-dashboard/scripts/app.py`
(fuera de este repo), expuesto en `/api/data` y pintado en el panel
`sistema` del dashboard.

## Forma del payload

```json
{
  "generado_en": "2026-08-13T18:30:00+00:00",
  "modo_rotar_log": "manual",
  "logs": [
    {"nombre": "health-docker", "tamano_bytes": 5032, "umbral_bytes": 10485760, "supera_umbral": false},
    {"nombre": "health-ha", "tamano_bytes": 0, "umbral_bytes": 10485760, "supera_umbral": false},
    {"nombre": "dashboard-socat", "tamano_bytes": 1778290, "umbral_bytes": 10485760, "supera_umbral": false}
  ]
}
```

## Garantías

1. **`escribir_snapshot()` nunca lanza** — un fallo de escritura (por
   ejemplo, `/data` no montado en un contexto de prueba) se traga en
   silencio, igual que el resto de escritores de estado del homelab.
2. **`logs` siempre tiene una entrada por cada `LOGS_VIGILADOS`
   vigente** (17 hoy) — un log cuyo fichero no existe en el momento de
   comprobar aparece igual, con `tamano_bytes: 0` (spec.md Edge
   Cases), nunca se omite.
3. **`generado_en` siempre presente y real** — nunca una marca de
   tiempo inventada o del momento de lectura del dashboard.
4. **El dashboard nunca deja de mostrar el resto de secciones si este
   fichero falta o está corrupto** (FR-007) — mismo patrón
   `try/except` que el resto de `app.py`.
5. **Ningún campo de este JSON es escribible desde el dashboard** — de
   solo lectura en todo el ciclo (FR-006).
