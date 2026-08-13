# Implementation Plan: Visor de Remediación en el Dashboard

**Branch**: `020-visor-remediacion` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-visor-remediacion/spec.md`

## Summary

`remediacion.cli comprobar` escribe, además de lo que ya hacía, un
snapshot JSON (`remediacion_estado.json`) a `/data` con el estado de
los 17 logs vigilados y el modo de `rotar_log`. Un LaunchAgent nuevo,
fuera de este repo, dispara `comprobar` cada 15 min. El dashboard
(`app.py`, fuera de este repo) lee ese JSON de solo lectura y muestra
una sección nueva — sin ningún control de acción, mismo patrón que el
resto del dashboard con datos de otros orígenes (`get_socat_relays()`,
`get_external_hosts()`). Decisión explícita: no montar
`~/Library/Logs` en el contenedor (research.md §1).

## Technical Context

**Language/Version**: Python 3.11, sin cambios.

**Primary Dependencies**: Ninguna nueva — `json`/`pathlib` de la
librería estándar en `remediacion.cli`; lectura JSON en `app.py`,
mismo patrón que el resto del dashboard.

**Storage**: `remediacion_estado.json`, fichero nuevo en
`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/` (ya
montado como `/data` en el contenedor del dashboard) — sin tabla ni
base de datos nueva, un snapshot de solo lectura.

**Testing**: La escritura del snapshot (`src/remediacion/`) sí vive en
este repo y tiene autocomprobación (`tests/selftest/`). El LaunchAgent
y la sección de `app.py` no — validación manual contra el dashboard
real (`quickstart.md`), mismo caso que 002/006/008/018.

**Target Platform**: macOS (LaunchAgent nuevo) + contenedor Docker
`homelab-dashboard` (lectura del JSON).

**Project Type**: Extensión de `src/remediacion/` (este repo) +
infraestructura nueva fuera de este repo (LaunchAgent, sección de
`app.py`).

**Performance Goals**: Sin objetivo nuevo — snapshot de 17 entradas,
instantáneo.

**Constraints**: Sin montar `~/Library/Logs` (FR-009). Sin ningún
control de acción en el dashboard (FR-006). Sin notificación (FR-008).

**Scale/Scope**: Un usuario, lectura ocasional del dashboard — mismo
perfil que el resto de secciones.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | Sección informativa, no una alarma nueva de la Central de Alarmas (006). |
| VII. Un Actor por Acción | Sí | El LaunchAgent nuevo solo ejecuta `comprobar` (lectura + snapshot) — nunca ejecuta una rotación por su cuenta salvo que `rotar_log` ya esté en modo automático, decisión de Miquel tomada aparte (019). |
| VIII. Registro de Acciones e Hipótesis | Ya cumplido por 019 | Este feature no añade ningún registro nuevo — expone lo que `comprobar` ya hace. |
| X. Local por Defecto | Sí | Tamaños de fichero y rutas del propio Mac, mismo tipo de dato ya aceptado en el dashboard. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí, con cuidado explícito | La marca de tiempo del snapshot siempre visible (FR-002) — nunca se presenta como "ahora mismo" un dato de hasta 15-20 min de antigüedad (spec.md Edge Cases, SC-002). |

**Resultado**: PASS. Sin violaciones que justificar.

## Project Structure

### Documentation (this feature)

```text
specs/020-visor-remediacion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── snapshot-json.md
└── tasks.md
```

### Source Code

```text
src/remediacion/
├── acciones.py          # + escribir_snapshot(conn) — llamada desde cli.py::_run_comprobar
└── cli.py               # comprobar ya existente, ahora también escribe el snapshot

tests/selftest/
└── test_remediacion_acciones.py   # + casos de escribir_snapshot()

# Fuera de este repo:
~/Library/LaunchAgents/amsterdam9.remediacion.comprobar.plist   # NUEVO
/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py  # + get_remediacion_estado(), sección nueva
```

**Structure Decision**: la parte con código real de este repo es
mínima (una función que escribe JSON) — el resto (LaunchAgent,
dashboard) vive fuera, documentado aquí igual que 002/006/008/018.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida.*
