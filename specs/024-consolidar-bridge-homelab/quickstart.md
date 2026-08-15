# Quickstart — validar el refactor de los bridges

## Prerrequisitos

- Repo en el estado de esta feature aplicado.
- Mismo entorno que 023 — no hace falta `homelab.db` real para este
  refactor (los bridges no lo tocan).

## 1. Línea base — ANTES del cambio

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m inventory.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m remediacion.cli --selftest 2>&1 | tail -3
```

Anotar recuento de aserciones (hoy: 595/595/595, 1785 total, sin fallos
— ver `specs/023-evidencia-por-origen/baseline-selftest.txt`, el
estado inmediatamente anterior a esta feature).

## 2. Tras aplicar el refactor — mismo resultado exacto

```bash
PYTHONPATH=src python3 -m diagnostico.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m inventory.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m remediacion.cli --selftest 2>&1 | tail -3
```

**Criterio de éxito (SC-003)**: mismo recuento, cero fallos nuevos —
sin haber tocado ningún fichero de test (research.md §2).

## 3. Confirmar que remediacion no depende de _homelab_bridge_heartbeat (research.md §1)

`sys.modules` no sirve de criterio: `docker_monitor.py` (fuera de este
repo) hace su propio `import heartbeat`, así que `heartbeat` ya
aparece en `sys.modules` de `remediacion` con o sin este refactor
— hallazgo real corregido en research.md §1 tras implementar. El
criterio correcto es por código fuente, no por estado de proceso:

```bash
grep -n "heartbeat" src/remediacion/_homelab_bridge.py
# No debe aparecer ninguna línea — ni import ni record_heartbeat
```

## 4. Confirmar el aislamiento del hook de prueba (SC-002)

```bash
REMEDIACION_TEST_FORZAR_CRITICO=beszel PYTHONPATH=src python3 -c "
from diagnostico import _homelab_bridge as diag
from inventory import _homelab_bridge as inv
from remediacion import _homelab_bridge as rem
assert 'beszel' not in diag.docker_critical(), 'el hook se filtró a diagnostico'
assert 'beszel' not in inv.docker_critical(), 'el hook se filtró a inventory'
print('OK — el hook de remediacion no se filtra a los otros dos')
"
```

## 5. Confirmar las firmas de la fachada (contracts/fachadas-bridge.md)

Ejecutar `inspect.signature()` sobre cada nombre de la tabla de
`contracts/fachadas-bridge.md`, antes/después, y comparar — mismo
patrón que 023.
