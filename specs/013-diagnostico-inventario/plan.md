# Implementation Plan: Generalizar el Diagnóstico al Inventario de Cobertura

**Branch**: `013-diagnostico-inventario` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-diagnostico-inventario/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, a HA
en 010, a backups en 011 y a relays en 012) para que un `Episodio`
pueda ser también de inventario: un sexto valor de `origen`
(`"inventario"`, sin migración de esquema). A diferencia de los cuatro
orígenes de disco/HA/backup/relay, la evidencia **no se lee de ningún
fichero ni de `homelab.db`**: se reutiliza directamente el paquete
hermano `src/inventory/` ya existente en este mismo repo —
`inventory.store.hallazgos_de_ejecucion`/`brechas_de_ejecucion` para el
hallazgo real de un componente en una ejecución concreta, e
`inventory.diff.compare_runs()` (ya usado por `--since` del propio CLI
de inventario) para lo que cambió respecto a la ejecución
inmediatamente anterior a que la brecha empezara
(`brecha.primera_ejecucion_id - 1`, ya guardado por componente — no
hace falta que Miquel lo calcule). Identificador simétrico en vivo y
en diferido (a diferencia de 012): `NOMBRE` del componente
(`nombre_actual`); en diferido se combina con `EJECUCION_ID` en el
propio flag del CLI (`--inventario-historico "NOMBRE@EJECUCION_ID"`),
mismo orden que `LABEL@MOMENTO_ISO` de discos/HA. La exclusión de
`condicion_incumplida` (FR-010) se valida en código antes de congelar
— mismo patrón que el bloqueo de los checks de la cerradura en 010
(`_validar_check_ha`), no una nota de prompt sin verificar. El gasto
diario sigue siendo un único acumulado compartido (FR-007) —
`gasto.py` no cambia. `store.py` (el de `diagnostico`, no el de
`inventory`) tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a
007/009/010/011/012)

**Primary Dependencies**: Ninguna nueva — a diferencia de 009-012 (que
leían ficheros/`homelab.db` con `json`/`re`/`sqlite3` de la librería
estándar), este feature importa directamente el paquete hermano
`inventory` (`inventory.store`, `inventory.diff`, `inventory.model`) ya
presente en `src/` de este mismo repo — primera vez que `diagnostico`
importa otro paquete de aplicación en vez de leer una fuente de datos
externa.

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1). Lectura de `inventario.db`
(`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/inventario.db`,
mismo directorio que `homelab.db`) a través de
`inventory.store.connect()` — respeta la misma variable de entorno
`INVENTORY_DB_PATH` que ya usa el propio CLI de inventario, sin
duplicar configuración. Nunca escritura — solo se llaman funciones de
lectura de `inventory.store`/`inventory.diff`.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007/009/010/011/012 — nuevos casos en `test_evidencia.py`
(`congelar_inventario_vivo`/`congelar_inventario_historico` contra una
`inventario.db` de prueba en un fichero temporal, nunca la real,
mismo patrón que `test_evidencia.py` ya usa para `homelab.db`) y
`test_deepseek.py` (prompt para `origen="inventario"`).

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007/009/010/011/012.

**Project Type**: Extensión de `src/diagnostico/` ya existente —
ningún paquete nuevo. `src/inventory/` tampoco cambia — solo se
consume, nunca se modifica (research.md §2).

**Performance Goals**: Sin cambios — herramienta manual. Leer
`hallazgos_de_ejecucion`/`brechas_de_ejecucion` de una ejecución
concreta y compararla contra otra vía `compare_runs()` son las mismas
consultas SQL indexadas que ya usa `inventory.cli --since` en
producción — sin coste nuevo que medir.

**Constraints**: Una brecha de tipo `condicion_incumplida` nunca llega
a congelarse — se rechaza en código antes de crear el episodio
(spec.md FR-010, research.md §5). Ningún dato nuevo sensible sale hacia
DeepSeek — `categoria`/`tipo`/`contexto`/`mecanismo_vigilancia` son
nombres de software (LaunchAgents, scripts, checks), misma categoría ya
aceptada para `check_id`/`entity` en 010 (research.md §6) — a
diferencia de 012, este feature no introduce ninguna categoría de dato
nueva para el Principio X. `inventario_comparacion` va acotada a 30
entradas por lista (`INVENTARIO_COMPARACION_MAX_ENTRADAS`) — hallazgo
real investigando la línea base: el ancla de comparación de las cuatro
brechas conocidas resulta ser una ejecución con 0 brechas registradas,
así que un diff sin límite listaría hasta 319 brechas como "nuevas"
(research.md §11).

**Scale/Scope**: Igual que 007/009/010/011/012 — un usuario, uso manual
y esporádico. Línea base real desde el arranque, igual que 012: cuatro
brechas históricas reales ya identificadas y resueltas (ejecuciones
#19, #28, #31, #52 — spec.md SC-005), no solo `--inventario-vivo`
contra el estado sano actual (que hoy no tiene ninguna brecha de los 5
tipos en alcance).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `inventory.cli` (Frente 1) ya calcula y persiste. |
| II. Salud por Resultado | No aplica | Sin cambios respecto a 007/009/010/011/012. |
| III. Estado Esperado Declarado | No aplica | El estado esperado de cada componente (si debe estar declarado, vigilado, llegar al dashboard) ya lo declara/calcula `inventory.evaluate`, este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007/009/010/011/012. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre ningún componente ni sobre `inventario.db` en este feature — solo lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca declara estado esperado, añade vigilancia ni corrige qué llega al dashboard — eso sigue siendo trabajo de `inventory.cli` y de los features 001-006. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007/009/010/011/012, ahora también para episodios de inventario. |
| IX. Mejora Medida Contra la Línea Base | **Sí, con línea base real** | Igual que 012: cuatro brechas reales ya identificadas y resueltas (spec.md SC-005), no una limitación aceptada como en 009/010/011. |
| X. Local por Defecto | Sí, sin categoría de dato nueva | research.md §6: `categoria`/`tipo`/`contexto`/`mecanismo_vigilancia` son nombres de software del propio homelab (LaunchAgents, scripts, checks) — misma naturaleza que `check_id`/`entity` ya aceptados en 010, sin IPs ni topología nueva (a diferencia de 012). |
| XI. Reproducibilidad Diferida | Sí | Las tablas de `inventory` (`ejecuciones`, `hallazgos`, `brechas`) son append-only (docstring de `inventory/store.py`) — `--inventario-historico` sobre la misma `EJECUCION_ID` produce siempre la misma evidencia. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | FR-010 es una restricción nueva de este principio, mismo patrón que FR-010 de 010 (bloqueo de la cerradura): el feature diagnostica los 5 tipos de brecha que no duplican otro origen ya generalizado, y explícitamente NO diagnostica `condicion_incumplida` — ese tipo es el propio inventario re-detectando, con otras palabras, lo que el origen `ha` (010) ya diagnostica desde su propia evidencia. |

**Resultado**: PASS. Sin riesgos de Principio IX (línea base real
disponible, igual que 012). Sin categoría de dato nueva para el
Principio X (a diferencia de 012, que sí tuvo que justificar IPs de la
LAN). El único riesgo de diseño — duplicar el origen `ha` vía
`condicion_incumplida` — se resuelve con una exclusión de alcance
explícita y validada en código (FR-010), no con una nota de prompt sin
verificar.

## Project Structure

### Documentation (this feature)

```text
specs/013-diagnostico-inventario/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/012-diagnostico-relays/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009/010/011/012 y ahora por 013 — mismo paquete
├── __init__.py
├── cli.py                # + flags --inventario-vivo/--inventario-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'inventario' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_inventario_vivo/congelar_inventario_historico,
│                              # + _brecha_de_componente/_hallazgo_de_componente (leen inventory.store),
│                              # + import inventory.store / inventory.diff / inventory.model
├── deepseek.py                # prompt generalizado una sexta vez
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature no lee homelab.db ni ejecuta subprocesos nuevos

src/inventory/             # feature 001, generalizado por 002-006 — SIN CAMBIOS,
│                            # solo se consume desde diagnostico/evidencia.py

tests/selftest/
├── test_evidencia.py       # + casos de congelar_inventario_vivo/historico, incluida la
│                             # exclusión en código de condicion_incumplida (ValueError)
├── test_deepseek.py         # + caso de prompt para origen="inventario"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009/010/011/012. La
única pieza de infraestructura nueva es un `import` de un paquete
hermano (`inventory`) en vez de una lectura de fichero/DB externa —
research.md §2 explica por qué es la opción correcta aquí y no en los
orígenes anteriores (`inventario.db` es generado por código de *este
mismo repo*, a diferencia de `homelab.db`, que genera código externo no
versionado aquí).

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
