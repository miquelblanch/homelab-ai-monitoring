# Quickstart — Visor de Remediación en el Dashboard

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/snapshot-json.md](./contracts/snapshot-json.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

## Prerrequisitos

- Feature 019 desplegada (`src/remediacion/` con `LOGS_VIGILADOS`
  ampliado a 17).
- El contenedor `homelab-dashboard` reconstruido con el cambio de
  `app.py` de este feature.
- El LaunchAgent `amsterdam9.remediacion.comprobar` cargado.

## Escenario 1 — El snapshot se escribe al ejecutar `comprobar` (User Story 1)

```bash
PYTHONPATH=src python3 -m remediacion.cli comprobar
cat /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json | python3 -m json.tool
```

**Resultado esperado**: JSON con `generado_en` reciente, `modo_rotar_log`,
y 17 entradas en `logs`, con tamaños reales.

## Escenario 2 — El dashboard muestra la lista (User Story 1)

```bash
curl -s http://192.168.4.87:8888/api/data | python3 -c "
import json, sys
d = json.load(sys.stdin)
r = d.get('remediacion')
print('presente:', r is not None)
print('logs:', len(r['logs']) if r else 0)
"
```

**Resultado esperado**: `presente: True`, `logs: 17`. Abrir el
dashboard y confirmar visualmente la sección dentro de "Sistema &
almacenamiento".

## Escenario 3 — El LaunchAgent mantiene el snapshot fresco (User Story 2)

```bash
launchctl list | grep remediacion.comprobar
cat /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json | python3 -c "import json,sys; print(json.load(sys.stdin)['generado_en'])"
# esperar >15 min
cat /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json | python3 -c "import json,sys; print(json.load(sys.stdin)['generado_en'])"
```

**Resultado esperado**: el LaunchAgent aparece cargado; la segunda
marca de tiempo es posterior a la primera, sin haber ejecutado nada a
mano.

## Escenario 4 — Sin snapshot, el dashboard no se rompe (Edge Case, FR-007)

```bash
mv /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json /tmp/backup-remediacion.json
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.4.87:8888/api/data
mv /tmp/backup-remediacion.json /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json
```

**Resultado esperado**: `200` — el resto del dashboard sigue
funcionando aunque el snapshot desaparezca momentáneamente.

## Escenario 5 — Modo visible, sin ningún control de acción (User Story 3, SC-004)

```bash
PYTHONPATH=src python3 -m remediacion.cli modo rotar_log --automatico
PYTHONPATH=src python3 -m remediacion.cli comprobar
```

Recargar el dashboard: la sección debe mostrar "automático". Inspeccionar
el HTML/JS de esa sección: ningún `<button>` ni `onclick` que dispare
`aprobar`/`rechazar`/`deshacer`/`modo`.

```bash
PYTHONPATH=src python3 -m remediacion.cli modo rotar_log --manual  # limpieza
PYTHONPATH=src python3 -m remediacion.cli comprobar
```

## Autocomprobación (sin tocar el dashboard real)

```bash
PYTHONPATH=src python3 -m remediacion.cli --selftest
```

Cubre `escribir_snapshot()` contra una ruta temporal: forma correcta
del JSON, `tamano_bytes: 0` para un log ausente, y que nunca lanza si
la ruta de escritura no existe.
