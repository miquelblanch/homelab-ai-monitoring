# Implementation Plan: Diagnóstico de Episodios (Frente 2, sin remediación)

**Branch**: `007-diagnostico-episodios` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-diagnostico-episodios/spec.md`

## Summary

Un CLI (`python3 -m diagnostico.cli`) que, bajo demanda (FR-015), congela un
snapshot de evidencia real de un episodio de contenedor (en vivo o de
`restart_history`), pide a DeepSeek (temperatura 0) que proponga varias
hipótesis de causa junto con su propio contraste contra esa evidencia, y
registra cada hipótesis y la conclusión final en una base SQLite propia —
sin ejecutar ni proponer ninguna acción correctiva (FR-012/013a). Un
acumulado diario de coste en euros, calculado a partir de los tokens que
reporta cada respuesta de DeepSeek, corta las llamadas nuevas al alcanzar el
límite configurado (FR-009/010). Nada nuevo se dispara solo: todo parte de
que Miquel elija explícitamente qué episodio diagnosticar.

No hay grafo de LangGraph en este feature — ver research.md §1: el flujo es
una tubería lineal (reunir evidencia → una llamada a DeepSeek → registrar),
sin bucles, ramas condicionales, ni necesidad de estado compartido entre
pasos, que es donde LangGraph aporta valor real. El framework queda para
cuando exista una lista cerrada de acciones con aprobación humana que
orquestar (Frente 2, fase de remediación, fuera de este feature).

## Technical Context

**Language/Version**: Python 3.11 (misma versión que el resto del repo, sin excepción)

**Primary Dependencies**: Ninguna nueva. Solo librería estándar
(`sqlite3`, `urllib.request`/`ssl` para la llamada HTTP a DeepSeek,
`subprocess` con lista blanca para `docker inspect`/`docker logs`,
`dataclasses`, `json`) — mismo patrón que `inventory/deliver.py` y
`inventory/sources.py`. Se descarta LangGraph/LangChain para este feature
(research.md §1); la premisa original de `CLAUDE.md` de este repo ("agente
de diagnóstico (LangGraph)") describe la visión completa del proyecto, no
el primer incremento de Frente 2.

**Storage**: Fichero SQLite propio, `diagnostico.db`, mismo directorio que
`inventario.db` (`docker/homelab-orchestrator/data/`) — cubierto por el
backup nocturno sin configuración adicional (research.md §4). Lectura
(nunca escritura) contra `homelab.db` existente para `restart_history` /
`container_metrics` / `container_metrics_hourly` / `disk_metrics`.

**Testing**: `tests/selftest/` (mismo runner sin pytest ya usado por
`inventory`, descubierto por `tests/selftest/__init__.py:run_all()`) más un
modo `--selftest` en el propio CLI. Las llamadas reales a DeepSeek y a
Docker quedan fuera del selftest (se simulan con fixtures/mocks, mismo
patrón que `test_evaluate.py` usa `unittest.mock.patch`).

**Target Platform**: macOS (Mac Mini M4 Pro del homelab), ejecución local
bajo demanda vía terminal — no LaunchAgent en este feature (FR-015: nunca
se dispara solo).

**Project Type**: Single project — nuevo paquete `src/diagnostico/`,
hermano de `src/inventory/`, mismo layout.

**Performance Goals**: No aplica un objetivo de rendimiento — es una
herramienta bajo demanda, de ejecución manual, no un monitor periódico. La
latencia aceptable es la de una llamada a la API de DeepSeek (segundos),
no algo que este feature deba optimizar.

**Constraints**: Reproducibilidad diferida (Principio XI, FR-002): dos
ejecuciones de `diagnosticar` contra el mismo snapshot deben producir la
misma conclusión — exige temperatura 0 y un prompt determinista
(research.md §2). Presupuesto diario máximo configurable, por defecto 5
€/día (FR-009/010, Assumptions). Ninguna acción correctiva sobre ningún
contenedor, crítico o no (FR-012/013a).

**Scale/Scope**: Un usuario (Miquel), uso manual y esporádico —
unos pocos episodios diagnosticados por semana, no un flujo de alto
volumen. 49 episodios históricos de `beszel` como corpus de validación
(FR-011).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | Este feature no vigila ni alerta — diagnostica bajo demanda lo que el feature 006 ya alertó. No introduce alertas nuevas que puedan silenciarse. |
| II. Salud por Resultado | No aplica | No hay componente cuya "salud" declare este feature. |
| III. Estado Esperado Declarado | No aplica | No añade nada nuevo a vigilar. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Este feature ES el diagnóstico; explícitamente no ejecuta ninguna acción (FR-012), así que el principio se cumple por ausencia — no hay acción que requiera diagnóstico previo todavía. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | No existe ninguna acción en este feature — la lista cerrada queda vacía a propósito (FR-012). Nada que el agente pueda ejecutar fuera de una lista que no existe. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, no hay nada que revertir. |
| VII. Un Actor por Acción | Sí | `docker_monitor.py` sigue siendo el único actor que reinicia contenedores; este feature nunca llama a `docker restart` ni equivalente — su único subproceso permitido es de solo lectura (`docker inspect`/`docker logs`, research.md §5). |
| VIII. Registro de Acciones e Hipótesis | Sí, es el núcleo | Cada hipótesis se persiste con su comprobación y desenlace en `diagnostico.db` (data-model.md), legible después sin re-ejecutar (FR-006). |
| IX. Mejora Medida Contra la Línea Base | Sí | FR-011/SC-002: los 5 episodios de `beszel` ya investigados a mano (3 sin evidencia suficiente) son el conjunto de validación explícito. |
| X. Local por Defecto | Sí, con justificación ya escrita en el spec | La evidencia de un episodio sale hacia DeepSeek — justificación explícita ya en spec.md (Assumptions: "nunca credenciales ni datos de seguridad física"), cumpliendo la excepción que el propio principio permite. |
| XI. Reproducibilidad Diferida | Sí, es un requisito central | FR-002: snapshot congelado en el momento de elegir diagnosticar; `diagnosticar` sobre el mismo `episodio_id` siempre parte de ese snapshot, nunca del estado en vivo. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-016 del propio `BRIEFING.md`/spec: este feature no añade pestaña nueva al dashboard. No toca `app.py`. |
| XIII. Cobertura Sistemática, No Anecdótica | Parcial, a propósito | FR-001 acota el alcance a episodios de contenedor únicamente (Clarification 1) — una limitación declarada, no una omisión accidental; generalizar a las otras 9 alarmas queda para un feature posterior una vez validado el mecanismo. |

**Resultado**: PASS. No hay violaciones que requieran justificación en
Complexity Tracking — la ausencia de acciones (Principios IV/V/VI) es el
alcance decidido explícitamente para este feature (FR-012), no un caso
donde el plan necesite una lista de acciones y no la tenga.

## Project Structure

### Documentation (this feature)

```text
specs/007-diagnostico-episodios/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── inventory/            # feature 001-006, sin cambios
└── diagnostico/          # NUEVO — este feature
    ├── __init__.py
    ├── cli.py             # congelar / diagnosticar / mostrar / --selftest
    ├── model.py           # Episodio, Hipotesis, Diagnostico, GastoDiario (dataclasses)
    ├── evidencia.py        # lectura de homelab.db (restart_history, métricas) + docker inspect/logs
    ├── deepseek.py         # llamada HTTP a DeepSeek, parseo de hipótesis, coste por tokens
    ├── gasto.py            # acumulado diario, cortacircuitos de presupuesto
    ├── store.py            # persistencia SQLite propia (diagnostico.db)
    └── _homelab_bridge.py  # copia mínima del bridge de `inventory` (get_secret, docker_critical, docker_never_restart, record_heartbeat) — research.md §7

tests/
└── selftest/
    ├── test_evidencia.py   # NUEVO
    ├── test_deepseek.py    # NUEVO (parseo/coste, sin llamada real)
    ├── test_gasto.py       # NUEVO
    └── test_store.py       # NUEVO
```

**Structure Decision**: mismo layout de "Option 1: single project" que ya
usa `src/inventory/` — un paquete nuevo hermano, sin tocar el existente.
`diagnostico` no importa nada de `inventory` ni viceversa (dos features
independientes que comparten convención, no código) — la única duplicación
deliberada es `_homelab_bridge.py` (research.md §7).

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
