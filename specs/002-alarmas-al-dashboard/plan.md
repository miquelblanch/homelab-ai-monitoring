# Implementation Plan: Alarmas Ya Calculadas al Panel del Dashboard

**Branch**: `002-alarmas-al-dashboard` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-alarmas-al-dashboard/spec.md`

## Summary

Dos señales que el homelab ya calcula pero que hoy no llegan al dashboard:
la alarma por contenedor de `docker_monitor.py` (`docker_monitor_state.json`)
y el estado que Beszel ya vigila sobre los hosts de Uptime Kuma y AdGuard
Home. Enfoque técnico: extender `docker/homelab-dashboard/scripts/app.py`
para leer un fichero que ya existe (contenedores) y uno nuevo que un
script pequeño escribe cada 5 minutos (hosts externos, leyendo el volumen
de datos de Beszel vía `docker run` — no hay otra vía de acceso desde
macOS, `research.md` §3). Ninguna interfaz nueva (`FR-005`): las dos
señales aparecen dentro del panel único que ya existe, fundidas en
elementos que ya están ahí (la fila del contenedor) o en una sección más
del mismo estilo que las que ya hay. El mecanismo nuevo se vigila a sí
mismo con el mismo patrón de latido que usa el resto del homelab
(`FR-008`), para no introducir el único monitor sin quien lo vigile.

## Technical Context

**Language/Version**: Python 3.11 — mismo runtime que el resto de
LaunchAgents del homelab (Regla 10 del `CLAUDE.md` general) para el script
nuevo; el cambio en `app.py` sigue el lenguaje ya usado ahí (Python +
JS embebido, FastAPI).

**Primary Dependencies**: Solo librería estándar para el script nuevo
(`sqlite3`, `subprocess`, `json`, `pathlib` — mismo patrón "sin
dependencias externas" que `docker_monitor.py`). El contenedor
`python:3.11-alpine` usado dentro del `docker run` (`research.md` §3) es
una dependencia de despliegue (una imagen más que Docker descarga una vez),
no una dependencia de código.

**Storage**: Ficheros JSON en `docker/homelab-orchestrator/data/` — ni el
script nuevo ni el cambio en `app.py` usan SQLite propio; `docker_monitor_state.json`
ya existe y no cambia. Ver `data-model.md`.

**Testing**: mismo patrón `--selftest` de lógica pura que el resto del
homelab (`docker_monitor.py`, feature 001) para el script nuevo — probar
el parseo de la salida de `sqlite3` y la decisión "sin evidencia" contra
datos de ejemplo, sin tocar Beszel ni Docker reales. El cambio en
`app.py` no tiene suite de test propia hoy (no la introduce este feature);
se valida con `quickstart.md`.

**Target Platform**: macOS (el script nuevo, como LaunchAgent nativo) +
el contenedor Docker existente del dashboard (el cambio en `app.py`) —
mismos dos entornos que ya usa el resto del homelab, ninguno nuevo.

**Project Type**: dos piezas pequeñas sobre infraestructura que ya existe
— un script nuevo (CLI invocable, sin subcomandos) y un parche a un
servicio web ya desplegado. No hay proyecto nuevo que estructurar.

**Performance Goals**: sin objetivo explícito en el spec (Outstanding de
bajo impacto). El `docker run` del script nuevo debe completarse en
segundos, no minutos, para no competir con el siguiente ciclo de 5
minutos; no hay objetivo de latencia para `app.py` porque ambas lecturas
son de ficheros locales ya en disco, mismo orden de magnitud que las
lecturas que `app.py` ya hace.

**Constraints**: no debe modificar nada de Beszel ni de los hosts
vigilados (`FR-006`, `contracts/ficheros.md` garantía 1); un ciclo fallido
del script nuevo no puede escribir un dato falso (garantía 2); nada de
credenciales nuevas (se descarta la vía de API HTTP de Beszel precisamente
por esto, `research.md` §3).

**Scale/Scope**: ~40 contenedores (ya cubiertos por `docker_monitor.py`,
solo se exponen), 2 hosts externos fijos (Kuma, AdGuard) — mismo alcance
que `FR-005` de feature 001, sin generalizar a más hosts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | El latido nuevo (`FR-008`) se reemite cada ciclo mientras el mecanismo esté vivo; si un host externo sigue caído, el dashboard lo sigue mostrando caído en cada carga, no solo en el primer cambio de estado. |
| II. Salud por Resultado | Sí | Núcleo de `FR-004`: un dato ausente o viejo no cuenta como "sano" — se muestra "sin evidencia", explícitamente distinto. |
| III. Estado Esperado Declarado | N/A | Este feature no declara estados esperados nuevos — expone lo que `docker_monitor.py` (feature existente) y Beszel ya declaran/calculan por su cuenta. |
| IV. Diagnóstico Previo a la Acción | N/A | Sin acciones correctivas (`FR-006`) — solo visualización. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento por ausencia. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | Ni el script nuevo ni el cambio en `app.py` reinician ni corrigen nada — `docker_monitor.py` sigue siendo el único actor de remediación, este feature solo lee su resultado. |
| VIII. Registro de Acciones e Hipótesis | N/A | No formula hipótesis de causa raíz ni ejecuta acciones que registrar. |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-003` se verifica relanzando el inventario de feature 001 — las brechas de `contenedor` y `host_externo` que ya contaba esa línea de base deben desaparecer. |
| X. Local por Defecto | Sí | Sin credenciales ni integración remota nueva — se descarta explícitamente la API HTTP de Beszel por esto (`research.md` §3); todo el acceso es local (Docker/volumen) o ya existente. |
| XI. Reproducibilidad Diferida | N/A | No diagnostica incidentes — solo expone estado ya calculado por otros componentes. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | Razón de ser del feature: cero ausencias (`FR-001`/`FR-002`) y cero duplicados (`FR-003`, Clarification 1 — fusión en la fila existente). |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | El mecanismo nuevo hereda su propia obligación de vigilancia (`FR-008`) en vez de convertirse en un punto ciego nuevo — aplicación directa del principio a sí mismo. |

## Project Structure

### Documentation (this feature)

```text
specs/002-alarmas-al-dashboard/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md         # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/             # Fase 1 (/speckit-plan)
│   └── ficheros.md
└── tasks.md               # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Este feature no toca nada dentro de `src/inventory/` (feature 001, paquete
Python de este repo). Todo lo que cambia vive **fuera de este
repositorio**, en la infraestructura privada del homelab — mismo patrón
que feature 001 ya estableció para `app.py` (ver su plan.md, "Nota de
límite del repo").

```text
# Fuera de este repo — /Volumes/FastData/homelab/ (privado)

scripts/
└── beszel_hosts_monitor.py       # nuevo — lee la tabla `systems` de Beszel
                                   # vía `docker run` (research.md §3),
                                   # escribe beszel_hosts.json + latido

docker/homelab-dashboard/
├── amsterdam9.beszel.hosts-reader.plist   # nuevo — LaunchAgent, cada 5 min
└── scripts/app.py                          # modificado:
    ├── get_containers()                    #   + fusiona docker_monitor_state.json
    ├── get_external_hosts()                #   nueva función
    ├── MONITOR_JOBS                        #   + entrada "beszel-hosts"
    ├── collect()                           #   + external_hosts
    └── HTML/render()                       #   + badge "caído desde" en la
                                             #     tarjeta de contenedor,
                                             #     + sección hosts externos,
                                             #     + MONITOR_INFO["beszel-hosts"]

docker/homelab-orchestrator/data/
└── beszel_hosts.json               # nuevo — escrito por el script nuevo
                                     # (docker_monitor_state.json ya existe,
                                     # sin cambios de formato)
```

**Structure Decision**: sin proyecto nuevo. Un script nativo más,
mismo patrón que `docker_monitor.py`/`dump_socat_status.py`, y un parche
al único servicio web que ya existe — nada que justifique una estructura
de repositorio propia. `tasks.md` debe reflejar el script nuevo y el
parche a `app.py` como cambios sobre la máquina del homelab, no como
ficheros que vivan dentro de `src/` de este repo público (mismo criterio
que feature 001).

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`, `quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Una decisión de diseño que
podría haber introducido una violación se revisó explícitamente y no lo
hace:

- Guardar `beszel_name` dentro de `beszel_hosts.json` (`data-model.md`) no
  es una declaración de estado esperado nueva (Principio III no aplica,
  ver tabla) — es un dato de depuración, no una condición que el dashboard
  evalúe.

Gate superado. Listo para `/speckit-tasks`.
